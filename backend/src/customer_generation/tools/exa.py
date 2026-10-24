"""Exa search + contents adapter, preserving bounded source text and estimated cost.
Official contract: https://exa.ai/docs/reference/search
"""
import hashlib
import math
from urllib.parse import urlsplit,urlunsplit
from ..state import utc_now
from .http import JsonTransport


class ResearchResponseError(RuntimeError):
    pass


class ExaClient:
    endpoint='https://api.exa.ai/search'
    def __init__(self,api_key,transport=None):
        self._api_key=api_key;self.transport=transport or JsonTransport()
    def search(self,query,*,num_results=3,text_characters=1200,timeout=30):
        if not isinstance(query,str) or not query.strip() or len(query)>1500:
            raise ValueError('Search query must contain 1–1500 characters')
        if type(num_results) is not int or not 1<=num_results<=10:
            raise ValueError('Research result limit must be 1–10')
        if type(text_characters) is not int or not 1<=text_characters<=4000:
            raise ValueError('Research text limit must be 1–4000')
        data=self.transport.post(self.endpoint,{'x-api-key':self._api_key},
            {'query':query,'type':'auto','numResults':num_results,'contents':{'text':True}},timeout)
        cost=data.get('costDollars',{}).get('total')
        if type(cost) not in (int,float) or not math.isfinite(cost) or cost<0:
            raise ResearchResponseError('Exa cost estimate is missing or invalid; incurred cost is unknown')
        if not isinstance(data.get('results'),list):
            raise ResearchResponseError('Exa returned invalid results')
        sources=[];snippets=[];seen=set();now=utc_now()
        for result in data['results'][:num_results]:
            if not isinstance(result,dict):continue
            url=result.get('url');text=result.get('text')
            if not isinstance(url,str):continue
            parsed=urlsplit(url)
            if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:continue
            # Preserve query parameters (they may identify a different page); discard fragment.
            url=urlunsplit((parsed.scheme,parsed.netloc,parsed.path,parsed.query,''))
            if url in seen:continue
            if not isinstance(text,str) or not text.strip():
                highlights=result.get('highlights',[])
                text='\n'.join(t for t in highlights if isinstance(t,str)) if isinstance(highlights,list) else ''
            if not text.strip():continue
            seen.add(url);sid='exa-'+hashlib.sha256(url.encode()).hexdigest()[:16]
            sources.append({'source_id':sid,'url':url,'retrieved_at':now,'title':str(result.get('title') or url)[:300]})
            snippets.append({'source_id':sid,'text':text[:text_characters],
                'truncated':len(text)>text_characters,'content_status':'untrusted_retrieved_text'})
        return {'sources':sources,'snippets':snippets,'estimated_cost_usd':float(cost),
            'request_id':data.get('requestId'),'query':query,'limitations':['Exa costDollars is a provider estimate, not verified account billing.','Text is bounded; missing context and source meaning need review.']}
