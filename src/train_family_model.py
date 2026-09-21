"""Train a pilot RMS-vs-EDF family tree; final test workloads remain untouched."""
import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path
import pickle

from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix
from sklearn.model_selection import StratifiedGroupKFold, ParameterGrid
from sklearn.tree import DecisionTreeClassifier, export_text, _tree

POLICIES=("RMS","EDF","RMS+Boost","EDF+Boost")

def json_scalar(value):
    if hasattr(value,'item'):
        return value.item()
    raise TypeError(f'Not JSON serializable: {type(value).__name__}')


def family(policy): return "EDF" if policy.startswith("EDF") else "RMS"


def eligible(row):
    families={family(p) for p in row['optimal_policies']}
    return len(families)==1


def flatten(row, columns): return [row['features'][c] for c in columns]


def predict_current_family(rows): return [family(r['behavior_policy']) for r in rows]


def scores(y,p):
    return {'accuracy':float(accuracy_score(y,p)),'balanced_accuracy':float(balanced_accuracy_score(y,p)),
            'confusion_matrix_RMS_EDF':[[int(v) for v in row] for row in confusion_matrix(y,p,labels=['RMS','EDF'])]}


def choose_params(rows, columns):
    groups=sorted({r['task_set_id'] for r in rows})
    folds=min(5,len(groups))
    cv=StratifiedGroupKFold(folds,shuffle=True,random_state=42)
    X=[flatten(r,columns) for r in rows];y=[family(r['optimal_policies'][0]) for r in rows]
    g=[r['task_set_id'] for r in rows]
    grid=ParameterGrid({'max_depth':[2,3,4,5,6], 'min_samples_leaf':[10,20,40,80],
                        'class_weight':[None,'balanced']})
    candidates=[]
    for params in grid:
        fold=[]
        for tr,va in cv.split(X,y,g):
            model=DecisionTreeClassifier(random_state=42,criterion='gini',**params)
            model.fit([X[i] for i in tr],[y[i] for i in tr])
            fold.append(float(balanced_accuracy_score([y[i] for i in va],model.predict([X[i] for i in va]))))
        candidates.append((float(sum(fold)/len(fold)),params,fold))
    # Prefer simpler trees when mean grouped-CV scores tie.
    candidates.sort(key=lambda x:(-x[0],x[1]['max_depth'],x[1]['min_samples_leaf'],str(x[1]['class_weight'])))
    return candidates[0],candidates


def c_export(model, columns, path):
    tree=model.tree_;names=[columns[i] if i!=_tree.TREE_UNDEFINED else '' for i in tree.feature]
    classes=list(model.classes_)
    def literal(value):
        text=f'{value:.9g}'
        if '.' not in text and 'e' not in text.lower():text+='.0'
        return text+'f'
    def walk(node,depth=1):
        ind='    '*depth
        if tree.feature[node]!=_tree.TREE_UNDEFINED:
            threshold=tree.threshold[node]
            return (f"{ind}if ({names[node]} <= {literal(threshold)}) {{\n"+walk(tree.children_left[node],depth+1)+
                    f"{ind}}} else {{\n"+walk(tree.children_right[node],depth+1)+f"{ind}}}\n")
        label=classes[max(range(len(tree.value[node][0])),key=lambda i:tree.value[node][0][i])]
        return f"{ind}return {0 if label=='RMS' else 1};  /* {label} */\n"
    args=',\n'.join(f"    float {c}" for c in columns)
    path.write_text('#include <stdint.h>\n\n/* 0=RMS family, 1=EDF family. Pilot model only. */\n'
                    f'uint8_t decide_scheduler_family(\n{args}\n) {{\n'+walk(0)+'}\n',encoding='utf-8')


def family_regret(rows,predictions):
    totals=Counter(); distributions=Counter()
    for r,pred in zip(rows,predictions):
        oracle=min((o['critical_misses'],o['total_misses']) for o in r['outcomes'].values())
        chosen=min((o['critical_misses'],o['total_misses']) for policy,o in r['outcomes'].items() if family(policy)==pred)
        totals['critical_miss_regret']+=chosen[0]-oracle[0]
        totals['total_miss_regret']+=chosen[1]-oracle[1]
        totals['oracle_critical_misses']+=oracle[0];totals['oracle_total_misses']+=oracle[1]
        totals['chosen_critical_misses']+=chosen[0];totals['chosen_total_misses']+=chosen[1]
        distributions[(chosen[0]-oracle[0],chosen[1]-oracle[1])]+=1
    return {**totals,'state_count':len(rows),'regret_distribution':{str(k):v for k,v in distributions.items()},
            'note':'Chosen family is scored using its better base/boost branch; this does not yet define a deployable boost selector.'}

