"""Deterministic single-CPU reference simulator, Python 3.9+, stdlib only.

One tick is one millisecond. This models preemptive RMS/EDF with zero overhead;
it is NOT a reproduction of the old AVR implementation or paper results.
"""
from dataclasses import asdict, dataclass
from typing import List, Optional, Tuple


def integer(name, value, minimum):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


@dataclass(frozen=True)
class Task:
    name: str
    period: int
    wcet: int
    deadline: int
    offset: int = 0
    # Optional exact, per-release execution demands. No random draws in engine.
    # Demands above WCET are intentional fault/overrun inputs, recorded as such.
    demands: Tuple[int, ...] = ()
    critical: bool = False
    # Optional explicit release times. When present, period remains the nominal
    # configuration feature but releases are taken only from this tuple.
    releases: Tuple[int, ...] = ()

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Task name must be nonempty")
        for field in ("period", "wcet", "deadline"):
            integer(field, getattr(self, field), 1)
        integer("offset", self.offset, 0)
        if type(self.critical) is not bool:
            raise ValueError("critical must be boolean")
        if self.deadline > self.period:
            raise ValueError("v1 supports relative deadline <= period")
        for demand in self.demands:
            integer("execution demand", demand, 1)
        for release in self.releases:
            integer("release time", release, 0)
        if self.releases and tuple(sorted(set(self.releases))) != self.releases:
            raise ValueError("Explicit releases must be strictly increasing")


@dataclass(frozen=True)
class BoostConfig:
    slack_threshold: int = 1
    per_job_budget: int = 2
    window: int = 10
    window_budget: int = 2

    def __post_init__(self):
        integer("slack_threshold", self.slack_threshold, 0)
        integer("per_job_budget", self.per_job_budget, 1)
        integer("window", self.window, 2)
        integer("window_budget", self.window_budget, 1)
        if self.window_budget >= self.window:
            raise ValueError("window_budget must be smaller than window")


@dataclass
class Job:
    task: str
    index: int
    release: int
    absolute_deadline: int
    demand: int
    remaining: int
    executed: int = 0
    first_start: Optional[int] = None
    completion: Optional[int] = None
    missed_at: Optional[int] = None
    dropped_at: Optional[int] = None
    overrun_at: Optional[int] = None
    boosted_execution: int = 0

    @property
    def key(self):
        return (self.task, self.index)


