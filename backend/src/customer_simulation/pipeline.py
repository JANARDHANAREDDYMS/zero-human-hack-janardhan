"""One independent, bounded offer comparison per customer; code-owned reports."""
import hashlib, html, json, math
from collections import Counter, defaultdict
from pathlib import Path
from customer_generation.validation import validate_schema

SCHEMAS=Path(__file__).resolve().parents[3]/'data/schemas'

def read(path):return json.loads(Path(path).read_text())
def save(path,value):
    path=Path(path);temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n');temp.replace(path)
def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

def build_offers(brief,evidence):
    """Preserve evidence as claims; never guess missing numeric specifications."""
    target={'offer_id':'target','name':brief['name'],'description':brief['description'],
        'price':brief.get('price'),'features':brief.get('known_features',{}),'claims':[],
        'limitations':['Client-supplied offer; performance and availability are not independently verified.']}
    groups=defaultdict(list)
    for finding in evidence['findings']:
        if finding.get('track')=='offers':
            if finding['basis']=='client_statement':target['claims'].append(finding)
            else:groups[finding['subject']].append(finding)
    offers=[target]
    for name,claims in sorted(groups.items()):
        # Comparison-page aggregates lack reliable model-to-feature alignment.
        if any(term in name.lower() for term in ('comparison page','comparison table','compare page')):continue
        offers.append({'offer_id':'alternative-'+hashlib.sha256(name.encode()).hexdigest()[:12],
            'name':name,'price':None,'features':{},'claims':claims,
            'limitations':['Use only supplied claims. Price currency/billing/availability may be incomplete; do not infer missing terms.']})
    return offers

def choose_customers(population,count):
    if type(count) is not int or not 1<=count<=len(population['customers']):raise ValueError('Invalid customer count')
    groups=defaultdict(list)
    for c in population['customers']:groups[c['segment_id']].append(c)
    selected=[]
    while len(selected)<count:
        for group in groups.values():
            if group and len(selected)<count:selected.append(group.pop(0))
    return selected

def profile_path(profile,path):
    """Resolve dotted fields, list indices, or unique attribute-keyed list entries.

    requirements.price names the one requirement with attribute == price. No
    fuzzy matching, case folding, missing-field defaults, or duplicate selection.
    """
    if not isinstance(path,str):raise ValueError('Unknown profile field reference')
    if path.startswith('customer.'):path=path[len('customer.'):]
    current=profile
    for part in path.split('.'):
        if isinstance(current,list):
            if part.isdigit():
                index=int(part)
                if index>=len(current):raise ValueError('Unknown profile field reference')
                current=current[index]
            else:
                matches=[item for item in current if isinstance(item,dict) and item.get('attribute')==part]
                if len(matches)!=1:raise ValueError('Unknown or ambiguous profile field reference')
                current=matches[0]
        elif isinstance(current,dict) and part in current:current=current[part]
        else:raise ValueError('Unknown profile field reference')
    return current

def profile_fields(profile,prefix=''):
    paths=[]
    if isinstance(profile,dict):
        for key,value in profile.items():
            if key=='provenance':continue
            path=prefix+'.'+key if prefix else key
            paths.append(path);paths.extend(profile_fields(value,path))
    elif isinstance(profile,list):
        for index,value in enumerate(profile):
            path=prefix+'.'+str(index);paths.append(path);paths.extend(profile_fields(value,path))
    return paths

