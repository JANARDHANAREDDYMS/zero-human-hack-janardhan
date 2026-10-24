"""Human-review concern generation only. No Terac SDK, MCP, hiring or submission."""
import html,json,math,re
from collections import Counter
from pathlib import Path
from .pipeline import read,save,fingerprint
from .concept import validate_customer,Calls,MAX_REPORT_PAYLOAD_BYTES
from customer_generation.validation import validate_schema

BATCH=40
FAN_IN=4

def prepare_sources(run):
    run=Path(run);inputs=read(run/'inputs.json');manifest=read(run/'manifest.json')
    if inputs.get('version')!='concept-interest-v2':raise ValueError('Use a concept-interest-v2 simulation; legacy decisions answer a different question')
    if fingerprint(inputs)!=manifest['input_sha256']:raise ValueError('Simulation input fingerprint mismatch')
    catalog=[];customers=[];decliners=[]
    for index,customer in enumerate(inputs['customers'],1):
        path=run/f'customer-{index:03}.json'
        if not path.exists():continue
        result=validate_customer(read(path),customer,inputs['offers'],inputs['evidence']);customers.append(result)
        if result['decision']=='choose_product':continue
        decliners.append(result['customer_id'])
        # Purchase checks are intentionally never fed into concern extraction.
        entries=result['objections'] or [{'category':'decline_reason','concern':reason['explanation'],
            'suggested_change':result['customer_story']['next_step'],'finding_ids':reason['finding_ids']} for reason in result['reasons']]
        for number,entry in enumerate(entries,1):
            catalog.append({'source_objection_id':f'signal-{index:04}-{number:02}',
                'customer_id':customer['customer_id'],'segment_id':customer['segment_id'],'decision':result['decision'],
                'kind':entry['category'],'concern':entry['concern'],'suggested_change':entry['suggested_change'],
                'finding_ids':entry['finding_ids'],'customer_context':{'current_solution':customer['current_solution'],
                    'budget':customer['budget'],'use_context':customer.get('category_context',{})}})
    if not customers:raise ValueError('No validated customer results available')
    return {'simulation_input_sha256':manifest['input_sha256'],'source_run':str(run.resolve()),
        'product':{k:inputs['brief'].get(k) for k in ['product_id','name','category','description','price','known_features']},
        'planned_customers':len(inputs['customers']),'completed_customers':len(customers),'declining_customer_ids':decliners,
        'source_simulation_status':manifest['status'],'rejection_catalog':catalog,
        'limitation':'These are concerns raised by simulated profiles, not confirmed real-world defects or real interviews.'}

def validate_groups(data,allowed):
    validate_schema(data,'review-concerns')
    titles=set()
    for concern in data['concerns']:
        refs=concern['source_objection_ids']
        if len(set(refs))!=len(refs) or not set(refs)<=allowed:raise ValueError('Unknown or duplicate concern source reference')
        title=' '.join(concern['title'].lower().split())
        if title in titles:raise ValueError('Duplicate concern title')
        titles.add(title)
    return data

def retain_supported_groups(data,allowed):
    """Withhold a whole concern if any citation is invalid; never invent a fix."""
    validate_schema(data,'review-concerns')
    import copy
    result=copy.deepcopy(data);accepted=[];withheld=[]
    for concern in result['concerns']:
        refs=concern['source_objection_ids']
        if set(refs)-allowed or len(refs)!=len(set(refs)):
            withheld.append({'title':concern['title'],'reason':'Unknown or duplicate source reference',
                'invalid_source_ids':sorted(set(refs)-allowed),'original_concern':concern})
        else:accepted.append(concern)
    result['concerns']=accepted
    if withheld:result['limitations'].append(f'{len(withheld)} proposed concern(s) were withheld because their source references could not be validated. They were not used to request experts.')
    validate_groups(result,allowed)
    return result,withheld

