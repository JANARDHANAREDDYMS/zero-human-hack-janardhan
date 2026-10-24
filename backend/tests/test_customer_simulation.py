import json,tempfile,unittest
from pathlib import Path
from customer_simulation.pipeline import *
from customer_generation.instructions import InstructionRegistry
from customer_generation.state import StageResponse
ROOT=Path(__file__).resolve().parents[2]
FIXTURE=ROOT/'data/products/sony-speaker/research-v2'

def decision(c):return {'customer_id':c['customer_id'],'decision':'keep_current','selected_offer_id':None,
    'headline':'Existing solution remains adequate','reasons':[{'explanation':'Switching barriers outweigh uncertain benefit.',
    'profile_fields':['switching_barriers'],'finding_ids':[]}],'objections':[{'category':'missing_information',
    'concern':'Performance is unverified.','suggested_change':'Provide a test result.','finding_ids':[]}],
    'missing_information':['Measured performance'],'change_that_might_help':'Independent testing.',
    'limitations':['Synthetic comparison; no product was tested.']}
class Fake:
    instructions=InstructionRegistry()
    def __init__(self):self.calls=0
    def call(self,stage,payload,limits,schema):
        self.calls+=1
        return StageResponse(decision(payload['customer']),100,200,0,metadata={})

class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.source=Path(self.temp.name)
        for name in ['brief.json','evidence.json','customers.json']:save(self.source/name,read(FIXTURE/name))
        save(self.source/'state.json',{'status':'completed'})
        self.pop=read(self.source/'customers.json');self.evidence=read(self.source/'evidence.json')
        self.offers=build_offers(read(self.source/'brief.json'),self.evidence);self.c=self.pop['customers'][0]
    def test_schema_and_instruction(self):
        validate_schema(decision(self.c),'customer-decision')
        text=InstructionRegistry().for_stage('simulate_customer')['system_text']
        self.assertNotIn('No Markdown fences, extra keys, executable code, buying decisions',text)
    def test_round_robin(self):
        selected=choose_customers(self.pop,5)
        self.assertEqual(len({c['segment_id'] for c in selected}),len({c['segment_id'] for c in self.pop['customers']}))
    def test_unknown_refs_and_decision(self):
        d=decision(self.c);d['reasons'][0]['finding_ids']=['invented']
        with self.assertRaises(ValueError):validate_decision(d,self.c,self.offers,self.evidence)
        d=decision(self.c);d['reasons'][0]['profile_fields']=['invented']
        with self.assertRaises(ValueError):validate_decision(d,self.c,self.offers,self.evidence)
    def test_budget_and_unknown_price(self):
        import copy
        c=copy.deepcopy(self.c);c['budget']['maximum']=1
        d=decision(c);d.update(decision='choose_product',selected_offer_id='target')
        with self.assertRaises(ValueError):validate_decision(d,c,self.offers,self.evidence)
        d.update(decision='choose_alternative',selected_offer_id=self.offers[1]['offer_id'])
        with self.assertRaises(ValueError):validate_decision(d,self.c,self.offers,self.evidence)
    def test_valid_purchase_and_selected_offer_consistency(self):
        import copy
        c=copy.deepcopy(self.c);c['budget'].update(maximum=200,upfront_maximum=200,currency='USD',billing_period='one_time')
        c['requirements']=[{'attribute':'price','operator':'lte','constraint':'hard','value':200,'unit':'USD'}]
        offers=[{'offer_id':'target','price':{'amount':119,'currency':'USD','billing_period':'one_time'}},
                {'offer_id':'alternative-test','price':{'amount':100,'currency':'USD','billing_period':'one_time'}}]
        d=decision(c);d.update(decision='choose_product',selected_offer_id='target')
        validate_decision(d,c,offers,self.evidence)
        d.update(decision='choose_alternative',selected_offer_id='alternative-test')
        validate_decision(d,c,offers,self.evidence)
        d['selected_offer_id']='target'
        with self.assertRaises(ValueError):validate_decision(d,c,offers,self.evidence)
    def test_complete_pipeline_through_real_python_bridge_client(self):
        from customer_generation.tools.llm import ModelBridgeClient
        test=self
        class Transport:
            calls=0
            def post(self,url,headers,body,timeout):
                self.calls+=1
                return {'contract_version':'1.1','stage':body['stage'],'model':body['model'],'request_id':'offline-test',
                    'instruction_version':body['instructions']['version'],'instruction_sha256':body['instructions']['sha256'],
                    'data':decision(body['payload']['customer']),
                    'usage':{'input_tokens':100,'output_tokens':200,'cost_usd':None,'cost_basis':'unavailable'}}
        transport=Transport();client=ModelBridgeClient('https://offline.example/bridge','offline-token','offline-model',transport)
        with tempfile.TemporaryDirectory() as tmp:
            run(self.source,tmp,client,count=5)
            self.assertEqual(transport.calls,5)
            self.assertTrue((Path(tmp)/'bridge-response-001.json').exists())
            self.assertEqual(read(Path(tmp)/'manifest.json')['status'],'completed')
            self.assertEqual(read(Path(tmp)/'usage-001.json')['metadata']['cost_uncertain'],True)
    def test_response_contract_covers_all_registered_stages(self):
        schema=read(ROOT/'data/schemas/model-bridge-response.schema.json')
        self.assertEqual(set(schema['properties']['stage']['enum']),set(InstructionRegistry().manifest()))
    def test_attribute_keyed_reference_is_exact_and_unambiguous(self):
        p={'requirements':[{'attribute':'price','value':119}]}
        self.assertEqual(profile_path(p,'requirements.price.value'),119)
        self.assertEqual(profile_path(p,'requirements.0.value'),119)
        for path in ['requirements.Price','requirements.fake','requirements.99']:
            with self.assertRaises(ValueError):profile_path(p,path)
        p['requirements'].append({'attribute':'price','value':200})
        with self.assertRaises(ValueError):profile_path(p,'requirements.price')
    def test_full_saved_response_replay_has_no_model_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            original=Path(tmp)/'original';replayed=Path(tmp)/'replayed'
            client=Fake();run(self.source,original,client,count=5)
            calls=client.calls;replay_saved(original,replayed)
            self.assertEqual(client.calls,calls)
            self.assertEqual(read(replayed/'manifest.json')['new_model_calls'],0)
            self.assertEqual(read(replayed/'summary.json')['evaluated'],5)
    def test_full_pipeline_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            client=Fake();run(self.source,tmp,client,count=5)
            self.assertEqual(client.calls,5);summary=read(Path(tmp)/'summary.json')
            self.assertEqual(summary['decisions']['keep_current'],5)
            self.assertEqual(sum(s['count'] for s in summary['segments'].values()),5)
            self.assertTrue((Path(tmp)/'report.html').exists())
            self.assertEqual(read(Path(tmp)/'terac-review-briefs.json')[0]['status'],'prepared_not_submitted')
            run(self.source,tmp,client,count=5);self.assertEqual(client.calls,5)
    def test_readable_report_has_customer_groups_and_improvements_without_terac(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(self.source,tmp,Fake(),count=5)
            report=(Path(tmp)/'report.html').read_text()
            for text in ['Each customer’s decision','Feedback by customer group','Overall feedback','Improvements to investigate','What might change their mind','Customer 5']:
                self.assertIn(text,report)
            self.assertNotIn('Prepare Terac',report);self.assertNotIn('<dialog',report)
            self.assertNotIn('purchasable offer',report.split('Original response and evidence references')[0])
    def test_editorial_language_is_bound_to_saved_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);run(self.source,out,Fake(),count=5)
            inputs=read(out/'inputs.json');cid=inputs['customers'][0]['customer_id']
            wording={'input_sha256':fingerprint(inputs),'customers':{cid:{'situation':'Their speaker battery runs out sooner than before.',
                'reason':'They want to compare fixing it with buying another one.','next_step':'Show both costs.'}},'segments':{}}
            save(out/'report-language.json',wording)
            results=[read(out/f'customer-{n:03}.json') for n in range(1,6)]
            write_reports(out,results,inputs['customers'],inputs['offers'])
            self.assertIn('Their speaker battery runs out sooner than before.',(out/'report.html').read_text())
            self.assertEqual(read(out/'customer-001.json'),results[0])
            wording['input_sha256']='wrong';save(out/'report-language.json',wording)
            write_reports(out,results,inputs['customers'],inputs['offers'])
            self.assertNotIn('Their speaker battery runs out sooner than before.',(out/'report.html').read_text())
    def test_report_escapes_model_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            results=[decision(self.c)];results[0]['headline']='<script>alert(1)</script>'
            write_reports(Path(tmp),results,[self.c],self.offers)
            report=(Path(tmp)/'report.html').read_text()
            self.assertNotIn('<script>alert(1)</script>',report)
            self.assertIn('&lt;script&gt;',report)
    def test_fail_stops_without_retry(self):
        class Bad(Fake):
            def call(self,*args):
                self.calls+=1
                return StageResponse({'bad':True},100,200,0,metadata={})
        with tempfile.TemporaryDirectory() as tmp:
            client=Bad()
            with self.assertRaises(ValueError):run(self.source,tmp,client,count=5)
            self.assertEqual(client.calls,1)
            self.assertTrue((Path(tmp)/'raw-001.json').exists())
            with self.assertRaises(ValueError):run(self.source,tmp,client,count=5)
            self.assertEqual(client.calls,1)
if __name__=='__main__':unittest.main()
