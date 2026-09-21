"""Resumable equivalent of the v3 engine, used for offline counterfactuals.

Workload demands belong to the simulator, never to observable_features().
Snapshots occur after boundary updates/releases, before dispatch.
"""
import copy
from dataclasses import asdict
from simulator import Task, Job, BoostConfig, integer

POLICIES = ("RMS", "EDF", "RMS+Boost", "EDF+Boost")


class Engine:
    def __init__(self, tasks, horizon, policy="EDF", boost_config=None):
        integer("horizon", horizon, 1)
        if policy not in POLICIES or not tasks or len({t.name for t in tasks}) != len(tasks):
            raise ValueError("Invalid tasks or policy")
        self.tasks = sorted(tasks, key=lambda t: t.name)
        self.configs = {t.name: t for t in self.tasks}
        self.release_maps = {}
        for t in self.tasks:
            releases=tuple(x for x in t.releases if x<horizon) if t.releases else tuple(range(t.offset,horizon,t.period))
            self.release_maps[t.name]={time:index for index,time in enumerate(releases)}
            count=len(releases)
            if t.demands and len(t.demands) < count:
                raise ValueError("Insufficient demands")
        self.horizon, self.policy = horizon, policy
        self.cfg = boost_config or BoostConfig()
        self.now, self.phase = 0, 0
        self.jobs, self.events, self.timeline, self.boost_intervals = [], [], [], []
        self.active = {}
        self.last = self.boosted_last = None
        self.window_used = 0
        self.counts = dict(dispatches=0, switches=0, preemptions=0, busy=0,
                           boost_activations=0, boost_ticks=0)
        self.completion_history = {t.name: [] for t in self.tasks}
        self.miss_history = []

    def event(self, kind, job, time=None):
        self.events.append(dict(time_ms=self.now if time is None else time,
                                event=kind, task=job.task, job=job.index,
                                remaining_ms=job.remaining))

    def prepare(self, releases=True):
        if self.phase == 0:
            if self.now % self.cfg.window == 0:
                self.window_used = 0
            self.miss_history = [m for m in self.miss_history if m[0] > self.now-100]
            for job in self.active.values():
                if job.remaining and job.absolute_deadline <= self.now and job.missed_at is None:
                    job.missed_at = self.now
                    self.event("deadline_miss", job)
                    self.miss_history.append([self.now, job.task, job.index])
            self.phase = 1
        if releases and self.phase == 1 and self.now < self.horizon:
            for task in self.tasks:
                if self.now not in self.release_maps[task.name]:
                    continue
                old = self.active.get(task.name)
                if old is not None:
                    old.dropped_at = self.now
                    self.event("drop_at_next_release", old)
                index = self.release_maps[task.name][self.now]
                demand = task.demands[index] if task.demands else task.wcet
                job = Job(task.name, index, self.now, self.now+task.deadline, demand, demand)
                self.jobs.append(job)
                self.active[task.name] = job
                self.event("release", job)
            self.phase = 2

    def step(self):
        if self.now >= self.horizon:
            raise ValueError("Simulation horizon reached")
        self.prepare()
        base = self.policy.split("+")[0]
        def priority(j):
            primary = self.configs[j.task].period if base == "RMS" else j.absolute_deadline
            return (primary, j.release, j.task, j.index)
        selected = min(self.active.values(), key=priority) if self.active else None
        boosted = None
        if self.policy.endswith("+Boost") and self.window_used < self.cfg.window_budget:
            urgent = []
            for j in self.active.values():
                estimate = self.configs[j.task].wcet-j.executed
                slack = j.absolute_deadline-self.now-estimate
                if (self.configs[j.task].critical and estimate > 0 and j.absolute_deadline > self.now
                        and 0 <= slack <= self.cfg.slack_threshold
                        and j.boosted_execution < self.cfg.per_job_budget):
                    urgent.append(j)
            if urgent:
                boosted = min(urgent, key=lambda j: (j.absolute_deadline,j.release,j.task,j.index))
                selected = boosted
        if self.boosted_last is not boosted:
            if self.boosted_last is not None:
                self.event("boost_end", self.boosted_last)
            if boosted is not None:
                self.counts['boost_activations'] += 1
                self.event("boost_start", boosted)
        self.boosted_last = boosted
        if selected is not None and (self.last is None or selected.key != self.last.key):
            self.counts['dispatches'] += 1
            self.event("dispatch", selected)
            if self.last is not None:
                self.counts['switches'] += 1
                if self.last.remaining > 0 and self.last.dropped_at is None:
                    self.counts['preemptions'] += 1
                    self.event("preempt", self.last)
        key = list(selected.key) if selected else None
        if self.timeline and self.timeline[-1]['job'] == key:
            self.timeline[-1]['end_ms'] = self.now+1
        else:
            self.timeline.append(dict(start_ms=self.now,end_ms=self.now+1,job=key))
        if selected is not None:
            self.counts['busy'] += 1
            if boosted is not None:
                self.counts['boost_ticks'] += 1
                self.window_used += 1
                selected.boosted_execution += 1
                if (self.boost_intervals and self.boost_intervals[-1]['job'] == key
                        and self.boost_intervals[-1]['end_ms'] == self.now):
                    self.boost_intervals[-1]['end_ms'] = self.now+1
                else:
                    self.boost_intervals.append(dict(start_ms=self.now,end_ms=self.now+1,job=key))
            if selected.first_start is None:
                selected.first_start = self.now
            selected.executed += 1
            selected.remaining -= 1
            if selected.executed > self.configs[selected.task].wcet and selected.overrun_at is None:
                selected.overrun_at = self.now+1
                self.event('wcet_overrun',selected,self.now+1)
            if selected.remaining == 0:
                selected.completion = self.now+1
                self.event('complete',selected,self.now+1)
                del self.active[selected.task]
                history = self.completion_history[selected.task]
                history.append(selected.executed)
                self.completion_history[selected.task] = history[-5:]
                if self.boosted_last is selected:
                    self.event('boost_end_complete',selected,self.now+1)
                    self.boosted_last = None
        self.last = selected
        self.now += 1
        self.phase = 0

    def advance(self, end):
        integer('end',end,0)
        if not self.now <= end <= self.horizon:
            raise ValueError('Cannot move backwards or beyond workload horizon')
        while self.now < end:
            self.step()
        self.prepare(releases=False)  # count deadlines at endpoint; no endpoint releases

    def checkpoint(self):
        self.prepare()
        # Retain live jobs plus completed jobs whose deadlines are still in the future.
        # The latter keep branch denominators identical after serialization/restore.
        keep = {j.key:j for j in self.jobs if j.absolute_deadline > self.now or j.task in self.active and self.active[j.task] is j}
        for j in (self.last,self.boosted_last):
            if j is not None:
                keep[j.key] = j
        return dict(now=self.now,phase=self.phase,horizon=self.horizon,policy=self.policy,
                    boost_config=asdict(self.cfg),window_used=self.window_used,
                    counts=copy.deepcopy(self.counts),
                    jobs=[asdict(j) for j in keep.values()],
                    active_keys=[list(j.key) for j in self.active.values()],
                    last_key=list(self.last.key) if self.last else None,
                    boosted_last_key=list(self.boosted_last.key) if self.boosted_last else None,
                    completion_history=copy.deepcopy(self.completion_history),
                    miss_history=copy.deepcopy(self.miss_history))

    @classmethod
    def restore(cls,tasks,checkpoint):
        c=copy.deepcopy(checkpoint)
        e=cls(tasks,c['horizon'],c['policy'],BoostConfig(**c['boost_config']))
        e.now,e.phase,e.window_used=c['now'],c['phase'],c['window_used']
        e.counts=c['counts'];e.jobs=[Job(**j) for j in c['jobs']]
        by_key={j.key:j for j in e.jobs}
        e.active={k[0]:by_key[tuple(k)] for k in c['active_keys']}
        e.last=by_key[tuple(c['last_key'])] if c['last_key'] else None
        e.boosted_last=by_key[tuple(c['boosted_last_key'])] if c['boosted_last_key'] else None
        e.completion_history=c['completion_history'];e.miss_history=c['miss_history']
        return e


