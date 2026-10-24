"""Harness control-flow tests with explicit offline responses, not model evaluations."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from customer_generation.pipeline import run_generation
from customer_generation.state import RunLimits, StageResponse
from customer_generation.storage import RunStore
from customer_generation.validation import ContractError
from customer_generation.tools.fixtures import FixtureBackend
from customer_generation.instructions import fixture_checks

FIX=Path(__file__).parent/'fixtures/keyboard'

def review(decision):
    return {'decision':decision,'summary':'Scripted review fixture.','checks':fixture_checks(),
        'findings':[] if decision=='accept' else [{'code':'coverage','severity':'blocking','message':'Reconsider coverage.','source_ids':[]}]}

class ScriptedBackend(FixtureBackend):
    def __init__(self, responses=None):
        super().__init__(FIX)
        self.responses=responses or {};self.calls=[]
    def execute(self,stage,payload,allowances):
        self.calls.append(stage)
        queue=self.responses.get(stage,[])
        if queue:
            result=queue.pop(0)
            if isinstance(result,Exception):raise result
            if callable(result):return result(payload,allowances)
            return StageResponse(copy.deepcopy(result),0,0,0)
        return super().execute(stage,payload,allowances)

class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.root=Path(self.directory.name)
        self.intake=json.loads((FIX/'intake.json').read_text())
    def tearDown(self):self.directory.cleanup()
    def run_harness(self,backend=None,**kwargs):
        return run_generation(self.intake,backend or ScriptedBackend(),self.root,'test',**kwargs)
    def artifact(self,name):return json.loads((self.root/'test'/name).read_text())
    def test_success_and_persisted_usage_inputs_and_review(self):
        state=self.run_harness()
        self.assertEqual(state.status,'completed');self.assertEqual(state.mode,'offline_fixture')
        self.assertEqual(state.stage_calls,3);self.assertEqual(self.artifact('customers.json')['count'],50)
        self.assertEqual(self.artifact('pilot-0.json')['count'],4)
        self.assertEqual(self.artifact('state.json')['status'],'completed')
        self.assertEqual(self.artifact('input.json'),self.intake)
        self.assertTrue((self.root/'test'/'call-01-response.json').exists())
    def test_one_review_correction_and_rereview(self):
        backend=ScriptedBackend({'review':[review('revise'),review('accept')]})
        state=self.run_harness(backend)
        self.assertEqual(state.status,'completed');self.assertEqual(state.corrections,1)
        self.assertEqual(backend.calls,['research','propose','review','correct','review'])
        self.assertTrue((self.root/'test'/'pilot-1.json').exists())
    def test_second_revision_stops_without_final_population(self):
        state=self.run_harness(ScriptedBackend({'review':[review('revise'),review('revise')]}))
        self.assertEqual(state.status,'incomplete');self.assertEqual(state.corrections,1)
        self.assertFalse((self.root/'test'/'customers.json').exists())
        self.assertTrue((self.root/'test'/'issues-1.json').exists())
    def test_invalid_proposal_can_be_corrected(self):
        bad=copy.deepcopy(ScriptedBackend().specification);bad['segments'][0]['count']=24
        state=self.run_harness(ScriptedBackend({'propose':[bad]}))
        self.assertEqual(state.status,'completed');self.assertEqual(state.corrections,1)
        self.assertEqual(self.artifact('issues-0.json')['type'],'validation')
    def test_correction_cannot_change_product_count_or_seed(self):
        for key,value in [('product_id','other'),('target_count',1),('seed',999)]:
            with tempfile.TemporaryDirectory() as root:
                spec=copy.deepcopy(ScriptedBackend().specification);spec[key]=value
                state=run_generation(self.intake,ScriptedBackend({'review':[review('revise')],'correct':[spec]}),Path(root),'run')
                self.assertEqual(state.status,'incomplete');self.assertFalse((Path(root)/'run/customers.json').exists())
    def test_research_failure_never_proposes_or_publishes(self):
        backend=ScriptedBackend({'research':[RuntimeError('Research unavailable')]})
        state=self.run_harness(backend)
        self.assertEqual(state.status,'failed');self.assertEqual(backend.calls,['research'])
        self.assertIsNotNone(state.finished_at);self.assertFalse((self.root/'test'/'customers.json').exists())
    def test_call_limit_is_checked_before_next_call(self):
        backend=ScriptedBackend();state=self.run_harness(backend,limits=RunLimits(max_stage_calls=1))
        self.assertEqual(state.status,'limit_exceeded');self.assertEqual(backend.calls,['research'])
    def test_actual_over_budget_usage_is_saved(self):
        base=ScriptedBackend()
        def costly(payload,allowances):return StageResponse(base.evidence,1,1,2)
        state=self.run_harness(ScriptedBackend({'research':[costly]}),limits=RunLimits(max_cost_usd=1))
        self.assertEqual(state.status,'limit_exceeded');self.assertEqual(state.cost_usd,2)
        self.assertEqual(self.artifact('call-01-response.json')['usage']['cost_usd'],2)
    def test_token_limit_stops_and_saves_usage(self):
        base=ScriptedBackend()
        state=self.run_harness(ScriptedBackend({'research':[lambda p,a:StageResponse(base.evidence,100,100,0)]}),limits=RunLimits(max_tokens_per_call=50))
        self.assertEqual(state.status,'limit_exceeded');self.assertEqual(state.total_tokens,200)
    def test_zero_corrections_supported(self):
        state=self.run_harness(ScriptedBackend({'review':[review('revise')]}),limits=RunLimits(max_corrections=0))
        self.assertEqual(state.status,'incomplete');self.assertEqual(state.corrections,0)
    def test_blocking_accept_and_unknown_sources_rejected(self):
        for r in [review('reject'),{'decision':'accept','summary':'Bad acceptance','findings':[{'code':'x','severity':'blocking','message':'Unresolved','source_ids':[]}]}, {'decision':'accept','summary':'Unknown source','findings':[{'code':'x','severity':'warning','message':'Unsupported','source_ids':['made-up']}]}]:
            with tempfile.TemporaryDirectory() as root:
                state=run_generation(self.intake,ScriptedBackend({'review':[r]}),Path(root),'run')
                self.assertEqual(state.status,'incomplete');self.assertFalse((Path(root)/'run/customers.json').exists())
    def test_provider_cannot_mutate_saved_input_or_evidence(self):
        def mutate(payload,allowances):
            payload['brief']['description']='changed';return StageResponse(ScriptedBackend().specification,0,0,0)
        state=self.run_harness(ScriptedBackend({'propose':[mutate]}))
        self.assertEqual(state.status,'completed');self.assertEqual(self.artifact('brief.json'),self.intake)
        self.assertEqual(self.artifact('evidence.json'),ScriptedBackend().evidence)
    def test_invalid_intake_does_not_call_backend(self):
        del self.intake['description'];backend=ScriptedBackend();state=self.run_harness(backend)
        self.assertEqual(state.status,'incomplete');self.assertEqual(backend.calls,[])
    def test_existing_run_is_not_overwritten_and_paths_are_restricted(self):
        self.run_harness();before=(self.root/'test/state.json').read_bytes()
        with self.assertRaises(FileExistsError):self.run_harness()
        self.assertEqual(before,(self.root/'test/state.json').read_bytes())
        with self.assertRaises(ContractError):RunStore(self.root,'../outside')
    def test_unbounded_corrections_and_nonfinite_limits_rejected(self):
        for limits in [RunLimits(max_corrections=2),RunLimits(max_cost_usd=float('nan'))]:
            with self.assertRaises(ContractError):self.run_harness(limits=limits)

if __name__=='__main__':unittest.main()
