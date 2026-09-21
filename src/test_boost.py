import unittest
from simulator import Task, BoostConfig, simulate


class BoostTests(unittest.TestCase):
    def test_critical_job_saved_under_rms(self):
        ts = [Task("A", 5, 2, 5), Task("B", 10, 2, 3, critical=True)]
        plain = simulate(ts, 10, "RMS")["summary"]
        boosted = simulate(ts, 10, "RMS+Boost")["summary"]
        self.assertEqual(plain["critical_deadline_misses"], 1)
        self.assertEqual(boosted["critical_deadline_misses"], 0)
        self.assertEqual(boosted["deadline_misses"], 0)
        self.assertEqual(boosted["boost_execution_ms"], 2)

    def test_explicit_tradeoff_not_universal_improvement(self):
        ts = [Task("A", 10, 2, 2), Task("B", 10, 2, 3, critical=True)]
        for base in ("RMS", "EDF"):
            p = simulate(ts, 10, base)["summary"]
            b = simulate(ts, 10, base+"+Boost")["summary"]
            self.assertEqual((p["critical_deadline_misses"], p["noncritical_deadline_misses"]), (1, 0))
            self.assertEqual((b["critical_deadline_misses"], b["noncritical_deadline_misses"]), (0, 1))

    def test_disabled_for_noncritical_tasks(self):
        ts = [Task("A", 5, 3, 3), Task("B", 8, 4, 8)]
        for base in ("RMS", "EDF"):
            p, b = [simulate(ts, 20, policy) for policy in (base, base+"+Boost")]
            self.assertEqual(p["timeline"], b["timeline"])
            self.assertEqual(b["summary"]["boost_execution_ms"], 0)

    def test_urgent_ties_by_absolute_deadline_then_name(self):
        ts = [Task("B", 10, 2, 3, critical=True), Task("A", 10, 2, 3, critical=True)]
        r = simulate(ts, 3, "EDF+Boost")
        self.assertEqual(r["timeline"][0]["job"], ["A", 0])
        self.assertEqual(r, simulate(ts[::-1], 3, "EDF+Boost"))

    def test_global_window_and_per_job_limits(self):
        ts = [Task("A", 5, 4, 5), Task("C", 20, 4, 12, critical=True)]
        cfg = BoostConfig(slack_threshold=8, per_job_budget=3, window=5, window_budget=1)
        r = simulate(ts, 40, "RMS+Boost", cfg)
        windows = {}
        for interval in r["boost_intervals"]:
            for t in range(interval["start_ms"], interval["end_ms"]):
                w = t // cfg.window
                windows[w] = windows.get(w, 0) + 1
        self.assertTrue(windows)
        self.assertTrue(all(n <= 1 for n in windows.values()))
        self.assertTrue(all(j["boosted_execution"] <= 3 for j in r["jobs"]))
        self.assertEqual(sum(windows.values()), r["summary"]["boost_execution_ms"])
        starts = [e for e in r["events"] if e["event"] == "boost_start" and e["task"] == "C" and e["job"] == 0]
        self.assertGreaterEqual(len(starts), 2)  # reactivation permitted within budgets

    def test_per_job_budget_does_not_reset_with_window(self):
        cfg = BoostConfig(slack_threshold=8, per_job_budget=1, window=5, window_budget=1)
        r = simulate([Task("A", 5, 4, 5), Task("C", 20, 4, 12, critical=True)], 20, "RMS+Boost", cfg)
        c = next(j for j in r["jobs"] if j["task"] == "C")
        self.assertEqual(c["boosted_execution"], 1)

    def test_no_boost_when_already_infeasible_or_past_deadline(self):
        r = simulate([Task("A", 10, 5, 2, critical=True)], 10, "EDF+Boost")
        self.assertEqual(r["summary"]["boost_execution_ms"], 0)

    def test_observable_wcet_budget_not_future_demand(self):
        # If hidden true demand (1) were used, slack=4 would not trigger.
        r = simulate([Task("A", 10, 5, 5, demands=(1,), critical=True)], 6, "EDF+Boost")
        self.assertEqual(r["summary"]["boost_execution_ms"], 1)
        self.assertEqual(r["events"][-1]["event"], "boost_end_complete")

    def test_boost_stops_at_wcet_exhaustion(self):
        cfg = BoostConfig(per_job_budget=4, window_budget=4)
        r = simulate([Task("A", 10, 2, 3, demands=(5,), critical=True)], 6, "EDF+Boost", cfg)
        self.assertEqual(r["summary"]["boost_execution_ms"], 2)
        self.assertEqual(r["summary"]["jobs_exceeding_wcet_observed"], 1)

    def test_end_at_horizon(self):
        r = simulate([Task("A", 10, 5, 5, critical=True)], 1, "RMS+Boost")
        self.assertEqual(r["events"][-1]["event"], "boost_end_horizon")

    def test_invalid_boost_configuration(self):
        for args in ({"slack_threshold": -1}, {"per_job_budget": 0}, {"window_budget": 10}, {"window": 1}):
            with self.assertRaises(ValueError):
                BoostConfig(**args)


if __name__ == "__main__":
    unittest.main(verbosity=2)
