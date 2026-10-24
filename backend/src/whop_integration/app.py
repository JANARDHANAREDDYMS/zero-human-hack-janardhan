"""Small WSGI API; same-origin checkout/status endpoints for the next UI phase."""
import json,re
from http.cookies import SimpleCookie
from urllib.parse import urlsplit
from .signatures import SignatureError
from .client import WhopError
from .intake import IntakeConflict
from pathlib import Path

MAX_BODY=256_000

def application(service,fulfillment=None):
    if fulfillment is None:
        from .fulfillment import Fulfillment
        fulfillment=Fulfillment(service)
    def app(environ,start_response):
        headers=[('Content-Type','application/json'),('Cache-Control','no-store')]
        status=200
        try:
            method=environ.get('REQUEST_METHOD');path=environ.get('PATH_INFO','')
            origin=environ.get('HTTP_ORIGIN')
            if origin and origin!=service.config.public_url:raise PermissionError('Origin not allowed')
            match=re.fullmatch(r'/api/orders/([a-f0-9]{32})/intake(?:/(preview|submit))?',path)
            if method=='GET' and path=='/intake-template.md':
                raw=Path(__file__).with_name('intake-template.md').read_bytes()
                start_response('200 OK',[('Content-Type','text/markdown; charset=utf-8'),('Content-Disposition','attachment; filename="product-brief.md"'),('Content-Length',str(len(raw)))])
                return [raw]
            if method=='GET' and path in {'/intake','/checkout/return'}:
                raw=Path(__file__).with_name('intake.html').read_bytes()
                start_response('200 OK',[('Content-Type','text/html; charset=utf-8'),('Cache-Control','no-store'),('Content-Length',str(len(raw))),('X-Content-Type-Options','nosniff')])
                return [raw]
            report=re.fullmatch(r'/api/orders/([a-f0-9]{32})/results(?:/(customers|evidence|specification|brief))?',path)
            if report and method=='GET':
                cookies=SimpleCookie();cookies.load(environ.get('HTTP_COOKIE',''))
                token=cookies.get('research_order_token')
                result=fulfillment.result(report[1],token.value if token else '',report[2])
            elif match and (method=='POST' and match[2] in {'preview','submit'} or method=='GET' and not match[2]):
                cookies=SimpleCookie();cookies.load(environ.get('HTTP_COOKIE',''))
                token=cookies.get('research_order_token');token=token.value if token else ''
                if method=='GET':result={'job':service.intake(match[1],token)}
                else:
                    size=int(environ.get('CONTENT_LENGTH') or 0)
                    if size<0 or size>MAX_BODY:status=413;result={'error':'Request too large'}
                    else:
                        payload=json.loads(environ['wsgi.input'].read(size))
                        result=service.intake(match[1],token,payload,submit=match[2]=='submit')
                        if match[2]=='submit':status=200 if result['duplicate'] else 201
            elif method=='GET' and path=='/health':
                result={'status':'ok','phase':3,'sales_enabled':service.config.sales_enabled,'environment':service.config.environment}
            elif method=='POST' and path in {'/api/checkout','/api/webhooks/whop'}:
                size=int(environ.get('CONTENT_LENGTH') or 0)
                if size<0 or size>MAX_BODY:
                    status=413;result={'error':'Request too large'}
                else:
                    body=environ['wsgi.input'].read(size)
                    if path=='/api/webhooks/whop':
                        sig_headers={k[5:].replace('_','-').lower():v for k,v in environ.items() if k.startswith('HTTP_')}
                        result=service.receive(body,sig_headers)
                    else:
                        if json.loads(body or b'{}')!={}:raise ValueError('Checkout accepts no client price, plan or payment status')
                        result,token=service.checkout()
                        secure='; Secure' if service.config.public_url.startswith('https:') else ''
                        headers.append(('Set-Cookie',f"research_order_token={token}; Path=/api/orders/{result['order_id']}; HttpOnly; SameSite=Lax; Max-Age=86400{secure}"))
                        status=201
            elif method=='GET' and re.fullmatch('/api/orders/[a-f0-9]{32}',path):
                cookies=SimpleCookie();cookies.load(environ.get('HTTP_COOKIE',''))
                token=cookies.get('research_order_token')
                result=service.status(path.rsplit('/',1)[1],token.value if token else '')
                if result is None:status=404;result={'error':'Order not found'}
            else:status=404;result={'error':'Not found'}
        except LookupError:status=404;result={'error':'Order not found'}
        except IntakeConflict:status=409;result={'error':'This order already has a different submitted brief'}
        except SignatureError:status=401;result={'error':'Invalid webhook signature'}
        except PermissionError:status=403;result={'error':'Action unavailable or origin/account not allowed'}
        except (ValueError,TypeError,AttributeError):status=400;result={'error':'Invalid request'}
        except WhopError:status=502;result={'error':'Whop request failed; no payment verified'}
        except Exception:status=503;result={'error':'Service temporarily unavailable'}
        raw=json.dumps(result).encode();headers.append(('Content-Length',str(len(raw))))
        labels={200:'OK',201:'Created',400:'Bad Request',401:'Unauthorized',403:'Forbidden',404:'Not Found',409:'Conflict',413:'Content Too Large',502:'Bad Gateway',503:'Service Unavailable'}
        start_response(f'{status} {labels[status]}',headers)
        return [raw]
    return app
