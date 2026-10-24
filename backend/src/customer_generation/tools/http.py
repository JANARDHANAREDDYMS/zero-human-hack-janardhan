"""Small bounded JSON transport. No retries or authenticated redirects."""
import json
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


class TransportError(RuntimeError):
    def __init__(self, category, status=None):
        self.category=category;self.status=status
        super().__init__(f'HTTP transport {category}' + (f' ({status})' if status else ''))


def validate_endpoint(url):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Service endpoint must be HTTPS without credentials, query, or fragment')
    return url


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


class JsonTransport:
    def __init__(self,max_response_bytes=2_000_000):
        self.max_response_bytes=max_response_bytes
    def post(self,url,headers,payload,timeout):
        validate_endpoint(url)
        request=Request(url,data=json.dumps(payload,allow_nan=False).encode(),headers={**headers,'Content-Type':'application/json','Accept':'application/json'},method='POST')
        try:
            with build_opener(NoRedirect()).open(request,timeout=timeout) as response:
                body=response.read(self.max_response_bytes+1)
                if len(body)>self.max_response_bytes:raise TransportError('response_too_large')
                try:value=json.loads(body)
                except (ValueError,UnicodeError):raise TransportError('invalid_json') from None
                if not isinstance(value,dict):raise TransportError('invalid_envelope')
                return value
        except HTTPError as exc:
            category={401:'authentication',403:'authorization',402:'credits_exhausted',429:'rate_limited'}.get(exc.code,'http_error')
            raise TransportError(category,exc.code) from None
        except (socket.timeout,TimeoutError):raise TransportError('timeout') from None
        except URLError:raise TransportError('connection') from None
