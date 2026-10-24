"""Bounded rule interpreter for any declared category; no product-name branches."""
import copy
import hashlib
import json
import math
import random
from .validation import ContractError, field_order, validate_schema, validate_specification

GENERATOR_VERSION='2.0.0'

class SamplingExhausted(ContractError):
    """Rules could not supply the requested distinct consistent profiles."""

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)

def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def get_path(record,path):
    value=record
    for key in path.split('.'):
        if not isinstance(value,dict) or key not in value:raise ContractError(f'Unknown field {path}')
        value=value[key]
    return value

def set_path(record,path,value):
    parts=path.split('.');target=record
    for key in parts[:-1]:target=target.setdefault(key,{})
    target[parts[-1]]=copy.deepcopy(value)

def numeric(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

def compare(left,op,right):
    if op=='eq':return type(left)==type(right) and left==right
    if op=='in':return any(type(left)==type(x) and left==x for x in right)
    if not numeric(left) or not numeric(right):raise ContractError('Ordered rule comparison requires finite numbers')
    return {'lt':lambda:left<right,'lte':lambda:left<=right,'gt':lambda:left>right,'gte':lambda:left>=right}[op]()

def evaluate(rule,context,rng):
    kind=rule['kind']
    if kind=='constant':return copy.deepcopy(rule['value'])
    if kind=='choice':return copy.deepcopy(rng.choices(rule['values'],weights=rule.get('weights'),k=1)[0])
    if kind=='integer':return rng.randint(rule['minimum'],rule['maximum'])
    if kind=='number':return round(rng.uniform(rule['minimum'],rule['maximum']),rule.get('decimals',6))
    if kind=='reference':return copy.deepcopy(get_path(context,rule['field']))
    if kind=='scale':
        value=get_path(context,rule['field'])
        if not numeric(value):raise ContractError('Scale rule requires a numeric dependency')
        value=value*rule['factor']+rule.get('offset',0)
        if not math.isfinite(value):raise ContractError('Scale output must be finite')
        mode=rule.get('round','none')
        return math.floor(value) if mode=='floor' else math.ceil(value) if mode=='ceil' else round(value,6)
    if kind=='conditional':
        c=rule['when'];branch='then' if compare(get_path(context,c['field']),c['operator'],c['value']) else 'else'
        return evaluate(rule[branch],context,rng)
    raise ContractError(f'Unsupported rule kind: {kind}')

def matches_type(value,kind,requirement=False,operator=None):
    if operator=='contains':return isinstance(value,str)
    return {'number':lambda:numeric(value),'integer':lambda:isinstance(value,int) and not isinstance(value,bool),
        'string':lambda:isinstance(value,str),'boolean':lambda:isinstance(value,bool),
        'string_array':lambda:isinstance(value,list) and all(isinstance(v,str) for v in value)}[kind]()

def candidate_consistency(customer,segment,spec):
    b=customer['budget']
    if not 0<=b['comfortable']<=b['maximum']:return 'Comfortable budget exceeds maximum'
    if b['currency']!=spec['market']['currency']:return 'Budget and market currencies differ'
    if abs(sum(x['weight'] for x in customer['tradeoffs'])-1)>1e-5:return 'Tradeoff weights must sum to one'
    if len({x['attribute'] for x in customer['tradeoffs']})!=len(customer['tradeoffs']):return 'Duplicate tradeoff priorities'
    for k,v in customer['category_context'].items():
        if not matches_type(v,spec['attributes'][k]['type']):raise ContractError(f'Category field type mismatch: {k}')
    for c in segment['constraints']:
        right=get_path(customer,c['right']['field']) if 'field' in c['right'] else c['right']['value']
        if not compare(get_path(customer,c['left']),c['operator'],right):return c['message']
    return None

def stratum_values(rule,count,rng):
    """Balanced marginals, independently shuffled; no preference/outcome quotas."""
    kind=rule['kind']
    if kind=='choice':
        values=rule['values'];weights=rule.get('weights') or [1]*len(values)
        total=sum(weights);expected=[count*w/total for w in weights]
        counts=[math.floor(x) for x in expected]
        # Seeded tie-breaking avoids consistently favoring the first category.
        ranked=list(range(len(values)));rng.shuffle(ranked)
        ranked.sort(key=lambda i:expected[i]-counts[i],reverse=True)
        for i in ranked[:count-sum(counts)]:counts[i]+=1
        result=[copy.deepcopy(v) for v,n in zip(values,counts) for _ in range(n)]
    elif kind in {'number','integer'}:
        lo,hi=rule['minimum'],rule['maximum']
        if kind=='number':result=[round(lo+(hi-lo)*(i+rng.random())/count,rule.get('decimals',6)) for i in range(count)]
        else:result=[min(hi,lo+math.floor((hi-lo+1)*(i+rng.random())/count)) for i in range(count)]
    else:return None
    rng.shuffle(result)
    return result

def generate_population(spec,evidence,*,max_attempts_per_customer=10,stratified=False,on_customer=None):
    """Return a validated population or fail without writing any partial output.

    Sampling randomness is isolated to a local seeded generator. Attempts are
    capped to prevent contradictory or insufficiently diverse rules looping.
    """
    if isinstance(max_attempts_per_customer,bool) or not isinstance(max_attempts_per_customer,int) or not 1<=max_attempts_per_customer<=100:
        raise ContractError('Attempt multiplier must be an integer between 1 and 100')
    validate_specification(spec,evidence)
    rng=random.Random(spec['seed']);customers=[];seen=set();attempts=0;rejections=0
    for segment in spec['segments']:
        order=field_order(segment['fields']);accepted=0;limit=segment['count']*max_attempts_per_customer
        schedules={path:stratum_values(segment['fields'][path]['rule'],segment['count'],rng) for path in order} if stratified else {}
        last_reason='Duplicate profile'
        for _ in range(limit):
            if accepted==segment['count']:break
            attempts+=1
            customer={'customer_id':f"{spec['product_id']}-{len(customers)+1:04d}",
                'segment_id':segment['segment_id'],'synthetic':True,
                'market':copy.deepcopy(spec['market']),'goal':segment['goal'],'category_context':{}}
            provenance=[{'field':'market','basis':spec['market_provenance']['basis'],
                'source_ids':spec['market_provenance']['source_ids'],'finding_ids':spec['market_provenance']['finding_ids'],'note':spec['market_provenance']['note']},
                {'field':'segment_id,goal','basis':segment['rationale']['basis'],
                'source_ids':segment['rationale']['source_ids'],'finding_ids':segment['rationale']['finding_ids'],'note':segment['rationale']['note']}]
            for path in order:
                definition=segment['fields'][path]
                schedule=schedules.get(path)
                set_path(customer,path,schedule[accepted] if schedule is not None else evaluate(definition['rule'],customer,rng))
                p=definition['provenance'];provenance.append({'field':path,'basis':p['basis'],'source_ids':p['source_ids'],'finding_ids':p['finding_ids'],'note':p['note']})
            customer['requirements']=[]
            for template in segment['requirements']:
                attr=spec['attributes'][template['attribute']]
                value=evaluate(template['value_rule'],customer,rng)
                if not matches_type(value,attr['type'],True,template['operator']):
                    raise ContractError(f"Requirement type mismatch: {template['attribute']}")
                customer['requirements'].append({'attribute':template['attribute'],'operator':template['operator'],
                    'constraint':template['constraint'],'value':value,'unit':attr['unit']})
                p=template['provenance'];provenance.append({'field':f"requirements.{template['attribute']}",
                    'basis':p['basis'],'source_ids':p['source_ids'],'finding_ids':p['finding_ids'],'note':p['note']})
            customer['provenance']=provenance
            validate_schema(customer,'customer-v2')
            reason=candidate_consistency(customer,segment,spec)
            sig=fingerprint({k:v for k,v in customer.items() if k not in {'customer_id','segment_id','provenance'}})
            if reason or sig in seen:
                rejections+=1;last_reason=reason or 'Duplicate profile';continue
            customers.append(customer);seen.add(sig);accepted+=1
            if on_customer:on_customer(copy.deepcopy(customer),len(customers),spec['target_count'])
        if accepted!=segment['count']:
            raise SamplingExhausted(f"Segment {segment['segment_id']}: generated {accepted}/{segment['count']} within {limit} attempts. Last issue: {last_reason}")
    result={'schema_version':'2.0','product_id':spec['product_id'],'population_version':spec['population_version'],
        'seed':spec['seed'],'specification_sha256':fingerprint(spec),'evidence_sha256':fingerprint(evidence),
        'generator_version':'2.1.0-stratified' if stratified else GENERATOR_VERSION,'status':'structurally_validated_synthetic',
        'count':len(customers),'customers':customers,'validation':{'attempts':attempts,'rejections':rejections,'behavioral_validity':'not_evaluated'}}
    validate_schema(result,'generated-population')
    return result
