import unittest
from analyze_validation import bootstrap_mean_ci,holm

class StatisticsTests(unittest.TestCase):
    def test_bootstrap_repeatable(self):
        self.assertEqual(bootstrap_mean_ci([1,2,3],1000),bootstrap_mean_ci([1,2,3],1000))
    def test_holm_monotone_in_sorted_order(self):
        adjusted=holm([.01,.04,.03]);self.assertEqual(adjusted,[.03,.06,.06])

if __name__=='__main__':unittest.main()
