"""Payment trust-boundary tests. Whop API and payments are entirely synthetic."""
import base64,copy,hashlib,hmac,io,json,tempfile,time,unittest
from unittest.mock import patch
from urllib.error import HTTPError
from dataclasses import replace
from pathlib import Path
from whop_integration.app import application,MAX_BODY
from whop_integration.client import Client,WhopError,setup_payloads
from whop_integration.config import Config
from whop_integration.service import Service,verify_payment
from whop_integration.signatures import verify,SignatureError
from whop_integration.store import Store

SECRET='ws_offline_test_signing_secret_only'

def signed(event,*,stamp=None,secret=SECRET):
    stamp=str(int(time.time()) if stamp is None else stamp)
    body=json.dumps(event,separators=(',',':')).encode()
    value=base64.b64encode(hmac.new(secret.encode(),event['id'].encode()+b'.'+stamp.encode()+b'.'+body,hashlib.sha256).digest()).decode()
    return body,{'webhook-id':event['id'],'webhook-timestamp':stamp,'webhook-signature':'v1,'+value}

class FakeClient:
    def __init__(self,c):self.c=c;self.calls=[];self.payment_data={};self.fail=False
    def plan(self,plan_id):
        return {'id':plan_id,'account':{'id':self.c.company_id},'product':{'id':self.c.product_id},'plan_type':'one_time',
            'currency':'usd','initial_price':9,'renewal_price':0,'adaptive_pricing_enabled':False}
    def checkout(self,plan_id,order_id,redirect):
        self.calls.append((plan_id,order_id,redirect))
        return {'id':'ch_'+order_id,'purchase_url':'https://whop.com/checkout/ch_'+order_id}
    def payment(self,pid):
        if self.fail:raise WhopError(503)
        return copy.deepcopy(self.payment_data)

