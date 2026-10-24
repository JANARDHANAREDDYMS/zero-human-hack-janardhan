"""Small model contract; code owns identifiers, field paths and canonical rules."""
import copy
import re
from .validation import validate_schema, validate_specification, ContractError


def category_catalog(evidence):
    """Stable, bounded slots. Offer evidence suggests fields, never buyer values."""
    catalog=[{'name':n,'type':'string','unit':None,'description':d} for n,d in [
        ('use_context','Hypothetical purchasing/usage setting'),
        ('usage_frequency','Hypothetical frequency of need'),
        ('category_experience','Hypothetical experience with the category')]]
    grouped={}
    for f in evidence['findings']:
        n=f['attribute'];v=f['value']
        if not re.fullmatch('[a-z][a-z0-9_]{0,59}',n) or n in {'price','choice','outcome','conversion','will_buy','preferred_product','winner','launch_verdict','recommended_product'}:continue
        t='boolean' if type(v) is bool else 'integer' if type(v) is int else 'number' if type(v) is float else 'string' if type(v) is str else None
        if t:grouped.setdefault(n,[]).append((t,f.get('unit')))
    for name,claims in sorted(grouped.items()):
        if len(catalog)>=11:break
        ts={t for t,u in claims};units={u for t,u in claims}
        if len(units)!=1 or not (len(ts)==1 or ts<={'integer','number'}):continue
        n='need_'+name
        catalog.append({'name':n,'type':'number' if ts=={'integer','number'} else claims[0][0],
            'unit':claims[0][1],'description':f'Hypothetical buyer need/context concerning {name}; not copied offer performance or measured preference'})
    return [{'slot':i,**c} for i,c in enumerate(catalog)]


def construct_specification(proposal,brief,evidence,count,seed):
    validate_schema(proposal,'compact-proposal')
    from .currency import currency_code
    proposal=copy.deepcopy(proposal)
    # The supplied price determines budget units; a model cannot redefine them.
    supplied=(brief.get('price') or {}).get('currency')
    proposal['market']['currency']=currency_code(supplied or proposal['market']['currency'])
    catalog=category_catalog(evidence)
    assumptions={'basis':'assumption','source_ids':[],'finding_ids':[],'note':''}
    segments=[]
    finding_catalog={f['finding_id']:f for f in evidence['findings']}
    source_ids={row['source_id'] for row in evidence['sources']}
    for index,s in enumerate(proposal['segments']):
        rationale=s['rationale']
        if set(rationale['finding_ids'])-finding_catalog.keys() or set(rationale['source_ids'])-source_ids:
            raise ContractError('Compact rationale references unknown source or finding')
        if rationale['basis']=='market_evidence':
            context=[fid for fid in rationale['finding_ids'] if finding_catalog[fid]['basis'] in {'unknown','assumption'}]
            if context:
                # Unknowns can explain limitations, but cannot support a market claim.
                # Preserve their IDs explicitly as context; never fabricate evidence.
                rationale['finding_ids']=[fid for fid in rationale['finding_ids'] if fid not in context]
                rationale['note']+=' Context only, not supporting market evidence: '+', '.join(context)+'.'
                if not rationale['finding_ids']:
                    rationale['basis']='assumption'
                    rationale['note']+=' No supporting market findings remain; this segment is an explicit hypothesis.'

        if s['budget_min']>s['budget_max']:raise ContractError('Compact budget minimum exceeds maximum')
        if len({x['attribute'] for x in s['tradeoffs']})!=len(s['tradeoffs']) or abs(sum(x['weight'] for x in s['tradeoffs'])-1)>1e-5:raise ContractError('Compact tradeoffs require distinct attributes and weights summing to one')
        note=s['assumption_note']+' Code uses uniform choices, a uniform budget range, and comfortable budget = 75% of maximum; these are coverage assumptions, not measured distributions.'
        p={**assumptions,'note':note}
        fields={}
        def put(name,rule):fields[name]={'rule':rule,'provenance':copy.deepcopy(p)}
        def constant(name,value):put(name,{'kind':'constant','value':value})
        def choice(name,values):put(name,{'kind':'choice','values':values})
        choice('purchase_trigger',s['purchase_triggers']);choice('current_solution',s['current_solutions'])
        constant('switching_barriers',s['switching_barriers']);constant('tradeoffs',s['tradeoffs'])
        put('budget.maximum',{'kind':'number','minimum':s['budget_min'],'maximum':s['budget_max']})
        put('budget.comfortable',{'kind':'scale','field':'budget.maximum','factor':0.75,'round':'none'})
        constant('budget.currency',proposal['market']['currency'])
        constant('budget.billing_period',(brief.get('price') or {}).get('billing_period') or 'one_time')
        constant('budget.scope_units',1)
        put('budget.upfront_maximum',{'kind':'reference','field':'budget.maximum'})
        constant('budget.scope_note','Assumed budget for one offered unit/service scope; billing commitments need separate review.')
        choice('urgency.deadline_days',s['deadline_days']);constant('urgency.basis','Assumed scenario horizon')
        for field,key in [('research_effort','research_effort'),('evidence_need','evidence_need'),('category_familiarity','familiarity'),('evaluation_action_budget','action_budget')]:choice('decision_style.'+field,s[key])
        seen=set()
        for row in s['category_values']:
            slot=row['slot']
            if slot in seen or slot>=len(catalog):raise ContractError('Duplicate or unknown compact category slot')
            seen.add(slot);attr=catalog[slot]
            key='boolean_values' if attr['type']=='boolean' else 'number_values' if attr['type'] in {'number','integer'} else 'text_values'
            if not row[key] or any(row[k] for k in ['text_values','number_values','boolean_values'] if k!=key):raise ContractError('Compact category values must match catalog type')
            if attr['type']=='integer' and any(type(v) is not int for v in row[key]):raise ContractError('Compact integer values must be integers')
            choice('category_context.'+attr['name'],row[key])
            fields['category_context.'+attr['name']]['provenance']['note']=row['note']+' Hypothetical range; not measured buyer data.'
        if seen!=set(range(len(catalog))):raise ContractError('Compact category slots must cover the supplied catalog exactly once')
        segments.append({'segment_id':f'segment-{index+1}','name':s['name'],'goal':s['goal'],'count':s['count'],
            'rationale':s['rationale'],'situation':s['situation'],'fields':fields,
            'requirements':[{'attribute':'price','operator':'lte','constraint':'hard',
                'value_rule':{'kind':'reference','field':'budget.maximum'},'provenance':copy.deepcopy(p)}],
            'constraints':[{'left':'budget.comfortable','operator':'lte','right':{'field':'budget.maximum'},'message':'Comfortable budget cannot exceed maximum.'}]})
    spec={'schema_version':'2.0','product_id':brief['product_id'],'population_version':'compact-1',
        'seed':seed,'target_count':count,'market':proposal['market'],
        'market_provenance':{**assumptions,'note':proposal['market_note']},
        'allocation_basis':'scenario_coverage_not_market_share',
        'attributes':{'price':{'type':'number','unit':proposal['market']['currency'],'description':'Comparable price for the declared budget scope and billing period'},
            **{c['name']:{k:c[k] for k in ['type','unit','description']} for c in catalog}},'segments':segments}
    validate_specification(spec,evidence)
    return spec
