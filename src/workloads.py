"""Expanded, reproducible workload generator with explicit release schedules."""
import hashlib,json,math,random
from dataclasses import asdict
from simulator import Task,integer

PERIODS=(20,30,40,50,80,100,150,200)
TASK_COUNTS=(3,5,8,10)
TARGET_UTILIZATIONS=(0.40,0.60,0.80,0.95,1.10)
DEADLINE_PROFILES=("implicit","constrained")
RELEASE_PROFILES=("synchronous","fixed_offsets","jitter","bursts")
SPLIT_REPLICATES={"train":2,"validation":1,"test":1}

def fingerprint(value):
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()

def explicit_releases(rng,period,horizon,profile,phase):
    nominal=list(range(phase,horizon,period))
    if profile in ("synchronous","fixed_offsets"):return tuple(nominal)
    if profile=="jitter":
        bound=max(1,period//10);result=[];previous=-1
        for nominal_time in nominal:
            time=max(0,min(horizon-1,nominal_time+rng.randint(-bound,bound)))
            time=max(previous+1,time)
            if time>=horizon:break
            result.append(time);previous=time
        return tuple(result)
    frame=100;result=[]
    for nominal_time in nominal:
        time=(nominal_time//frame)*frame+phase%5
        if time<horizon and (not result or time>result[-1]):result.append(time)
    return tuple(result)

def generate_case(master_seed,split,n,target,deadline_profile,release_profile,replicate,horizon=3000):
    integer('master_seed',master_seed,0);integer('horizon',horizon,1);integer('replicate',replicate,0)
    if split not in SPLIT_REPLICATES or n not in TASK_COUNTS or target not in TARGET_UTILIZATIONS:raise ValueError('Outside grid')
    if deadline_profile not in DEADLINE_PROFILES or release_profile not in RELEASE_PROFILES:raise ValueError('Unsupported profile')
    case_id=f"{split}_n{n}_u{int(round(target*100))}_{deadline_profile}_{release_profile}_r{replicate}"
    seed=int(fingerprint([master_seed,case_id])[:16],16);rng=random.Random(seed)
    for attempt in range(1,2001):
        periods=[rng.choice(PERIODS) for _ in range(n)];weights=[rng.uniform(.5,1.5) for _ in range(n)]
        wcets=[max(1,min(int(.75*p),int(target*w/sum(weights)*p+.5))) for p,w in zip(periods,weights)]
        achieved=sum(c/p for c,p in zip(wcets,periods))
        if abs(achieved-target)<=.015000001:break
    else:raise RuntimeError('Utilization target not reached')
    execution_profile=rng.choice(('fixed_wcet','variable_50_to_100_percent'))
    critical_indices=set(rng.sample(range(n),max(1,math.ceil(.25*n))));tasks=[]
    for i,(period,wcet) in enumerate(zip(periods,wcets)):
        deadline=period if deadline_profile=='implicit' else rng.randint(max(wcet,math.ceil(.4*period)),period-1)
        phase=0 if release_profile in ('synchronous','jitter') else rng.randrange(period)
        releases=explicit_releases(rng,period,horizon,release_profile,phase)
        demands=tuple(wcet if execution_profile=='fixed_wcet' else rng.randint(math.ceil(.5*wcet),wcet) for _ in releases)
        tasks.append(Task(f'T{i+1}',period,wcet,deadline,phase,demands,i in critical_indices,releases))
    task_data=[asdict(t) for t in tasks];payload={'horizon_ms':horizon,'tasks':task_data}
    return {'schema_version':2,'generator_version':'expanded-v6','task_set_id':case_id,'split':split,
            'master_seed':master_seed,'seed':seed,'replicate':replicate,'requested_utilization':target,
            'nominal_utilization':achieved,'utilization_tolerance':.015,'sampling_attempts':attempt,
            'deadline_profile':deadline_profile,'execution_profile':execution_profile,'release_profile':release_profile,
            'critical_task_count':len(critical_indices),'release_jitter':release_profile=='jitter',
            'burst_arrivals':release_profile=='bursts','overruns':False,'horizon_ms':horizon,'tasks':task_data,
            'workload_sha256':fingerprint(payload)}

def build_suite(master_seed=20260920,horizon=3000):
    cases=[]
    for split,repeats in SPLIT_REPLICATES.items():
        for n in TASK_COUNTS:
            for target in TARGET_UTILIZATIONS:
                for deadline in DEADLINE_PROFILES:
                    for release in RELEASE_PROFILES:
                        for replicate in range(repeats):cases.append(generate_case(master_seed,split,n,target,deadline,release,replicate,horizon))
    for key in ('task_set_id','seed','workload_sha256'):
        if len({c[key] for c in cases})!=len(cases):raise RuntimeError(f'Duplicate {key}')
    return cases

def load_case(case):
    if fingerprint({'horizon_ms':case['horizon_ms'],'tasks':case['tasks']})!=case['workload_sha256']:raise ValueError('Workload hash mismatch')
    tasks=[Task(**{**t,'demands':tuple(t['demands']),'releases':tuple(t.get('releases',()))}) for t in case['tasks']]
    return tasks,case['horizon_ms']
