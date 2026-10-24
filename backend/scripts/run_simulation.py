"""Default is a free local plan. --execute explicitly spends configured model-provider credits."""
import argparse,json,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'backend/src'))
from customer_simulation.pipeline import read,build_offers,choose_customers,replay_saved
from customer_simulation.concept import run,execution_plan
from customer_generation.instructions import InstructionRegistry
from customer_generation.environment import load_environment
from customer_generation.tools.llm import ModelBridgeClient

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--render-saved',action='store_true',help='Revalidate/render saved responses only; never load API credentials or call models');p.add_argument('--max-total-tokens',type=int,help='Optional explicit total-token ceiling; default scales to the selected population');p.add_argument('--population-run',required=True);p.add_argument('--count',type=int,default=5)
    p.add_argument('--resume',action='store_true',help='Reuse exact saved responses in --output; no automatic retries');p.add_argument('--output');p.add_argument('--execute',action='store_true');p.add_argument('--replay-from')
    p.add_argument('--approve-population',action='store_true',help='Confirm you reviewed this population for synthetic simulation')
    args=p.parse_args()
    if args.replay_from:
        if args.execute:p.error('Replay makes no model calls; omit --execute')
        out=Path(args.output) if args.output else ROOT/'data/simulations'/('replay-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f'))
        print(replay_saved(args.replay_from,out));return
    if args.resume and not args.output:p.error('--resume requires --output')
    source=(ROOT/'data/runs'/args.population_run).resolve()
    if source.parent!=(ROOT/'data/runs').resolve():p.error('Use a run directory name')
    if read(source/'state.json')['status']!='completed':p.error('Population is not completed')
    population=read(source/'customers.json')
    available=len(population['customers'])
    if not 1<=args.count<=available:p.error(f'This population contains {available} customers. Choose 1–{available}, or generate a larger population first. Profiles are never duplicated to increase the count.')
    customers=choose_customers(population,args.count)
    offers=build_offers(read(source/'brief.json'),read(source/'evidence.json'))
    out=Path(args.output) if args.output else ROOT/'data/simulations'/('simulation-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f'))
    plan=execution_plan(customers,offers,read(source/'evidence.json'),InstructionRegistry())
    if args.max_total_tokens is not None and args.max_total_tokens<1:p.error('--max-total-tokens must be positive')
    saved=sum((out/f'customer-{index:03}.json').exists() for index in range(1,args.count+1)) if args.resume else 0
    print(json.dumps({'saved_customers_to_reuse':saved,'additional_calls_upper_bound':0 if args.render_saved else plan['model_calls']-saved,'available_customers':available,'execution_plan':plan,'token_ceiling':args.max_total_tokens or plan['automatic_token_ceiling'],'mode':'offline_render' if args.render_saved else 'execute' if args.execute else 'plan','customers':len(customers),'offers':[o['name'] for o in offers],
        'output':str(out),'model_calls':0 if args.render_saved else plan['model_calls'],'scenario':'Assume the proposed offer is available at its stated price and works as described.', 'note':'Counts scale to the available population. Large reports use bounded batches; resume reuses saved responses. No Exa calls or Terac actions.'},indent=2))
    if args.render_saved:
        if args.execute or not args.resume:p.error('--render-saved requires --resume --output and cannot use --execute')
        class SavedOnlyClient:
            instructions=InstructionRegistry()
            def call(self,*a,**k):raise ValueError('A reusable saved response is missing; render-saved never calls a model')
        print(run(source,out,SavedOnlyClient(),count=args.count,total_token_limit=args.max_total_tokens,resume=True));return
    if not args.execute:return
    if not args.approve_population:p.error('Review the population, then add --approve-population')
    import os
    load_environment(ROOT/'backend/.env')
    from customer_generation.tools.llm import configured_client
    client=configured_client()
    print(run(source,out,client,count=args.count,total_token_limit=args.max_total_tokens,resume=args.resume))
if __name__=='__main__':main()
