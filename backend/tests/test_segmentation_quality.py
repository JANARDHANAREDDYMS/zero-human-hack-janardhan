"""Evidence gaps, research intent and Sony scenario consistency regressions."""
import copy,json,tempfile,unittest
from pathlib import Path
from customer_generation.quality import research_plan,segmentation_quality
from customer_generation.validation import validate_evidence,ContractError
from customer_generation.sampling import generate_population
from customer_generation.pipeline import run_generation
from test_phase3 import config,FakeModel,FakeTransport,result,ALLOW,FIX
from customer_generation.tools.exa import ExaClient
from customer_generation.tools.live import LiveBackend

SONY=Path(__file__).resolve().parents[2]/'data/products/sony-speaker/research-v2'
def load(n):return json.loads((SONY/n).read_text())

class SegmentationQualityTests(unittest.TestCase):
    def test_research_uses_category_and_three_distinct_intents(self):
        p=research_plan({'category':'portable speaker','description':'MAGIC CLIENT FEATURE'})
        self.assertEqual([x['track'] for x in p],['offers','buyer_situations','counterevidence'])
        self.assertTrue(all('MAGIC' not in x['query'] for x in p))
        self.assertIn('repair',p[2]['query'])
    def test_search_intent_does_not_fabricate_evidence_coverage(self):
        backend=LiveBackend(config(),exa=ExaClient('x',FakeTransport([result()]*3)),model=FakeModel())
        response=backend.execute('research',{'brief':json.loads((FIX/'intake.json').read_text())},ALLOW)
        report=segmentation_quality(json.loads((FIX/'specification.json').read_text()),response.data)
        self.assertEqual(len(report['warnings']),3)
        self.assertTrue(all(s['status']=='provisional' for s in report['segments']))
        self.assertEqual([b['track'] for b in response.artifacts['research-retrieval.json']['batches']],['offers','buyer_situations','counterevidence'])
    def test_observed_report_requires_real_source_reference(self):
        e=load('evidence.json');validate_evidence(e)
        e['findings'][3]['source_ids']=[]
        with self.assertRaises(ContractError):validate_evidence(e)
    def test_offer_only_citations_do_not_establish_buyer_support(self):
        e=load('evidence.json');s=load('specification.json')
        s['segments'][0]['rationale']['finding_ids']=['offer-price']
        self.assertEqual(segmentation_quality(s,e)['segments'][0]['status'],'provisional')
    def test_duplicate_situations_reported(self):
        s=load('specification.json');s['segments'][1]['situation']=copy.deepcopy(s['segments'][0]['situation'])
        self.assertTrue(any('Duplicate' in x for x in segmentation_quality(s,load('evidence.json'))['segments'][1]['warnings']))
    def test_sony_reproducible_and_distinct_with_coherent_situations(self):
        s=load('specification.json');e=load('evidence.json');p=generate_population(s,e)
        self.assertEqual(p,generate_population(s,e));self.assertEqual(p,load('customers.json'))
        self.assertEqual(p['count'],50)
        self.assertEqual(len({c['customer_id'] for c in p['customers']}),50)
        for c in p['customers']:
            ctx=c['category_context']
            self.assertLessEqual(c['budget']['comfortable'],c['budget']['maximum'])
            if c['segment_id'].startswith('repair-'):
                self.assertLess(ctx['existing_battery_hours'],ctx['required_session_hours'])
            if c['segment_id']=='satisfied-retain':
                self.assertGreaterEqual(ctx['existing_battery_hours'],ctx['required_session_hours'])
        self.assertTrue(any(c['budget']['maximum']<119 for c in p['customers']))
        self.assertTrue(any(c['budget']['maximum']>=148 for c in p['customers']))
        self.assertTrue(any(c['category_context']['maximum_carry_weight_g']<550 for c in p['customers'] if c['segment_id']=='travel-upgrade'))
    def test_live_missing_situation_does_not_publish(self):
        class MissingSituation(FakeModel):
            def call(self,stage,*args):
                r=super().call(stage,*args)
                if stage in {'propose','correct'}:
                    for seg in r.data['segments']:seg.pop('situation',None)
                return r
        backend=LiveBackend(config(),exa=ExaClient('x',FakeTransport([result()]*3)),model=MissingSituation())
        with tempfile.TemporaryDirectory() as root:
            state=run_generation(json.loads((FIX/'intake.json').read_text()),backend,Path(root),'run')
            self.assertEqual(state.status,'incomplete')
            self.assertFalse((Path(root)/'run/customers.json').exists())
    def test_quality_artifact_saved_and_sent_to_reviewer(self):
        model=FakeModel();backend=LiveBackend(config(),exa=ExaClient('x',FakeTransport([result()]*3)),model=model)
        with tempfile.TemporaryDirectory() as root:
            state=run_generation(json.loads((FIX/'intake.json').read_text()),backend,Path(root),'run')
            self.assertEqual(state.status,'completed')
            self.assertTrue((Path(root)/'run/segmentation-quality-0.json').exists())
            review=[c for c in model.calls if c[0]=='review'][0]
            self.assertEqual(len(review[1]['segmentation_quality']['warnings']),3)
    def test_missing_evidence_cannot_be_reviewed_as_pass(self):
        class InflatedReview(FakeModel):
            def call(self,stage,*args):
                r=super().call(stage,*args)
                if stage=='review':
                    for check in r.data['checks']:
                        if check['category']=='evidence_support':check['status']='pass'
                return r
        backend=LiveBackend(config(),exa=ExaClient('x',FakeTransport([result()]*3)),model=InflatedReview())
        with tempfile.TemporaryDirectory() as root:
            state=run_generation(json.loads((FIX/'intake.json').read_text()),backend,Path(root),'run')
            self.assertEqual(state.status,'incomplete');self.assertIn('review warning',state.error['message'])

if __name__=='__main__':unittest.main()
