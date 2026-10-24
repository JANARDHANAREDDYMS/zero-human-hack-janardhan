"""Generate human-review concerns from saved non-choosing customers. No Terac actions."""
import argparse,json,os,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'backend/src'))
from customer_simulation.review_concerns import prepare_sources,generate
from customer_generation.environment import load_environment
from customer_generation.tools.llm import ModelBridgeClient

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--simulation-run',required=True)
    p.add_argument('--output');p.add_argument('--execute',action='store_true');p.add_argument('--resume',action='store_true')
    args=p.parse_args();source=(ROOT/'data/simulations'/args.simulation_run).resolve()
    if source.parent!=(ROOT/'data/simulations').resolve():p.error('Use a simulation directory name')
    if args.resume and not args.output:p.error('--resume requires --output')
    sources=prepare_sources(source)
    out=Path(args.output) if args.output else source/'review-concerns'/datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    print(json.dumps({'mode':'execute' if args.execute else 'plan','completed_customers':sources['completed_customers'],
        'non_choosing_customers':len(sources['declining_customer_ids']),'candidate_signals':len(sources['rejection_catalog']),
        'target':'Up to 10 distinct supported concerns; fewer if appropriate','output':str(out),
        'note':'Uses Lovable only when --execute is passed. No Terac API/MCP connection, hiring or submission.'},indent=2))
    if not args.execute:return
    load_environment(ROOT/'backend/.env')
    names=['MODEL_BRIDGE_URL','MODEL_BRIDGE_TOKEN','MODEL_ID']
    if any(not os.environ.get(n) for n in names):p.error('Bridge configuration missing')
    client=ModelBridgeClient(*(os.environ[n] for n in names))
    print(generate(source,out,client,resume=args.resume))
if __name__=='__main__':main()
