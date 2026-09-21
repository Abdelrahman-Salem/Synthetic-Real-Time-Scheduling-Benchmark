"""Evaluate the deployable two-stage scheduler on validation workloads only."""
import argparse,csv,json,pickle
from collections import Counter
from pathlib import Path

from state_engine import Engine,observable_features,POLICIES
from workloads import load_case


def load_bundle(path):
    with open(path,'rb') as f:return pickle.load(f)


def predict(bundle,features):
    return str(bundle['model'].predict([[features[c] for c in bundle['features']]])[0])


def metrics(engine):
    completed=[j for j in engine.jobs if j.completion is not None]
    misses=[j for j in engine.jobs if j.missed_at is not None]
    critical=sum(engine.configs[j.task].critical for j in misses)
    return {
        'critical_misses':int(critical),'total_misses':len(misses),
        'completed_jobs':len(completed),
        'dropped_jobs':sum(j.dropped_at is not None for j in engine.jobs),
        'mean_response_ms':(sum(j.completion-j.release for j in completed)/len(completed) if completed else None),
        'context_switches':engine.counts['switches'],
        'preemptions':engine.counts['preemptions'],
        'boost_activations':engine.counts['boost_activations'],
        'boost_execution_ms':engine.counts['boost_ticks'],
        'busy_ms':engine.counts['busy'],
    }


def run_static(tasks,horizon,policy):
    engine=Engine(tasks,horizon,policy);engine.advance(horizon)
    return metrics(engine)


def run_adaptive(tasks,horizon,family,boost_models,interval):
    engine=Engine(tasks,horizon,'RMS');decisions=[];mode_switches=0
    for start in range(0,horizon,interval):
        engine.prepare()
        f=observable_features(engine)
        fam=predict(family,f)
        action=predict(boost_models[fam],f)
        policy=fam+'+Boost' if action=='BOOST' else fam
        if decisions and policy!=decisions[-1]['policy']:mode_switches+=1
        engine.policy=policy
        decisions.append({'time_ms':start,'policy':policy})
        engine.advance(min(horizon,start+interval))
    result=metrics(engine)
    result.update(mode_switches=mode_switches,decision_count=len(decisions),
                  decision_distribution=dict(Counter(d['policy'] for d in decisions)))
    return result,decisions


def aggregate(rows):
    fields=('critical_misses','total_misses','completed_jobs','dropped_jobs','context_switches',
            'preemptions','boost_activations','boost_execution_ms','busy_ms')
    result={k:sum(r[k] for r in rows) for k in fields}
    completed=sum(r['completed_jobs'] for r in rows)
    result['mean_response_ms_completed_weighted']=(sum((r['mean_response_ms'] or 0)*r['completed_jobs'] for r in rows)/completed if completed else None)
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--workloads',default='workloads')
    ap.add_argument('--family-model',default='family_model/without_current_mode.pkl')
    ap.add_argument('--boost-model',default='boost_model')
    ap.add_argument('--interval-ms',type=int,default=100)
    ap.add_argument('--out',default='closed_loop_results')
    args=ap.parse_args();out=Path(args.out)
    if out.exists():ap.error('Output exists; select a new --out.')
    if args.interval_ms<1:ap.error('--interval-ms must be positive')
    root=Path(args.workloads);manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    entries=[e for e in manifest['cases'] if e['split']=='validation']
    if not entries:raise ValueError('No validation workloads')
    family=load_bundle(args.family_model)
    boost={f:load_bundle(Path(args.boost_model)/(f.lower()+'_boost.pkl')) for f in ('RMS','EDF')}
    out.mkdir();records=[];traces={}
    for i,entry in enumerate(entries,1):
        case=json.loads((root/entry['path']).read_text(encoding='utf-8'))
        if case['split']!='validation':raise ValueError('Refusing non-validation workload')
        tasks,horizon=load_case(case);per={}
        for policy in POLICIES:per[policy]=run_static(tasks,horizon,policy)
        per['ADAPTIVE'],trace=run_adaptive(tasks,horizon,family,boost,args.interval_ms)
        traces[case['task_set_id']]=trace
        records.append({'task_set_id':case['task_set_id'],'metrics':per})
        if i%20==0 or i==len(entries):print(f'Completed {i}/{len(entries)} validation task sets')
    methods=list(POLICIES)+['ADAPTIVE']
    summary={'version':'v8-closed-loop','split':'validation','test_evaluated':False,
             'decision_interval_ms':args.interval_ms,'task_sets':len(records),
             'methods':{m:aggregate([r['metrics'][m] for r in records]) for m in methods}}
    adaptive=[r['metrics']['ADAPTIVE'] for r in records]
    for base in POLICIES:
        wins=ties=losses=0
        for r,a in zip(records,adaptive):
            b=r['metrics'][base];ka=(a['critical_misses'],a['total_misses']);kb=(b['critical_misses'],b['total_misses'])
            if ka<kb:wins+=1
            elif ka==kb:ties+=1
            else:losses+=1
        summary.setdefault('adaptive_pairwise',{})[base]={'wins':wins,'ties':ties,'losses':losses}
    summary['adaptive_mode_switches']=sum(r['metrics']['ADAPTIVE']['mode_switches'] for r in records)
    summary['adaptive_decision_distribution']=dict(sum((Counter(r['metrics']['ADAPTIVE']['decision_distribution']) for r in records),Counter()))
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (out/'per_task_set.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    (out/'adaptive_traces.json').write_text(json.dumps(traces,indent=2),encoding='utf-8')
    with (out/'per_task_set.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['task_set_id','method','critical_misses','total_misses','mean_response_ms','context_switches','boost_execution_ms'])
        for r in records:
            for method,m in r['metrics'].items():w.writerow([r['task_set_id'],method,m['critical_misses'],m['total_misses'],m['mean_response_ms'],m['context_switches'],m['boost_execution_ms']])
    print('\nClosed-loop validation totals:')
    for m in methods:
        x=summary['methods'][m];print(f"{m:10s} critical={x['critical_misses']}, total={x['total_misses']}, response={x['mean_response_ms_completed_weighted']:.3f}, switches={x['context_switches']}")
    print('Adaptive decisions:',summary['adaptive_decision_distribution'])
    print('Test workloads were not evaluated.')


if __name__=='__main__':main()
