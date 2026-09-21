import unittest
from simulator import Task, simulate


class SemanticsTests(unittest.TestCase):
    def test_early_completion(self):
        r = simulate([Task("A", 5, 2, 5)], 10)
        self.assertEqual([j["completion"] for j in r["jobs"]], [2, 7])
        self.assertEqual(r["summary"]["deadline_misses"], 0)
        self.assertEqual(r["summary"]["busy_time_ms"], 4)

    def test_completion_exactly_at_deadline_and_release(self):
        r = simulate([Task("A", 4, 4, 4)], 8)
        self.assertEqual([j["completion"] for j in r["jobs"]], [4, 8])
        self.assertEqual(r["summary"]["deadline_misses"], 0)
        self.assertEqual(r["summary"]["dropped_jobs"], 0)

    def test_miss_once_and_tardy_completion(self):
        r = simulate([Task("A", 10, 7, 2)], 10)
        self.assertEqual(r["summary"]["deadline_misses"], 1)
        self.assertEqual(r["jobs"][0]["missed_at"], 2)
        self.assertEqual(r["jobs"][0]["completion"], 7)
        self.assertEqual(sum(e["event"] == "deadline_miss" for e in r["events"]), 1)

    def test_drop_at_next_release_no_duplicate_miss(self):
        r = simulate([Task("A", 4, 2, 2, demands=(6, 6, 6))], 12)
        s = r["summary"]
        self.assertEqual((s["released_jobs"], s["deadline_misses"], s["dropped_jobs"]), (3, 3, 2))
        self.assertEqual(s["pending_jobs_at_end"], 1)
        self.assertEqual([j["missed_at"] for j in r["jobs"]], [2, 6, 10])
        self.assertEqual(s["jobs_exceeding_wcet_observed"], 3)

    def test_miss_before_drop_on_same_boundary(self):
        r = simulate([Task("A", 4, 6, 4)], 8)
        at_four = [e["event"] for e in r["events"] if e["time_ms"] == 4]
        self.assertEqual(at_four, ["deadline_miss", "drop_at_next_release", "release", "dispatch"])

    def test_preemption_resume_preserves_remaining(self):
        r = simulate([Task("A", 5, 1, 5, offset=2), Task("B", 10, 5, 10)], 10, "RMS")
        b = next(j for j in r["jobs"] if j["task"] == "B")
        self.assertEqual((b["completion"], b["executed"]), (6, 5))
        self.assertEqual(r["summary"]["preemptions"], 1)
        self.assertEqual(r["summary"]["context_switches_busy_to_different_job"], 2)

    def test_edf_uses_absolute_deadline(self):
        tasks = [Task("A", 5, 2, 5), Task("B", 8, 3, 3)]
        rms, edf = [simulate(tasks, 8, p) for p in ("RMS", "EDF")]
        self.assertEqual(rms["timeline"][0]["job"], ["A", 0])
        self.assertEqual(edf["timeline"][0]["job"], ["B", 0])
        self.assertEqual(rms["summary"]["deadline_misses"], 1)
        self.assertEqual(edf["summary"]["deadline_misses"], 0)

    def test_edf_does_not_use_relative_deadline_alone(self):
        r = simulate([Task("A", 10, 7, 7), Task("B", 20, 1, 3, offset=5)], 10)
        self.assertEqual(r["timeline"][0], {"start_ms": 0, "end_ms": 7, "job": ["A", 0]})

    def test_censored_deadlines_not_in_denominator(self):
        r = simulate([Task("A", 10, 8, 10)], 5)
        self.assertIsNone(r["summary"]["deadline_miss_rate"])
        self.assertEqual(r["summary"]["deadline_censored_jobs"], 1)
        self.assertEqual(r["summary"]["pending_jobs_at_end"], 1)

    def test_deadline_at_horizon_observed_without_new_release(self):
        r = simulate([Task("A", 4, 6, 4)], 4)
        self.assertEqual(r["summary"]["deadline_misses"], 1)
        self.assertEqual(r["summary"]["released_jobs"], 1)
        self.assertEqual(r["summary"]["dropped_jobs"], 0)

    def test_idle_not_context_switch(self):
        s = simulate([Task("A", 5, 1, 5)], 10)["summary"]
        self.assertEqual(s["dispatches_including_idle"], 2)
        self.assertEqual(s["context_switches_busy_to_different_job"], 0)

    def test_ties_independent_of_input_order(self):
        tasks = [Task("B", 5, 1, 5), Task("A", 5, 1, 5)]
        for p in ("RMS", "EDF"):
            r = simulate(tasks, 10, p)
            self.assertEqual(r, simulate(list(reversed(tasks)), 10, p))
            self.assertEqual(r["timeline"][0]["job"], ["A", 0])

    def test_invariants_and_repeatability(self):
        tasks = [Task("A", 4, 3, 2), Task("B", 7, 4, 7)]
        for p in ("RMS", "EDF"):
            r = simulate(tasks, 100, p)
            self.assertEqual(r, simulate(tasks, 100, p))
            self.assertEqual(sum(j["executed"] for j in r["jobs"]), r["summary"]["busy_time_ms"])
            self.assertEqual(sum(x["end_ms"]-x["start_ms"] for x in r["timeline"]), 100)
            for j in r["jobs"]:
                self.assertEqual(j["executed"] + j["remaining"], j["demand"])
                self.assertFalse(j["completion"] is not None and j["dropped_at"] is not None)

    def test_invalid_inputs(self):
        for args in [("A", 0, 1, 1), ("A", 5, 1, 6), ("A", 5, 0, 5), ("A", 5.0, 1, 5)]:
            with self.assertRaises(ValueError):
                Task(*args)
        with self.assertRaises(ValueError):
            simulate([Task("A", 4, 1, 4, demands=(1,))], 8)
        with self.assertRaises(ValueError):
            simulate([Task("A", 4, 1, 4)]*2, 8)
        with self.assertRaises(ValueError):
            simulate([Task("A", 4, 1, 4)], 8, "AI")


if __name__ == "__main__":
    unittest.main(verbosity=2)