def simulate(tasks: List[Task], horizon: int, policy: str = "EDF",
             boost_config: Optional[BoostConfig] = None):
    """Run [0, horizon), observing completions/deadlines at horizon too.

    At each boundary: previous interval has completed; mark due misses once;
    drop an unfinished old job on its next release; release; dispatch.
    Tardy jobs may finish until their next release. No overlapping jobs per task.
    Tie order: primary priority, release time, task name, job index.
    """
    integer("horizon", horizon, 1)
    if policy not in ("RMS", "EDF", "RMS+Boost", "EDF+Boost"):
        raise ValueError("Unknown scheduling policy")
    base_policy = policy.split("+")[0]
    boost_enabled = policy.endswith("+Boost")
    boost_config = boost_config or BoostConfig()
    if not tasks or len({t.name for t in tasks}) != len(tasks):
        raise ValueError("Use at least one task with unique names")
    tasks = sorted(tasks, key=lambda t: t.name)
    release_maps = {}
    for t in tasks:
        releases = tuple(x for x in t.releases if x < horizon) if t.releases else tuple(range(t.offset,horizon,t.period))
        release_maps[t.name] = {time:index for index,time in enumerate(releases)}
        count = len(releases)
        if t.demands and len(t.demands) < count:
            raise ValueError(f"Insufficient explicit demands for {t.name}")
    configs = {t.name: t for t in tasks}
    jobs, events, timeline, boost_intervals = [], [], [], []
    active = {}
    last: Optional[Job] = None
    dispatches = context_switches = preemptions = busy = 0
    boosted_last = None
    boost_activations = boost_ticks = window_used = 0

    def event(time, kind, job):
        events.append({"time_ms": time, "event": kind,
                       "task": job.task, "job": job.index,
                       "remaining_ms": job.remaining})

    for now in range(horizon + 1):
        if now % boost_config.window == 0:
            window_used = 0
        for job in active.values():
            if job.remaining and job.absolute_deadline <= now and job.missed_at is None:
                job.missed_at = now
                event(now, "deadline_miss", job)
        if now == horizon:
            if boosted_last is not None:
                event(now, "boost_end_horizon", boosted_last)
            break  # no new releases at horizon
        for task in tasks:
            if now not in release_maps[task.name]:
                continue
            old = active.get(task.name)
            if old is not None:
                old.dropped_at = now
                event(now, "drop_at_next_release", old)
            index = release_maps[task.name][now]
            demand = task.demands[index] if task.demands else task.wcet
            job = Job(task.name, index, now, now + task.deadline, demand, demand)
            jobs.append(job)
            active[task.name] = job
            event(now, "release", job)
        candidates = list(active.values())
        def priority(job):
            primary = configs[job.task].period if base_policy == "RMS" else job.absolute_deadline
            return (primary, job.release, job.task, job.index)
        selected = min(candidates, key=priority) if candidates else None
        boosted = None
        if boost_enabled and window_used < boost_config.window_budget:
            urgent = []
            for job in candidates:
                # Use observable remaining WCET budget, not hidden actual demand.
                # Once WCET is exhausted, suspend boosting: no remaining bound known.
                estimated_remaining = configs[job.task].wcet - job.executed
                slack = job.absolute_deadline - now - estimated_remaining
                if (configs[job.task].critical and estimated_remaining > 0
                        and job.absolute_deadline > now
                        and 0 <= slack <= boost_config.slack_threshold
                        and job.boosted_execution < boost_config.per_job_budget):
                    urgent.append(job)
            if urgent:
                boosted = min(urgent, key=lambda j: (j.absolute_deadline, j.release, j.task, j.index))
                selected = boosted
        if boosted_last is not boosted:
            if boosted_last is not None:
                event(now, "boost_end", boosted_last)
            if boosted is not None:
                boost_activations += 1
                event(now, "boost_start", boosted)
        boosted_last = boosted
        if selected is not None and (last is None or selected.key != last.key):
            dispatches += 1
            event(now, "dispatch", selected)
            if last is not None:
                context_switches += 1
                if last.remaining > 0 and last.dropped_at is None:
                    preemptions += 1
                    event(now, "preempt", last)
        key = list(selected.key) if selected else None
        if timeline and timeline[-1]["job"] == key:
            timeline[-1]["end_ms"] = now + 1
        else:
            timeline.append({"start_ms": now, "end_ms": now + 1, "job": key})
        if selected is not None:
            busy += 1
            if boosted is not None:
                boost_ticks += 1
                window_used += 1
                selected.boosted_execution += 1
                if (boost_intervals and boost_intervals[-1]["job"] == key
                        and boost_intervals[-1]["end_ms"] == now):
                    boost_intervals[-1]["end_ms"] = now + 1
                else:
                    boost_intervals.append({"start_ms": now, "end_ms": now + 1, "job": key})
            if selected.first_start is None:
                selected.first_start = now
            selected.executed += 1
            selected.remaining -= 1
            if selected.executed > configs[selected.task].wcet and selected.overrun_at is None:
                selected.overrun_at = now + 1
                event(now + 1, "wcet_overrun", selected)
            if selected.remaining == 0:
                selected.completion = now + 1
                event(now + 1, "complete", selected)
                del active[selected.task]
                if boosted_last is selected:
                    event(now + 1, "boost_end_complete", selected)
                    boosted_last = None
        last = selected

    observed = [j for j in jobs if j.absolute_deadline <= horizon]
    completed = [j for j in jobs if j.completion is not None]
    missed = sum(j.missed_at is not None for j in observed)
    critical_observed = [j for j in observed if configs[j.task].critical]
    critical_missed = sum(j.missed_at is not None for j in critical_observed)
    summary = {
        "policy": policy, "horizon_ms": horizon,
        "nominal_utilization": sum(t.wcet / t.period for t in tasks),
        "released_jobs": len(jobs), "deadline_observed_jobs": len(observed),
        "deadline_censored_jobs": len(jobs) - len(observed),
        "deadline_misses": missed,
        "critical_deadline_observed_jobs": len(critical_observed),
        "critical_deadline_misses": critical_missed,
        "critical_deadline_miss_rate": critical_missed / len(critical_observed) if critical_observed else None,
        "noncritical_deadline_misses": missed - critical_missed,
        "deadline_miss_rate": missed / len(observed) if observed else None,
        "completed_jobs": len(completed),
        "dropped_jobs": sum(j.dropped_at is not None for j in jobs),
        "pending_jobs_at_end": len(active),
        "mean_response_ms_completed_only": (
            sum(j.completion - j.release for j in completed) / len(completed)
            if completed else None),
        "busy_time_ms": busy, "idle_time_ms": horizon - busy,
        "dispatches_including_idle": dispatches,
        "context_switches_busy_to_different_job": context_switches,
        "preemptions": preemptions,
        "boost_activations": boost_activations,
        "boost_execution_ms": boost_ticks,
        "jobs_exceeding_wcet_observed": sum(j.overrun_at is not None for j in jobs),
        "modeled_scheduler_overhead_ms": 0,
        "measured_decision_latency_us": None,
    }
    return {"schema_version": 2, "boost_config": asdict(boost_config),
            "tasks": [asdict(t) for t in tasks],
            "summary": summary, "jobs": [asdict(j) for j in jobs],
            "events": events, "timeline": timeline, "boost_intervals": boost_intervals}
