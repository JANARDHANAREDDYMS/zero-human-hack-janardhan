import copy,json,unittest
from pathlib import Path
from customer_generation.tools.openrouter import OpenRouterClient,bundled_schema
from customer_generation.config import AdapterConfig
from customer_generation.tools.llm import ModelResponseError,configured_client
from customer_generation.validation import ContractError,SCHEMAS
from customer_generation.worker_readiness import check_worker
from jsonschema import Draft202012Validator

class Transport:
 def __init__(self):
  self.calls=[];self.response={'id':'offline-request','model':'test/model','choices':[{'finish_reason':'stop','message':{'content':'{"result":"ok"}'}}],'usage':{'prompt_tokens':12,'completion_tokens':8,'cost':0.001}}
 def post(self,url,headers,body,timeout):self.calls.append((url,body));return copy.deepcopy(self.response)

class OpenRouterTests(unittest.TestCase):
 def setUp(self):
  self.transport=Transport();self.client=OpenRouterClient('secret-offline','test/model',self.transport)
  self.schema={'type':'object','properties':{'result':{'type':'string'}},'required':['result'],'additionalProperties':False}
 def call(self):return self.client.call('compact_propose',{}, {'max_tokens':500,'timeout_seconds':10,'max_cost_usd':1},self.schema)
 def test_direct_call_uses_canonical_schema_and_reports_usage(self):
  response=self.call();self.assertEqual(response.data,{'result':'ok'});self.assertEqual(response.cost_usd,0.001)
  body=self.transport.calls[0][1];self.assertFalse(body['response_format']['json_schema']['strict']);self.assertTrue(body['provider']['require_parameters']);self.assertFalse(body['provider']['allow_fallbacks'])
  self.assertNotIn('secret-offline',json.dumps(body))
 def test_bad_output_truncation_refusal_and_missing_usage_rejected_without_retry(self):
  for change in ['invalid','wrong_type','truncated','refusal','usage']:
   self.setUp()
   if change=='invalid':self.transport.response['choices'][0]['message']['content']='not json'
   if change=='wrong_type':self.transport.response['choices'][0]['message']['content']='{"result":1}'
   if change=='truncated':self.transport.response['choices'][0]['finish_reason']='length'
   if change=='refusal':self.transport.response['choices'][0]['message']['refusal']='Refused'
   if change=='usage':self.transport.response.pop('usage')
   with self.assertRaises((ModelResponseError,ContractError)):self.call()
   self.assertEqual(len(self.transport.calls),1)
 def test_unknown_cost_is_disclosed(self):
  self.transport.response['usage'].pop('cost');self.assertTrue(self.call().metadata['cost_uncertain'])
 def test_external_refs_are_bundled_with_nested_local_ref_scope(self):
  schema={'type':'object','properties':{'customer':{'$ref':'customer-v2.schema.json'}}}
  bundled=bundled_schema(schema);Draft202012Validator.check_schema(bundled)
  errors=list(Draft202012Validator(bundled).iter_errors({'customer':{}}));self.assertTrue(errors)
  self.assertEqual(schema['properties']['customer']['$ref'],'customer-v2.schema.json')
  with self.assertRaises(ValueError):bundled_schema({'$ref':'https://example.org/schema'})
 def test_all_stage_schemas_bundle_locally(self):
  from customer_generation.instructions import InstructionRegistry
  # Every schema is syntactically valid after bundling; runtime output remains validated.
  for path in SCHEMAS.glob('*.schema.json'):Draft202012Validator.check_schema(bundled_schema(json.loads(path.read_text())))
 def test_configuration_requires_explicit_openrouter_model_and_skips_worker_probe(self):
  env={'MODEL_BACKEND':'openrouter','EXA_API_KEY':'offline','OPENROUTER_API_KEY':'secret','OPENROUTER_MODEL':'test/model'}
  config=AdapterConfig.from_environment(env);self.assertEqual(config.model_backend,'openrouter');self.assertIsInstance(configured_client(config),OpenRouterClient)
  class Never:
   def post(self,*a):raise AssertionError('No inference during readiness check')
  self.assertTrue(check_worker(config,Never()));self.assertNotIn('secret',repr(config))
  env.pop('OPENROUTER_MODEL')
  with self.assertRaises(ValueError):AdapterConfig.from_environment(env)
