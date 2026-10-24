"""Plan expert checks locally; explicit --request-feasibility submits non-binding Terac requests."""
import argparse,json,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'backend/src'))
from customer_generation.environment import load_environment
from terac_integration.policy import expert_policy,feasibility_arguments
from terac_integration.feasibility import request_improvements,refresh_improvements
from terac_integration.mcp import TeracMCP

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--concerns',required=True,help='Saved concerns.json or availability-plan.json')
    parser.add_argument('--output',required=True)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--request-feasibility',action='store_true')
    mode.add_argument('--refresh',action='store_true',help='Read saved request statuses; never create requests')
    args=parser.parse_args();plan=json.loads(Path(args.concerns).read_text())
    rows=plan.get('improvements',plan.get('concerns',[]))
    prepared=[] if args.refresh else [{'title':row['title'],'arguments':feasibility_arguments(plan['product'],row)} for row in rows]
    if not args.request_feasibility and not args.refresh:
        print(json.dumps({'mode':'local_plan','policy':expert_policy(),'requests':prepared,'network_calls':0},indent=2));return
    load_environment(ROOT/'backend/.env');client=TeracMCP(os.environ.get('TERAC_API_KEY'))
    result=refresh_improvements(Path(args.output),client) if args.refresh else request_improvements(plan,Path(args.output),client)
    print(json.dumps({'mode':'status_read' if args.refresh else 'non_binding_feasibility','requests':result,'studies_launched':0,'experts_hired':0},indent=2))
if __name__=='__main__':main()
