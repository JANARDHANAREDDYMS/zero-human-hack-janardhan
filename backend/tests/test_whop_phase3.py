"""Paid fulfillment integration, with offline generation and synthetic payments."""
import json,io,unittest
from pathlib import Path
from dataclasses import replace
from whop_integration.fulfillment import Fulfillment
from whop_integration.app import application
from whop_integration.store import Store
from customer_generation.state import StageResponse
from customer_generation.instructions import fixture_checks
import test_whop_phase1 as phase1
ROOT=Path(__file__).resolve().parents[2]

class WhopFulfillmentTests(unittest.TestCase):
    setUpBase=phase1.WhopPhase1Tests.setUp
    tearDown=phase1.WhopPhase1Tests.tearDown
    order_and_payment=phase1.WhopPhase1Tests.order_and_payment
    def setUp(self):
        self.setUpBase();self.calls=[];self.refund_during_run=False;test=self
        class Backend:
            name='offline-paid-handoff';mode='offline_fixture'
            def execute(self,stage,payload,limits):
                test.calls.append(stage);folder=ROOT/'data/products/sony-speaker/research-v2'
                if stage=='research':data=json.loads((folder/'evidence.json').read_text());data['product_id']=payload['brief']['product_id']
                elif stage=='propose':data=json.loads((folder/'specification.json').read_text());data['product_id']=payload['brief']['product_id']
                elif stage=='review':
                    data={'decision':'accept','summary':'Offline test only','checks':fixture_checks(),'findings':[]}
                    if test.refund_during_run:test.client.payment_data['refunded_amount']=9
                else:raise AssertionError(stage)
                return StageResponse(data,1,1,0)
        self.root=Path(self.tmp.name)/'runs'
        self.fulfill=Fulfillment(self.service,self.root,backend_factory=Backend)
    def paid_job(self):
        oid,token,p=self.order_and_payment()
        with self.store.connect() as db:db.execute("UPDATE orders SET status='paid',payment_id='pay_demo' WHERE id=?",(oid,))
        job=self.service.intake(oid,token,{'fields':{'name':'Speaker','description':'Portable speaker'}},submit=True)
        return oid,token,job
    def test_complete_paid_intake_to_report_and_no_duplicate_run(self):
        oid,token,job=self.paid_job();result=self.fulfill.process_once()
        self.assertEqual(result['status'],'completed');self.assertEqual(self.calls,['research','propose','review'])
        report=self.fulfill.result(oid,token)
        self.assertTrue(report['report_ready']);self.assertEqual(report['count'],50)
        self.assertEqual(len(report['summary']),5);self.assertEqual(sum(s['count'] for s in report['segments']),50)
        self.assertEqual(len(self.fulfill.result(oid,token,'customers')['customers']),50)
        self.assertFalse(self.fulfill.process_once()['processed']);self.assertEqual(len(self.calls),3)
        self.assertEqual(Store(self.c.database).research_job(oid)['status'],'completed')
    def test_refunded_before_start_makes_no_generation_calls(self):
        oid,token,_=self.paid_job();self.client.payment_data['refunded_amount']=9
        self.fulfill.process_once();self.assertEqual(self.calls,[])
        self.assertEqual(self.store.research_job(oid)['status'],'payment_revoked')
    def test_refunded_during_generation_never_publishes(self):
        oid,token,_=self.paid_job();self.refund_during_run=True
        self.fulfill.process_once();self.assertEqual(self.store.research_job(oid)['status'],'payment_revoked')
        with self.assertRaises(PermissionError):self.fulfill.result(oid,token)
    def test_refunded_after_completion_blocks_report_and_download(self):
        oid,token,_=self.paid_job();self.fulfill.process_once();self.client.payment_data['refunded_amount']=9
        with self.assertRaises(PermissionError):self.fulfill.result(oid,token,'customers')
        self.assertEqual(self.store.order(oid)['status'],'revoked')
    def test_wrong_owner_unpaid_and_environment_cannot_read(self):
        oid,token,_=self.paid_job();self.fulfill.process_once()
        with self.assertRaises(LookupError):self.fulfill.result(oid,'wrong-token')
        self.service.config=replace(self.c,environment='sandbox')
        with self.assertRaises(PermissionError):self.fulfill.result(oid,token)
    def test_provider_failure_before_start_does_not_spend_or_retry(self):
        oid,_,_=self.paid_job();self.client.fail=True
        self.assertEqual(self.fulfill.process_once()['status'],'failed');self.assertEqual(self.calls,[])
        self.assertFalse(self.fulfill.process_once()['processed'])
    def test_changed_artifacts_cannot_be_delivered(self):
        oid,token,_=self.paid_job();self.fulfill.process_once()
        folder=self.root/self.store.research_job(oid)['run_id'];(folder/'customers.json').write_text('{}')
        with self.assertRaises(ValueError):self.fulfill.result(oid,token)
    def test_claim_is_exclusive_and_crashed_job_not_automatically_retried(self):
        oid,_,_=self.paid_job();first=self.store.claim_research(self.c.environment)
        self.assertIsNotNone(first);self.assertIsNone(Store(self.c.database).claim_research(self.c.environment))
        self.assertEqual(self.store.research_job(oid)['status'],'processing')
    def test_incomplete_generation_does_not_deliver(self):
        oid,token,_=self.paid_job()
        class State:status='incomplete'
        self.fulfill.generator=lambda *a,**k:State()
        self.assertEqual(self.fulfill.process_once()['status'],'needs_attention')
        self.assertFalse(self.fulfill.result(oid,token)['report_ready'])
    def test_http_report_is_cookie_protected(self):
        oid,token,_=self.paid_job();self.fulfill.process_once();app=application(self.service,self.fulfill)
        def request(cookie):
            result={};env={'REQUEST_METHOD':'GET','PATH_INFO':f'/api/orders/{oid}/results','HTTP_COOKIE':cookie}
            raw=b''.join(app(env,lambda s,h:result.update(status=int(s.split()[0]))))
            return result['status'],json.loads(raw)
        self.assertEqual(request('')[0],404)
        status,data=request('research_order_token='+token)
        self.assertEqual(status,200);self.assertTrue(data['report_ready'])
        self.assertNotIn('run_id',data)
if __name__=='__main__':unittest.main()
