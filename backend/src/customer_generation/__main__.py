"""Customer generation CLI: validate, generate, and evaluate saved runs."""
import os
import argparse
import json
import sys
from pathlib import Path
from .sampling import generate_population
from .pipeline import run_generation
from .state import RunLimits
from .instructions import InstructionRegistry
from .tools.fixtures import FixtureBackend
from .tools.llm import ModelResponseError
from .tools.http import TransportError
from .tools.live import LiveBackend
from .tools.codex import CodexModelError
from .environment import load_environment
from .evaluation import evaluate_run, audit_template, write_new
from .config import AdapterConfig
from .validation import ContractError, validate_intake, validate_evidence, validate_specification

def load(path):
    with Path(path).open() as f:return json.load(f)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file',help='Explicit local env file; exported variables take precedence')
    commands=parser.add_subparsers(dest='command',required=True)
    check=commands.add_parser('validate');check.add_argument('--intake');check.add_argument('--evidence',required=True);check.add_argument('--spec',required=True)
    sample=commands.add_parser('sample');sample.add_argument('--evidence',required=True);sample.add_argument('--spec',required=True);sample.add_argument('--output',required=True)
    run=commands.add_parser('run-fixture',help='Exercise Phase 2 harness using explicitly offline saved stages')
    run.add_argument('--fixture-dir',required=True);run.add_argument('--run-root',default='data/runs');run.add_argument('--run-id',required=True)
    evaluate=commands.add_parser('evaluate-run',help='Inspect saved artifacts without API calls; never asserts buyer validity')
    evaluate.add_argument('--run-dir',required=True);evaluate.add_argument('--output',required=True)
    evaluate.add_argument('--audit');evaluate.add_argument('--audit-template-output')
    commands.add_parser('show-instructions',help='Print version/hash manifest without network calls')
    configuration=commands.add_parser('check-config',help='Validate environment configuration without API calls')
    configuration.add_argument('--model-backend',choices=['bridge','codex','openrouter'])
    bridge_smoke=commands.add_parser('bridge-smoke',help='One real deployed model-worker intake call; no Exa required')
    bridge_smoke.add_argument('--output',required=True)
    smoke=commands.add_parser('codex-smoke',help='Make one small real Codex intake call without Exa')
    smoke.add_argument('--model');smoke.add_argument('--output',required=True)
    live=commands.add_parser('run-live',help='Explicitly make configured Exa/model calls')
    live.add_argument('--model-backend',choices=['bridge','codex','openrouter'])
    live.add_argument('--intake',required=True);live.add_argument('--run-id',required=True);live.add_argument('--run-root',default='data/runs')
    live.add_argument('--count',type=int,default=50);live.add_argument('--seed',type=int,default=42)
    live.add_argument('--max-tokens-per-call',type=int,default=None);live.add_argument('--max-total-tokens',type=int,default=None)
    live.add_argument('--max-cost-usd',type=float,default=1.0)
    args=parser.parse_args()
    try:
        if args.env_file:load_environment(args.env_file)
        if args.command=='evaluate-run':
            report=evaluate_run(args.run_dir,load(args.audit) if args.audit else None)
            template=audit_template(report) if args.audit_template_output else None
            if Path(args.output).exists() or (args.audit_template_output and Path(args.audit_template_output).exists()):
                raise ValueError('Evaluation output already exists; choose new paths')
            if args.audit_template_output and Path(args.output).resolve()==Path(args.audit_template_output).resolve():
                raise ValueError('Report and audit template require different output paths')
            write_new(args.output,report)
            if template is not None:write_new(args.audit_template_output,template)
            print(f"Evaluation status: {report['status']}. Saved to {args.output}. No API calls made.")
            return 1 if report['status'] in {'evaluation_failed','run_not_completed'} else 0
        if args.command=='show-instructions':
            print(json.dumps(InstructionRegistry().manifest(),indent=2))
            return 0
        if args.command=='bridge-smoke':
            from .tools.llm import ModelBridgeClient
            from dataclasses import asdict
            required=['MODEL_BRIDGE_URL','MODEL_BRIDGE_TOKEN','MODEL_ID']
            missing=[k for k in required if not os.environ.get(k,'').strip()]
            if missing:raise ValueError('Missing configuration: '+', '.join(missing))
            if Path(args.output).exists():raise ValueError('Smoke output already exists')
            client=ModelBridgeClient(*(os.environ[k].strip() for k in required))
            response=client.call('intake_extract',{'submission':{'product_id':'worker-smoke','text':'A proposed USB-C hub priced at 39 USD. Exact capabilities unknown.'}},
                {'max_tokens':40000,'max_cost_usd':1.0,'timeout_seconds':60},
                load(Path(__file__).resolve().parents[3]/'data/schemas/intake.schema.json'))
            if response.data['product_id']!='worker-smoke':raise ValueError('Worker changed the supplied product ID')
            write_new(args.output,{'status':'model_call_succeeded','scope':'single worker intake, not full generation evaluation',**asdict(response)})
            print('Worker structured intake smoke test passed; inspect usage and actual Lovable credit billing.')
            return 0
        if args.command=='codex-smoke':
            from .tools.codex import CodexModelClient,configured_model
            from dataclasses import asdict
            if Path(args.output).exists():raise ValueError('Smoke output already exists')
            response=CodexModelClient(args.model or configured_model()).call('intake_extract',
                {'submission':{'product_id':'codex-smoke','text':'A proposed portable speaker priced at 119 USD. Other specifications unknown.'}},
                {'max_tokens':40000,'max_cost_usd':1.0,'timeout_seconds':60},
                load(Path(__file__).resolve().parents[3]/'data/schemas/intake.schema.json'))
            write_new(args.output,{'status':'model_call_succeeded','scope':'single intake call, not full pipeline evaluation',**asdict(response)})
            print('Codex structured intake smoke test passed; dollar cost is unknown.')
            return 0
        if args.command=='check-config':
            AdapterConfig.from_environment(backend=args.model_backend)
            print('Required configuration is present and structurally valid. Connectivity, credentials, server instructions, and credits are NOT verified. No API calls made.')
            return 0
        if args.command=='run-live':
            config=AdapterConfig.from_environment(backend=args.model_backend)
            if config.model_backend=='codex' and (args.max_tokens_per_call is None or args.max_total_tokens is None):
                raise ValueError('Codex requires explicit --max-tokens-per-call and --max-total-tokens: the intake smoke test used about 14,400 tokens including CLI overhead.')
            state=run_generation(load(args.intake),LiveBackend(config),Path(args.run_root),args.run_id,target_count=args.count,seed=args.seed,limits=RunLimits(max_tokens_per_call=args.max_tokens_per_call if args.max_tokens_per_call is not None else 6000,max_total_tokens=args.max_total_tokens if args.max_total_tokens is not None else 40000,max_cost_usd=args.max_cost_usd))
            print(json.dumps(state.to_dict(),indent=2))
            return 0 if state.status=='completed' else 1
        if args.command=='run-fixture':
            folder=Path(args.fixture_dir)
            spec=load(folder/'specification.json')
            state=run_generation(load(folder/'intake.json'),FixtureBackend(folder),Path(args.run_root),args.run_id,target_count=spec['target_count'],seed=spec['seed'])
            print(json.dumps(state.to_dict(),indent=2))
            return 0 if state.status=='completed' else 1
        evidence=load(args.evidence);spec=load(args.spec)
        validate_evidence(evidence);validate_specification(spec,evidence)
        if args.command=='validate':
            if args.intake:
                intake=load(args.intake);validate_intake(intake)
                if intake['product_id']!=spec['product_id']:raise ContractError('Intake and specification product IDs differ')
            print('Contracts and specification references valid. No research or model calls performed.')
        else:
            result=generate_population(spec,evidence)
            output=Path(args.output)
            output.parent.mkdir(parents=True,exist_ok=True)
            # Fail on existing output: no silent overwrite of reviewed demo data.
            with output.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
            print(f"Saved {result['count']} synthetic profiles to {output}. Behavioral validity not evaluated.")
    except (ValueError,OSError,CodexModelError,ModelResponseError,TransportError) as exc:
        print(str(exc),file=sys.stderr);return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