def observable_features(engine):
    """Explicit allowlist: no Job.demand, true remaining or future release demands."""
    if engine.phase != 2:
        raise ValueError('Features must be extracted after releases, before dispatch')
    jobs=list(engine.active.values())
    critical=[j for j in jobs if engine.configs[j.task].critical]
    def slack(j):
        return j.absolute_deadline-engine.now-max(0,engine.configs[j.task].wcet-j.executed)
    recent=engine.miss_history
    variances=[]
    for history in engine.completion_history.values():
        if len(history)>=2 and sum(history)>0:
            variances.append(100*(max(history)-min(history))/(sum(history)/len(history)))
    return {
        'nominal_utilization_pct':100*sum(t.wcet/t.period for t in engine.tasks),
        'task_count':len(engine.tasks), 'ready_queue_length':len(jobs),
        'critical_ready_count':len(critical),
        'min_slack_ms':min(map(slack,jobs),default=0),
        'mean_slack_ms':sum(map(slack,jobs))/len(jobs) if jobs else 0,
        'min_critical_slack_ms':min(map(slack,critical),default=0),
        'misses_last_100ms':len(recent),
        'critical_misses_last_100ms':sum(engine.configs[m[1]].critical for m in recent),
        'completed_execution_range_pct':sum(variances)/len(variances) if variances else 0,
        'execution_history_task_count':len(variances),
        'current_mode':POLICIES.index(engine.policy),
        'boost_window_remaining_ms':max(0,engine.cfg.window_budget-engine.window_used),
        'boost_window_phase_ms':engine.now%engine.cfg.window,
        'critical_job_boost_budget_remaining_ms':sum(max(0,engine.cfg.per_job_budget-j.boosted_execution) for j in critical),
        'wcet_exhausted_active_count':sum(j.executed>=engine.configs[j.task].wcet for j in jobs),
    }


