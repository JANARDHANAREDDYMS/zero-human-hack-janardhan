"""Complete offline worker responses; saved manual Sony fixtures are not live model results."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from customer_generation.pipeline import run_generation
from customer_generation.sampling import generate_population
from customer_generation.state import StageResponse
from customer_generation.validation import validate_specification, ContractError

ROOT=Path(__file__).resolve().parents[2]
EXPORT=ROOT/'backend/workers/lovable-export-2026-10-24/customer-generation-source/src/server/customer-generation'
WORKING=ROOT/'backend/workers/lovable-current'
SONY=ROOT/'data/products/sony-speaker/research-v2'

def load(path):return json.loads(path.read_text())

class CompleteWorkerResponses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Copy exact exported runtime beside existing dependencies; no installation,
        # secrets, network access or edits to the imported snapshot.
        cls.temp=tempfile.TemporaryDirectory(prefix='offline-runtime-',dir=ROOT/'backend/workers/lovable')
        for name in ['worker.mjs','wire-schema.mjs','auth.mjs','validators.generated.mjs']:
            shutil.copyfile(WORKING/name,Path(cls.temp.name)/name)
        cls.brief=load(SONY/'brief.json')
        # Optional nullable fields have no absence sentinel distinct from null.
        # Use explicit nulls in this fixture; omission normalization is tested below.
        cls.brief.update(audience=None,market=None)
        cls.evidence=load(SONY/'evidence.json')
        cls.spec=load(SONY/'specification.json')
        cls.review=load(ROOT/'data/runs/phase4-keyboard-offline/review-0.json')
        cls.review['summary']='Synthetic full-response Sony control-flow fixture; no model or human quality judgment.'

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def bridge(self,stage,data,mutation=None):
        result=subprocess.run(['node',str(ROOT/'backend/tests/worker_roundtrip.mjs')],cwd=ROOT,
            input=json.dumps({'runtime':self.temp.name,'policy':str(WORKING/'policy.json'),'stage':stage,'data':data,'mutation':mutation}),
            text=True,capture_output=True,check=True,timeout=30)
        return json.loads(result.stdout)

    def test_complete_responses_all_five_stages(self):
        fixtures={'intake_extract':self.brief,'research_extract':self.evidence,'propose':self.spec,'correct':self.spec,'review':self.review}
        for stage,data in fixtures.items():
            with self.subTest(stage=stage):
                r=self.bridge(stage,data)
                self.assertTrue(r['wire_valid'])
                self.assertEqual(r['status'],200)
                self.assertEqual(r['response']['data'],data)
                self.assertEqual(r['decoded'],data)
                self.assertEqual(r['mock_gateway_calls'],1)

    def test_complete_saved_live_research_response(self):
        evidence=load(ROOT/'data/runs/sony-live-v3-sony-speaker/evidence.json')
        r=self.bridge('research_extract',evidence)
        self.assertTrue(r['wire_valid'])
        self.assertEqual(r['status'],200)
        self.assertEqual(r['response']['data'],evidence)

    def test_sony_full_pipeline_through_real_worker_with_mock_gateway(self):
        test=self
        class Backend:
            mode='live';name='offline-worker-integration-test'
            def execute(self,stage,payload,allowances):
                data={'research':test.evidence,'propose':test.spec,'correct':test.spec,'review':test.review}[stage]
                r=test.bridge('research_extract' if stage=='research' else stage,data)
                if r['status']!=200:raise AssertionError({'status':r['status'],'response':r['response'],'errors':r['canonical_errors']})
                return StageResponse(r['response']['data'],1,1,0,metadata={'test_only':True,'mocked_gateway':True})
        with tempfile.TemporaryDirectory() as directory:
            state=run_generation(self.brief,Backend(),directory,'sony-complete-offline',target_count=50,seed=42)
            self.assertEqual(state.status,'completed',state.error)
            population=load(Path(directory)/'sony-complete-offline/customers.json')
            self.assertEqual(len(population['customers']),50)
            self.assertEqual(population,generate_population(self.spec,self.evidence,stratified=True))

    def test_duplicate_attributes_rejected_by_complete_worker(self):
        r=self.bridge('propose',self.spec,'duplicate_attribute')
        # Per-entry schema acceptance does not guarantee map-key uniqueness.
        self.assertTrue(r['wire_valid'])
        self.assertEqual(r['status'],502)
        self.assertIn('duplicate map key',r['decode_error'])

    def test_original_export_reproduces_optional_enum_branch_bug(self):
        runtime=Path(self.temp.name)
        shutil.copyfile(EXPORT/'wire-schema.mjs',runtime/'wire-schema.mjs')
        try:
            r=self.bridge('propose',self.spec)
            self.assertTrue(r['wire_valid'])
            self.assertEqual(r['status'],502)
            self.assertTrue(any('/round' in e['instancePath'] for e in r['canonical_errors']))
        finally:shutil.copyfile(WORKING/'wire-schema.mjs',runtime/'wire-schema.mjs')

    def test_optional_nullable_intake_fields_normalize_to_null(self):
        brief=load(SONY/'brief.json')
        r=self.bridge('intake_extract',brief)
        self.assertEqual(r['status'],200)
        self.assertEqual(r['response']['data'],self.brief)

    def test_malformed_tags_and_branches_rejected(self):
        for mutation in ['invalid_tag','wrong_rule_branch','outer_json']:
            with self.subTest(mutation=mutation):
                self.assertEqual(self.bridge('propose',self.spec,mutation)['status'],502)

    def test_missing_source_reference_rejected_after_worker_schema_acceptance(self):
        bad=copy.deepcopy(self.spec)
        bad['market_provenance']['source_ids']=['nonexistent-source']
        r=self.bridge('propose',bad)
        self.assertEqual(r['status'],200)
        with self.assertRaises(ContractError):validate_specification(r['response']['data'],self.evidence)

    def test_choice_weight_mismatch_rejected_after_schema_acceptance(self):
        bad=copy.deepcopy(self.spec)
        choices=[f['rule'] for s in bad['segments'] for f in s['fields'].values() if f['rule']['kind']=='choice' and len(f['rule']['values'])>1]
        self.assertTrue(choices)
        choices[0]['weights']=[1]
        r=self.bridge('correct',bad)
        self.assertEqual(r['status'],200)
        with self.assertRaises(ContractError):validate_specification(r['response']['data'],self.evidence)

if __name__=='__main__':unittest.main()
