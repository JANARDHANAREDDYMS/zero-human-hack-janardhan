"""Plan or explicitly execute USB-C hub then Sony generation/evaluation runs."""
import argparse,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend/src'))
from customer_generation.config import AdapterConfig
from customer_generation.environment import load_environment
from customer_generation.pipeline import run_generation
from customer_generation.state import RunLimits
from customer_generation.tools.live import LiveBackend
from customer_generation.validation import validate_intake
from customer_generation.validation import validate_evidence,validate_specification
from customer_generation.state import StageResponse
from customer_generation.sampling import fingerprint
from customer_generation.evaluation import evaluate_run,audit_template,write_new

CASES=[('usb-c-hub',ROOT/'data/evaluations/cases/usb-c-hub.json'),
       ('sony-speaker',ROOT/'data/products/sony-speaker/research-v2/brief.json')]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--env-file',default=str(ROOT/'backend/.env'))
    p.add_argument('--model-backend',choices=['codex','bridge','openrouter'])
    p.add_argument('--run-prefix',required=True)
    p.add_argument('--execute',action='store_true',help='Actually spend configured service credits; omit for plan only')
    p.add_argument('--product',choices=['all','usb-c-hub','sony-speaker'],default='all',help='Run only the selected product to control credit usage')
    p.add_argument('--reuse-research-run',help='Reuse validated evidence from a prior live run with an identical brief; no new research calls')
    p.add_argument('--proposal-format',choices=['canonical','compact'],default='canonical',help='Compact requires the updated worker policy to be published first')
    p.add_argument('--reuse-proposal-run',help='Reuse the latest saved specification from a matching live run; performs no new proposal call')
    p.add_argument('--max-corrections',type=int,choices=[0,1],default=1)
    p.add_argument('--count',type=int,default=50);p.add_argument('--seed',type=int,default=42)
    p.add_argument('--max-tokens-per-call',type=int,default=40000)
    p.add_argument('--max-total-tokens',type=int,default=160000)
    p.add_argument('--max-cost-usd',type=float,default=1.0,help='Per-product known-dollar allowance; unknown model costs are separate')
    args=p.parse_args()
    try:
        if not re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9_-]{0,49}',args.run_prefix):raise ValueError('Use a run prefix of 1–50 letters/digits/hyphens/underscores')
        load_environment(args.env_file)
        reused=None
        if args.reuse_research_run:
            if args.product=='all':raise ValueError('Research reuse requires selecting one product')
            if not re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9_-]*',args.reuse_research_run):raise ValueError('Invalid research source run ID')
            source=ROOT/'data/runs'/args.reuse_research_run
            source_state=json.loads((source/'state.json').read_text())
            if source_state.get('mode')!='live':raise ValueError('Research reuse requires a live source run')
            reused=json.loads((source/'evidence.json').read_text());validate_evidence(reused)
            source_brief=json.loads((source/'brief.json').read_text())
        cases=[]
        saved_spec=None;saved_compact=None
        if args.reuse_proposal_run:
            if not reused or args.product=='all' or args.proposal_format!='compact':raise ValueError('Proposal reuse requires one compact product and explicit research reuse')
            if not re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9_-]*',args.reuse_proposal_run):raise ValueError('Invalid proposal source run ID')
            proposal_source=ROOT/'data/runs'/args.reuse_proposal_run
            ps=json.loads((proposal_source/'state.json').read_text())
            if ps.get('mode')!='live':raise ValueError('Proposal source must be a live run')
            if json.loads((proposal_source/'brief.json').read_text())!=source_brief or json.loads((proposal_source/'evidence.json').read_text())!=reused:raise ValueError('Proposal source brief/evidence mismatch')
            saved_spec=json.loads((proposal_source/f"specification-{ps['corrections']}.json").read_text())
            validate_specification(saved_spec,reused)
            if saved_spec['target_count']!=args.count or saved_spec['seed']!=args.seed:raise ValueError('Reused specification count/seed mismatch')
            raw_name='compact_correct' if ps['corrections'] else 'compact_propose'
            raw_files=sorted(proposal_source.glob(f'call-*-{raw_name}-raw-output.json'))
            if not raw_files:raise ValueError('Source compact proposal artifact missing')
            saved_compact=json.loads(raw_files[-1].read_text())
            from customer_generation.compact import construct_specification
            if construct_specification(saved_compact,source_brief,reused,args.count,args.seed)!=saved_spec:raise ValueError('Saved compact proposal does not reconstruct the specification')
        for name,path in CASES:
            if args.product!='all' and name!=args.product:continue
            intake=json.loads(path.read_text());validate_intake(intake)
            if reused is not None and (source_brief!=intake or reused['product_id']!=intake['product_id']):raise ValueError('Saved research brief does not match selected product')
            run_id=f'{args.run_prefix}-{name}'
            outputs=[ROOT/'data/evaluations'/f'{run_id}-{suffix}.json' for suffix in ['report','audit']]
            if (ROOT/'data/runs'/run_id).exists() or any(o.exists() for o in outputs):raise ValueError('Run/report already exists; select a new prefix')
            cases.append((intake,run_id,outputs))
        error=None;config=None
        try:config=AdapterConfig.from_environment(backend=args.model_backend)
        except ValueError as exc:error=str(exc)
        plan={'mode':'execute' if args.execute else 'plan_only_no_api_calls',
            'proposal_format':args.proposal_format,'reused_research_run':args.reuse_research_run,
            'reused_proposal_run':args.reuse_proposal_run,'max_corrections':args.max_corrections,
            'order':[{'product_id':b['product_id'],'run_id':r,'target_count':args.count} for b,r,_ in cases],
            'per_product_limits':{'max_tokens_per_call':args.max_tokens_per_call,'max_total_tokens':args.max_total_tokens,'known_cost_usd':args.max_cost_usd},
            'configuration':'structurally_ready_not_connectivity_verified' if config else error,
            'note':'Selected bounded runs; stop after first failure. Review actual sources/segments/profiles before calling quality meaningful.'}
        print(json.dumps(plan,indent=2))
        if not args.execute:return 0
        if config is None:raise ValueError(error)
        for brief,run_id,outputs in cases:
            backend=LiveBackend(config,proposal_format=args.proposal_format)
            if saved_compact is not None:backend.last_compact_proposal=saved_compact
            if reused is not None:
                class ReuseResearchBackend:
                    mode='live'
                    name=backend.name+'-saved-research'
                    instruction_manifest=backend.instruction_manifest
                    def execute(self,stage,payload,allowances):
                        if stage=='research':
                            return StageResponse(reused,0,0,0.0,metadata={'reused_from_run':args.reuse_research_run,'evidence_sha256':fingerprint(reused),'usage_basis':'reused_artifact_no_new_calls; historical charges belong to source run'})
                        if stage=='propose' and saved_spec is not None:
                            return StageResponse(saved_spec,0,0,0.0,metadata={'reused_from_run':args.reuse_proposal_run,'specification_sha256':fingerprint(saved_spec),'usage_basis':'reused_artifact_no_new_calls'})
                        return backend.execute(stage,payload,allowances)
                selected_backend=ReuseResearchBackend()
            else:selected_backend=backend
            state=run_generation(brief,selected_backend,ROOT/'data/runs',run_id,target_count=args.count,seed=args.seed,
                limits=RunLimits(max_tokens_per_call=args.max_tokens_per_call,max_total_tokens=args.max_total_tokens,max_cost_usd=args.max_cost_usd,max_corrections=args.max_corrections))
            report=evaluate_run(ROOT/'data/runs'/run_id)
            if state.status=='completed':
                from customer_generation.approval import write_summary
                summary=write_summary(ROOT/'data/runs'/run_id)
                print(json.dumps({'summary':str(summary),'approval_command':f'python3 backend/scripts/review_population.py --run-id {run_id}'}))
            write_new(outputs[0],report)
            if report['input_hashes'].get('customers_sha256'):write_new(outputs[1],audit_template(report))
            print(json.dumps({'run_id':run_id,'generation_status':state.status,'evaluation_status':report['status'],'report':str(outputs[0])}))
            if state.status!='completed' or report['status'] in {'evaluation_failed','run_not_completed'}:return 1
        return 0
    except (ValueError,OSError) as exc:print(str(exc),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