def compare_policies(engine, lookahead=400):
    integer('lookahead',lookahead,1)
    if engine.now+lookahead > engine.horizon:
        raise ValueError('A full lookahead window is required')
    snapshot=engine.checkpoint()
    start,end=engine.now,engine.now+lookahead
    outcomes={}
    for policy in POLICIES:
        branch=Engine.restore(engine.tasks,snapshot)
        branch.policy=policy
        before=branch.counts.copy()
        branch.advance(end)
        misses=[j for j in branch.jobs if j.missed_at is not None and start<j.missed_at<=end]
        critical_misses=sum(branch.configs[j.task].critical for j in misses)
        observed=[j for j in branch.jobs if start<j.absolute_deadline<=end]
        completed=[j for j in branch.jobs if j.completion is not None and start<j.completion<=end]
        outcomes[policy]={
            'critical_misses':critical_misses,'total_misses':len(misses),
            'noncritical_misses':len(misses)-critical_misses,
            'deadline_observed_jobs':len(observed),
            'completed_jobs':len(completed),
            'mean_response_ms_completed_only':sum(j.completion-j.release for j in completed)/len(completed) if completed else None,
            'dropped_jobs':sum(j.dropped_at is not None and start<j.dropped_at<=end for j in branch.jobs),
            'pending_jobs_at_endpoint':len(branch.active),
            'context_switches':branch.counts['switches']-before['switches'],
            'boost_execution_ms':branch.counts['boost_ticks']-before['boost_ticks'],
        }
    best=min((o['critical_misses'],o['total_misses']) for o in outcomes.values())
    winners=[p for p in POLICIES if (outcomes[p]['critical_misses'],outcomes[p]['total_misses'])==best]
    unique=winners[0] if len(winners)==1 else None
    recommendation=unique or (engine.policy if engine.policy in winners else None)
    return {'decision_time_ms':start,'comparison_end_ms':end,'outcomes':outcomes,
            'optimal_policies':winners,'unique_best_policy':unique,
            'recommended_policy':recommendation,
            'recommendation_reason':'unique_best' if unique else 'keep_current_tied_best' if recommendation else 'unresolved_tie',
            'has_policy_discrimination':len(winners)<len(POLICIES)}