def one_regret(row,pred):
    oracle=min((o['critical_misses'],o['total_misses']) for o in row['outcomes'].values())
    chosen=min((o['critical_misses'],o['total_misses']) for p,o in row['outcomes'].items() if family(p)==pred)
    return chosen[0]-oracle[0],chosen[1]-oracle[1]

def choose_cost_params(rows,columns):
    X=[flatten(r,columns) for r in rows];y=[family(r['optimal_policies'][0]) for r in rows]
    g=[r['task_set_id'] for r in rows]
    max_total=max(one_regret(r,'EDF' if family(r['optimal_policies'][0])=='RMS' else 'RMS')[1] for r in rows)
    critical_multiplier=max_total+1
    weights=[]
    for r,true in zip(rows,y):
        wrong='EDF' if true=='RMS' else 'RMS';cr,tr=one_regret(r,wrong)
        weights.append(1+critical_multiplier*cr+tr)
    cv=StratifiedGroupKFold(min(5,len(set(g))),shuffle=True,random_state=42)
    candidates=[]
    for params in ParameterGrid({'max_depth':[2,3,4,5,6], 'min_samples_leaf':[10,20,40,80]}):
        fold=[]
        for tr,va in cv.split(X,y,g):
            model=DecisionTreeClassifier(random_state=42,criterion='gini',**params)
            model.fit([X[i] for i in tr],[y[i] for i in tr],sample_weight=[weights[i] for i in tr])
            pred=model.predict([X[i] for i in va])
            regrets=[one_regret(rows[i],p) for i,p in zip(va,pred)]
            fold.append({'critical_regret_per_state':sum(x[0] for x in regrets)/len(va),
                         'total_regret_per_state':sum(x[1] for x in regrets)/len(va)})
        mean_c=sum(x['critical_regret_per_state'] for x in fold)/len(fold)
        mean_t=sum(x['total_regret_per_state'] for x in fold)/len(fold)
        candidates.append((mean_c,mean_t,params,fold))
    candidates.sort(key=lambda x:(x[0],x[1],x[2]['max_depth'],-x[2]['min_samples_leaf']))
    return candidates[0],weights,critical_multiplier


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data',default='label_data');ap.add_argument('--out',default='family_model')
    args=ap.parse_args();out=Path(args.out)
    if out.exists():ap.error('Output exists. Choose a new --out directory.')
    summary=json.loads((Path(args.data)/'label_summary.json').read_text(encoding='utf-8'))
    if summary['test_evaluated']:raise ValueError('Refusing input that evaluated test workloads')
    rows=[json.loads(line) for line in (Path(args.data)/'states.jsonl').open(encoding='utf-8')]
    train=[r for r in rows if r['split']=='train' and eligible(r)]
    validation=[r for r in rows if r['split']=='validation' and eligible(r)]
    if any(r['split']=='test' for r in rows):raise ValueError('Test rows must not be present')
    base=list(summary['feature_columns'])
    variants={'without_current_mode':[c for c in base if c!='current_mode'],
              'with_current_mode':base}
    out.mkdir()
    report={'version':'v5-pilot-family','target':'unique optimal scheduler family RMS vs EDF',
            'target_rule':'include row iff all optimal_policies belong to one family',
            'train_rows':len(train),'validation_rows':len(validation),
            'train_task_sets':len({r['task_set_id'] for r in train}),
            'validation_task_sets':len({r['task_set_id'] for r in validation}),
            'excluded_train_ambiguous_family_rows':summary['statistics']['train']['rows']-len(train),
            'excluded_validation_ambiguous_family_rows':summary['statistics']['validation']['rows']-len(validation),
            'class_distribution':{'train':Counter(family(r['optimal_policies'][0]) for r in train),
                                  'validation':Counter(family(r['optimal_policies'][0]) for r in validation)},
            'selection':'hyperparameters by grouped CV on train; variants reported on validation; no test use',
            'current_family_baseline':{},'models':{},'test_evaluated':False}
    ytr=[family(r['optimal_policies'][0]) for r in train]
    yva=[family(r['optimal_policies'][0]) for r in validation]
    report['current_family_baseline']={'train':scores(ytr,predict_current_family(train)),
                                       'validation':scores(yva,predict_current_family(validation)),
                                       'validation_counterfactual':family_regret(validation,predict_current_family(validation))}
    prediction_table=[]
    for name,columns in variants.items():
        best,candidates=choose_params(train,columns);params=best[1]
        model=DecisionTreeClassifier(random_state=42,criterion='gini',**params)
        model.fit([flatten(r,columns) for r in train],ytr)
        ptr=list(model.predict([flatten(r,columns) for r in train]))
        pva=list(model.predict([flatten(r,columns) for r in validation]))
        with (out/f'{name}.pkl').open('wb') as f:pickle.dump({'model':model,'features':columns},f)
        (out/f'{name}_tree.txt').write_text(export_text(model,feature_names=columns),encoding='utf-8')
        c_export(model,columns,out/f'{name}.c')
        report['models'][name]={'features':columns,'selected_params':params,
            'group_cv_balanced_accuracy_mean':best[0], 'group_cv_fold_scores':best[2],
            'depth':int(model.get_depth()),'leaves':int(model.get_n_leaves()),
            'train':scores(ytr,ptr),'validation':scores(yva,pva),
            'validation_counterfactual':family_regret(validation,pva),
            'feature_importance':dict(sorted(((c,float(v)) for c,v in zip(columns,model.feature_importances_)),key=lambda x:-x[1]))}
        for r,true,a,b in zip(validation,yva,pva,predict_current_family(validation)):
            if name=='without_current_mode':
                prediction_table.append({'snapshot_id':r['snapshot_id'],'task_set_id':r['task_set_id'],
                                         'true_family':true,'prediction_without_current_mode':a,
                                         'current_family_baseline':b})
            else:
                next(x for x in prediction_table if x['snapshot_id']==r['snapshot_id'])['prediction_with_current_mode']=a
    # A third model explicitly minimizes grouped CV counterfactual regret and excludes current_mode.
    name='cost_sensitive_without_current_mode';columns=variants['without_current_mode']
    best,weights,multiplier=choose_cost_params(train,columns);params=best[2]
    model=DecisionTreeClassifier(random_state=42,criterion='gini',**params)
    model.fit([flatten(r,columns) for r in train],ytr,sample_weight=weights)
    ptr=list(model.predict([flatten(r,columns) for r in train]));pva=list(model.predict([flatten(r,columns) for r in validation]))
    with (out/f'{name}.pkl').open('wb') as f:pickle.dump({'model':model,'features':columns},f)
    (out/f'{name}_tree.txt').write_text(export_text(model,feature_names=columns),encoding='utf-8')
    c_export(model,columns,out/f'{name}.c')
    report['models'][name]={'features':columns,'selected_params':params,
        'selection_objective':'lexicographic mean critical regret then total regret in grouped CV',
        'critical_weight_multiplier':multiplier,
        'group_cv_critical_regret_per_state':best[0],'group_cv_total_regret_per_state':best[1],
        'group_cv_fold_scores':best[3],'depth':int(model.get_depth()),'leaves':int(model.get_n_leaves()),
        'train':scores(ytr,ptr),'validation':scores(yva,pva),
        'validation_counterfactual':family_regret(validation,pva),
        'feature_importance':dict(sorted(((c,float(v)) for c,v in zip(columns,model.feature_importances_)),key=lambda x:-x[1]))}
    for x,p in zip(prediction_table,pva):x['prediction_cost_sensitive']=p
    (out/'report.json').write_text(json.dumps(report,indent=2,default=json_scalar),encoding='utf-8')
    with (out/'validation_predictions.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=prediction_table[0]);w.writeheader();w.writerows(prediction_table)
    print(f"Eligible family rows: train={len(train)}, validation={len(validation)}")
    for name,m in report['models'].items():
        cv_text=(f"grouped-CV balanced={m['group_cv_balanced_accuracy_mean']:.3f}" if 'group_cv_balanced_accuracy_mean' in m
                 else f"grouped-CV regret=({m['group_cv_critical_regret_per_state']:.3f}, {m['group_cv_total_regret_per_state']:.3f})")
        print(f"{name}: {cv_text}, validation balanced={m['validation']['balanced_accuracy']:.3f}, accuracy={m['validation']['accuracy']:.3f}, depth={m['depth']}, leaves={m['leaves']}")
    b=report['current_family_baseline']['validation']
    print(f"current-family baseline: validation balanced={b['balanced_accuracy']:.3f}, accuracy={b['accuracy']:.3f}")
    print('No boost selector trained. Test workloads were not evaluated.')


if __name__=='__main__':main()