def validate_decision(data,customer,offers,evidence):
    validate_schema(data,'customer-decision')
    if data['customer_id']!=customer['customer_id']:raise ValueError('Customer ID mismatch')
    ids={f['finding_id'] for f in evidence['findings']}
    for reason in data['reasons']:
        for path in reason['profile_fields']:profile_path(customer,path)
    for item in data['reasons']+data['objections']:
        if not set(item['finding_ids'])<=ids:raise ValueError('Unknown evidence reference')
    chosen=data['selected_offer_id'];by_id={o['offer_id']:o for o in offers}
    if data['decision'] in {'keep_current','defer'}:
        if chosen is not None:raise ValueError('Non-purchase decision cannot select an offer')
    else:
        if chosen not in by_id:raise ValueError('Unknown selected offer')
        if (data['decision']=='choose_product')!=(chosen=='target'):raise ValueError('Decision/offer mismatch')
        price=by_id[chosen].get('price');budget=customer['budget']
        if not price or price.get('currency')!=budget['currency'] or price.get('billing_period')!=budget['billing_period']:
            raise ValueError('Chosen offer has unknown or incompatible price terms')
        amount=price.get('amount')
        ceiling=min(budget['maximum'],budget.get('upfront_maximum',budget['maximum']))
        if type(amount) not in (int,float) or not math.isfinite(amount) or amount<0 or amount>ceiling:raise ValueError('Chosen offer exceeds hard budget')
        for req in customer.get('requirements',[]):
            if req.get('constraint')!='hard':continue
            if req['attribute']!='price' or req['operator']!='lte' or req.get('unit')!=price['currency']:
                raise ValueError('Unsupported hard requirement; this MVP cannot verify purchase eligibility')
            if amount>req['value']:raise ValueError('Chosen offer violates hard requirement')
    return data

SPECIALTIES={'price':'Consumer pricing / category strategy','positioning':'Product marketing / consumer research',
    'hardware':'Relevant category product engineering','usability':'UX research / interaction design',
    'service_delivery':'Service operations / category specialist','missing_information':'Category product reviewer'}

def write_reports(out,results,customers,offers):
    out=Path(out);by_id={c['customer_id']:c for c in customers}
    counts=Counter(r['decision'] for r in results);segments={};issues=defaultdict(list)
    for r in results:
        sid=by_id[r['customer_id']]['segment_id']
        segments.setdefault(sid,{'count':0,'decisions':Counter(),'customer_ids':[],'feedback':[]})
        segments[sid]['count']+=1;segments[sid]['decisions'][r['decision']]+=1;segments[sid]['customer_ids'].append(r['customer_id'])
        segments[sid]['feedback'].append({'customer_id':r['customer_id'],'headline':r['headline'],'objections':r['objections']})
        for issue in r['objections']:issues[issue['category']].append({'customer_id':r['customer_id'],**issue})
    summary={'label':'Synthetic offer comparison; not measured demand or conversion','evaluated':len(results),
        'decisions':dict(counts),'segments':segments,'issues':dict(issues),'offers':offers}
    save(out/'summary.json',summary)
    # Briefs are prepared only; no Terac hiring or message is sent here.
    briefs=[{'category':category,'expert_specialty':SPECIALTIES[category],
        'customer_count':len({i['customer_id'] for i in entries}),
        'review_question':'Assess whether these synthetic concerns are technically or commercially justified; identify missing evidence and one testable improvement.',
        'deliverable':'Short assessment with evidence, uncertainty, and one recommended experiment.',
        'supporting_concerns':entries,'status':'prepared_not_submitted','budget':None}
        for category,entries in sorted(issues.items(),key=lambda x:-len({i['customer_id'] for i in x[1]}))]
    save(out/'terac-review-briefs.json',briefs)
    from .reporting import render_report
    render_report(out,results,customers,offers,summary,briefs)
    return summary