def enrich(data,sources):
    catalog={s['source_objection_id']:s for s in sources['rejection_catalog']};concerns=[]
    for item in data['concerns']:
        signals=[catalog[s] for s in item['source_objection_ids']]
        customers=sorted({s['customer_id'] for s in signals});members={s['customer_id']:s['segment_id'] for s in signals}
        concerns.append({**item,'affected_customer_count':len(customers),'customer_ids':customers,
            'segment_counts':dict(Counter(members.values())),
            'evidence_basis':'synthetic_customer_feedback','status':'needs_human_validation'})
    concerns.sort(key=lambda c:(-c['affected_customer_count'],c['title']))
    for index,c in enumerate(concerns,1):c['concern_id']=f'concern-{index:02}'
    from terac_integration.policy import expert_policy
    return {'expert_targeting_policy':expert_policy(),'source_run':sources['source_run'],'product':sources['product'],'completed_customers':sources['completed_customers'],
        'planned_customers':sources['planned_customers'],'non_choosing_customers':len(sources['declining_customer_ids']),
        'partial_customer_results':sources['completed_customers']<sources['planned_customers'],
        'concerns':concerns,'limitations':data['limitations'],
        'ranking_basis':'Distinct simulated customers whose cited objections support the concern; not measured prevalence or predicted sales.',
        'terac_status':'not_connected_or_submitted'}

