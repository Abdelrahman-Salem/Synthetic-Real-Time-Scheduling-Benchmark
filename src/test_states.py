import copy
from dataclasses import asdict, replace
import json
from pathlib import Path
import unittest
from simulator import Task, BoostConfig, simulate
from state_engine import Engine, POLICIES, observable_features, compare_policies
from workloads import build_suite, load_case, fingerprint


class StateTests(unittest.TestCase):
    def test_engine_matches_v3_for_all_pilot_train_validation_workloads(self):
        for case in build_suite():
            if case['split']=='test':
                continue
            tasks,horizon=load_case(case)
            for policy in POLICIES:
                old=simulate(tasks,horizon,policy)
                engine=Engine(tasks,horizon,policy);engine.advance(horizon)
                self.assertEqual([asdict(j) for j in engine.jobs],old['jobs'],case['task_set_id'])
                self.assertEqual(engine.timeline,old['timeline'])
                self.assertEqual(engine.boost_intervals,old['boost_intervals'])
                self.assertEqual(engine.counts['switches'],old['summary']['context_switches_busy_to_different_job'])
                self.assertEqual(engine.counts['boost_activations'],old['summary']['boost_activations'])

    def test_serialized_checkpoint_preserves_branch_outcomes(self):
        tasks=[Task('A',5,4,5),Task('C',20,4,12,critical=True)]
        engine=Engine(tasks,40,'RMS+Boost',BoostConfig(slack_threshold=8,window=5,window_budget=1,per_job_budget=3))
        engine.advance(6);checkpoint=engine.checkpoint()
        restored=Engine.restore(tasks,json.loads(json.dumps(checkpoint)))
        self.assertEqual(observable_features(engine),observable_features(restored))
        self.assertEqual(compare_policies(engine,20),compare_policies(restored,20))

    def test_fork_does_not_mutate_parent(self):
        e=Engine([Task('A',5,2,5),Task('B',10,2,3,critical=True)],30,'RMS')
        e.advance(3);before=fingerprint(e.checkpoint())
        compare_policies(e,10)
        self.assertEqual(fingerprint(e.checkpoint()),before)

    def test_resume_equivalent_to_uninterrupted(self):
        tasks=[Task('A',5,3,4),Task('B',8,4,6,critical=True)]
        for policy in POLICIES:
            full=Engine(tasks,40,policy);full.advance(40)
            chunk=Engine(tasks,40,policy)
            for t in (1,5,8,10,17,23,40):
                chunk.advance(t)
                if t<40:chunk.checkpoint()
            self.assertEqual([asdict(j) for j in full.jobs],[asdict(j) for j in chunk.jobs])
            self.assertEqual(full.timeline,chunk.timeline)
            self.assertEqual(full.counts,chunk.counts)

    def test_no_future_demand_in_features(self):
        a=[Task('A',10,5,10,demands=(4,4,4),critical=True)]
        b=[Task('A',10,5,10,demands=(5,1,2),critical=True)]
        engines=[Engine(t,30,'EDF') for t in (a,b)]
        for e in engines:e.advance(2);e.checkpoint()
        self.assertNotEqual(engines[0].active['A'].remaining,engines[1].active['A'].remaining)
        self.assertEqual(observable_features(engines[0]),observable_features(engines[1]))

    def test_completed_history_is_observed(self):
        e=Engine([Task('A',5,3,5,demands=(1,3,2))],15)
        e.advance(9);e.checkpoint()
        f=observable_features(e)
        self.assertEqual(f['execution_history_task_count'],1)
        self.assertEqual(f['completed_execution_range_pct'],100)

    def test_full_tie_keeps_current_without_unique_label(self):
        e=Engine([Task('A',5,1,5)],20,'RMS+Boost')
        r=compare_policies(e,10)
        self.assertEqual(r['optimal_policies'],list(POLICIES))
        self.assertIsNone(r['unique_best_policy'])
        self.assertEqual(r['recommended_policy'],'RMS+Boost')

    def test_tie_excludes_current_remains_unresolved(self):
        e=Engine([Task('A',5,2,5),Task('B',10,2,3,critical=True)],10,'RMS')
        r=compare_policies(e,10)
        self.assertNotIn('RMS',r['optimal_policies'])
        self.assertGreater(len(r['optimal_policies']),1)
        self.assertIsNone(r['recommended_policy'])
        self.assertEqual(r['recommendation_reason'],'unresolved_tie')

    def test_critical_priority_and_tradeoff_preserved(self):
        e=Engine([Task('A',10,2,2),Task('B',10,2,3,critical=True)],10,'EDF')
        r=compare_policies(e,10)
        self.assertEqual(r['optimal_policies'],['RMS+Boost','EDF+Boost'])
        self.assertEqual(r['outcomes']['EDF']['total_misses'],r['outcomes']['EDF+Boost']['total_misses'])
        self.assertEqual(r['outcomes']['EDF+Boost']['noncritical_misses'],1)

    def test_existing_miss_excluded_from_future_score(self):
        e=Engine([Task('A',10,8,2,critical=True)],10,'RMS')
        e.advance(3)
        r=compare_policies(e,7)
        self.assertTrue(all(o['total_misses']==0 for o in r['outcomes'].values()))

    def test_miss_at_endpoint_counted(self):
        e=Engine([Task('A',10,8,4,critical=True)],10,'RMS')
        r=compare_policies(e,4)
        self.assertTrue(all(o['total_misses']==1 for o in r['outcomes'].values()))

    def test_boost_budget_survives_mode_change(self):
        e=Engine([Task('A',10,5,5,critical=True)],20,'EDF+Boost')
        e.advance(1);state=e.checkpoint()
        for policy in POLICIES:
            branch=Engine.restore(e.tasks,state);branch.policy=policy
            self.assertEqual(branch.window_used,1)
            self.assertEqual(branch.active['A'].boosted_execution,1)
            branch.advance(3)
            if policy.endswith('+Boost'):
                self.assertEqual(branch.window_used,2)

    def test_saved_parent_restores_execution_and_future_deadline_denominator(self):
        tasks=[Task('A',10,1,9),Task('B',20,6,10,critical=True)]
        e=Engine(tasks,40,'EDF');e.advance(3);state=e.checkpoint()
        restored=Engine.restore(tasks,state)
        self.assertEqual(compare_policies(e,20),compare_policies(restored,20))
        self.assertEqual(len({o['deadline_observed_jobs'] for o in compare_policies(e,20)['outcomes'].values()}),1)

    def test_invalid_horizon(self):
        e=Engine([Task('A',10,1,10)],20)
        with self.assertRaises(ValueError):compare_policies(e,21)
        with self.assertRaises(ValueError):compare_policies(e,0)


if __name__=='__main__':unittest.main(verbosity=2)
