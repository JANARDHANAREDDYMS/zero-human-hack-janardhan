"""Safe local config and explicit unknown-dollar bridge accounting."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
from customer_generation.environment import load_environment
from customer_generation.tools.llm import ModelBridgeClient
from customer_generation.validation import ContractError
from test_phase3 import bridge,FakeTransport,ALLOW

ROOT=Path(__file__).resolve().parents[2]
class EnvironmentTests(unittest.TestCase):
 def read(self,text,env=None):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'.env';p.write_text(text);result={} if env is None else env;load_environment(p,result);return result
 def test_exported_values_win_and_quoted_hash_is_literal(self):
  env=self.read('TOKEN="a # b"\nEXA_API_KEY=file-key\n',{'EXA_API_KEY':'exported-key'})
  self.assertEqual(env,{'TOKEN':'a # b','EXA_API_KEY':'exported-key'})
 def test_values_are_never_shell_executed_or_interpolated(self):
  env=self.read('TOKEN=$(echo should-not-run)\nOTHER=${TOKEN}\n')
  self.assertEqual(env['TOKEN'],'$(echo should-not-run)');self.assertEqual(env['OTHER'],'${TOKEN}')
 def test_malformed_or_duplicate_entries_rejected_without_secret_output(self):
  for text in ['EXA_API_KEY=secret\nEXA_API_KEY=secret2','bad key=secret','TOKEN="secret']:
   with self.assertRaises(ValueError) as caught:self.read(text)
   self.assertNotIn('secret',str(caught.exception))
 def test_bridge_can_explicitly_report_unknown_cost(self):
  response=bridge();response['usage'].update(cost_usd=None,cost_basis='unavailable')
  result=ModelBridgeClient('https://bridge.example/run','token','workspace-model',FakeTransport([response])).call('propose',{},ALLOW,{})
  self.assertTrue(result.metadata['cost_uncertain']);self.assertEqual(result.cost_usd,0)
 def test_null_cost_cannot_claim_a_known_estimate(self):
  response=bridge();response['usage']['cost_usd']=None
  with self.assertRaises(ContractError):ModelBridgeClient('https://bridge.example/run','token','workspace-model',FakeTransport([response])).call('propose',{},ALLOW,{})
 def test_exported_worker_policy_is_current(self):
  spec=importlib.util.spec_from_file_location('export_policy',ROOT/'backend/scripts/export_worker_policy.py')
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  saved=json.loads((ROOT/'backend/workers/lovable-current/policy.json').read_text())
  self.assertEqual(saved,module.build_policy())
 def test_smoke_inputs_use_briefs_only_and_distinct_ids(self):
  files=[ROOT/'data/evaluations/cases/usb-c-hub.json',ROOT/'data/products/sony-speaker/research-v2/brief.json']
  briefs=[json.loads(p.read_text()) for p in files]
  self.assertEqual(len({b['product_id'] for b in briefs}),2)
  self.assertTrue(all('segments' not in b and 'customers' not in b for b in briefs))

if __name__=='__main__':unittest.main()