class WhopPhase1Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.c=Config(api_key='offline-api-key',webhook_secret=SECRET,company_id='biz_demo',product_id='prod_demo',plan_id='plan_demo',
            public_url='https://research.example',environment='production',sales_enabled=True,database=Path(self.tmp.name)/'orders.sqlite3')
        self.store=Store(self.c.database);self.client=FakeClient(self.c);self.service=Service(self.c,self.store,self.client)
    def tearDown(self):self.tmp.cleanup()

    def order_and_payment(self):
        result,token=self.service.checkout();oid=result['order_id'];o=self.store.order(oid)
        p={'id':'pay_demo','company':{'id':'biz_demo'},'product':{'id':'prod_demo'},'plan':{'id':'plan_demo'},
            'checkout_configuration_id':o['checkout_id'],'metadata':{'research_order_id':oid},'currency':'usd',
            'status':'paid','substatus':'succeeded','subtotal':9,'total':9.80,'refunded_amount':0,
            'paid_at':'2026-10-24T16:00:00Z','user':{'id':'user_demo'}}
        self.client.payment_data=p
        return oid,token,p

    def event(self,payment_id='pay_demo',event_id='msg_demo',kind='payment.succeeded'):
        data={'id':payment_id} if kind.startswith('payment.') else {'id':'rf_demo','payment':{'id':payment_id}}
        return {'id':event_id,'type':kind,'api_version':'v1','api_version_date':self.c.api_version,'account_id':'biz_demo','data':data}

    def request(self,path,method='GET',body=b'',cookie='',headers=None):
        env={'REQUEST_METHOD':method,'PATH_INFO':path,'CONTENT_LENGTH':str(len(body)),'wsgi.input':io.BytesIO(body),'HTTP_COOKIE':cookie}
        env.update({'HTTP_'+k.upper().replace('-','_'):v for k,v in (headers or {}).items()})
        captured={}
        def start(status,h):captured.update(status=int(status.split()[0]),headers=dict(h))
        result=b''.join(application(self.service)(env,start))
        return captured,json.loads(result) if captured['headers']['Content-Type']=='application/json' else result.decode()

    def test_sales_closed_blocks_api_calls(self):
        self.service.config=replace(self.c,sales_enabled=False)
        response,_=self.request('/api/checkout','POST',b'{}')
        self.assertEqual(response['status'],403);self.assertEqual(self.client.calls,[])

    def test_checkout_does_not_mark_paid_and_session_token_is_hashed(self):
        oid,token,_=self.order_and_payment();order=self.store.order(oid)
        self.assertEqual(order['status'],'awaiting_payment');self.assertNotEqual(order['token_hash'],token)
        self.assertFalse(self.service.status(oid,token)['intake_unlocked'])
        self.assertIsNone(self.service.status(oid,'wrong-token'))

    def test_checkout_http_cookie_and_reject_client_price(self):
        response,_=self.request('/api/checkout','POST',b'{"amount":0}')
        self.assertEqual(response['status'],400)
        response,data=self.request('/api/checkout','POST',b'{}')
        self.assertEqual(response['status'],201)
        for flag in ['HttpOnly','Secure','SameSite=Lax']:self.assertIn(flag,response['headers']['Set-Cookie'])
        r,_=self.request('/api/orders/'+data['order_id']);self.assertEqual(r['status'],404)
        r,_=self.request('/api/orders/'+data['order_id'],cookie=response['headers']['Set-Cookie'].split(';')[0]);self.assertEqual(r['status'],200)

    def test_redirect_is_never_payment_proof(self):
        oid,token,_=self.order_and_payment()
        self.request('/checkout/return')
        self.assertFalse(self.service.status(oid,token)['intake_unlocked'])

    def test_signature_literal_secret_tampering_staleness_and_rotation(self):
        event=self.event();body,headers=signed(event)
        self.assertEqual(verify(body,headers,SECRET),event)
        with self.assertRaises(SignatureError):verify(body+b' ',headers,SECRET)
        with self.assertRaises(SignatureError):verify(body,headers,'wrong')
        old,oldh=signed(event,stamp=int(time.time())-301)
        with self.assertRaises(SignatureError):verify(old,oldh,SECRET)
        future,futureh=signed(event,stamp=int(time.time())+301)
        with self.assertRaises(SignatureError):verify(future,futureh,SECRET)
        headers['webhook-signature']='v1,oldsignature '+headers['webhook-signature']
        self.assertEqual(verify(body,headers,SECRET),event)

    def test_signed_event_enqueues_without_synchronous_remote_calls(self):
        oid,token,_=self.order_and_payment();body,h=signed(self.event())
        self.client.fail=True
        response,result=self.request('/api/webhooks/whop','POST',body,headers=h)
        self.assertEqual(response['status'],200)
        self.assertFalse(self.service.status(oid,token)['intake_unlocked'])

    def test_paid_event_verified_against_remote_current_state(self):
        oid,token,_=self.order_and_payment();body,h=signed(self.event())
        self.service.receive(body,h)
        self.assertEqual(self.service.drain_once()['result'],'paid')
        self.assertTrue(self.service.status(oid,token)['intake_unlocked'])

    def test_duplicate_deliveries_and_durable_restart(self):
        oid,token,_=self.order_and_payment();body,h=signed(self.event())
        self.assertFalse(self.service.receive(body,h)['duplicate']);self.assertTrue(self.service.receive(body,h)['duplicate'])
        self.service=Service(self.c,Store(self.c.database),self.client)
        self.assertEqual(self.service.drain_once()['result'],'paid')
        self.assertEqual(self.service.drain_once(),{'processed':False})

    def test_conflicting_duplicate_event_rejected(self):
        self.order_and_payment();body,h=signed(self.event());self.service.receive(body,h)
        body,h=signed(self.event(kind='payment.failed'))
        with self.assertRaises(ValueError):self.service.receive(body,h)

    def test_wrong_account_and_version_rejected(self):
        for field,value in [('account_id','biz_other'),('api_version','v5'),('api_version_date','old')]:
            e=self.event();e[field]=value;body,h=signed(e)
            with self.assertRaises((PermissionError,ValueError)):self.service.receive(body,h)

    def test_event_alone_cannot_forge_success(self):
        oid,token,p=self.order_and_payment();p.update(status='pending',substatus='pending');self.client.payment_data=p
        body,h=signed(self.event());self.service.receive(body,h)
        self.assertEqual(self.service.drain_once()['result'],'not_paid')
        self.assertFalse(self.service.status(oid,token)['intake_unlocked'])

    def test_payment_scope_amount_currency_and_test_checks(self):
        oid,_,p=self.order_and_payment();order=self.store.order(oid)
        edits=[{'company':{'id':'biz_other'}},{'plan':{'id':'plan_other'}},{'product':{'id':'prod_other'}},
            {'metadata':{'research_order_id':'other'}},{'checkout_configuration_id':'ch_other'},
            {'currency':'eur'},{'subtotal':0},{'total':0},{'refunded_amount':9},{'paid_at':None},{'user':None},{'test_mode':True},{'subtotal':float('nan')}]
        for edit in edits:
            with self.subTest(edit=edit):self.assertNotEqual(verify_payment(order,{**p,**edit},self.c),'paid')

    def test_reversal_is_terminal_even_with_later_success_delivery(self):
        oid,token,p=self.order_and_payment();body,h=signed(self.event());self.service.receive(body,h);self.service.drain_once()
        self.client.payment_data={**p,'refunded_amount':9,'substatus':'refunded'}
        body,h=signed(self.event(event_id='msg_refund',kind='refund.updated'));self.service.receive(body,h)
        self.assertEqual(self.service.drain_once()['result'],'revoked');self.assertFalse(self.service.status(oid,token)['intake_unlocked'])
        self.client.payment_data=p
        body,h=signed(self.event(event_id='msg_late'));self.service.receive(body,h)
        self.assertEqual(self.service.drain_once()['result'],'revoked')

    def test_remote_outage_leaves_retryable_durable_event(self):
        self.order_and_payment();body,h=signed(self.event());self.service.receive(body,h);self.client.fail=True
        self.assertTrue(self.service.drain_once()['retry_pending'])
        with self.store.connect() as db:self.assertEqual(db.execute('SELECT status FROM events').fetchone()[0],'pending')

    def test_abandoned_event_lease_is_reclaimable(self):
        body,h=signed(self.event());self.service.receive(body,h)
        self.assertIsNotNone(self.store.claim(now=1000));self.assertIsNone(self.store.claim(now=1001));self.assertIsNotNone(self.store.claim(now=1061))

    def test_setup_creates_hidden_zero_stock_offer(self):
        payload=setup_payloads(self.c)
        self.assertEqual(payload['product']['visibility'],'hidden')
        self.assertEqual(payload['variant']['stock'],0);self.assertFalse(payload['variant']['unlimited_stock'])
        self.assertLessEqual(len(payload['variant']['title']),30)

    def test_cross_origin_and_oversized_request_rejected(self):
        r,_=self.request('/api/checkout','POST',b'{}',headers={'origin':'https://other.example'});self.assertEqual(r['status'],403)
        r,_=self.request('/api/webhooks/whop','POST',b'x'*(MAX_BODY+1));self.assertEqual(r['status'],413)

    def test_private_configuration_and_live_https_guard(self):
        self.assertNotIn(SECRET,repr(self.c));self.assertNotIn('offline-api-key',repr(self.c))
        with self.assertRaises(ValueError):replace(self.c,public_url='http://127.0.0.1:8080').validate()
        self.assertEqual(Config.from_env({'WHOP_DATABASE':''}).database,Path('backend/var/whop-sandbox.sqlite3'))

    def test_client_api_errors_never_expose_provider_body_or_key(self):
        with patch('whop_integration.client.build_opener') as opener:
            opener.return_value.open.side_effect=HTTPError('https://api.whop.com',400,'offline-api-key',{},io.BytesIO(b'private provider payload'))
            with self.assertRaises(WhopError) as caught:Client(self.c).companies()
            self.assertEqual(caught.exception.status,400)
            self.assertNotIn('offline-api-key',str(caught.exception));self.assertNotIn('private',str(caught.exception))

    def test_checkout_request_locks_plan_metadata_and_idempotency(self):
        class Capture(Client):
            def call(self,*args,**kwargs):self.captured=(args,kwargs);return {}
        c=Capture(self.c);c.checkout('plan_demo','order-demo','https://research.example/checkout/return')
        args,kwargs=c.captured
        self.assertEqual(args[0:2],('POST','/checkout_configurations'))
        self.assertEqual(args[2]['metadata'],{'research_order_id':'order-demo'})
        self.assertNotIn('price',args[2]);self.assertEqual(kwargs['idempotency_key'],'research-checkout-order-demo')

    def test_missing_signature_never_queues_payment(self):
        body,_=signed(self.event())
        r,_=self.request('/api/webhooks/whop','POST',body)
        self.assertEqual(r['status'],401);self.assertIsNone(self.store.claim())

    def test_plan_mismatch_blocks_checkout(self):
        self.client.plan=lambda _: {'id':'plan_other'}
        with self.assertRaises(ValueError):self.service.checkout()
        self.assertEqual(self.client.calls,[])

if __name__=='__main__':unittest.main()
