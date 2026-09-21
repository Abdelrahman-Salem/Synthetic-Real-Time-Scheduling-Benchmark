"""Train family-specific conservative Boost selectors and combine with family tree."""
import argparse,csv,json,pickle
from collections import Counter
from pathlib import Path
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import GroupKFold,ParameterGrid
from sklearn.tree import DecisionTreeClassifier,export_text,_tree

FAMILIES=('RMS','EDF')

def key(outcome):return outcome['critical_misses'],outcome['total_misses']
def boost_target(row,fam):
    return 'BOOST' if key(row['outcomes'][fam+'+Boost'])<key(row['outcomes'][fam]) else 'BASE'
def features(row,columns):return [row['features'][c] for c in columns]
def variant(fam,label):return fam+'+Boost' if label=='BOOST' else fam

def regret(rows,families,boost_labels):
    total=Counter();dist=Counter()
    for row,fam,label in zip(rows,families,boost_labels):
        oracle=min(key(o) for o in row['outcomes'].values());chosen=key(row['outcomes'][variant(fam,label)])
        d=(chosen[0]-oracle[0],chosen[1]-oracle[1]);dist[d]+=1
        total['critical_miss_regret']+=d[0];total['total_miss_regret']+=d[1]
        total['chosen_critical_misses']+=chosen[0];total['chosen_total_misses']+=chosen[1]
        total['oracle_critical_misses']+=oracle[0];total['oracle_total_misses']+=oracle[1]
        total['boost_decisions']+=label=='BOOST';total['states']+=1
    return {**total,'regret_distribution':{str(k):v for k,v in dist.items()}}

def within_family_regret(rows,fam,pred):
    c=t=boost=0
    for row,label in zip(rows,pred):
        oracle=min(key(row['outcomes'][fam]),key(row['outcomes'][fam+'+Boost']))
        chosen=key(row['outcomes'][variant(fam,label)])
        c+=chosen[0]-oracle[0];t+=chosen[1]-oracle[1];boost+=label=='BOOST'
    return c,t,boost

def choose(rows,fam,columns):
    X=[features(r,columns) for r in rows];y=[boost_target(r,fam) for r in rows];groups=[r['task_set_id'] for r in rows]
    cv=GroupKFold(5);grid=ParameterGrid({'max_depth':[2,3,4,5,6], 'min_samples_leaf':[20,50,100,200],
        'class_weight':[None,'balanced',{'BASE':1,'BOOST':5},{'BASE':1,'BOOST':10},{'BASE':1,'BOOST':20},{'BASE':1,'BOOST':50}]})
    results=[]
    for params in grid:
        folds=[]
        for tr,va in cv.split(X,y,groups):
            m=DecisionTreeClassifier(random_state=42,criterion='gini',**params);m.fit([X[i] for i in tr],[y[i] for i in tr])
            p=m.predict([X[i] for i in va]);c,t,b=within_family_regret([rows[i] for i in va],fam,p)
            folds.append({'critical_regret':c,'total_regret':t,'boost_decisions':b,'states':len(va)})
        sums={k:sum(f[k] for f in folds) for k in ('critical_regret','total_regret','boost_decisions','states')}
        results.append((sums['critical_regret'],sums['total_regret'],sums['boost_decisions'],params,folds))
    results.sort(key=lambda x:(x[0],x[1],x[2],x[3]['max_depth'],-x[3]['min_samples_leaf']))
    return results[0]

