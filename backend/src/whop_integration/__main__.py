import argparse,json,os,threading,time,hashlib
from pathlib import Path
from socketserver import ThreadingMixIn
from wsgiref.simple_server import make_server,WSGIServer,WSGIRequestHandler
from customer_generation.environment import load_environment
from .config import Config,resource
from .client import Client,WhopError,setup_payloads
from .store import Store
from .service import Service,EVENTS
from .app import application

def save_private(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:json.dump(data,f,indent=2);f.write('\n')

def main():
    p=argparse.ArgumentParser(description='Whop phase 1; sales disabled by default')
    p.add_argument('--env-file',default='backend/.env')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('check')
    provision=sub.add_parser('setup-offer');provision.add_argument('--execute',action='store_true');provision.add_argument('--output',default='backend/var/whop-offer.json')
    webhook=sub.add_parser('setup-webhook');webhook.add_argument('--execute',action='store_true');webhook.add_argument('--output',default='backend/var/whop-webhook.json')
    worker=sub.add_parser('worker');worker.add_argument('--once',action='store_true')
    fulfill=sub.add_parser('fulfill');fulfill.add_argument('--execute',action='store_true');fulfill.add_argument('--once',action='store_true')
    serve=sub.add_parser('serve');serve.add_argument('--host',default='127.0.0.1');serve.add_argument('--port',type=int,default=8080)
    args=p.parse_args();load_environment(args.env_file)
    try:
        c=Config.from_env();client=Client(c)
        if args.command=='check':
            print(json.dumps({'sales_enabled':c.sales_enabled,'environment':c.environment,
                'configured':{k:bool(getattr(c,k)) for k in ['api_key','webhook_secret','company_id','product_id','plan_id']},
                'note':'Read-only API discovery; no products or payments created'}))
            result=client.companies()
            print(json.dumps({'companies':[{'id':x.get('id'),'title':x.get('title')} for x in result.get('data',[])]}));return 0
        if args.command=='setup-offer':
            payloads=setup_payloads(c)
            if not args.execute:print(json.dumps({'mode':'plan_only','payloads':payloads,'sales_closed':True},indent=2));return 0
            if Path(args.output).exists():raise ValueError('Setup record exists; reuse its IDs rather than creating duplicates')
            # Stable keys survive ambiguous network failures and explicit retries.
            key=hashlib.sha256(json.dumps(payloads,sort_keys=True).encode()).hexdigest()
            if c.product_id:
                pid=resource(c.product_id,'prod')
            else:
                product=client.call('POST','/products',payloads['product'],idempotency_key='research-product-'+key)
                pid=resource(product.get('id'),'prod')
            variant=client.call('POST','/variants',{**payloads['variant'],'product_id':pid},idempotency_key='research-variant-'+key)
            plan=resource(variant.get('id'),'plan')
            save_private(args.output,{'company_id':c.company_id,'product_id':pid,'plan_id':plan,'environment':c.environment,'price':c.price,'stock':0,'visibility':'hidden'})
            print(json.dumps({'created':True,'record':args.output,'sales_closed':True}));return 0
        if args.command=='setup-webhook':
            resource(c.company_id,'biz')
            if not c.public_url.startswith('https://'):raise ValueError('A public HTTPS origin is required for the webhook')
            payload={'url':c.public_url+'/api/webhooks/whop','events':sorted(EVENTS),'api_version':'v1','api_version_date':c.api_version,'resource_id':c.company_id,'enabled':True}
            if not args.execute:print(json.dumps({'mode':'plan_only','payload':payload},indent=2));return 0
            if Path(args.output).exists():raise ValueError('Webhook record exists; reuse the existing registration')
            # Create destination exclusively BEFORE the external mutation so a
            # returned one-time secret cannot overwrite an existing record.
            destination=Path(args.output);destination.parent.mkdir(parents=True,exist_ok=True)
            fd=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            try:
                result=client.call('POST','/webhooks',payload,idempotency_key='research-webhook-'+hashlib.sha256(payload['url'].encode()).hexdigest())
                secret=result.get('webhook_secret')
                if not isinstance(secret,str) or not secret:raise ValueError('Whop returned no signing secret; inspect the dashboard')
                with os.fdopen(fd,'w') as f:fd=None;json.dump(result,f,indent=2)
            finally:
                if fd is not None:os.close(fd)
            print(json.dumps({'created':True,'private_record':args.output,'next':'Copy webhook_secret privately into WHOP_WEBHOOK_SECRET; never paste it into chat'}));return 0
        store=Store(c.database);service=Service(c,store,client)
        if args.command=='fulfill':
            if not args.execute:
                print(json.dumps({'mode':'plan_only','action':'Process paid intake jobs through research and generation','note':'Use --execute --once to process at most one job. No API/model calls made.'}));return 0
            from .fulfillment import Fulfillment
            fulfillment=Fulfillment(service)
            while True:
                print(json.dumps(fulfillment.process_once()),flush=True)
                if args.once:return 0
                time.sleep(2)
        if args.command=='worker':
            while True:
                print(json.dumps(service.drain_once()),flush=True)
                if args.once:return 0
                time.sleep(2)
        if args.command=='serve':
            class Server(ThreadingMixIn,WSGIServer):daemon_threads=True
            class QuietHandler(WSGIRequestHandler):
                def log_message(self,*args):pass
            stopped=threading.Event()
            def drain():
                while not stopped.is_set():
                    try:service.drain_once()
                    except Exception:pass
                    stopped.wait(1)
            threading.Thread(target=drain,daemon=True).start()
            print(json.dumps({'listen':f'http://{args.host}:{args.port}','sales_enabled':c.sales_enabled,'phase':3}),flush=True)
            try:
                with make_server(args.host,args.port,application(service),server_class=Server,handler_class=QuietHandler) as server:server.serve_forever()
            finally:stopped.set()
    except (ValueError,OSError,WhopError) as e:
        print(str(e));return 1

if __name__=='__main__':raise SystemExit(main())
