"""Bounded Whop API calls; no credential-bearing redirects or automatic retries."""
import json,re
from urllib.request import Request,build_opener
from urllib.error import HTTPError,URLError
from customer_generation.tools.http import NoRedirect
from .config import resource

class WhopError(RuntimeError):
    def __init__(self,status=None,permissions=()):
        self.status=status
        self.permissions=tuple(permissions)
        suffix='; missing permissions: '+', '.join(self.permissions) if self.permissions else ''
        super().__init__('Whop API unavailable' if status is None else f'Whop API rejected request (HTTP {status}{suffix})')

class Client:
    def __init__(self,config):self.config=config
    def call(self,method,path,payload=None,*,idempotency_key=None):
        if not self.config.api_key:raise ValueError('WHOP_API_KEY is missing')
        headers={'Authorization':'Bearer '+self.config.api_key,'Accept':'application/json','Content-Type':'application/json','Api-Version-Date':self.config.api_version}
        if idempotency_key:headers['Idempotency-Key']=idempotency_key
        req=Request(self.config.api_base+path,method=method,headers=headers,data=None if payload is None else json.dumps(payload,allow_nan=False).encode())
        try:
            with build_opener(NoRedirect()).open(req,timeout=15) as response:
                raw=response.read(1_000_001)
                if len(raw)>1_000_000:raise WhopError()
                result=json.loads(raw)
                if not isinstance(result,dict):raise WhopError()
                return result
        except HTTPError as e:
            permissions=[]
            try:
                error=json.loads(e.read(8000)).get('error',{})
                message=error.get('message','')
                if 'missing' in message.lower() and 'permission' in message.lower():permissions=re.findall(r'\b[a-z_]+(?::[a-z_]+){1,3}\b',message)
            except (ValueError,AttributeError):pass
            raise WhopError(e.code,permissions) from None
        except (URLError,TimeoutError,ValueError):raise WhopError() from None
    def companies(self):return self.call('GET','/companies')
    def payment(self,payment_id):return self.call('GET','/payments/'+resource(payment_id,'pay'))
    def plan(self,plan_id):return self.call('GET','/variants/'+resource(plan_id,'plan'))
    def checkout(self,plan_id,order_id,redirect_url):
        return self.call('POST','/checkout_configurations',{'mode':'payment','plan_id':resource(plan_id,'plan'),
            'metadata':{'research_order_id':order_id},'redirect_url':redirect_url},idempotency_key='research-checkout-'+order_id)

def setup_payloads(config):
    resource(config.company_id,'biz')
    return {'product':{'account_id':config.company_id,'title':'Customer Research Snapshot','visibility':'hidden',
        'description':'Competitor evidence, synthetic customer profiles and a research summary. Synthetic findings are hypotheses, not surveyed buyers or revenue forecasts.'},
        'variant':{'account_id':config.company_id,'title':'Snapshot — one product','plan_type':'one_time','currency':'usd',
        'initial_price':float(config.price),'renewal_price':0,'release_method':'buy_now','visibility':'hidden','adaptive_pricing_enabled':False,
        'unlimited_stock':False,'stock':0}}
