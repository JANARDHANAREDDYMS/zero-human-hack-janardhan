"""Staged harness with immutable snapshots, validation gates, and bounded repair."""
import copy
import math
import time
from dataclasses import asdict
from .sampling import generate_population, fingerprint
from .population_quality import population_quality,require_population_quality
from .state import RunLimits, RunState, StageResponse, utc_now
from .quality import segmentation_quality
from .instructions import REVIEW_CATEGORIES
from .storage import RunStore
from .validation import ContractError, validate_intake, validate_evidence, validate_specification, validate_schema


class PipelineError(RuntimeError):
    pass


class LimitExceeded(PipelineError):
    pass


class ReviewRejected(PipelineError):
    pass


def check_limits(limits):
    for name in ['max_stage_calls','max_total_tokens','max_tokens_per_call','pilot_per_segment']:
        value = getattr(limits, name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ContractError(f'{name} must be a positive integer')
    if limits.max_corrections not in (0, 1) or isinstance(limits.max_corrections, bool):
        raise ContractError('Only zero or one correction is supported')
    for name in ['max_cost_usd','timeout_seconds','max_elapsed_seconds']:
        value = getattr(limits, name)
        if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value) or value <= 0:
            raise ContractError(f'{name} must be positive and finite')


def run_generation(intake, backend, run_root, run_id, *, target_count=50, seed=42, limits=None, pause_after_segmentation=False):
    """Return terminal state; failed runs keep artifacts but never final customers.

    Backend exceptions are classified and saved. Invalid run configuration or
    an already existing run directory raises before a new run starts. Resume
    and concurrent writes to the same run are intentionally unsupported.
    """
    limits = limits or RunLimits()
    check_limits(limits)
    if type(target_count) is not int or not 1 <= target_count <= 10000:
        raise ContractError('target_count must be an integer from 1 to 10000')
    if type(seed) is not int or seed < 0:
        raise ContractError('seed must be a nonnegative integer')
    if backend.mode not in {'offline_fixture','live'}:
        raise ContractError('Backend mode must be explicit')
    # Reject non-JSON configuration before reserving a run directory.
    try:
        fingerprint(intake)
    except (ValueError,TypeError) as exc:
        raise ContractError('Intake must contain serializable finite JSON') from exc
    store = RunStore(run_root, run_id)
    state = RunState(run_id=run_id, mode=backend.mode, backend=backend.name)
    started = time.monotonic()
    original = copy.deepcopy(intake)

    def persist():
        store.write('state.json', state.to_dict())

    def artifact(name, value):
        state.artifacts[name] = store.write(name, value)
        persist()

    def event(stage, status, **extra):
        state.stage = stage
        state.events.append({'at':utc_now(), 'stage':stage, 'status':status, **extra})
        persist()

    def elapsed_gate():
        if time.monotonic() - started >= limits.max_elapsed_seconds:
            raise LimitExceeded('Run elapsed-time allowance exhausted')

    def invoke(stage, payload):
        elapsed_gate()
        if state.stage_calls >= limits.max_stage_calls:
            raise LimitExceeded('Stage-call allowance exhausted')
        tokens_left = limits.max_total_tokens-state.total_tokens
        cost_left = limits.max_cost_usd-state.cost_usd
        if tokens_left <= 0 or cost_left <= 0:
            raise LimitExceeded('Token or cost allowance exhausted')
        event(stage, 'started')
        state.stage_calls += 1
        call_id = state.stage_calls
        allowances = {'max_tokens':min(tokens_left, limits.max_tokens_per_call),
            'max_cost_usd':cost_left,
            'timeout_seconds':min(limits.timeout_seconds, limits.max_elapsed_seconds-(time.monotonic()-started))}
        artifact(f'call-{call_id:02d}-request.json', {'stage':stage, 'input_sha256':fingerprint(payload),
            'payload':copy.deepcopy(payload), 'allowances':allowances, 'mode':state.mode})
        # A provider sees its own copy, not the evidence or accepted state objects.
        tick = time.monotonic()
        backend_error = None
        try:
            response = backend.execute(stage, copy.deepcopy(payload), copy.deepcopy(allowances))
        except Exception as exc:
            if not isinstance(getattr(exc, 'partial', None), StageResponse):
                raise
            backend_error = exc
            response = exc.partial
        if not isinstance(response, StageResponse):
            raise PipelineError('Backend must return structured data and explicit usage')
        if any(type(v) is not int or v < 0 for v in [response.input_tokens,response.output_tokens]):
            raise PipelineError('Invalid token usage report')
        if isinstance(response.cost_usd,bool) or not isinstance(response.cost_usd,(int,float)) or not math.isfinite(response.cost_usd) or response.cost_usd < 0:
            raise PipelineError('Invalid cost usage report')
        state.total_tokens += response.input_tokens+response.output_tokens
        state.cost_usd += response.cost_usd
        state.cost_uncertain = state.cost_uncertain or bool(response.metadata.get("cost_uncertain", False))
        artifact(f'call-{call_id:02d}-response.json', {'stage':stage, 'data':response.data,
            'duration_seconds':time.monotonic()-tick,
            'usage':{'input_tokens':response.input_tokens,'output_tokens':response.output_tokens,'cost_usd':response.cost_usd},
            'metadata':response.metadata})
        for name, value in response.artifacts.items():
            artifact(f'call-{call_id:02d}-{name}', value)
        if backend_error is not None:
            raise backend_error
        if response.input_tokens+response.output_tokens > allowances['max_tokens'] or response.cost_usd > cost_left:
            raise LimitExceeded('Backend exceeded its stage allowance; usage was recorded')
        if time.monotonic()-tick > allowances['timeout_seconds']:
            raise LimitExceeded('Backend exceeded its timeout; usage was recorded')
        elapsed_gate()
        event(stage, 'returned')
        return copy.deepcopy(response.data)

    def check_spec(spec, evidence):
        validate_specification(spec, evidence)
        if backend.mode=='live' and any('situation' not in s for s in spec['segments']):
            raise ContractError('Live proposals require a purchasing situation for every segment')
        if spec['product_id'] != original['product_id'] or spec['target_count'] != target_count or spec['seed'] != seed:
            raise ContractError('Proposed specification changed locked product/count/seed')

    persist()
    artifact('input.json', original)
    artifact('configuration.json', {'target_count':target_count,'seed':seed,'limits':asdict(limits),
        'mode':state.mode,'backend':state.backend,'harness_version':'0.4.1',
        'instruction_manifest':getattr(backend,'instruction_manifest',{})})
    try:
        event('intake_validation', 'started')
        if 'text' in original:
            validate_schema(original,'intake-submission')
            brief=invoke('intake',{'submission':original})
            validate_intake(brief)
            if brief['product_id']!=original['product_id']:
                raise ContractError('Intake extraction changed product ID')
            if original.get('research_question') and brief['research_question']!=original['research_question']:
                raise ContractError('Intake extraction changed supplied research question')
        else:
            validate_intake(original)
            brief=copy.deepcopy(original)
        artifact('brief.json', brief)
        event('intake_validation', 'passed')
        evidence = invoke('research', {'brief':brief})
        validate_evidence(evidence)
        if evidence['product_id'] != original['product_id']:
            raise ContractError('Research changed the product ID')
        artifact('evidence.json', evidence)
        event('evidence_validation', 'passed')
        spec = invoke('propose', {'brief':brief,'evidence':evidence,'target_count':target_count,'seed':seed})
        while True:
            revision = state.corrections
            artifact(f'specification-{revision}.json', spec)
            issue = None
            pilot = None
            try:
                event('specification_validation', 'started', revision=revision)
                check_spec(spec,evidence)
                quality=segmentation_quality(spec,evidence)
                artifact(f'segmentation-quality-{revision}.json',quality)
                # Construct deterministically but withhold final publication until review.
                population = generate_population(spec,evidence,stratified=True)
                coverage=population_quality(spec,population,brief)
                artifact(f'population-quality-{revision}.json',coverage)
                require_population_quality(coverage)
                elapsed_gate()
                selected=[]
                for segment in spec['segments']:
                    selected += [c for c in population['customers'] if c['segment_id']==segment['segment_id']][:limits.pilot_per_segment]
                pilot = {'status':'synthetic_pilot','count':len(selected),'customers':selected,
                    'specification_sha256':population['specification_sha256']}
                artifact(f'pilot-{revision}.json',pilot)
                event('specification_validation','passed',revision=revision)
            except ContractError as exc:
                issue={'type':'validation','message':str(exc)}
            if issue is None:
                review=invoke('review',{'brief':brief,'evidence':evidence,'specification':spec,'pilot':pilot,'segmentation_quality':quality,'population_quality':coverage})
                validate_schema(review,'population-review')
                artifact(f'review-{revision}.json',review)
                known_sources={source['source_id'] for source in evidence['sources']}
                checks=review['checks']
                if len({c['category'] for c in checks})!=len(REVIEW_CATEGORIES):
                    raise ContractError('Review must cover each required category exactly once')
                known_segments={s['segment_id'] for s in spec['segments']}
                known_customers={c['customer_id'] for c in pilot['customers']}
                for check in checks:
                    if set(check['source_ids'])-known_sources or set(check['segment_ids'])-known_segments or set(check['customer_ids'])-known_customers:
                        raise ContractError('Review check references unknown source, segment, or pilot customer')
                if backend.mode=='live' and (quality['warnings'] or any(s['status']=='provisional' for s in quality['segments'])):
                    if any(c['category']=='evidence_support' and c['status']=='pass' for c in checks):
                        raise ContractError('Missing buyer evidence must remain a review warning or failure')
                if review['decision']=='accept' and any(c['status']=='fail' for c in checks):
                    raise ContractError('Review cannot accept failed qualitative checks')
                failed_categories={c['category'] for c in checks if c['status']=='fail'}
                blocking_codes={f['code'] for f in review['findings'] if f['severity']=='blocking'}
                if failed_categories-blocking_codes:
                    raise ContractError('Each failed qualitative check requires a matching actionable blocking finding')
                if any(set(f['source_ids'])-known_sources for f in review['findings']):
                    raise ContractError('Review references unknown sources')
                if review['decision']=='accept' and any(f['severity']=='blocking' for f in review['findings']):
                    raise ContractError('Review cannot accept with blocking findings')
                if review['decision']=='revise' and not review['findings']:
                    raise ContractError('Revision requires actionable review findings')
                if review['decision']=='accept':
                    event('review','accepted',revision=revision)
                    break
                issue={'type':'review','message':'Reviewer requested changes','findings':review['findings']}
                if review['decision']=='reject':
                    raise ReviewRejected('Reviewer rejected the population; no final population published')
            artifact(f'issues-{revision}.json',issue)
            if state.corrections >= limits.max_corrections:
                raise ReviewRejected('Correction allowance exhausted; population remains incomplete')
            state.corrections += 1
            event('correction','started',attempt=state.corrections)
            issue={**issue,'sampling_context':{
                'method':'Fields are sampled independently within each segment. Every allowed current solution, purchase trigger and deadline can co-occur.',
                'required_repair':'Repair the segment distributions, not just one pilot customer. Every option must fit the stated situation. For a no-immediate-need group, exclude scheduled or urgent triggers and incompatible deadline options; do not relabel it to erase the nonbuyer situation.',
                'pilot':pilot or {},
                'limits':'Sparse evidence and authored distributions remain disclosed assumptions. Do not invent evidence or remove meaningful customer situations to pass.'}}
            artifact(f'correction-context-{revision}.json',issue)
            spec=invoke('correct',{'brief':brief,'evidence':evidence,'specification':spec,'issues':issue,
                'target_count':target_count,'seed':seed})
        elapsed_gate()
        artifact('specification.json',spec)
        if pause_after_segmentation:
            artifact('population-quality.json',coverage)
            artifact('segmentation-checkpoint.json',{
                'specification_sha256':fingerprint(spec),'evidence_sha256':fingerprint(evidence),
                'brief_sha256':fingerprint(brief),'target_count':target_count,'seed':seed})
            state.status='awaiting_segmentation_approval'
            event('segmentation_approval','waiting')
            persist()
            return state
        artifact('validation.json' ,{'status':'passed','count':population['count'],
            'specification_sha256':population['specification_sha256'],'evidence_sha256':population['evidence_sha256'],
            'review_mode':state.mode,'behavioral_validity':'not_evaluated'})
        artifact('customers.json',population)
        artifact('population-quality.json',coverage)
        state.status='completed'
        event('completed','passed')
    except Exception as exc:
        state.status = 'limit_exceeded' if isinstance(exc,LimitExceeded) else 'incomplete' if isinstance(exc,(ContractError,ReviewRejected)) else 'failed'
        # Error messages are stored; no traceback/request credentials are printed.
        state.error={'type':type(exc).__name__,'message':str(exc),'stage':state.stage}
        event(state.stage,'stopped',error_type=type(exc).__name__)
    state.finished_at=utc_now()
    persist()
    return state
