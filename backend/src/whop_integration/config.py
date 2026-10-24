from dataclasses import dataclass,field
from decimal import Decimal,InvalidOperation
import os,re
from pathlib import Path
from urllib.parse import urlsplit

def resource(value,prefix):
    if not re.fullmatch(prefix+r'_[A-Za-z0-9]+',value or ''):raise ValueError('Missing or invalid Whop '+prefix+' ID')
    return value

@dataclass(frozen=True)
class Config:
    api_key:str=field(repr=False,default='')
    webhook_secret:str=field(repr=False,default='')
    company_id:str=''
    product_id:str=''
    plan_id:str=''
    public_url:str='http://127.0.0.1:8080'
    environment:str='sandbox'
    sales_enabled:bool=False
    price:str='9.00'
    currency:str='usd'
    database:Path=Path('backend/var/whop-sandbox.sqlite3')
    api_version:str='2026-08-14'

    @property
    def api_base(self):
        return 'https://api.whop.com/api/v1' if self.environment=='production' else 'https://sandbox-api.whop.com/api/v1'

    @classmethod
    def from_env(cls,env=None):
        e=os.environ if env is None else env
        mode=e.get('WHOP_ENVIRONMENT','sandbox')
        c=cls(api_key=e.get('WHOP_API_KEY',''),webhook_secret=e.get('WHOP_WEBHOOK_SECRET',''),
            company_id=e.get('WHOP_COMPANY_ID',''),product_id=e.get('WHOP_PRODUCT_ID',''),plan_id=e.get('WHOP_PLAN_ID',''),
            public_url=e.get('WHOP_PUBLIC_URL','http://127.0.0.1:8080').rstrip('/'),environment=mode,
            sales_enabled=e.get('WHOP_SALES_ENABLED','false').lower()=='true',price=e.get('WHOP_PRICE_USD','9.00'),
            database=Path(e.get('WHOP_DATABASE') or f'backend/var/whop-{mode}.sqlite3'))
        c.validate();return c

    def validate(self):
        if self.environment not in {'sandbox','production'}:raise ValueError('WHOP_ENVIRONMENT must be sandbox or production')
        try:amount=Decimal(self.price)
        except InvalidOperation:raise ValueError('Invalid Whop price') from None
        if not amount.is_finite() or amount<1 or amount.as_tuple().exponent < -2:raise ValueError('Price must be positive USD with at most two decimals')
        u=urlsplit(self.public_url)
        if u.scheme not in {'https','http'} or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in {'','/'}:raise ValueError('Public URL must be an origin without credentials or a path')
        if u.scheme!='https' and u.hostname not in {'localhost','127.0.0.1'}:raise ValueError('Public URL requires HTTPS outside localhost')
        if self.sales_enabled:
            for value,prefix in [(self.company_id,'biz'),(self.product_id,'prod'),(self.plan_id,'plan')]:resource(value,prefix)
            if not self.api_key or not self.webhook_secret:raise ValueError('Checkout requires API key and webhook signing secret')
            if self.environment=='production' and u.scheme!='https':raise ValueError('Live checkout requires public HTTPS')
