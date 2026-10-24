"""Small MCP client with an explicit allowlist excluding all hiring/launch tools."""
import json,urllib.request,urllib.error

class TeracError(RuntimeError):pass
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

class TeracMCP:
    ENDPOINT='https://terac.com/api/mcp'
    ALLOWED={'terac_get_context','terac_get_filter_options','terac_list_filters',
        'terac_request_feasibility','terac_get_feasibility_request'}
    def __init__(self,key,transport=None):
        if not key:raise ValueError('TERAC_API_KEY is required')
        self.headers={'x-api-key':key,'Content-Type':'application/json','Accept':'application/json, text/event-stream'}
        self.transport=transport or self._post;self.sequence=0;self.connected=False;self.context_read=False
    def _post(self,body,headers):
        request=urllib.request.Request(self.ENDPOINT,data=json.dumps(body).encode(),headers=headers,method='POST')
        try:
            with urllib.request.build_opener(NoRedirect()).open(request,timeout=45) as response:
                return response.read(3_000_001).decode(),dict(response.headers)
        except urllib.error.HTTPError as error:raise TeracError('Terac HTTP '+str(error.code)) from None
        except (urllib.error.URLError,TimeoutError):raise TeracError('Terac network failure; do not automatically repeat a request') from None
    def _rpc(self,method,params=None,notification=False):
        self.sequence+=1;rid=self.sequence
        body={'jsonrpc':'2.0','method':method}
        if not notification:body['id']=rid
        if params is not None:body['params']=params
        raw,headers=self.transport(body,dict(self.headers))
        for k,v in headers.items():
            if k.lower()=='mcp-session-id':self.headers['Mcp-Session-Id']=v
        if notification:return {}
        if len(raw)>3_000_000:raise TeracError('Terac response exceeds size limit')
        try:
            if raw.lstrip().startswith('{'):result=json.loads(raw)
            else:
                messages=[json.loads(line[5:].strip()) for line in raw.splitlines() if line.startswith('data:')]
                result=next(m for m in messages if m.get('id')==rid)
        except (ValueError,StopIteration):raise TeracError('Invalid Terac MCP response') from None
        if result.get('id')!=rid or result.get('error'):raise TeracError('Terac RPC rejected')
        value=result.get('result',{})
        if value.get('isError'):raise TeracError('Terac tool rejected the request')
        return value
    def connect(self):
        initial=self._rpc('initialize',{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'product-improvement-feasibility','version':'1.0'}})
        self.headers['MCP-Protocol-Version']=initial.get('protocolVersion','2025-03-26')
        self._rpc('notifications/initialized',notification=True);self.connected=True
    def call(self,name,arguments):
        if name not in self.ALLOWED:raise ValueError('Only read operations and non-binding feasibility requests are allowed')
        if not self.connected:self.connect()
        if name!='terac_get_context' and not self.context_read:self.call('terac_get_context',{})
        result=self._rpc('tools/call',{'name':name,'arguments':arguments})
        if name=='terac_get_context':self.context_read=True
        return result

def tool_data(result):
    if isinstance(result.get('structuredContent'),dict):return result['structuredContent']
    text='\n'.join(c['text'] for c in result.get('content',[]) if c.get('type')=='text')
    try:return json.loads(text)
    except ValueError:return {'text':text}
