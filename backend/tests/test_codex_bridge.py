"""Local Codex adapter tests. Runners are injected; no subscription calls."""
import json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from customer_generation.tools.codex import CodexModelClient,CodexModelError,run_process
from customer_generation.config import AdapterConfig
from customer_generation.tools.live import LiveBackend
from customer_generation.pipeline import run_generation
from test_phase3 import FakeModel,FakeTransport,result,FIX
from customer_generation.tools.exa import ExaClient
from customer_generation.state import StageResponse

ALLOW={'max_tokens':6000,'max_cost_usd':1,'timeout_seconds':10}
SCHEMA={'type':'object','properties':{'value':{'type':'integer'}},'required':['value'],'additionalProperties':False}
def events(data=None,usage=None):
 return '\n'.join(json.dumps(x) for x in [
  {'type':'thread.started','thread_id':'local-1'},
  {'type':'item.completed','item':{'type':'agent_message','text':json.dumps({'result_json':json.dumps(data or {'value':1})})}},
  {'type':'turn.completed','usage':usage or {'input_tokens':10,'output_tokens':20,'cached_input_tokens':0}}])
class CodexBridgeTests(unittest.TestCase):
 def call(self,runner,**kwargs):
  with patch('customer_generation.tools.codex.shutil.which',return_value='/bin/codex'):
   return CodexModelClient('enabled-model',runner=runner).call('propose',{'text':'UNTRUSTED'},kwargs.get('allowances',ALLOW),SCHEMA)
 def test_command_is_read_only_fresh_and_payload_not_shell(self):
  def runner(command,prompt,timeout,cwd):
   self.assertIn('--ephemeral',command);self.assertIn('read-only',command);self.assertIn('--ignore-user-config',command)
   self.assertIn('web_search="disabled"',command);self.assertIn('UNTRUSTED',prompt)
   self.assertNotIn('UNTRUSTED',command);self.assertNotIn('--dangerously-bypass-approvals-and-sandbox',command)
   self.assertTrue(Path(cwd).exists());return events()
  r=self.call(runner);self.assertEqual(r.data,{'value':1});self.assertTrue(r.metadata['cost_uncertain'])
  self.assertEqual(r.cost_usd,0);self.assertEqual(r.input_tokens,10)
 def test_output_must_match_actual_stage_schema(self):
  with self.assertRaises(CodexModelError):self.call(lambda *a:events({'value':'wrong type'}))
 def test_missing_usage_not_reported_as_zero(self):
  with self.assertRaises(CodexModelError):self.call(lambda *a:'{"type":"thread.started","thread_id":"x"}')
 def test_model_tool_action_is_rejected(self):
  raw=events()+'\n'+json.dumps({'type':'item.completed','item':{'type':'command_execution'}})
  with self.assertRaisesRegex(CodexModelError,'tool action'):self.call(lambda *a:raw)
 def test_invalid_json_errors_do_not_expose_raw_payload(self):
  with self.assertRaises(CodexModelError) as caught:self.call(lambda *a:'secret-token')
  self.assertNotIn('secret-token',str(caught.exception))
 def test_measured_tokens_returned_even_over_budget(self):
  r=self.call(lambda *a:events(usage={'input_tokens':8000,'output_tokens':100}))
  self.assertEqual(r.input_tokens,8000)
 def test_unknown_stage_or_bad_allowance_does_not_launch(self):
  runner=lambda *a:self.fail('must not execute')
  with self.assertRaises(ValueError):self.call(runner,allowances={**ALLOW,'timeout_seconds':float('nan')})
  with self.assertRaises(ValueError):CodexModelClient('model',runner=runner).call('not-a-stage',{},ALLOW,SCHEMA)
 def test_codex_config_does_not_require_lovable_credentials(self):
  c=AdapterConfig.from_environment({'EXA_API_KEY':'exa-secret','CODEX_MODEL':'enabled-model'},backend='codex')
  self.assertEqual(c.model_backend,'codex');self.assertEqual(c.model_bridge_token,'');self.assertNotIn('exa-secret',repr(c))
 def test_codex_still_requires_research_key(self):
  with self.assertRaisesRegex(ValueError,'EXA_API_KEY'):AdapterConfig.from_environment({'CODEX_MODEL':'model'},backend='codex')
 def test_model_unknown_dollar_usage_reaches_terminal_state(self):
  class SubscriptionModel(FakeModel):
   def call(self,*args):
    r=super().call(*args);r.cost_usd=0;r.metadata={'cost_uncertain':True,'cost_basis':'subscription_usage_unknown_dollars'};return r
  c=AdapterConfig.from_environment({'EXA_API_KEY':'x','CODEX_MODEL':'m'},backend='codex')
  backend=LiveBackend(c,exa=ExaClient('x',FakeTransport([result()]*3)),model=SubscriptionModel())
  with tempfile.TemporaryDirectory() as root:
   state=run_generation(json.loads((FIX/'intake.json').read_text()),backend,Path(root),'run')
   self.assertEqual(state.status,'completed');self.assertTrue(state.cost_uncertain);self.assertAlmostEqual(state.cost_usd,.03)
 def test_timeout_kills_child_group(self):
  import sys
  with tempfile.TemporaryDirectory() as cwd:
   with self.assertRaisesRegex(CodexModelError,'timed out'):
    run_process([sys.executable,'-c','import time; time.sleep(5)'],'',.1,cwd)

if __name__=='__main__':unittest.main()

class CodexFailureAccountingTests(unittest.TestCase):
 def test_invalid_output_preserves_reported_usage(self):
  with patch('customer_generation.tools.codex.shutil.which',return_value='/bin/codex'):
   with self.assertRaises(CodexModelError) as caught:
    CodexModelClient('model',runner=lambda *a:events({'value':'invalid'})).call('propose',{},ALLOW,SCHEMA)
  self.assertEqual(caught.exception.partial.input_tokens,10)
  self.assertEqual(caught.exception.partial.output_tokens,20)
 def test_stage_failure_preserves_model_usage(self):
  class FailedModel:
   def call(self,*args):
    raise CodexModelError('Invalid output',StageResponse({},40,20,0,metadata={'cost_uncertain':True}))
  c=AdapterConfig.from_environment({'EXA_API_KEY':'x','CODEX_MODEL':'m'},backend='codex')
  backend=LiveBackend(c,exa=ExaClient('x',FakeTransport([result()]*3)),model=FailedModel())
  with tempfile.TemporaryDirectory() as root:
   state=run_generation(json.loads((FIX/'intake.json').read_text()),backend,Path(root),'run')
   self.assertEqual(state.status,'failed');self.assertEqual(state.total_tokens,60);self.assertTrue(state.cost_uncertain)
