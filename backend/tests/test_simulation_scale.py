"""Scaling and cost-preserving resume; all model responses are offline fixtures."""
import copy
from pathlib import Path
import test_concept_simulation as fixtures
from customer_generation.tools.llm import ModelBridgeClient
from customer_simulation.concept import run,report_call_count
from customer_simulation.pipeline import read,save

import unittest
class SimulationScaleTests(unittest.TestCase):
    setUp=fixtures.ConceptTests.setUp
    def test_25_and_50_customers_complete_with_dynamic_budget_and_full_report_coverage(self):
        original=read(self.source/'customers.json')
        for count in [25,50]:
            with self.subTest(count=count):
                transport=fixtures.Transport();client=ModelBridgeClient('https://offline.example/run','offline-token','offline-model',transport)
                out=self.root/f'scale-{count}';run(self.source,out,client,count=count)
                manifest=read(out/'manifest.json');coverage=read(out/'report-narrative.json')['coverage']
                self.assertEqual(manifest['status'],'completed')
                self.assertEqual(len(coverage['covered_customer_ids']),count)
                self.assertEqual(len(set(coverage['covered_customer_ids'])),count)
                self.assertEqual(len(transport.calls),count+report_call_count(count))
                self.assertEqual(sum(s['count'] for s in read(out/'summary.json')['segments'].values()),count)
                for body,data in transport.answers:
                    if body['stage']=='summarize_simulation':self.assertLessEqual(len(body['payload']['customers']),20)
                self.assertIn('All '+str(count)+' customer results were included',(out/'report.html').read_text())
    def test_500_distinct_fixture_customers_complete_with_bounded_synthesis(self):
        population=read(self.source/'customers.json');base=population['customers'];population['customers']=[]
        for index in range(500):
            c=copy.deepcopy(base[index%len(base)]);c['customer_id']=f'scale-fixture-{index:04}'
            population['customers'].append(c)
        population['count']=500;save(self.source/'customers.json',population)
        out=self.root/'scale-500';run(self.source,out,self.client,count=500)
        manifest=read(out/'manifest.json');narrative=read(out/'report-narrative.json')
        self.assertEqual(manifest['status'],'completed');self.assertEqual(len(narrative['coverage']['covered_customer_ids']),500)
        self.assertEqual(len(set(narrative['coverage']['covered_customer_ids'])),500)
        self.assertEqual(self.transport.calls.count('simulate_concept'),500)
        self.assertEqual(self.transport.calls.count('summarize_simulation'),report_call_count(500))
        self.assertEqual(read(out/'summary.json')['evaluated'],500)
        self.assertEqual(sum(s['count'] for s in read(out/'summary.json')['segments'].values()),500)
    def test_budget_stop_resumes_without_rebilling_completed_customers(self):
        class HighUsage(fixtures.Transport):
            def post(self,*args):
                answer=super().post(*args);answer['usage'].update(input_tokens=10000,output_tokens=200)
                return answer
        transport=HighUsage();client=ModelBridgeClient('https://offline.example/run','offline-token','offline-model',transport)
        out=self.root/'resume'
        with self.assertRaisesRegex(ValueError,'Insufficient remaining token budget'):
            run(self.source,out,client,count=25,total_token_limit=160000)
        before=read(out/'manifest.json')['completed'];self.assertGreater(before,0);self.assertLess(before,25)
        run(self.source,out,client,count=25,resume=True)
        self.assertEqual(transport.calls.count('simulate_concept'),25)
        self.assertEqual(read(out/'manifest.json')['status'],'completed')
    def test_reduction_accepts_child_references_outside_full_response_examples(self):
        out=self.root/'child-refs';run(self.source,out,self.client,count=25)
        payload=read(out/'report-input.json');data=read(out/'report-raw.json')
        full_examples={c['customer_id'] for c in payload['customers']}
        all_allowed={c['customer_id'] for c in payload['allowed_customer_references']}
        self.assertEqual(len(all_allowed),25)
        cited={cid for group in data['segments'] for cid in group['customer_ids']}
        self.assertTrue(cited-full_examples)
        self.assertTrue(cited<=all_allowed)
        from customer_simulation.concept import validate_narrative
        customers=read(out/'inputs.json')['customers']
        data['overview'][0]['customer_ids']=['not-a-covered-customer']
        with self.assertRaises(ValueError):validate_narrative(data,customers,allow_group_examples=True)
        data=read(out/'report-raw.json');first=data['segments'][0];other=next(c for c in customers if c['segment_id']!=first['segment_id'])
        first['customer_ids']=[other['customer_id']]
        with self.assertRaises(ValueError):validate_narrative(data,customers,allow_group_examples=True)
    def test_refuses_more_customers_than_exist(self):
        with self.assertRaises(ValueError):run(self.source,self.root/'no500',self.client,count=500)
        self.assertEqual(self.transport.calls,[])