def c_export(model,columns,fam,path):
    tree=model.tree_;classes=list(model.classes_)
    def literal(value):
        text=f'{value:.9g}'
        if '.' not in text and 'e' not in text.lower():text+='.0'
        return text+'f'
    def walk(node,depth=1):
        ind='    '*depth
        if tree.feature[node]!=_tree.TREE_UNDEFINED:
            name=columns[tree.feature[node]];th=tree.threshold[node]
            return f'{ind}if ({name} <= {literal(th)}) {{\n'+walk(tree.children_left[node],depth+1)+f'{ind}}} else {{\n'+walk(tree.children_right[node],depth+1)+f'{ind}}}\n'
        label=classes[max(range(len(tree.value[node][0])),key=lambda i:tree.value[node][0][i])]
        return f"{ind}return {1 if label=='BOOST' else 0};  /* {label} */\n"
    args=',\n'.join('    float '+c for c in columns)
    path.write_text(f'#include <stdint.h>\n\n/* {fam}: 0=BASE, 1=BOOST. */\nuint8_t decide_{fam.lower()}_boost(\n{args}\n) {{\n'+walk(0)+'}\n')

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--data',default='label_data');ap.add_argument('--family-model',default='family_model/without_current_mode.pkl');ap.add_argument('--out',default='boost_model');args=ap.parse_args()
    out=Path(args.out)
    if out.exists():ap.error('Output exists; select a new --out.')
    rows=[json.loads(x) for x in (Path(args.data)/'states.jsonl').open()]
    if any(r['split']=='test' for r in rows):raise ValueError('Test rows present')
    train=[r for r in rows if r['split']=='train'];validation=[r for r in rows if r['split']=='validation']
    family_bundle=pickle.load(open(args.family_model,'rb'));family_model=family_bundle['model'];family_columns=family_bundle['features']
    boost_columns=[c for c in json.loads((Path(args.data)/'label_summary.json').read_text())['feature_columns'] if c!='current_mode']
    out.mkdir();models={};report={'version':'v7-pilot','train_rows':len(train),'validation_rows':len(validation),'test_evaluated':False,'boost_models':{}}
    for fam in FAMILIES:
        best=choose(train,fam,boost_columns);params=best[3]
        model=DecisionTreeClassifier(random_state=42,criterion='gini',**params);y=[boost_target(r,fam) for r in train]
        model.fit([features(r,boost_columns) for r in train],y);models[fam]=model
        p=model.predict([features(r,boost_columns) for r in validation]);truth=[boost_target(r,fam) for r in validation]
        c,t,b=within_family_regret(validation,fam,p);cm=confusion_matrix(truth,p,labels=['BASE','BOOST'])
        with (out/f'{fam.lower()}_boost.pkl').open('wb') as f:pickle.dump({'model':model,'features':boost_columns},f)
        (out/f'{fam.lower()}_boost_tree.txt').write_text(export_text(model,feature_names=boost_columns))
        c_export(model,boost_columns,fam,out/f'{fam.lower()}_boost.c')
        report['boost_models'][fam]={'train_target_distribution':Counter(y),'validation_target_distribution':Counter(truth),'params':params,
            'group_cv':{'critical_regret':best[0],'total_regret':best[1],'boost_decisions':best[2],'folds':best[4]},
            'depth':int(model.get_depth()),'leaves':int(model.get_n_leaves()),
            'validation_confusion_BASE_BOOST':[[int(v) for v in row] for row in cm],
            'validation_within_family':{'critical_regret':c,'total_regret':t,'boost_decisions':b},
            'feature_importance':dict(sorted(((c,float(v)) for c,v in zip(boost_columns,model.feature_importances_)),key=lambda x:-x[1]))}
    fam_pred=list(family_model.predict([features(r,family_columns) for r in validation]))
    boost_pred=[models[f].predict([features(r,boost_columns)])[0] for r,f in zip(validation,fam_pred)]
    report['combined_validation']=regret(validation,fam_pred,boost_pred)
    report['combined_validation']['selected_policy_distribution']=Counter(variant(f,b) for f,b in zip(fam_pred,boost_pred))
    base_labels=['BASE']*len(validation)
    report['family_tree_always_base_validation']=regret(validation,fam_pred,base_labels)
    current_families=['EDF' if r['behavior_policy'].startswith('EDF') else 'RMS' for r in validation]
    current_labels=['BOOST' if r['behavior_policy'].endswith('+Boost') else 'BASE' for r in validation]
    report['keep_current_policy_validation']=regret(validation,current_families,current_labels)
    (out/'report.json').write_text(json.dumps(report,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x)))
    with (out/'validation_predictions.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['snapshot_id','family','boost_action','selected_policy'])
        for r,fam,b in zip(validation,fam_pred,boost_pred):w.writerow([r['snapshot_id'],fam,b,variant(fam,b)])
    for fam,m in report['boost_models'].items():print(f"{fam}: validation targets={dict(m['validation_target_distribution'])}, confusion={m['validation_confusion_BASE_BOOST']}, within-family regret=({m['validation_within_family']['critical_regret']}, {m['validation_within_family']['total_regret']}), depth={m['depth']}, leaves={m['leaves']}")
    c=report['combined_validation'];k=report['keep_current_policy_validation']
    print(f"combined selector validation regret=({c['critical_miss_regret']}, {c['total_miss_regret']}), boost decisions={c['boost_decisions']}")
    print(f"keep-current-policy validation regret=({k['critical_miss_regret']}, {k['total_miss_regret']})")
    print('Test workloads were not evaluated. Closed-loop evaluation still required.')

if __name__=='__main__':main()
