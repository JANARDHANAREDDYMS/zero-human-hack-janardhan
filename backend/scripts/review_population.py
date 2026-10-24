"""Local five-line summary and explicit approval; no model or simulation calls."""
import argparse,html,json,secrets,sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend/src'))
from customer_generation.approval import summary_lines,read_population,write_summary,approval_valid
from customer_generation.evaluation import write_new

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-id',required=True);p.add_argument('--port',type=int,default=8081);a=p.parse_args()
    if not a.run_id or Path(a.run_id).name!=a.run_id or a.run_id in {'.','..'}:raise ValueError('Invalid run ID')
    run=ROOT/'data/runs'/a.run_id;write_summary(run);lines=summary_lines(run);_,_,hashes=read_population(run)
    nonce=secrets.token_urlsafe(32);origin=f'http://127.0.0.1:{a.port}'
    def app(env,start):
        status='200 OK';body=''
        if env.get('HTTP_HOST')!=f'127.0.0.1:{a.port}':status='403 Forbidden';body='Local access only'
        elif env['REQUEST_METHOD']=='POST' and env.get('PATH_INFO')=='/approve':
            size=int(env.get('CONTENT_LENGTH') or 0)
            if size>1000 or env.get('HTTP_ORIGIN') not in {None,origin}:status='403 Forbidden';body='Invalid approval'
            else:
                data=parse_qs(env['wsgi.input'].read(size).decode())
                if not secrets.compare_digest(data.get('nonce',[''])[0],nonce):status='403 Forbidden';body='Invalid approval'
                elif read_population(run)[2]!=hashes:status='409 Conflict';body='Inputs changed; restart this review.'
                else:
                    out=ROOT/'data/approvals'/f'{a.run_id}.json';out.parent.mkdir(parents=True,exist_ok=True)
                    if out.exists() and not approval_valid(run,out):
                        status='409 Conflict';body='Existing approval refers to different inputs; review record must be resolved.'
                    elif not out.exists():write_new(out,{'run_id':a.run_id,'input_hashes':hashes,'scope':'summary_approval_for_simulation',
                        'approved_at':datetime.now(timezone.utc).isoformat(),'limitations':'Summary approval only; not a complete evidence audit or real buyer validation.'})
                    if status=='200 OK':body='<h1>Approved for simulation</h1><p>These profiles are ready as simulation inputs. Simulation has not started.</p>'
        elif env['REQUEST_METHOD']=='GET' and env.get('PATH_INFO')=='/':
            body='<h1>Review customer segments</h1>'+''.join('<p>'+html.escape(x)+'</p>' for x in lines)+'<p>Summary approval permits simulation use. It is not a full evidence audit.</p><form method="post" action="/approve"><input type="hidden" name="nonce" value="'+nonce+'"><button style="font:inherit;padding:12px" type="submit">Approve for simulation</button></form>'
        else:status='404 Not Found';body='Not found'
        raw=('<!doctype html><meta charset="utf-8"><title>Approve population</title><main style="max-width:850px;margin:50px auto;font:18px/1.6 system-ui">'+body+'</main>').encode()
        start(status,[('Content-Type','text/html; charset=utf-8'),('Cache-Control','no-store'),('Content-Length',str(len(raw)))]);return [raw]
    print('Open '+origin+' to review and approve. No model calls.',flush=True)
    with make_server('127.0.0.1',a.port,app) as server:server.serve_forever()

if __name__=='__main__':main()
