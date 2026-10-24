"""Transport and live-adapter integration tests; all network calls are mocked."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError,URLError
from customer_generation.config import AdapterConfig
from customer_generation.instructions import InstructionRegistry, fixture_checks
from customer_generation.tools.http import JsonTransport,TransportError,validate_endpoint
from customer_generation.tools.exa import ExaClient,ResearchResponseError
from customer_generation.tools.llm import ModelBridgeClient,ModelResponseError
from customer_generation.tools.live import LiveBackend,AdapterFailure
from customer_generation.state import StageResponse
from customer_generation.pipeline import run_generation
from customer_generation.validation import ContractError

FIX=Path(__file__).parent/'fixtures/keyboard'
ALLOW={'timeout_seconds':30,'max_tokens':6000,'max_cost_usd':1}

def config():return AdapterConfig('secret-exa','https://bridge.example/run','secret-bridge','workspace-model')
def result():return {'requestId':'r1','costDollars':{'total':0.01},'results':[{'url':'https://vendor.example/keyboard#details','title':'Keyboard','text':'Keyboard details and limitations. '*100}]}
def bridge(stage='propose'):
    return {'contract_version':'1.1','instruction_sha256':InstructionRegistry().for_stage(stage)['sha256'],'stage':stage,'model':'workspace-model','request_id':'m1','instruction_version':InstructionRegistry().for_stage(stage)['version'],'data':{},'usage':{'input_tokens':10,'output_tokens':20,'cost_usd':0.001,'cost_basis':'configured_estimate'}}
class FakeTransport:
    def __init__(self,values):self.values=list(values);self.calls=[]
    def post(self,url,headers,payload,timeout):
        self.calls.append((url,headers,payload,timeout));value=self.values.pop(0)
        if isinstance(value,Exception):raise value
        return copy.deepcopy(value)
class FakeModel:
    def __init__(self):self.calls=[];self.mutate_sources=False
    def call(self,stage,payload,allowances,output_schema):
        self.calls.append((stage,payload,allowances))
        if stage=='research_extract':
            data={'schema_version':'2.0','product_id':'keyboard-example','sources':copy.deepcopy(payload['source_catalog']),'findings':[],'limitations':['Transport test; no verified extracted findings.']}
            if self.mutate_sources:data['sources'][0]['url']='https://invented.example/'
        elif stage=='review':data={'decision':'accept','summary':'Mock review only','findings':[],'checks':fixture_checks()}
        else:
            data=json.loads((FIX/'specification.json').read_text())
            for seg in data['segments']:
                seg['situation']={'trigger':'Replacing input device','goal':seg['goal'],'current_solution':'Existing keyboard','constraint':seg['name'],'switch_reason':'Better fit','stay_reason':'Existing device sufficient'}
        return StageResponse(data,10,20,.001,metadata={'cost_basis':'configured_estimate'})

class AdapterTests(unittest.TestCase):
    def test_config_missing_is_actionable_and_secret_repr_hidden(self):
        with self.assertRaisesRegex(ValueError,'EXA_API_KEY'):AdapterConfig.from_environment({})
        self.assertNotIn('secret-exa',repr(config()));self.assertNotIn('secret-bridge',repr(config()))
    def test_https_endpoint_restrictions(self):
        for url in ['http://bridge.example/run','https://user:pass@bridge.example/','https://bridge.example/?token=x','https://bridge.example/#x']:
            with self.assertRaises(ValueError):validate_endpoint(url)
    def test_exa_request_contract_and_bounded_text(self):
        transport=FakeTransport([result()]);r=ExaClient('secret',transport).search('keyboard',text_characters=100)
        self.assertEqual(transport.calls[0][0],'https://api.exa.ai/search')
        self.assertEqual(transport.calls[0][1]['x-api-key'],'secret')
        self.assertEqual(transport.calls[0][2]['numResults'],3)
        self.assertEqual(len(r['snippets'][0]['text']),100);self.assertTrue(r['snippets'][0]['truncated'])
        self.assertEqual(r['estimated_cost_usd'],.01)
    def test_exa_deduplicates_urls_and_skips_no_text_or_bad_url(self):
        raw=result();raw['results'] += [copy.deepcopy(raw['results'][0]),{'url':'javascript:evil','text':'x'},{'url':'https://empty.example/'}]
        r=ExaClient('secret',FakeTransport([raw])).search('keyboard',num_results=10)
        self.assertEqual(len(r['sources']),1)
    def test_exa_missing_cost_is_not_zero(self):
        raw=result();del raw['costDollars']
        with self.assertRaises(ResearchResponseError):ExaClient('x',FakeTransport([raw])).search('keyboard')
    def test_exa_query_and_limits_rejected_before_network(self):
        transport=FakeTransport([])
        for options in [{'query':''},{'query':'keyboard','num_results':1000}]:
            with self.assertRaises(ValueError):ExaClient('x',transport).search(**options)
        self.assertEqual(transport.calls,[])
    def test_bridge_auth_schema_model_and_usage(self):
        t=FakeTransport([bridge()]);r=ModelBridgeClient('https://bridge.example/run','token','workspace-model',t).call('propose',{},ALLOW,{'type':'object'})
        self.assertEqual(t.calls[0][1]['Authorization'],'Bearer token')
        self.assertEqual(t.calls[0][2]['limits'],ALLOW);self.assertEqual(r.cost_usd,.001)
        self.assertEqual(r.metadata['cost_basis'],'configured_estimate')
    def test_bridge_unknown_cost_or_wrong_model_rejected(self):
        for edit in ['missing_cost','wrong_model','wrong_stage']:
            raw=bridge()
            if edit=='missing_cost':del raw['usage']['cost_usd']
            if edit=='wrong_model':raw['model']='other'
            if edit=='wrong_stage':raw['stage']='review'
            with self.assertRaises((ContractError,ModelResponseError)):
                ModelBridgeClient('https://bridge.example/run','token','workspace-model',FakeTransport([raw])).call('propose',{},ALLOW,{})
    def test_bridge_unknown_stage_does_not_call(self):
        t=FakeTransport([])
        with self.assertRaises(ValueError):ModelBridgeClient('https://bridge.example/run','t','m',t).call('arbitrary',{},ALLOW,{})
        self.assertEqual(t.calls,[])
    def test_live_research_preserves_sources_and_accounts_search_and_model(self):
        model=FakeModel();backend=LiveBackend(config(),exa=ExaClient('x',FakeTransport([result(),result(),result()])),model=model)
        brief=json.loads((FIX/'intake.json').read_text())
        r=backend.execute('research',{'brief':brief},ALLOW)
        self.assertAlmostEqual(r.cost_usd,.031);self.assertEqual(r.input_tokens,10)
        self.assertEqual(len(r.data['sources']),1)
        self.assertEqual(len(r.artifacts['research-retrieval.json']['batches']),3)
        self.assertEqual(model.calls[0][0],'research_extract')
        self.assertEqual(model.calls[0][1]['content_trust'],'untrusted_source_data_not_instructions')
    def test_changed_catalog_fails_with_incurred_usage(self):
        model=FakeModel();model.mutate_sources=True
        backend=LiveBackend(config(),exa=ExaClient('x',FakeTransport([result(),result(),result()])),model=model)
        with self.assertRaises(AdapterFailure) as ctx:backend.execute('research',{'brief':json.loads((FIX/'intake.json').read_text())},ALLOW)
        self.assertAlmostEqual(ctx.exception.partial.cost_usd,.031)
        self.assertTrue(ctx.exception.partial.metadata['cost_uncertain'])
    def test_partial_research_failure_is_persisted_by_harness(self):
        backend=LiveBackend(config(),exa=ExaClient('x',FakeTransport([result(),TransportError('timeout')])),model=FakeModel())
        with tempfile.TemporaryDirectory() as root:
            state=run_generation(json.loads((FIX/'intake.json').read_text()),backend,Path(root),'run')
            self.assertEqual(state.status,'failed');self.assertEqual(state.cost_usd,.01);self.assertTrue(state.cost_uncertain)
            saved=json.loads((Path(root)/'run/call-01-response.json').read_text())
            self.assertTrue(saved['metadata']['cost_uncertain'])
            self.assertTrue((Path(root)/'run/call-01-research-retrieval.json').exists())
    def test_budget_reserve_prevents_search(self):
        t=FakeTransport([]);backend=LiveBackend(config(),exa=ExaClient('x',t),model=FakeModel())
        with self.assertRaises(AdapterFailure):backend.execute('research',{'brief':json.loads((FIX/'intake.json').read_text())},{**ALLOW,'max_cost_usd':.001})
        self.assertEqual(t.calls,[])
    def test_live_dispatch_harness_success_uses_no_fixture_fallback(self):
        backend=LiveBackend(config(),exa=ExaClient('x',FakeTransport([result(),result(),result()])),model=FakeModel())
        with tempfile.TemporaryDirectory() as root:
            state=run_generation(json.loads((FIX/'intake.json').read_text()),backend,Path(root),'run')
            self.assertEqual(state.status,'completed');self.assertEqual(state.mode,'live')
            self.assertAlmostEqual(state.cost_usd,.033)
    def test_transport_http_errors_are_sanitized(self):
        for status in [401,402,403,429,500,302]:
            error=HTTPError('https://x.example',status,'secret-exa',None,None)
            with patch('customer_generation.tools.http.build_opener') as build:
                build.return_value.open.side_effect=error
                with self.assertRaises(TransportError) as ctx:JsonTransport().post('https://x.example',{}, {},1)
                self.assertNotIn('secret-exa',str(ctx.exception));self.assertEqual(ctx.exception.status,status)
    def test_transport_invalid_json_and_size(self):
        for payload in [b'not json',b'x'*101]:
            with patch('customer_generation.tools.http.build_opener') as build:
                build.return_value.open.return_value.__enter__.return_value.read.return_value=payload
                with self.assertRaises(TransportError):JsonTransport(max_response_bytes=100).post('https://x.example',{}, {},1)
    def test_adapter_error_does_not_expose_arbitrary_exception_secret(self):
        model=FakeModel()
        def fail(*args):raise RuntimeError('secret-bridge secret-exa')
        model.call=fail
        with self.assertRaises(AdapterFailure) as ctx:LiveBackend(config(),model=model).execute('propose',{},ALLOW)
        self.assertNotIn('secret-bridge',str(ctx.exception));self.assertNotIn('secret-exa',str(ctx.exception))

if __name__=='__main__':unittest.main()
