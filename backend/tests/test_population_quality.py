"""No model/network calls: stratification, failure gates and unchanged input rules."""
import copy,json,random,unittest
from pathlib import Path
from customer_generation.sampling import generate_population,stratum_values,fingerprint
from customer_generation.population_quality import population_quality,require_population_quality
from customer_generation.validation import ContractError
from customer_generation.compact import construct_specification
ROOT=Path(__file__).resolve().parents[2]
class PopulationQualityTests(unittest.TestCase):
 def setUp(self):
  load=lambda p:json.loads(p.read_text());r=ROOT/'data/products/sony-speaker/research-v2'
  self.brief=load(r/'brief.json');self.evidence=load(r/'evidence.json')
  proposal=load(ROOT/'backend/tests/fixtures/sony-compact/proposal.json')
  self.spec=construct_specification(proposal,self.brief,self.evidence,50,42)
 def test_reproducible_strata_25_50_500(self):
  for count in [25,50,500]:
   spec=copy.deepcopy(self.spec);spec['target_count']=count
   k=len(spec['segments'])
   for i,s in enumerate(spec['segments']):s['count']=count//k+(i<count%k)
   original=copy.deepcopy(spec)
   pop=generate_population(spec,self.evidence,stratified=True)
   self.assertEqual(pop,generate_population(spec,self.evidence,stratified=True))
   self.assertEqual(spec,original)
   report=population_quality(spec,pop,self.brief)
   self.assertEqual(report['blocking_issues'],[],report['blocking_issues'])
   self.assertEqual(sum(s['count'] for s in report['segments']),count)
   self.assertGreater(report['can_afford'],0);self.assertLess(report['can_afford'],count)
 def test_clones_and_missing_strata_block(self):
  pop=generate_population(self.spec,self.evidence,stratified=True)
  pop['customers'][1]=copy.deepcopy(pop['customers'][0])
  report=population_quality(self.spec,pop,self.brief)
  self.assertTrue(report['blocking_issues'])
  with self.assertRaises(ContractError):require_population_quality(report)
 def test_all_below_price_is_not_silently_fixed(self):
  for s in self.spec['segments']:s['fields']['budget.maximum']['rule'].update(minimum=0,maximum=self.brief['price']['amount']*.9)
  original=copy.deepcopy(self.spec)
  pop=generate_population(self.spec,self.evidence,stratified=True)
  report=population_quality(self.spec,pop,self.brief)
  self.assertEqual(report['can_afford'],0)
  self.assertTrue(any('one side' in error for error in report['blocking_issues']))
  self.assertEqual(self.spec,original)
 def test_weighted_marginals_and_small_segment(self):
  rule={'kind':'choice','values':['free','paid','peer'],'weights':[.6,.3,.1]}
  for n in [1,5,25,500]:
   values=stratum_values(rule,n,random.Random(42))
   for v,w in zip(rule['values'],rule['weights']):self.assertLessEqual(abs(values.count(v)-n*w),1)
