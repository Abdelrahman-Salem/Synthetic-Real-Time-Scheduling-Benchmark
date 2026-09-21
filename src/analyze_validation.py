"""Paired statistical analysis of closed-loop validation results."""
import argparse,csv,json,math,random,statistics
from pathlib import Path
from scipy.stats import wilcoxon

BASELINES=('RMS','EDF','RMS+Boost','EDF+Boost')
METRICS=('critical_misses','total_misses','mean_response_ms','context_switches')


def bootstrap_mean_ci(values,repetitions=10000,seed=20260921):
    if not values:return [None,None]
    rng=random.Random(seed);n=len(values)
    means=sorted(sum(values[rng.randrange(n)] for _ in range(n))/n for _ in range(repetitions))
    return [means[int(.025*repetitions)],means[min(repetitions-1,int(.975*repetitions))]]


def holm(pvalues):
    ordered=sorted(enumerate(pvalues),key=lambda x:x[1]);m=len(pvalues);adjusted=[0.0]*m;running=0.0
    for rank,(index,p) in enumerate(ordered):
        running=max(running,min(1.0,(m-rank)*p));adjusted[index]=running
    return adjusted


def paired_test(differences):
    nonzero=[x for x in differences if x!=0]
    if not nonzero:return 1.0
    return float(wilcoxon(differences,zero_method='pratt',alternative='two-sided',method='auto').pvalue)


def analyze(records,bootstrap_repetitions=10000):
    comparisons=[]
    for baseline in BASELINES:
        for metric in METRICS:
            differences=[]
            for row in records:
                a=row['metrics']['ADAPTIVE'][metric];b=row['metrics'][baseline][metric]
                if a is not None and b is not None:differences.append(a-b)
            wins=sum(x<0 for x in differences);ties=sum(x==0 for x in differences);losses=sum(x>0 for x in differences)
            comparisons.append({'baseline':baseline,'metric':metric,'n':len(differences),
                'adaptive_mean':statistics.fmean(row['metrics']['ADAPTIVE'][metric] for row in records),
                'baseline_mean':statistics.fmean(row['metrics'][baseline][metric] for row in records),
                'paired_mean_difference_adaptive_minus_baseline':statistics.fmean(differences),
                'paired_median_difference':statistics.median(differences),
                'bootstrap_95pct_ci_mean_difference':bootstrap_mean_ci(differences,bootstrap_repetitions),
                'wins_lower_is_better':wins,'ties':ties,'losses':losses,
                'win_rate_excluding_ties':wins/(wins+losses) if wins+losses else None,
                'wilcoxon_two_sided_p_raw':paired_test(differences)})
    adjusted=holm([x['wilcoxon_two_sided_p_raw'] for x in comparisons])
    for row,p in zip(comparisons,adjusted):row['holm_adjusted_p_across_16_tests']=p
    totals={}
    for method in BASELINES+('ADAPTIVE',):
        totals[method]={m:sum(r['metrics'][method][m] for r in records) for m in ('critical_misses','total_misses','context_switches')}
    reductions={}
    for baseline in BASELINES:
        reductions[baseline]={}
        for metric in ('critical_misses','total_misses'):
            b=totals[baseline][metric];a=totals['ADAPTIVE'][metric]
            reductions[baseline][metric+'_reduction_pct']=100*(b-a)/b if b else None
    return {'split':'validation','test_evaluated':False,'task_sets':len(records),
            'bootstrap_repetitions':bootstrap_repetitions,'bootstrap_seed':20260921,
            'primary_metrics':['critical_misses','total_misses'],
            'multiplicity':'Holm correction across all 16 reported paired tests',
            'totals':totals,'aggregate_reductions':reductions,'comparisons':comparisons}


def markdown(report):
    lines=['# Closed-loop validation statistical report','',
      'Validation only; test workloads were not evaluated. Differences are Adaptive minus baseline, so negative values favor Adaptive.', '',
      '| Baseline | Metric | Mean difference | 95% bootstrap CI | Wins–ties–losses | Holm p |','|---|---:|---:|---:|---:|---:|']
    for r in report['comparisons']:
        lo,hi=r['bootstrap_95pct_ci_mean_difference']
        lines.append(f"| {r['baseline']} | {r['metric']} | {r['paired_mean_difference_adaptive_minus_baseline']:.4f} | [{lo:.4f}, {hi:.4f}] | {r['wins_lower_is_better']}–{r['ties']}–{r['losses']} | {r['holm_adjusted_p_across_16_tests']:.4g} |")
    lines += ['', 'Wilcoxon signed-rank tests are two-sided. The bootstrap resamples complete task sets, preserving paired comparisons. Statistical significance does not replace practical-effect reporting.']
    return '\n'.join(lines)+'\n'


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--results',default='closed_loop_results/per_task_set.json')
    ap.add_argument('--out',default='validation_statistics');ap.add_argument('--bootstrap',type=int,default=10000);args=ap.parse_args()
    out=Path(args.out)
    if out.exists():ap.error('Output exists; select a new --out.')
    records=json.loads(Path(args.results).read_text(encoding='utf-8'))
    if args.bootstrap<1000:ap.error('--bootstrap must be at least 1000')
    report=analyze(records,args.bootstrap);out.mkdir()
    (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (out/'report.md').write_text(markdown(report),encoding='utf-8')
    with (out/'paired_comparisons.csv').open('w',newline='',encoding='utf-8') as f:
        fields=list(report['comparisons'][0]);w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in report['comparisons']:w.writerow(r)
    print('Validation task sets:',report['task_sets'])
    for b in BASELINES:
        rows=[r for r in report['comparisons'] if r['baseline']==b and r['metric'] in report['primary_metrics']]
        print(b)
        for r in rows:print(f"  {r['metric']}: diff={r['paired_mean_difference_adaptive_minus_baseline']:.3f}, CI={tuple(round(x,3) for x in r['bootstrap_95pct_ci_mean_difference'])}, W/T/L={r['wins_lower_is_better']}/{r['ties']}/{r['losses']}, Holm p={r['holm_adjusted_p_across_16_tests']:.4g}")
    print('Test workloads were not evaluated.')


if __name__=='__main__':main()
