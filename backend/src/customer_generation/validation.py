"""Local JSON contracts and semantic checks. No remote schema retrieval."""
import json
import math
from pathlib import Path
from functools import lru_cache
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

SCHEMAS = Path(__file__).resolve().parents[3] / 'data' / 'schemas'

class ContractError(ValueError):
    """Invalid input/specification or incompatible rule output."""

def _guard(value, depth=0, counter=None, limit=50000):
    counter = [0] if counter is None else counter
    counter[0] += 1
    if depth > 40 or counter[0] > limit:
        raise ContractError('Input exceeds structural limits')
    if isinstance(value, float) and not math.isfinite(value):
        raise ContractError('Non-finite numbers are not allowed')
    if isinstance(value, dict):
        if not all(isinstance(k, str) for k in value):
            raise ContractError('JSON object keys must be strings')
        for v in value.values(): _guard(v, depth+1, counter, limit)
    elif isinstance(value, list):
        for v in value: _guard(v, depth+1, counter, limit)
    elif value is not None and not isinstance(value, (str, int, float, bool)):
        raise ContractError('Input must contain only JSON values')

@lru_cache(maxsize=16)
def _schema_validator(name):
    resources=[]
    for path in SCHEMAS.glob('*.schema.json'):
        content=json.loads(path.read_text())
        resources.append((path.resolve().as_uri(),Resource.from_contents(content)))
    registry=Registry().with_resources(resources)
    path=SCHEMAS/f'{name}.schema.json'
    schema=json.loads(path.read_text())
    schema['$id']=path.resolve().as_uri()
    validator=Draft202012Validator(schema,registry=registry,format_checker=FormatChecker())
    return validator

def validate_schema(value,name):
    _guard(value, limit=2000000 if name=='generated-population' else 50000)
    errors=list(_schema_validator(name).iter_errors(value))
    if errors:
        error=errors[0]; loc='.'.join(map(str,error.absolute_path)) or '<root>'
        raise ContractError(f'{name} at {loc}: {error.message}')

def _unique(values, label):
    if len(set(values))!=len(values):raise ContractError(f'Duplicate {label}')

def validate_intake(value):
    validate_schema(value,'intake')

def validate_evidence(value):
    validate_schema(value,'evidence')
    sources={x['source_id'] for x in value['sources']}
    _unique([s['source_id'] for s in value['sources']],'source IDs')
    _unique([f['finding_id'] for f in value['findings']],'finding IDs')
    for finding in value['findings']:
        if set(finding['source_ids'])-sources:raise ContractError('Finding references unknown source')
        if finding['basis'] in {'provider_claim','observed_report'} and not finding['source_ids']:
            raise ContractError('Provider claim or observed report requires a source')
        if finding['basis']=='unknown' and finding['value'] is not None:
            raise ContractError('Unknown findings must retain a null value')

# Shared profile fields, not a category-specific field catalog.
LEAVES={'purchase_trigger','current_solution','tradeoffs','switching_barriers',
 'budget.comfortable','budget.maximum','budget.currency','budget.billing_period',
 'budget.scope_units','budget.upfront_maximum','budget.scope_note',
 'urgency.deadline_days','urgency.basis','decision_style.research_effort',
 'decision_style.evidence_need','decision_style.category_familiarity','decision_style.evaluation_action_budget'}

def dependencies(rule, depth=0):
    if depth>8:raise ContractError('Rule nesting exceeds eight levels')
    kind=rule['kind']
    if kind in {'reference','scale'}:return {rule['field']}
    if kind=='conditional':
        if rule['when']['operator']=='in' and not isinstance(rule['when']['value'],list):
            raise ContractError('An in condition requires a list')
        return {rule['when']['field']}|dependencies(rule['then'],depth+1)|dependencies(rule['else'],depth+1)
    if kind in {'number','integer'} and rule['minimum']>rule['maximum']:
        raise ContractError('Rule minimum exceeds maximum')
    if kind=='choice':
        if len({json.dumps(x,sort_keys=True) for x in rule['values']})!=len(rule['values']):
            raise ContractError('Choice values must be distinct')
        if 'weights' in rule:
            if len(rule['weights'])!=len(rule['values']):
                raise ContractError('Choice weights do not match values')
            if not math.isfinite(sum(rule['weights'])):
                raise ContractError('Choice weight sum must be finite')
    return set()

def field_order(fields):
    deps={k:dependencies(v['rule']) for k,v in fields.items()}
    known=set(fields)
    for k, refs in deps.items():
        if refs-known:raise ContractError(f'{k} references unknown fields: {sorted(refs-known)}')
    order=[]
    while deps:
        available=sorted(k for k,refs in deps.items() if refs<=set(order))
        if not available:raise ContractError('Cyclic rule dependencies')
        order.extend(available)
        for k in available:del deps[k]
    return order

def validate_specification(spec, evidence):
    validate_evidence(evidence)
    validate_schema(spec,'population-specification')
    if spec['product_id']!=evidence['product_id']:raise ContractError('Product IDs do not match')
    _unique([s['segment_id'] for s in spec['segments']],'segment IDs')
    if sum(s['count'] for s in spec['segments'])!=spec['target_count']:
        raise ContractError('Segment counts do not sum to target_count')
    forbidden={'choice','outcome','conversion','will_buy','preferred_product','launch_verdict','recommended_product','winner'}
    if set(spec['attributes']) & forbidden:
        raise ContractError('Population attributes cannot preassign buying outcomes')
    sources={s['source_id'] for s in evidence['sources']}
    findings={f['finding_id']:f for f in evidence['findings']}
    def check_provenance(p):
        if set(p['source_ids'])-sources or set(p['finding_ids'])-set(findings):
            raise ContractError('Provenance references unknown source or finding')
        if p['basis']=='market_evidence':
            if not p['finding_ids']:raise ContractError('Market evidence requires linked findings')
            for fid in p['finding_ids']:
                f=findings[fid]
                if f['basis'] in {'assumption','unknown'}:
                    raise ContractError('Assumptions/unknowns cannot become market evidence')
                if set(f['source_ids'])-set(p['source_ids']):
                    raise ContractError('Provenance omits a linked finding source')
    check_provenance(spec['market_provenance'])
    for seg in spec['segments']:
        check_provenance(seg['rationale'])
        fields=seg['fields']
        if LEAVES-set(fields):raise ContractError(f'Missing shared profile fields: {sorted(LEAVES-set(fields))}')
        for path, definition in fields.items():
            if path not in LEAVES and not (path.startswith('category_context.') and len(path.split('.'))==2):
                raise ContractError(f'Unsupported output path: {path}')
            if path.startswith('category_context.') and path.split('.')[1] not in spec['attributes']:
                raise ContractError(f'Category field lacks an attribute definition: {path}')
            check_provenance(definition['provenance'])
        field_order(fields)
        _unique([r['attribute'] for r in seg['requirements']],'requirement attributes')
        for r in seg['requirements']:
            attr=spec['attributes'].get(r['attribute'])
            if attr is None:raise ContractError('Requirement references undefined attribute')
            if r['operator'] in {'lte','gte'} and attr['type'] not in {'number','integer'}:
                raise ContractError('Ordered comparison requires a numeric attribute')
            if r['operator']=='contains' and attr['type']!='string_array':
                raise ContractError('Contains requires a declared string_array capability')
            if dependencies(r['value_rule'])-set(fields):raise ContractError('Requirement references unknown field')
            check_provenance(r['provenance'])
        for c in seg['constraints']:
            paths={c['left']}|({c['right']['field']} if 'field' in c['right'] else set())
            if paths-set(fields):raise ContractError('Constraint references unknown field')
