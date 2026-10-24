"""Launch local research demo; API calls happen only after clicking Start."""
import argparse,sys
from pathlib import Path
from socketserver import ThreadingMixIn
from wsgiref.simple_server import make_server,WSGIServer
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend/src'))
from customer_generation.environment import load_environment
from customer_generation.demo import Demo,application

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,default=8082);p.add_argument('--customers',type=int,default=25);a=p.parse_args()
    load_environment(ROOT/'backend/.env')
    class Server(ThreadingMixIn,WSGIServer):daemon_threads=True
    if not 1<=a.customers<=500:p.error('--customers must be between 1 and 500')
    demo=Demo(ROOT/'data/runs',full_pipeline=True,target_count=a.customers,guided_flow=True)
    print(f'Open http://127.0.0.1:{a.port}. Upload a brief, check your work, then Start research. Approve segmentations to generate profiles; click Start simulation when ready. Uses Exa and configured model-provider credits; no Terac hiring.',flush=True)
    with make_server('127.0.0.1',a.port,application(demo,a.port),server_class=Server) as server:server.serve_forever()