def render(out,data):
    esc=lambda value:html.escape(str(value))
    lines=['# Concerns worth asking a real person about',data['product']['name'],
        f"Based on {data['completed_customers']} completed synthetic customers; {data['non_choosing_customers']} did not choose the proposed offer.",
        'These are simulation concerns, not confirmed defects. No expert has been contacted or hired.']
    body=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Concerns for human review</title><style>body{font:16px/1.65 system-ui;background:#f5f7fb;color:#1c2a40}main{max-width:1050px;margin:40px auto;padding:20px}section{background:white;border:1px solid #dce2ed;border-radius:14px;padding:24px;margin:20px 0}small{color:#53647b}details{margin-top:15px}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><main><h1>Concerns worth asking a real person about</h1>']
    body.extend('<p>'+esc(line)+'</p>' for line in lines[1:])
    if data.get('expert_targeting_policy'):
        preference='Expert sourcing preference: one English-speaking expert per improvement, residing and working in the United States only.'
        body.append('<p>'+esc(preference)+'</p>');lines.append(preference)
    if data['partial_customer_results']:body.append('<p><strong>Partial results:</strong> Some planned customers have not completed. Counts cover saved results only.</p>')
    for c in data['concerns']:
        pairs=[('What stopped these customers',c['explanation']),('Why a person could help',c['why_human_review']),
            ('Suggested expertise',c['suggested_expertise']),('Question to investigate',c['review_question']),
            ('One test to try',c['proposed_test']),('What would count as useful evidence',c['success_criterion']),
            ('Could a change help?',c['helpfulness']+' — '+c['helpfulness_reason'])]
        body.append('<section><h2>'+esc(c['title'])+'</h2><p>'+str(c['affected_customer_count'])+' non-choosing customers cited supporting concerns.</p>')
        lines.extend(['','## '+c['title'],str(c['affected_customer_count'])+' affected simulated customers.'])
        for label,value in pairs:
            body.append('<p><strong>'+esc(label)+':</strong> '+esc(value)+'</p>');lines.append(label+': '+value)
        body.append('<details><summary>Supporting customer and source references</summary><pre>'+esc(json.dumps({k:c[k] for k in ['customer_ids','segment_counts','source_objection_ids']},indent=2))+'</pre></details></section>')
    if not data['concerns']:body.append('<p>No supported concerns requiring human review were identified. The list was not padded.</p>')
    body.append('<h2>Limits of this feedback</h2>')
    for note in data['limitations']:body.append('<p>'+esc(note)+'</p>')
    body.append('</main></html>');(out/'concerns.html').write_text(''.join(body));(out/'concerns.md').write_text('\n'.join(lines)+'\n')

def generate(run,out,client,*,resume=False):
    sources=prepare_sources(run);out=Path(out)
    instructions=client.instructions.for_stage('extract_review_concerns')
    inputs={'version':'review-concerns-v1','sources':sources,'instructions':instructions}
    digest=fingerprint(inputs)
    if (out/'manifest.json').exists():
        if not resume or read(out/'manifest.json')['input_sha256']!=digest:raise ValueError('Use explicit resume with unchanged source inputs')
    elif out.exists() and any(out.iterdir()):raise ValueError('Output directory is not empty')
    out.mkdir(parents=True,exist_ok=True);save(out/'inputs.json',inputs)
    manifest={'input_sha256':digest,'status':'running','terac_connected':False,'experts_contacted':0}
    save(out/'manifest.json',manifest)
    catalog=sources['rejection_catalog'];allowed={s['source_objection_id'] for s in catalog}
    batches=[];batch=[]
    for signal in catalog:
        trial=batch+[signal]
        probe={'product':sources['product'],'rejection_catalog':trial,'source_basis':'synthetic_customer_decisions'}
        if batch and (len(trial)>BATCH or len(json.dumps(probe).encode())>MAX_REPORT_PAYLOAD_BYTES):
            batches.append(batch);batch=[signal]
        else:batch=trial
        if len(json.dumps({'product':sources['product'],'rejection_catalog':batch}).encode())>MAX_REPORT_PAYLOAD_BYTES:
            raise ValueError('A single source signal exceeds the bounded payload size')
    if batch:batches.append(batch)
    nodes=len(batches);bound=2*max(1,nodes)
    calls=Calls(client,out,bound*(MAX_REPORT_PAYLOAD_BYTES+50000))
    withheld_records=[]
    def checked(value,ids,node):
        accepted,withheld=retain_supported_groups(value,ids)
        withheld_records.extend({'node':node,**row} for row in withheld)
        return accepted
    try:
        if not catalog:data={'concerns':[],'limitations':[sources['limitation'],'No customers with saved results declined the proposed product.']}
        else:
            current=[]
            for batch in batches:
                ids={s['source_objection_id'] for s in batch}
                payload={'product':sources['product'],'rejection_catalog':batch,'source_basis':'synthetic_customer_decisions'}
                name='concerns' if len(batches)==1 else f'concerns-batch-{len(current)+1:03}'
                value=calls.invoke(name,'extract_review_concerns',payload,'review-concerns',lambda d:checked(d,ids,name),max_output=8000)
                current.append(value)
            level=0
            while len(current)>1:
                level+=1;parents=[]
                for start in range(0,len(current),FAN_IN):
                    children=current[start:start+FAN_IN]
                    if len(children)==1:parents.append(children[0]);continue
                    # Include every cited source ID from all children, not only
                    # selected representative customers: no dangling references.
                    ids={sid for d in children for c in d['concerns'] for sid in c['source_objection_ids']}
                    payload={'product':sources['product'],'mode':'merge_and_deduplicate_prior_concerns',
                        'prior_concerns':children,'allowed_source_objection_ids':sorted(ids),
                        'source_basis':'synthetic_customer_decisions'}
                    if len(json.dumps(payload).encode())>MAX_REPORT_PAYLOAD_BYTES:raise ValueError('Concern reduction payload exceeds bounded size')
                    name='concerns' if len(current)<=FAN_IN else f'concerns-reduce-{level:02}-{len(parents)+1:03}'
                    parents.append(calls.invoke(name,'extract_review_concerns',payload,'review-concerns',lambda d:checked(d,ids,name),max_output=8000))
                current=parents
            data=current[0]
        validate_groups(data,allowed);report=enrich(data,sources)
        save(out/'withheld-concerns.json',withheld_records)
        report['withheld_concern_count']=len(withheld_records)
        save(out/'concerns.json',report);render(out,report)
        manifest.update(status='completed',withheld_concern_count=len(withheld_records),concern_count=len(report['concerns']),total_tokens=calls.tokens,new_model_calls=calls.new_calls)
        save(out/'manifest.json',manifest)
    except Exception as error:
        manifest.update(status='failed',error_type=type(error).__name__,total_tokens=calls.tokens,new_model_calls=calls.new_calls);save(out/'manifest.json',manifest)
        raise
    return out/'concerns.html'
