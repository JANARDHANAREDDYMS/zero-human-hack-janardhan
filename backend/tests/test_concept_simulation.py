"""Full concept/report path through actual Python bridge, using offline transport."""
import copy,json,tempfile,unittest
from pathlib import Path
from customer_simulation.pipeline import read,save
from customer_simulation.concept import run,validate_customer,validate_narrative,SCENARIO
from customer_generation.tools.llm import ModelBridgeClient
from customer_generation.instructions import InstructionRegistry
ROOT=Path(__file__).resolve().parents[2]
FIX=ROOT/'data/products/sony-speaker/research-v2'

def customer_answer(payload):
    c=payload['customer'];service='documents' in c['current_solution']
    affordable=next(x['eligible'] for x in payload['purchase_eligibility'] if x['offer_id']=='target')
    chosen='choose_product' if affordable else 'keep_current'
    situation='They currently edit their own documents and want help before sending them to clients.' if service else 'They already have a speaker, but would like something easier to use around the house.'
    reason='They would choose this because it fits their needs and budget.' if affordable else 'They would keep what they use because the proposed price is more than they can spend.'
    return {'customer_id':c['customer_id'],'decision':chosen,'selected_offer_id':'target' if affordable else None,
        'headline':reason,'reasons':[{'explanation':reason,'profile_fields':['budget.maximum','current_solution'],'finding_ids':[]}],
        'objections':[] if affordable else [{'category':'price','concern':'It costs more than they can spend.','suggested_change':'Test a less expensive offer.','finding_ids':[]}],
        'missing_information':[],'change_that_might_help':'Show what is included for the price.',
        'limitations':['This is a hypothetical choice, not a real order.'],
        'customer_story':{'situation':situation,'reason':reason,'next_step':'Show what is included for the price.','profile_fields':['current_solution','budget.maximum'],'finding_ids':[]},
        'purchase_checks':[{'topic':'performance','question':'Before paying, they would want to see that it works as described.','finding_ids':[]}]}

def narrative_answer(payload):
    ids=[c['customer_id'] for c in payload['customers']]
    return {'overview':[{'text':t,'customer_ids':ids} for t in [
        'These customers already have a way to meet this need.','The price matters to whether they would switch.',
        'Some would keep what they use when the new offer costs too much.','Ask what would make switching worthwhile.',
        'Try a clearer explanation of what the price includes.']],
        'segments':[{'segment_id':g['segment_id'],'name':'Buyers comparing their current option with a new one',
            'feedback':'These customers compare what they already use with the proposed offer.',
            'next_step':'Explain the practical benefit of switching.','customer_ids':g['tested_customer_ids'][:50]} for g in payload['tested_segments']],
        'improvements':[{'title':'Make the benefit clear','explanation':'People need a reason to change what they already use.',
            'next_step':'Show one practical example of what changes for them.','customer_ids':ids}]}

class Transport:
    def __init__(self):self.calls=[];self.fail_report=False;self.unknown_report_ref=False;self.answers=[]
    def post(self,url,headers,body,timeout):
        self.calls.append(body['stage'])
        if body['stage']=='simulate_concept':data=customer_answer(body['payload'])
        elif body['stage']=='summarize_simulation':
            if self.fail_report:raise RuntimeError('Offline failure')
            data=narrative_answer(body['payload'])
            if self.unknown_report_ref:data['overview'][0]['customer_ids']=['invented']
        else:raise AssertionError(body['stage'])
        self.answers.append((body,data))
        return {'contract_version':'1.1','stage':body['stage'],'model':body['model'],'request_id':'offline',
            'instruction_version':body['instructions']['version'],'instruction_sha256':body['instructions']['sha256'],
            'data':data,'usage':{'input_tokens':100,'output_tokens':200,'cost_usd':None,'cost_basis':'unavailable'}}

class ConceptTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.source=self.root/'source';self.source.mkdir()
        for name in ['brief.json','evidence.json','customers.json']:save(self.source/name,read(FIX/name))
        save(self.source/'state.json',{'status':'completed'})
        population=read(self.source/'customers.json')
        for c in population['customers']:
            c['requirements']=[{'attribute':'price','operator':'lte','constraint':'hard','value':c['budget']['maximum'],'unit':c['budget']['currency']}]
        save(self.source/'customers.json',population)
        self.transport=Transport();self.client=ModelBridgeClient('https://offline.example/model','offline-token','offline-model',self.transport)
    def test_complete_run_has_conversation_and_separate_checks_without_sidecar(self):
        out=self.root/'result';run(self.source,out,self.client,count=5)
        self.assertEqual(self.transport.calls,['simulate_concept']*5+['summarize_simulation'])
        self.assertEqual(read(out/'manifest.json')['status'],'completed')
        self.assertEqual(read(out/'summary.json')['evaluated'],5)
        html=(out/'report.html').read_text();self.assertIn('They already have a speaker',html)
        self.assertIn('What they would check before paying',html);self.assertIn('If your proposed product were available',html)
        self.assertFalse((out/'report-language.json').exists());self.assertFalse((out/'terac-review-briefs.json').exists())
        before=len(self.transport.calls);run(self.source,out,self.client,count=5,resume=True)
        self.assertEqual(len(self.transport.calls),before)
    def test_explicit_resume_retries_unanswered_report_without_repeating_customers(self):
        from customer_generation.tools.http import TransportError
        original=self.transport.post
        failed=[False]
        def interrupted(url,headers,body,timeout):
            if body['stage']=='summarize_simulation' and not failed[0]:
                failed[0]=True;raise TransportError('timeout')
            return original(url,headers,body,timeout)
        self.transport.post=interrupted;out=self.root/'interrupted-report'
        with self.assertRaises(TransportError):run(self.source,out,self.client,count=5)
        self.assertEqual(self.transport.calls.count('simulate_concept'),5)
        self.assertFalse((out/'report-raw.json').exists())
        self.assertEqual(read(out/'report-call-failure.json')['transport_category'],'timeout')
        run(self.source,out,self.client,count=5,resume=True)
        self.assertEqual(self.transport.calls.count('simulate_concept'),5)
        self.assertEqual(read(out/'manifest.json')['status'],'completed')
        self.assertTrue(list((out/'report-retry-attempts').glob('*.json')))
        self.assertTrue(read(out/'report-usage.json')['metadata']['previous_attempt_usage_unknown'])
        before=len(self.transport.calls);run(self.source,out,self.client,count=5,resume=True)
        self.assertEqual(len(self.transport.calls),before)

    def test_second_category_uses_same_generic_path(self):
        brief=read(self.source/'brief.json');brief.update(name='Document review service',description='Review a document before sending it to a client.',category='professional service',known_features={'review':'One document reviewed'})
        save(self.source/'brief.json',brief)
        evidence=read(self.source/'evidence.json');evidence['findings']=[];evidence['sources']=[];save(self.source/'evidence.json',evidence)
        population=read(self.source/'customers.json')
        for index,c in enumerate(population['customers']):c.update(customer_id=f'document-review-{index:04}',current_solution='Edits documents themselves',goal='Get a document ready for a client')
        save(self.source/'customers.json',population)
        out=self.root/'service';run(self.source,out,self.client,count=5)
        self.assertIn('They currently edit their own documents',(out/'report.html').read_text())
        self.assertNotIn('speaker',(out/'report.html').read_text().lower())
    def test_customer_can_like_concept_and_request_proof(self):
        from customer_simulation.pipeline import build_offers
        offers=build_offers(read(self.source/'brief.json'),read(self.source/'evidence.json'))
        c=read(self.source/'customers.json')['customers'][0];c['budget'].update(maximum=10000,upfront_maximum=10000)
        c['requirements']=[]
        payload={'customer':c,'purchase_eligibility':[{'offer_id':'target','eligible':True}]};data=customer_answer(payload)
        validate_customer(data,c,offers,read(self.source/'evidence.json'))
        self.assertEqual(data['decision'],'choose_product');self.assertTrue(data['purchase_checks'])
        self.assertEqual(data['objections'],[])
    def test_invalid_summary_reference_blocks_publication(self):
        self.transport.unknown_report_ref=True;out=self.root/'bad'
        with self.assertRaises(ValueError):run(self.source,out,self.client,count=5)
        self.assertFalse((out/'report.html').exists());self.assertEqual(read(out/'manifest.json')['status'],'failed')
        self.assertTrue((out/'customer-005.json').exists());self.assertTrue((out/'report-raw.json').exists())
    def test_report_outage_preserves_customers_and_does_not_automatically_retry(self):
        self.transport.fail_report=True;out=self.root/'failed'
        with self.assertRaises(RuntimeError):run(self.source,out,self.client,count=5)
        self.assertEqual(len(self.transport.calls),6);self.assertTrue((out/'customer-005.json').exists())
        self.transport.fail_report=False
        run(self.source,out,self.client,count=5,resume=True)
        self.assertEqual(len(self.transport.calls),7)
        self.assertEqual(self.transport.calls.count('simulate_concept'),5)
    def test_policy_contains_explicit_scenario_and_conversational_rules(self):
        instructions=InstructionRegistry()
        text=instructions.for_stage('simulate_concept')['system_text']
        self.assertIn('Do NOT reject or defer merely because it is hypothetical',text)
        self.assertIn('purchase_checks',text);self.assertIn('THIRD-PERSON',text)
        self.assertNotIn('No Markdown fences, extra keys, executable code, buying decisions',text)
        self.assertTrue(SCENARIO['assumptions_are_not_verified_facts'])
    def test_schema_and_instruction_changes_prevent_stale_resume(self):
        out=self.root/'done';run(self.source,out,self.client,count=5)
        brief=read(self.source/'brief.json');brief['description']='Changed offer';save(self.source/'brief.json',brief)
        with self.assertRaises(ValueError):run(self.source,out,self.client,count=5,resume=True)
        self.assertEqual(len(self.transport.calls),6)
    def test_summary_requires_exact_group_membership(self):
        customers=read(self.source/'customers.json')['customers'][:2]
        data={'overview':[{'text':'A supported conclusion','customer_ids':[customers[0]['customer_id']]}]*5,
            'segments':[{'segment_id':customers[0]['segment_id'],'name':'A group','feedback':'Feedback','next_step':'Test something','customer_ids':[customers[0]['customer_id']]}], 'improvements':[]}
        with self.assertRaises(ValueError):validate_narrative(data,customers)
if __name__=='__main__':unittest.main()