def run(source,out,client,*,count=5,total_token_limit=80000):
    source=Path(source);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if read(source/'state.json')['status']!='completed':raise ValueError('Population must be completed')
    brief=read(source/'brief.json');evidence=read(source/'evidence.json');population=read(source/'customers.json')
    validate_schema(population,'generated-population')
    if not (brief['product_id']==evidence['product_id']==population['product_id']):raise ValueError('Product mismatch')
    customers=choose_customers(population,count);offers=build_offers(brief,evidence)
    inputs={'version':'offer-comparison-v1','brief':brief,'evidence':evidence,'customers':customers,'offers':offers,
        'instructions':client.instructions.for_stage('simulate_customer')}
    digest=fingerprint(inputs)
    manifest={'input_sha256':digest,'source_run':str(source.resolve()),'count':count,'mode':'bounded_offer_comparison',
        'synthetic':True,'limits':{'max_output_tokens_per_call':3000,'max_total_tokens':total_token_limit},'status':'running'}
    if (out/'manifest.json').exists() and read(out/'manifest.json')['input_sha256']!=digest:raise ValueError('Output directory belongs to different inputs')
    # Resumption reuses validated complete decisions. Failed attempts require a new run directory.
    if (out/'failure.json').exists():raise ValueError('Previous attempt failed; inspect failure before starting a new output directory')
    save(out/'manifest.json',manifest);save(out/'inputs.json',inputs)
    results=[];used=0
    try:
        schema=read(SCHEMAS/'customer-decision.schema.json')
        for index,c in enumerate(customers,1):
            decision_file=out/f'customer-{index:03}.json';usage_file=out/f'usage-{index:03}.json'
            cached=decision_file.exists()
            if cached:
                result=validate_decision(read(decision_file),c,offers,evidence);usage=read(usage_file)
            else:
                payload={'customer':c,'profile_field_paths':profile_fields(c),'offers':offers,'evidence_findings':evidence['findings'],
                    'contract':{'mode':'single_offer_comparison','target_offer_id':'target','no_physical_or_browser_testing':True}}
                # Conservative preflight reserve includes input and maximum completion.
                estimate=2000+len(json.dumps(payload).encode())+len(json.dumps(schema).encode())+len(inputs['instructions']['system_text'].encode())+3000
                if used+estimate>total_token_limit:raise ValueError('Token budget insufficient for next customer')
                save(out/f'input-{index:03}.json',payload)
                previous_observer=getattr(client,'response_observer',None)
                if hasattr(client,'response_observer'):
                    client.response_observer=lambda envelope:save(out/f'bridge-response-{index:03}.json',envelope)
                try:
                    response=client.call('simulate_customer',payload,{'max_tokens':3000,'max_cost_usd':0.10,'timeout_seconds':100},schema)
                finally:
                    if hasattr(client,'response_observer'):client.response_observer=previous_observer
                save(out/f'raw-{index:03}.json',response.data)
                usage={'input_tokens':response.input_tokens,'output_tokens':response.output_tokens,'metadata':response.metadata}
                save(usage_file,usage)
                used+=usage['input_tokens']+usage['output_tokens']
                result=validate_decision(response.data,c,offers,evidence);save(decision_file,result)
            if cached:used+=usage['input_tokens']+usage['output_tokens']
            if used>total_token_limit:raise ValueError('Token budget exceeded')
            results.append(result);write_reports(out,results,customers,offers)
        manifest.update(status='completed',total_tokens=used);save(out/'manifest.json',manifest)
    except Exception as error:
        manifest.update(status='failed',completed=len(results),total_tokens=used);save(out/'manifest.json',manifest)
        save(out/'failure.json',{'error_type':type(error).__name__,'message':'Simulation stopped. Inspect saved inputs, raw output, and usage; no automatic retry.'})
        raise
    return out/'report.html'


def replay_saved(source,out):
    """Revalidate all archived responses into a new report; zero model calls."""
    import shutil
    source=Path(source);out=Path(out)
    inputs=read(source/'inputs.json');manifest=read(source/'manifest.json')
    if fingerprint(inputs)!=manifest['input_sha256']:raise ValueError('Saved input fingerprint mismatch')
    if out.exists():raise ValueError('Replay output must be a new directory')
    customers=inputs['customers'];offers=inputs['offers'];evidence=inputs['evidence'];results=[];usage=[]
    for index,c in enumerate(customers,1):
        payload=read(source/f'input-{index:03}.json')
        if payload['customer']!=c or payload['offers']!=offers or payload['evidence_findings']!=evidence['findings']:
            raise ValueError('Saved customer input mismatch')
        results.append(validate_decision(read(source/f'raw-{index:03}.json'),c,offers,evidence))
        usage.append(read(source/f'usage-{index:03}.json'))
    out.mkdir(parents=True)
    for path in source.iterdir():
        if path.is_file() and (path.name in {'inputs.json'} or path.name.startswith(('input-','raw-','usage-','bridge-response-'))):
            shutil.copyfile(path,out/path.name)
    for index,result in enumerate(results,1):save(out/f'customer-{index:03}.json',result)
    write_reports(out,results,customers,offers)
    save(out/'manifest.json',{**manifest,'status':'completed','completed':len(results),
        'replayed_from':str(source.resolve()),'new_model_calls':0,
        'total_tokens':sum(u['input_tokens']+u['output_tokens'] for u in usage),
        'reference_resolution':'dotted fields, list indices, unique exact attribute keys'})
    return out/'report.html'
