"""One-shot final evaluation on the sealed test split. No training or tuning."""
import argparse,csv,hashlib,json
from pathlib import Path

from analyze_validation import analyze,markdown
from evaluate_closed_loop import POLICIES,aggregate,run_adaptive,run_static,load_bundle
from workloads import load_case


def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--workloads',default='workloads')
    ap.add_argument('--family-model',default='family_model/without_current_mode.pkl')
    ap.add_argument('--boost-model',default='boost_model')
    ap.add_argument('--out',default='FINAL_TEST_RESULTS_DO_NOT_RERUN')
    args=ap.parse_args();out=Path(args.out)
    if out.exists():ap.error('Final-test output already exists. Do not rerun or tune on test results.')
    root=Path(args.workloads);manifest_path=root/'manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    entries=[e for e in manifest['cases'] if e['split']=='test']
    if not entries:raise ValueError('No sealed test workloads found')
    family=load_bundle(args.family_model)
    boost_paths={f:Path(args.boost_model)/(f.lower()+'_boost.pkl') for f in ('RMS','EDF')}
    boost={f:load_bundle(p) for f,p in boost_paths.items()}
    out.mkdir();records=[];traces={}
    for i,entry in enumerate(entries,1):
        case=json.loads((root/entry['path']).read_text(encoding='utf-8'))
        if case['split']!='test':raise ValueError('Split contamination detected')
        tasks,horizon=load_case(case);per={}
        for policy in POLICIES:per[policy]=run_static(tasks,horizon,policy)
        per['ADAPTIVE'],trace=run_adaptive(tasks,horizon,family,boost,100)
        traces[case['task_set_id']]=trace;records.append({'task_set_id':case['task_set_id'],'metrics':per})
        if i%20==0 or i==len(entries):print(f'Completed {i}/{len(entries)} sealed test task sets')
    methods=list(POLICIES)+['ADAPTIVE']
    totals={m:aggregate([r['metrics'][m] for r in records]) for m in methods}
    stats=analyze(records,10000);stats['split']='test';stats['test_evaluated']=True
    provenance={'status':'FINAL_FROZEN_TEST_EVALUATION','decision_interval_ms':100,
        'task_sets':len(entries),'manifest_sha256':sha256(manifest_path),
        'suite_sha256':manifest['suite_sha256'],'family_model_sha256':sha256(args.family_model),
        'rms_boost_model_sha256':sha256(boost_paths['RMS']),'edf_boost_model_sha256':sha256(boost_paths['EDF']),
        'training_performed':False,'hyperparameter_tuning_performed':False}
    (out/'provenance.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    (out/'summary.json').write_text(json.dumps({'provenance':provenance,'methods':totals},indent=2),encoding='utf-8')
    (out/'per_task_set.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    (out/'adaptive_traces.json').write_text(json.dumps(traces,indent=2),encoding='utf-8')
    (out/'statistical_report.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
    (out/'statistical_report.md').write_text(markdown(stats).replace('validation','test').replace('Validation','Test'),encoding='utf-8')
    with (out/'paired_comparisons.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(stats['comparisons'][0]));w.writeheader();w.writerows(stats['comparisons'])
    print('\nFINAL sealed-test totals:')
    for m in methods:
        x=totals[m];print(f"{m:10s} critical={x['critical_misses']}, total={x['total_misses']}, response={x['mean_response_ms_completed_weighted']:.3f}, switches={x['context_switches']}")
    print('\nPrimary paired comparisons (Adaptive minus baseline):')
    for r in stats['comparisons']:
        if r['metric'] in ('critical_misses','total_misses'):
            lo,hi=r['bootstrap_95pct_ci_mean_difference']
            print(f"{r['baseline']:10s} {r['metric']:16s} diff={r['paired_mean_difference_adaptive_minus_baseline']:.3f}, CI=({lo:.3f}, {hi:.3f}), Holm p={r['holm_adjusted_p_across_16_tests']:.4g}")
    print('\nFINAL TEST COMPLETE. Freeze these results; do not tune or retrain from them.')


if __name__=='__main__':main()
