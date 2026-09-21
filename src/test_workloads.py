import collections,json,unittest
from workloads import build_suite,load_case
from simulator import simulate

class ExpandedWorkloadTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.cases=build_suite()
 def test_counts_and_unique_splits(self):
  self.assertEqual(len(self.cases),640)
  self.assertEqual({s:sum(c['split']==s for c in self.cases) for s in ('train','validation','test')},{'train':320,'validation':160,'test':160})
  for k in ('task_set_id','seed','workload_sha256'):self.assertEqual(len({c[k] for c in self.cases}),640)
 def test_reproducibility(self):
  self.assertEqual(self.cases,build_suite());self.assertNotEqual(self.cases[0]['workload_sha256'],build_suite(20260921)[0]['workload_sha256'])
 def test_grid_coverage(self):
  for split in ('train','validation','test'):
   rows=[c for c in self.cases if c['split']==split]
   self.assertEqual({c['release_profile'] for c in rows},{'synchronous','fixed_offsets','jitter','bursts'})
   self.assertEqual({c['requested_utilization'] for c in rows},{.4,.6,.8,.95,1.1});self.assertEqual({len(c['tasks']) for c in rows},{3,5,8,10})
 def test_valid_explicit_releases_and_demands(self):
  for c in self.cases:
   self.assertLessEqual(abs(c['nominal_utilization']-c['requested_utilization']),.015000001)
   for t in c['tasks']:
    self.assertTrue(1<=t['wcet']<=t['deadline']<=t['period']);self.assertEqual(tuple(t['releases']),tuple(sorted(set(t['releases']))))
    self.assertEqual(len(t['releases']),len(t['demands']));self.assertTrue(all(0<=x<c['horizon_ms'] for x in t['releases']))
    self.assertTrue(all(1<=d<=t['wcet'] for d in t['demands']))
 def test_profiles_have_actual_effect(self):
  jitter=[c for c in self.cases if c['release_profile']=='jitter']
  self.assertTrue(any(any(any(r%t['period'] for r in t['releases']) for t in c['tasks']) for c in jitter))
  bursts=[c for c in self.cases if c['release_profile']=='bursts'];self.assertTrue(all(c['burst_arrivals'] for c in bursts))
  self.assertTrue(any(max(collections.Counter(r for t in c['tasks'] for r in t['releases']).values())>1 for c in bursts))
 def test_hash_tampering_and_roundtrip(self):
  c=json.loads(json.dumps(self.cases[0]));tasks,h=load_case(c);self.assertEqual(tuple(c['tasks'][0]['releases']),tasks[0].releases)
  c['tasks'][0]['releases'][0]+=1
  with self.assertRaises(ValueError):load_case(c)
 def test_same_exogenous_inputs_all_policies(self):
  selected=(self.cases[0],next(x for x in self.cases if x['release_profile']=='jitter'),next(x for x in self.cases if x['release_profile']=='bursts'))
  for c in selected:
   tasks,h=load_case(c);inputs=[]
   for p in ('RMS','EDF','RMS+Boost','EDF+Boost'):
    r=simulate(tasks,h,p);inputs.append([(j['task'],j['index'],j['release'],j['demand'],j['absolute_deadline']) for j in r['jobs']])
   self.assertTrue(all(x==inputs[0] for x in inputs))

if __name__=='__main__':unittest.main(verbosity=2)
