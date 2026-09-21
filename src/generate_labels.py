"""Generate offline state-wise counterfactual targets; never evaluate test split."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
from state_engine import Engine, POLICIES, observable_features, compare_policies
from workloads import fingerprint, load_case


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workloads',default='workloads')
    parser.add_argument('--out',default='label_data')
    parser.add_argument('--interval',type=int,default=100)
    parser.add_argument('--lookahead',type=int,default=400)
    parser.add_argument('--splits',nargs='+',choices=('train','validation'),default=['train','validation'])
    args=parser.parse_args()
    if args.interval<1 or args.lookahead<1:
        parser.error('interval and lookahead must be positive')
    root,out=Path(args.workloads),Path(args.out)
    if out.exists():
        parser.error('Output exists. Choose a new --out directory.')
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    if fingerprint(manifest['cases'])!=manifest['suite_sha256']:
        raise ValueError('Manifest hash mismatch')
    cases=[]
    for entry in manifest['cases']:
        if entry['split'] not in args.splits:
            continue
        path=(root/entry['path']).resolve()
        if root.resolve() not in path.parents:
            raise ValueError('Case outside workload directory')
        case=json.loads(path.read_text(encoding='utf-8'))
        if any(case[k]!=entry[k] for k in ('task_set_id','split','workload_sha256')):
            raise ValueError('Case does not match manifest')
        tasks,horizon=load_case(case)
        if horizon<args.lookahead:
            raise ValueError('Workload shorter than lookahead')
        cases.append((case,tasks,horizon))
    out.mkdir(parents=True)
    stats={s:{'rows':0,'unique_best':Counter(),'optimal_sets':Counter(),
              'recommendations':Counter(),'discriminating_rows':0,
              'all_four_tied':0,'unresolved_ties':0} for s in args.splits}
    feature_names=None
    with (out/'states.jsonl').open('w',encoding='utf-8') as dataset, (out/'checkpoints.jsonl').open('w',encoding='utf-8') as checkpoints:
        for number,(case,tasks,horizon) in enumerate(cases,1):
            for behavior in POLICIES:
                engine=Engine(tasks,horizon,behavior)
                for time in range(0,horizon-args.lookahead+1,args.interval):
                    engine.advance(time)
                    state=engine.checkpoint()
                    features=observable_features(engine)
                    feature_names=list(features)
                    comparison=compare_policies(engine,args.lookahead)
                    snapshot_id=f"{case['task_set_id']}__{behavior}__t{time}"
                    checkpoint_hash=fingerprint(state)
                    row={'snapshot_id':snapshot_id,'task_set_id':case['task_set_id'],
                         'split':case['split'],'workload_sha256':case['workload_sha256'],
                         'seed':case['seed'],'behavior_policy':behavior,
                         'checkpoint_sha256':checkpoint_hash,'features':features,**comparison}
                    dataset.write(json.dumps(row,separators=(',',':'))+'\n')
                    checkpoints.write(json.dumps({'snapshot_id':snapshot_id,
                        'workload_sha256':case['workload_sha256'],'checkpoint_sha256':checkpoint_hash,
                        'private_simulator_state':state},separators=(',',':'))+'\n')
                    s=stats[case['split']];s['rows']+=1
                    if comparison['unique_best_policy']:
                        s['unique_best'][comparison['unique_best_policy']]+=1
                    s['optimal_sets'][' | '.join(comparison['optimal_policies'])]+=1
                    s['recommendations'][comparison['recommended_policy'] or 'UNRESOLVED']+=1
                    s['discriminating_rows']+=int(comparison['has_policy_discrimination'])
                    s['all_four_tied']+=int(len(comparison['optimal_policies'])==4)
                    s['unresolved_ties']+=int(comparison['recommendation_reason']=='unresolved_tie')
            if number%6==0 or number==len(cases):
                total=sum(s['rows'] for s in stats.values())
                print(f'Completed {number}/{len(cases)} task sets: {total} states, {total*4} policy rollouts',flush=True)
    source_files=('state_engine.py','simulator.py','workloads.py','generate_labels.py')
    source_hashes={n:hashlib.sha256((Path(__file__).parent/n).read_bytes()).hexdigest() for n in source_files}
    report={'version':'v4-pilot','objective':['critical_misses','total_misses'],
            'interval_ms':args.interval,'lookahead_ms':args.lookahead,'behavior_policies':list(POLICIES),
            'task_sets':len(cases),'suite_sha256':manifest['suite_sha256'],
            'test_evaluated':False,'feature_columns':feature_names,'statistics':stats,
            'source_sha256':source_hashes,'python':platform.python_version(),
            'interpretation':'Offline finite-lookahead targets, not globally optimal or deployable future knowledge'}
    (out/'label_summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    total=sum(s['rows'] for s in stats.values())
    print(f'Saved {total} state records and checkpoints.')
    for split,s in stats.items():
        print(f"{split}: unique_best={sum(s['unique_best'].values())}, all_four_tied={s['all_four_tied']}, unresolved_ties={s['unresolved_ties']}")
    print('Test workloads were not evaluated. No model trained.')


if __name__=='__main__':
    main()
