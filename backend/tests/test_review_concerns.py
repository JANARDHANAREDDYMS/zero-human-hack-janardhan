"""Concern generation only, tested with offline model envelopes."""
import json,tempfile,unittest
from pathlib import Path
import test_concept_simulation as fixtures
from customer_generation.tools.llm import ModelBridgeClient
from customer_simulation.concept import run as simulate
from customer_simulation.review_concerns import prepare_sources,generate,validate_groups,enrich
from customer_simulation.pipeline import read,save

class ConcernTransport:
    def __init__(self):self.calls=0;self.unknown=False;self.payloads=[];self.answers=[]
    def post(self,url,headers,body,timeout):
        self.calls+=1;payload=body['payload'];self.payloads.append(payload)
        ids=[s['source_objection_id'] for s in payload.get('rejection_catalog',[])] or payload.get('allowed_source_objection_ids',[])
        concerns=[]
        if ids:concerns=[{'title':'The price is more than some people can spend','explanation':'These people would keep what they already use because the price is too high for their budgets.',
            'why_human_review':'A category pricing specialist could investigate whether a less expensive offer is practical.',
            'suggested_expertise':'Category pricing and product strategy','review_question':'Can a simpler offer meet these needs at a viable price?',
            'proposed_test':'Compare the existing offer with a clearly priced simpler version.','success_criterion':'Observe whether the same profiles reconsider and check with real prospective buyers.',
            'helpfulness':'uncertain','helpfulness_reason':'A lower price may not be economically viable.','source_objection_ids':['invented'] if self.unknown else ids}]
        data={'concerns':concerns,'limitations':['Synthetic concerns, not verified real-world defects.']}
        self.answers.append((body,data))
        return {'contract_version':'1.1','stage':body['stage'],'model':body['model'],'request_id':'offline',
            'instruction_version':body['instructions']['version'],'instruction_sha256':body['instructions']['sha256'],
            'data':data,'usage':{'input_tokens':100,'output_tokens':200,'cost_usd':None,'cost_basis':'unavailable'}}

class ReviewConcernTests(unittest.TestCase):
    setUp=fixtures.ConceptTests.setUp
    def make_source(self):
        out=self.root/'simulation';simulate(self.source,out,self.client,count=5)
        return out
    def client_for_concerns(self):
        transport=ConcernTransport();return ModelBridgeClient('https://offline.example/model','offline-token','offline-model',transport),transport
    def test_excludes_buyers_and_purchase_readiness_checks(self):
        source=self.make_source();data=prepare_sources(source)
        self.assertEqual(data['completed_customers'],5)
        for signal in data['rejection_catalog']:
            self.assertNotEqual(signal['decision'],'choose_product')
            self.assertNotIn('purchase_checks',signal)
            self.assertNotIn('Before paying',signal['concern'])
    def test_generic_generation_has_supported_concerns_and_counts_without_terac(self):
        source=self.make_source();client,t=self.client_for_concerns();out=self.root/'concerns'
        generate(source,out,client);result=read(out/'concerns.json')
        self.assertEqual(len(result['concerns']),1) # Never pad to five.
        self.assertGreater(result['concerns'][0]['affected_customer_count'],0)
        self.assertEqual(result['terac_status'],'not_connected_or_submitted')
        self.assertTrue((out/'concerns.html').exists())
        calls=t.calls;generate(source,out,client,resume=True);self.assertEqual(t.calls,calls)
        self.assertFalse(read(out/'manifest.json')['terac_connected'])
    def test_unknown_source_reference_withholds_concern_without_blocking_report(self):
        source=self.make_source();client,t=self.client_for_concerns();t.unknown=True;out=self.root/'invalid'
        generate(source,out,client)
        self.assertTrue((out/'concerns.html').exists())
        self.assertEqual(read(out/'concerns.json')['concerns'],[])
        self.assertEqual(read(out/'concerns.json')['withheld_concern_count'],1)
        self.assertEqual(read(out/'withheld-concerns.json')[0]['invalid_source_ids'],['invented'])
        self.assertIn('withheld',read(out/'concerns.json')['limitations'][-1])
        self.assertTrue(read(out/'concerns-raw.json')['concerns'])
    def test_all_buyers_needs_zero_model_calls(self):
        source=self.make_source()
        # Build a genuine all-buyer fixture through another offline simulation.
        pop=read(self.source/'customers.json')
        for c in pop['customers']:
            c['budget'].update(maximum=10000,upfront_maximum=10000)
            c['requirements']=[{'attribute':'price','operator':'lte','constraint':'hard','value':10000,'unit':c['budget']['currency']}]
        save(self.source/'customers.json',pop)
        source=self.root/'buyers';simulate(self.source,source,self.client,count=5)
        client,t=self.client_for_concerns();out=self.root/'none';generate(source,out,client)
        self.assertEqual(t.calls,0);self.assertEqual(read(out/'concerns.json')['concerns'],[])
    def test_partial_results_are_disclosed_and_cannot_include_unsaved_customers(self):
        source=self.make_source();(source/'customer-005.json').unlink()
        data=prepare_sources(source);self.assertEqual(data['completed_customers'],4)
        enriched=enrich({'concerns':[],'limitations':['Partial fixture']},data)
        self.assertTrue(enriched['partial_customer_results'])
    def test_large_catalog_uses_bounded_grouping_with_all_source_ids_allowed(self):
        source=self.make_source()
        import unittest.mock
        data=prepare_sources(source);base=data['rejection_catalog'][0]
        data['rejection_catalog']=[{**base,'source_objection_id':f'signal-test-{i}'} for i in range(90)]
        client,t=self.client_for_concerns();out=self.root/'batches'
        with unittest.mock.patch('customer_simulation.review_concerns.prepare_sources',return_value=data):generate(source,out,client)
        self.assertEqual(t.calls,4)
        refs=read(out/'concerns.json')['concerns'][0]['source_objection_ids']
        self.assertEqual(len(refs),90);self.assertEqual(len(set(refs)),90)
    def test_named_specialist_is_not_hired_by_generation(self):
        source=self.make_source();client,t=self.client_for_concerns();out=self.root/'planning';generate(source,out,client)
        self.assertEqual(read(out/'manifest.json')['experts_contacted'],0)
        self.assertNotIn('TERAC_API_KEY',json.dumps(t.payloads))

class SupportedConcernTests(unittest.TestCase):
 def test_mixed_concerns_preserve_only_fully_cited_groups(self):
  from customer_simulation.review_concerns import retain_supported_groups
  import copy
  base={'title':'Supported','explanation':'Some customers raised this concern.','why_human_review':'A specialist can investigate.','suggested_expertise':'Product specialist','review_question':'What should change?','proposed_test':'Compare two options.','success_criterion':'Clear evidence of usefulness.','helpfulness':'uncertain','helpfulness_reason':'Needs validation.','source_objection_ids':['signal-1']}
  bad=copy.deepcopy(base);bad['title']='Unsupported';bad['source_objection_ids']=['invented']
  result,withheld=retain_supported_groups({'concerns':[base,bad],'limitations':['Synthetic feedback only.']},{'signal-1'})
  self.assertEqual([c['title'] for c in result['concerns']],['Supported']);self.assertEqual(len(withheld),1)
  with self.assertRaises(ValueError):validate_groups({'concerns':[bad],'limitations':['Synthetic feedback only.']},{'signal-1'})
