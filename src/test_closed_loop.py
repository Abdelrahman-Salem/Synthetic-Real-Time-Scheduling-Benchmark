import unittest
from simulator import Task
from state_engine import Engine
from evaluate_closed_loop import metrics,run_static


class ClosedLoopTests(unittest.TestCase):
    def test_static_is_repeatable(self):
        tasks=[Task('A',10,2,10),Task('B',15,3,15)]
        self.assertEqual(run_static(tasks,100,'EDF'),run_static(tasks,100,'EDF'))

    def test_metrics_count_critical_miss(self):
        tasks=[Task('A',10,10,5,critical=True)]
        e=Engine(tasks,20,'RMS');e.advance(20)
        self.assertGreater(metrics(e)['critical_misses'],0)


if __name__=='__main__':unittest.main()
