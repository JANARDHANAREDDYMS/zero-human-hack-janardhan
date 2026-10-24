"""Read-only evaluation of saved runs; model acceptance is not human validation."""
import json
from datetime import datetime
from pathlib import Path
from .instructions import REVIEW_CATEGORIES
from .quality import segmentation_quality
from .sampling import generate_population, fingerprint
from .validation import ContractError, validate_schema


def load(path):
    return json.loads(Path(path).read_text())


def evaluate_run(directory, audit=None):
    directory=Path(directory)
    state=load(directory/'state.json')
    checks=[]
    def check(name,status,note):
        checks.append({'check':name,'status':status,'note':note})
    completed=state.get('status')=='completed'
    check('run_completion','pass' if completed else 'fail',f"Saved run status: {state.get('status')}")
    config=load(directory/'configuration.json')
    responses=sorted(directory.glob('call-*-response.json'))
    calls=[]
    tokens=0;cost=0.0
    for path in responses:
        response=load(path);usage=response['usage'];tokens+=usage['input_tokens']+usage['output_tokens'];cost+=usage['cost_usd']
        calls.append({'artifact':path.name,'stage':response['stage'],'input_tokens':usage['input_tokens'],
            'output_tokens':usage['output_tokens'],'cost_usd':usage['cost_usd'],
            'duration_seconds':response.get('duration_seconds'),
            'cost_basis':response.get('metadata',{}).get('cost_basis','not_recorded'),
            'model_usage':response.get('metadata',{}).get('last_model_call')})
    consistent=(tokens==state['total_tokens'] and abs(cost-state['cost_usd'])<1e-8 and len(responses)==state['stage_calls'])
    check('usage_accounting','pass' if consistent else 'fail','Saved responses must reconcile with terminal state; an interrupted call can lack a response.')
    limits=config['limits']
    within_limits=(state['total_tokens']<=limits['max_total_tokens'] and state['cost_usd']<=limits['max_cost_usd'] and state['stage_calls']<=limits['max_stage_calls'] and all(c['input_tokens']+c['output_tokens']<=limits['max_tokens_per_call'] for c in calls))
    check('configured_usage_limits','pass' if within_limits else 'fail',"Compare recorded aggregate usage against the run’s configured allowances.")
    if state.get('cost_uncertain'):
        check('billing_certainty','warning','Some incurred costs are unknown; known totals are not a final bill.')
    else:
        check('billing_certainty','warning' if state['mode']=='live' else 'not_evaluated',
            'Reported/estimated costs are not verified account billing.' if state['mode']=='live' else 'Offline run has no provider billing measurement.')
    elapsed=None
    try:
        elapsed=(datetime.fromisoformat(state['finished_at'])-datetime.fromisoformat(state['started_at'])).total_seconds()
        if elapsed<0:raise ValueError('negative duration')
    except (KeyError,TypeError,ValueError):elapsed=None
    check('elapsed_time','not_evaluated' if elapsed is None else 'fail' if elapsed>limits['max_elapsed_seconds'] else 'pass',
        'Wall-clock elapsed time is unavailable.' if elapsed is None else 'Wall-clock elapsed time compared with configured run limit; clock changes can affect it.')
    evidence=load(directory/'evidence.json') if (directory/'evidence.json').exists() else None
    spec=load(directory/'specification.json') if (directory/'specification.json').exists() else None
    population=load(directory/'customers.json') if (directory/'customers.json').exists() else None
    quality=None;input_hashes={}
    if completed and evidence is not None and spec is not None and population is not None:
        try:
            validate_schema(population,'generated-population')
            expected=generate_population(spec,evidence,stratified=population.get('generator_version')=='2.1.0-stratified')
            if fingerprint(expected)!=fingerprint(population):raise ContractError('Saved population differs from deterministic replay')
            if spec['product_id']!=load(directory/'brief.json')['product_id']:raise ContractError('Brief/specification product IDs differ')
            if spec['target_count']!=config['target_count'] or spec['seed']!=config['seed']:raise ContractError('Saved specification changed configured count/seed')
            check('reproducibility','pass','Regenerated population matches the saved artifact, including evidence/specification hashes.')
            input_hashes={'specification_sha256':fingerprint(spec),'evidence_sha256':fingerprint(evidence),'customers_sha256':fingerprint(population)}
            if population.get('generator_version')=='2.1.0-stratified':
                from .population_quality import population_quality
                coverage=population_quality(spec,population,load(directory/'brief.json'))
                check('population_design_coverage','fail' if coverage['blocking_issues'] else 'pass','; '.join(coverage['blocking_issues']) or 'Declared within-segment marginal allocations and affordability coverage passed; this does not validate market prevalence.')
            quality=segmentation_quality(spec,evidence)
            gaps=quality['warnings']+[w for seg in quality['segments'] for w in seg['warnings']]
            check('research_and_segment_support','warning' if gaps else 'pass',
                '; '.join(gaps) if gaps else 'All tracks and segment buyer links are present; source meaning and representativeness still require human review.')
        except (ContractError,KeyError,ValueError) as exc:
            check('reproducibility','fail',str(exc))
    else:
        check('reproducibility','fail' if completed else 'not_evaluated','Complete saved evidence/specification/customers artifacts are required.')
    revision=state.get('corrections',0)
    review_path=directory/f'review-{revision}.json'
    if completed and review_path.exists():
        try:
            review=load(review_path);validate_schema(review,'population-review')
            if review['decision']!='accept' or {c['category'] for c in review['checks']}!=set(REVIEW_CATEGORIES) or len(review['checks'])!=len(REVIEW_CATEGORIES):
                raise ContractError('Final review must accept and cover all seven categories exactly once')
            if any(c['status']=='fail' for c in review['checks']) or any(f['severity']=='blocking' for f in review['findings']):raise ContractError('Accepted review contains failures/blockers')
            known_sources={s['source_id'] for s in evidence['sources']} if evidence else set()
            known_segments={s['segment_id'] for s in spec['segments']} if spec else set()
            pilot=load(directory/f'pilot-{revision}.json')
            known_customers={c['customer_id'] for c in pilot['customers']}
            for c in review['checks']:
                if set(c['source_ids'])-known_sources or set(c['segment_ids'])-known_segments or set(c['customer_ids'])-known_customers:
                    raise ContractError('Review references unknown source, segment or pilot customer')
            if any(set(f['source_ids'])-known_sources for f in review['findings']):raise ContractError('Review finding references unknown source')
            check('model_review_contract','pass','Accepted saved review has seven checks and no blockers. This is not an independent quality verdict.')
        except (ContractError,KeyError,ValueError,OSError) as exc:check('model_review_contract','fail',str(exc))
    else:check('model_review_contract','fail' if completed else 'not_evaluated','No final accepted review available.')
    audit_summary=None
    if audit is not None:
        validate_schema(audit,'evaluation-audit')
        if audit['run_id']!=state['run_id'] or audit['customers_sha256']!=input_hashes.get('customers_sha256'):
            raise ContractError('Human audit must bind to this run and exact customer artifact')
        if {c['category'] for c in audit['checks']}!=set(REVIEW_CATEGORIES):raise ContractError('Human audit requires all seven categories exactly once')
        if len(audit['checks'])!=len(REVIEW_CATEGORIES):raise ContractError('Duplicate human audit categories')
        if audit['reviewer'].strip().upper()=='UNASSIGNED' and any(c['status']!='not_evaluated' for c in audit['checks']):
            raise ContractError('Assign the human reviewer before recording audit judgments')
        audit_summary=audit
        statuses=[c['status'] for c in audit['checks']]
        check('human_quality_review','fail' if 'fail' in statuses else 'not_evaluated' if 'not_evaluated' in statuses else 'warning' if 'warning' in statuses else 'pass',
            'Human-authored audit supplied; reviewer identity is self-declared, not independently authenticated.')
    else:check('human_quality_review','not_evaluated','No human audit supplied; model acceptance and structural tests cannot substitute.')
    failures=any(c['status']=='fail' for c in checks)
    if not completed:status='run_not_completed'
    elif failures:status='evaluation_failed'
    elif state['mode']!='live':status='offline_only'
    elif any(c['check']=='human_quality_review' and c['status']=='not_evaluated' for c in checks):status='needs_human_review'
    else:status='reviewed_with_limitations'
    return {'evaluation_version':'1.0','run_id':state['run_id'],'mode':state['mode'],'status':status,
        'run_status':state['status'],'checks':checks,'input_hashes':input_hashes,
        'measurements':{'stage_calls':state['stage_calls'],'total_tokens':state['total_tokens'],
            'known_cost_usd':state['cost_usd'],'cost_uncertain':state.get('cost_uncertain',False),
            'elapsed_seconds':elapsed,'calls':calls},'segmentation_quality':quality,'human_audit':audit_summary,
        'limits':config['limits'],'limitations':['This evaluates saved artifacts, not actual buyer behavior or conversion.',
            'No automatic report establishes source truth or market representativeness.','A live-mode label reflects backend configuration; it is not independent proof of network execution.']}


def audit_template(report):
    if not report['input_hashes'].get('customers_sha256'):raise ContractError('A complete reproducible population is needed before human review')
    return {'run_id':report['run_id'],'customers_sha256':report['input_hashes']['customers_sha256'],
        'reviewer':'UNASSIGNED','checks':[{'category':c,'status':'not_evaluated','rationale':'Inspect source findings, segment rules and profiles; record concrete evidence and limitations.'} for c in REVIEW_CATEGORIES]}


def write_new(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as handle:json.dump(value,handle,indent=2,allow_nan=False);handle.write('\n')
