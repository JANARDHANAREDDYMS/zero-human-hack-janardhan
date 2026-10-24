import hashlib,hmac,secrets,uuid
from decimal import Decimal,InvalidOperation
from urllib.parse import urljoin,urlsplit
from .client import WhopError
from .config import resource
from .signatures import verify

EVENTS={'payment.succeeded','payment.failed','payment.canceled','refund.created','refund.updated','dispute.created','dispute.updated'}

def money(value):
    if isinstance(value,bool) or value is None:raise ValueError('Missing amount')
    try:v=Decimal(str(value))
    except InvalidOperation:raise ValueError('Invalid amount') from None
    if not v.is_finite():raise ValueError('Invalid amount')
    return v

def verify_payment(order,p,config):
    """Only current Whop API state can unlock an order, never browser redirects."""
    seller=(p.get('company') or p.get('account') or {}).get('id')
    if order['environment']!=config.environment or seller!=order['company_id']:return 'seller_mismatch'
    if (p.get('plan') or {}).get('id')!=order['plan_id'] or (p.get('product') or {}).get('id')!=order['product_id']:return 'product_mismatch'
    if p.get('checkout_configuration_id')!=order['checkout_id']:return 'checkout_mismatch'
    if (p.get('metadata') or {}).get('research_order_id')!=order['id']:return 'order_mismatch'
    if p.get('currency')!=order['currency']:return 'currency_mismatch'
    if p.get('test_mode') is True or p.get('livemode') is False:
        if config.environment=='production':return 'test_payment'
    if p.get('status')!='paid' or p.get('substatus')!='succeeded':
        return 'revoked' if order['payment_id']==p.get('id') else 'not_paid'
    try:
        if money(p.get('refunded_amount'))!=0:return 'revoked' if order['payment_id']==p.get('id') else 'refunded'
        if money(p.get('subtotal'))!=money(order['amount']) or money(p.get('total'))<money(order['amount']):return 'amount_mismatch'
    except ValueError:return 'amount_unverified'
    if not p.get('paid_at') or not (p.get('user') or {}).get('id'):return 'payer_unverified'
    if order['payment_id'] and order['payment_id']!=p.get('id'):return 'payment_conflict'
    return 'paid'

class Service:
    def __init__(self,config,store,client):self.config=config;self.store=store;self.client=client

    def checkout(self):
        c=self.config
        if not c.sales_enabled:raise PermissionError('Sales are closed until fulfillment is ready')
        c.validate()
        plan=self.client.plan(c.plan_id)
        if ((plan.get('account') or {}).get('id')!=c.company_id or (plan.get('product') or {}).get('id')!=c.product_id
            or plan.get('id')!=c.plan_id or plan.get('plan_type')!='one_time' or plan.get('currency')!=c.currency
            or money(plan.get('initial_price'))!=money(c.price) or money(plan.get('renewal_price'))!=0
            or plan.get('adaptive_pricing_enabled') is not False):raise ValueError('Whop plan does not match configured one-time offer')
        oid=uuid.uuid4().hex;token=secrets.token_urlsafe(32)
        self.store.create_order(oid,token,c)
        try:
            checkout=self.client.checkout(c.plan_id,oid,c.public_url+'/checkout/return?order='+oid)
            resource(checkout.get('id'),'ch')
            url=urljoin('https://whop.com',checkout.get('purchase_url') or '')
            parsed=urlsplit(url)
            allowed={'whop.com','www.whop.com'}|({'sandbox.whop.com'} if c.environment=='sandbox' else set())
            if not checkout.get('purchase_url') or parsed.scheme!='https' or parsed.hostname not in allowed or parsed.username or parsed.password:raise ValueError('Invalid Whop checkout URL')
            self.store.bind_checkout(oid,checkout['id'],url)
            return {'order_id':oid,'checkout_url':url},token
        except Exception:
            self.store.checkout_failed(oid);raise

    def receive(self,body,headers):
        c=self.config
        if not c.webhook_secret or not c.company_id:raise RuntimeError('Webhook configuration is incomplete')
        event=verify(body,headers,c.webhook_secret)
        if event.get('api_version')!='v1' or event.get('api_version_date')!=c.api_version:raise ValueError('Unexpected webhook version')
        if event.get('account_id')!=c.company_id:raise PermissionError('Webhook account mismatch')
        if event.get('type') not in EVENTS:return {'received':True,'ignored':True}
        data=event.get('data') or {}
        payment_id=data.get('id') if event['type'].startswith('payment.') else (data.get('payment') or {}).get('id')
        resource(payment_id,'pay')
        fresh=self.store.enqueue(event,body,payment_id)
        return {'received':True,'duplicate':not fresh}

    def drain_once(self):
        event=self.store.claim()
        if not event:return {'processed':False}
        try:
            payment=self.client.payment(event['payment_id'])
            if payment.get('id')!=event['payment_id']:raise ValueError('Whop payment ID mismatch')
            result=self.store.apply(event['id'],payment,self.config,verify_payment)
            return {'processed':True,'result':result}
        except Exception:
            self.store.retry(event['id'],'verification_failed')
            return {'processed':False,'retry_pending':True}

    def status(self,oid,token):
        order=self.store.order(oid)
        if not order or not token or not hmac.compare_digest(order['token_hash'],hashlib.sha256(token.encode()).hexdigest()):return None
        return {'order_id':oid,'payment_status':order['status'],'fulfillment_status':order['fulfillment_status'],
            'environment':order['environment'],'intake_unlocked':order['status']=='paid'}

    def intake(self,oid,token,payload=None,*,submit=False):
        from .intake import prepare
        status=self.status(oid,token)
        if not status:raise LookupError('Order not found')
        if not status['intake_unlocked'] or status['environment']!=self.config.environment:raise PermissionError('Verified payment required')
        if payload is None:return self.store.intake_job(oid)
        prepared=prepare(oid,payload)
        if not submit:return prepared
        if not prepared['can_submit']:raise ValueError('Product name and description are required')
        source={'kind':'markdown','filename':payload['filename'],'text':payload['markdown']} if 'markdown' in payload else {'kind':'form'}
        return self.store.submit_intake(oid,prepared,source)
