"""Deterministic design-coverage gates; never a claim about market prevalence."""
from collections import Counter
import math
from .sampling import get_path,canonical,fingerprint
from .validation import ContractError
from .currency import simulation_currency_check

def population_quality(spec,population,brief):
    errors=[];warnings=[];rows=[]
    customers=population['customers']
    counts=Counter(c['segment_id'] for c in customers)
    expected=Counter({s['segment_id']:s['count'] for s in spec['segments']})
    if counts!=expected or len(customers)!=spec['target_count']:errors.append('Segment allocation or total count differs from the declared design')
    if len({c['customer_id'] for c in customers})!=len(customers):errors.append('Duplicate customer IDs')
    try:simulation_currency_check(customers)
    except ValueError as error:errors.append(str(error))
    price=brief.get('price') or {};amount=price.get('amount')
    comparable=type(amount) in (int,float) and math.isfinite(amount) and amount>0
    affordable=0;priced=0
    for segment in spec['segments']:
        group=[c for c in customers if c['segment_id']==segment['segment_id']];n=len(group);diagnostics=[]
        signatures=[fingerprint({k:v for k,v in c.items() if k not in {'customer_id','provenance'}}) for c in group]
        if len(set(signatures))!=n:errors.append(f"{segment['segment_id']}: duplicate full profiles")
        for path,definition in segment['fields'].items():
            rule=definition['rule'];kind=rule['kind']
            if kind not in {'choice','number','integer'} or not n:continue
            values=[get_path(c,path) for c in group]
            if kind=='choice':
                weights=rule.get('weights') or [1]*len(rule['values']);total=sum(weights)
                actual=Counter(canonical(v) for v in values)
                if set(actual)-{canonical(v) for v in rule['values']}:errors.append(f"{segment['segment_id']}: {path} contains undeclared choices")
                if any(abs(actual[canonical(v)]-n*w/total)>1.000001 for v,w in zip(rule['values'],weights)):
                    errors.append(f"{segment['segment_id']}: {path} does not match declared categorical allocation within rounding tolerance")
                diagnostics.append({'field':path,'counts':dict(actual),'expected_weights':weights})
            elif kind in {'number','integer'} and any(v<rule['minimum'] or v>rule['maximum'] for v in values):
                errors.append(f"{segment['segment_id']}: {path} contains values outside its declared range")
            elif kind=='number' and rule['maximum']>rule['minimum']:
                bins=n;lo,hi=rule['minimum'],rule['maximum']
                counts_by_bin=Counter(min(bins-1,int((v-lo)/(hi-lo)*bins)) for v in values)
                if any(abs(counts_by_bin[i]-n/bins)>0.000001 for i in range(bins)):
                    errors.append(f"{segment['segment_id']}: {path} lacks balanced coverage across its declared range")
                diagnostics.append({'field':path,'range':[lo,hi],'equal_width_bin_counts':[counts_by_bin[i] for i in range(bins)]})
        eligible=[]
        for c in group:
            b=c['budget']
            if comparable and b['currency']==price.get('currency') and b['billing_period']==price.get('billing_period'):
                priced+=1;ok=min(b['maximum'],b.get('upfront_maximum',b['maximum']))>=amount;affordable+=ok;eligible.append(ok)
        context_signatures={canonical({k:get_path(c,k) for k in ['purchase_trigger','current_solution','category_context']}) for c in group}
        if n>1 and len(context_signatures)==1:warnings.append(f"{segment['segment_id']}: all customers share the same trigger, current solution and category context")
        rows.append({'segment_id':segment['segment_id'],'name':segment['name'],'count':n,
            'can_afford':sum(eligible),'cannot_afford':len(eligible)-sum(eligible),'budget_min':min((c['budget']['maximum'] for c in group),default=None),
            'budget_max':max((c['budget']['maximum'] for c in group),default=None),'distinct_contexts':len(context_signatures),'distributions':diagnostics})
    if comparable and priced!=len(customers):errors.append('Not all budgets use the supplied price currency and billing period')
    if priced>=4 and affordable in {0,priced}:
        errors.append('Population covers only one side of the offer price; declare and review broader affordability scenarios or an explicitly narrower research design before simulation')
    return {'status':'blocked' if errors else 'passed_with_warnings' if warnings else 'passed',
        'blocking_issues':errors,'warnings':warnings,'segments':rows,'can_afford':affordable,'comparable_customers':priced,
        'method':'Stratified marginal coverage within each declared segment; not market-calibrated joint distributions.',
        'limitations':['Scenario counts and budget ranges are assumptions unless independently supported.','Balanced marginals do not guarantee coherent combinations or representative buyers.','No purchase decisions or positive feedback are forced.']}

def require_population_quality(report):
    if report['blocking_issues']:raise ContractError('Population quality gate: '+'; '.join(report['blocking_issues']))
