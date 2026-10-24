"""Full compact contract conversion tests: no network or AI calls."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from customer_generation.compact import category_catalog,construct_specification
from customer_generation.config import AdapterConfig
from customer_generation.pipeline import run_generation
from customer_generation.sampling import generate_population
from customer_generation.state import StageResponse
from customer_generation.tools.live import LiveBackend
from customer_generation.validation import ContractError
import test_worker_complete_responses as full
ROOT,WORKING,EXPORT,load=full.ROOT,full.WORKING,full.EXPORT,full.load


class CompactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        full.CompleteWorkerResponses.setUpClass.__func__(cls)
        cls.proposal=load(ROOT/'backend/tests/fixtures/sony-compact/proposal.json')

    tearDownClass=classmethod(full.CompleteWorkerResponses.tearDownClass.__func__)
    bridge=full.CompleteWorkerResponses.bridge

    def test_compact_full_worker_decode_construct_and_sample(self):
        for stage in ['compact_propose','compact_correct']:
            r=self.bridge(stage,self.proposal)
            self.assertTrue(r['wire_valid']);self.assertEqual(r['status'],200)
            self.assertEqual(r['response']['data'],self.proposal)
            spec=construct_specification(r['response']['data'],self.brief,self.evidence,50,42)
            customers=generate_population(spec,self.evidence)
            self.assertEqual(customers['count'],50)
            self.assertEqual(customers,generate_population(spec,self.evidence))

    def test_brief_currency_overrides_model_prose(self):
        proposal=copy.deepcopy(self.proposal)
        proposal['market']['currency']='USD (assumed from price)'
        brief=copy.deepcopy(self.brief);brief['price']['currency']='USD'
        spec=construct_specification(proposal,brief,self.evidence,50,42)
        self.assertEqual(spec['market']['currency'],'USD')
        self.assertEqual(spec['attributes']['price']['unit'],'USD')
        self.assertTrue(all(s['fields']['budget.currency']['rule']['value']=='USD' for s in spec['segments']))
        self.assertEqual(proposal['market']['currency'],'USD (assumed from price)')

    def test_compact_schema_is_identity_wire_without_maps_tags_or_refs(self):
        schema=load(WORKING/'policy.json')['stages']['compact_propose']['output_schema']
        def walk(s):
            if isinstance(s,dict):
                self.assertNotIn('$ref',s)
                if 'properties' in s:
                    self.assertEqual(set(s['required']),set(s['properties']))
                    self.assertFalse(s['additionalProperties'])
                for v in s.values():walk(v)
            elif isinstance(s,list):
                for v in s:walk(v)
        walk(schema)
        r=self.bridge('compact_propose',self.proposal)
        self.assertEqual(r['decoded'],self.proposal)

    def test_compact_duplicate_missing_unknown_slots_and_bad_values_rejected(self):
        for mutation in ['duplicate','missing','unknown','type','count','range','source','weights']:
            with self.subTest(mutation=mutation):
                p=copy.deepcopy(self.proposal);s=p['segments'][0]
                if mutation=='duplicate':s['category_values'].append(copy.deepcopy(s['category_values'][0]))
                if mutation=='missing':s['category_values'].pop()
                if mutation=='unknown':s['category_values'][0]['slot']=31
                if mutation=='type':s['category_values'][0].update(text_values=[],number_values=[1])
                if mutation=='count':s['count']+=1
                if mutation=='range':s['budget_min']=s['budget_max']+1
                if mutation=='source':s['rationale']['source_ids']=['invented']
                if mutation=='weights':s['tradeoffs'][0]['weight']=0.99
                with self.assertRaises(ContractError):construct_specification(p,self.brief,self.evidence,50,42)

    def test_compact_actual_adapter_full_pipeline_and_targeted_correction(self):
        test=self
        class Model:
            calls=[]
            def call(self,stage,payload,allowances,output_schema):
                self.calls.append(stage)
                if stage=='review':
                    data=copy.deepcopy(test.review)
                    if self.calls.count('review')==1:
                        data['decision']='revise';data['findings']=[{'code':'offline-revision','severity':'warning','message':'Synthetic correction-path exercise only.','source_ids':[]}]
                else:
                    test.assertIn(stage,{'compact_propose','compact_correct'})
                    test.assertNotIn('specification',payload)
                    test.assertEqual(payload['category_catalog'],category_catalog(test.evidence))
                    r=test.bridge(stage,test.proposal);test.assertEqual(r['status'],200)
                    data=r['response']['data']
                return StageResponse(data,1,1,0,metadata={'mocked_gateway':True})
        model=Model()
        config=AdapterConfig('offline-exa','https://offline.invalid','offline-token','offline-model')
        backend=LiveBackend(config,model=model,proposal_format='compact')
        class SavedResearch:
            mode='live';name='offline-compact-test'
            def execute(self,stage,payload,allowances):
                if stage=='research':return StageResponse(test.evidence,0,0,0,metadata={'test_fixture':True})
                return backend.execute(stage,payload,allowances)
        with tempfile.TemporaryDirectory() as directory:
            state=run_generation(self.brief,SavedResearch(),directory,'compact-sony',target_count=50,seed=42)
            self.assertEqual(state.status,'completed',state.error)
            self.assertEqual(state.corrections,1)
            self.assertEqual(model.calls,['compact_propose','review','compact_correct','review'])
            self.assertEqual(len(load(Path(directory)/'compact-sony/customers.json')['customers']),50)
            self.assertTrue((Path(directory)/'compact-sony/call-02-compact-limitations.json').exists())

    def test_unknown_context_is_not_promoted_to_market_evidence(self):
        evidence=copy.deepcopy(self.evidence);unknown=copy.deepcopy(evidence['findings'][0]);unknown.update(finding_id='unmeasured_wtp',subject='Customers',attribute='willingness_to_pay',value=None,unit=None,basis='unknown',source_ids=[],note='Not measured');evidence['findings'].append(unknown)
        # Reuse a known valid rationale and add the exact class of bad reference.
        proposal=copy.deepcopy(self.proposal)
        finding=next(f for f in evidence['findings'] if f['basis'] not in {'unknown','assumption'})
        proposal['segments'][0]['rationale']={'basis':'market_evidence','source_ids':finding['source_ids'],'finding_ids':[finding['finding_id'],'unmeasured_wtp'],'note':'One finding illustrates a situation; willingness to pay remains unknown.'}
        spec=construct_specification(proposal,self.brief,evidence,50,42)
        rationale=spec['segments'][0]['rationale']
        self.assertEqual(rationale['finding_ids'],[finding['finding_id']]);self.assertIn('unmeasured_wtp',rationale['note'])
        self.assertEqual(proposal['segments'][0]['rationale']['finding_ids'],[finding['finding_id'],'unmeasured_wtp'])
        proposal['segments'][0]['rationale']['finding_ids']=['unmeasured_wtp'];proposal['segments'][0]['rationale']['source_ids']=[]
        spec=construct_specification(proposal,self.brief,evidence,50,42)
        self.assertEqual(spec['segments'][0]['rationale']['basis'],'assumption')
        self.assertEqual(spec['segments'][0]['rationale']['finding_ids'],[])
        proposal['segments'][0]['rationale']['finding_ids']=['made-up-finding']
        with self.assertRaises(ContractError):construct_specification(proposal,self.brief,evidence,50,42)

    def test_existing_policy_instructions_unchanged(self):
        previous=load(EXPORT/'policy.json')['stages'];current=load(WORKING/'policy.json')['stages']
        for stage in previous:
            if stage!='review':self.assertEqual(previous[stage],current[stage])
        self.assertEqual(previous['review']['output_schema'],current['review']['output_schema'])

    def test_compact_bounds_and_enums_match_customer_contract(self):
        segment=load(ROOT/'data/schemas/compact-proposal.schema.json')['properties']['segments']['items']['properties']
        customer=load(ROOT/'data/schemas/customer-v2.schema.json')['properties']
        pairs=[('action_budget',customer['decision_style']['properties']['evaluation_action_budget']),
               ('deadline_days',customer['urgency']['properties']['deadline_days'])]
        for field,target in pairs:
            compact=segment[field]['items']
            self.assertGreaterEqual(compact['minimum'],target['minimum'])
            if 'maximum' in target:self.assertLessEqual(compact['maximum'],target['maximum'])
        for field,target in [('research_effort','research_effort'),('evidence_need','evidence_need'),('familiarity','category_familiarity')]:
            self.assertLessEqual(set(segment[field]['items']['enum']),set(customer['decision_style']['properties'][target]['enum']))

    def test_invalid_deadline_and_action_budget_rejected_before_sampling(self):
        for field,value in [('action_budget',6),('deadline_days',0)]:
            p=copy.deepcopy(self.proposal);p['segments'][0][field]=[value]
            with self.assertRaises(ContractError):construct_specification(p,self.brief,self.evidence,50,42)
            self.assertEqual(self.bridge('compact_propose',p)['status'],502)

    def test_valid_action_and_deadline_boundaries_sample_successfully(self):
        p=copy.deepcopy(self.proposal)
        for s in p['segments']:
            s['action_budget']=[1,5];s['deadline_days']=[1,3650]
        spec=construct_specification(p,self.brief,self.evidence,50,42)
        self.assertEqual(generate_population(spec,self.evidence)['count'],50)

if __name__=='__main__':unittest.main()
