"""Versioned concept-interest simulation and evidence-linked conversational reports."""
import json,math
from collections import Counter,defaultdict
from pathlib import Path
from .pipeline import read,save,fingerprint,build_offers,choose_customers,profile_fields,profile_path,validate_decision,SCHEMAS
from customer_generation.validation import validate_schema

VERSION='concept-interest-v2'
SCENARIO={'mode':VERSION,'target_offer_id':'target','assume_target_available':True,
    'assume_target_delivers_stated_features':True,'assume_stated_target_price':True,
    'assumptions_are_not_verified_facts':True,'purchase_checks_are_separate_from_concept_choice':True,
    'no_physical_or_browser_testing':True}
LEGACY_KEYS=set(read(SCHEMAS/'customer-decision.schema.json')['properties'])

def validate_customer(data,customer,offers,evidence):
    validate_schema(data,'customer-concept-decision')
    validate_decision({k:data[k] for k in LEGACY_KEYS},customer,offers,evidence)
    ids={f['finding_id'] for f in evidence['findings']}
    story=data['customer_story']
    for path in story['profile_fields']:profile_path(customer,path)
    for item in [story,*data['purchase_checks']]:
        if not set(item['finding_ids'])<=ids:raise ValueError('Unknown story/check evidence reference')
    return data

def eligible_offers(customer,offers):
    result=[]
    for offer in offers:
        probe={'customer_id':customer['customer_id'],'decision':'choose_product' if offer['offer_id']=='target' else 'choose_alternative',
            'selected_offer_id':offer['offer_id'],'headline':'Eligibility probe','reasons':[{'explanation':'Budget check','profile_fields':['budget.maximum'],'finding_ids':[]}],
            'objections':[],'missing_information':[],'change_that_might_help':'Eligibility probe','limitations':['Code check, not customer feedback.']}
        try:validate_decision(probe,customer,offers,{'findings':[]});entry={'offer_id':offer['offer_id'],'eligible':True,'reason':None}
        except ValueError as error:entry={'offer_id':offer['offer_id'],'eligible':False,'reason':str(error)}
        result.append(entry)
    return result

def validate_narrative(data,customers,*,allow_group_examples=False):
    validate_schema(data,'simulation-report')
    groups=defaultdict(set);ids={c['customer_id'] for c in customers}
    for c in customers:groups[c['segment_id']].add(c['customer_id'])
    seen=[]
    for item in [*data['overview'],*data['segments'],*data['improvements']]:
        refs=item['customer_ids']
        if len(set(refs))!=len(refs) or not set(refs)<=ids:raise ValueError('Unknown or duplicate report customer reference')
    for segment in data['segments']:
        sid=segment['segment_id'];seen.append(sid)
        if sid not in groups:raise ValueError('Report segment coverage mismatch')
        refs=set(segment['customer_ids'])
        if not refs<=groups[sid] or (not allow_group_examples and refs!=groups[sid]):raise ValueError('Report segment coverage mismatch')
    if len(set(seen))!=len(seen) or set(seen)!=set(groups):raise ValueError('Missing or duplicate report segment')
    return data

def summary_data(results,customers,offers):
    by_id={c['customer_id']:c for c in customers};groups={};issues=defaultdict(list)
    for r in results:
        sid=by_id[r['customer_id']]['segment_id']
        group=groups.setdefault(sid,{'count':0,'decisions':Counter(),'customer_ids':[]})
        group['count']+=1;group['decisions'][r['decision']]+=1;group['customer_ids'].append(r['customer_id'])
        for issue in r['objections']:issues[issue['category']].append({'customer_id':r['customer_id'],**issue})
    return {'version':VERSION,'label':'Interest assuming the proposed offer works as described; not actual purchases.',
        'evaluated':len(results),'decisions':dict(Counter(r['decision'] for r in results)),'segments':groups,'issues':dict(issues),'offers':offers,
        'purchase_checks':[{'customer_id':r['customer_id'],'checks':r['purchase_checks']} for r in results],
        'research_gaps':[{'offer_id':o['offer_id'],'name':o['name'],'gap':'Comparable numeric price, currency and billing terms are not established.'} for o in offers[1:] if not o.get('price')]}

REPORT_BATCH_SIZE=20
REPORT_FAN_IN=4
MAX_REPORT_PAYLOAD_BYTES=600000

def customer_payload(customer,offers,evidence):
    return {'customer':customer,'profile_field_paths':profile_fields(customer),'offers':offers,'evidence_findings':evidence['findings'],
        'scenario_assumptions':SCENARIO,'purchase_eligibility':eligible_offers(customer,offers)}

def report_call_count(count):
    nodes=math.ceil(count/REPORT_BATCH_SIZE);total=nodes
    while nodes>1:
        full,remainder=divmod(nodes,REPORT_FAN_IN)
        total+=full+(1 if remainder>1 else 0)
        nodes=full+(1 if remainder else 0)
    return total

def call_reserve(payload,schema,instructions,max_output=5000):
    # UTF-8 bytes are a deliberately conservative input-token bound; include
    # instructions, schema/envelope overhead and maximum completion allowance.
    return 2000+len(json.dumps(payload).encode())+len(json.dumps(schema).encode())+len(instructions['system_text'].encode())+max_output

def execution_plan(customers,offers,evidence,instructions):
    customer_schema=read(SCHEMAS/'customer-concept-decision.schema.json')
    customer_cap=sum(call_reserve(customer_payload(c,offers,evidence),customer_schema,instructions.for_stage('simulate_concept')) for c in customers)
    report_schema=read(SCHEMAS/'simulation-report.schema.json')
    overhead=call_reserve({},report_schema,instructions.for_stage('summarize_simulation'),24000)
    reports=report_call_count(len(customers))
    return {'customer_calls':len(customers),'report_calls':reports,'model_calls':len(customers)+reports,
        'report_batch_size':REPORT_BATCH_SIZE,'report_fan_in':REPORT_FAN_IN,
        'automatic_token_ceiling':customer_cap+reports*(MAX_REPORT_PAYLOAD_BYTES+overhead),
        'budget_note':'Conservative token ceiling, not expected usage, dollar cost or a credit reservation.'}

def report_payload(brief,customers,results,names,research_gaps):
    groups=defaultdict(list)
    for c in customers:groups[c['segment_id']].append(c['customer_id'])
    return {'product':{'name':brief['name'],'description':brief['description']},'scenario_assumptions':SCENARIO,
        'tested_segments':[{'segment_id':sid,'source_name':names.get(sid,sid),'tested_customer_ids':ids} for sid,ids in groups.items()],
        'customers':[{'customer_id':c['customer_id'],'segment_id':c['segment_id'],'result':r} for c,r in zip(customers,results)],
        'counts_computed_by_code':{'evaluated':len(customers),'decisions':dict(Counter(r['decision'] for r in results))},'research_gaps':research_gaps}

def generate_reports(calls,out,brief,customers,results,names,research_gaps):
    """Map every customer once, then reduce bounded summaries with explicit coverage."""
    lookup={c['customer_id']:(c,r) for c,r in zip(customers,results)}
    def node(name,selected,children=None):
        covered=[cid for child in children for cid in child['covered']] if children else [c['customer_id'] for c,_ in selected]
        if len(set(covered))!=len(covered):raise ValueError('Duplicate report coverage')
        payload=report_payload(brief,[c for c,_ in selected],[r for _,r in selected],names,research_gaps)
        if children:
            # All child summaries are retained. Original full decisions remain
            # saved; representative examples are selected by segment AND choice.
            payload['aggregation']={'mode':'summarize_all_child_feedback','covered_count':len(covered),
                'decision_counts':dict(Counter(lookup[cid][1]['decision'] for cid in covered)),
                'segment_counts':dict(Counter(lookup[cid][0]['segment_id'] for cid in covered)),
                'reference_note':'Linked customer IDs are representative examples; all child feedback is supplied.',
                'child_summaries':[{'node':child['name'],'covered_count':len(child['covered']),'data':child['data']} for child in children]}
            # Avoid duplicating full long responses at reduction levels.
            for item in payload['customers']:
                r=item['result'];item['result']={'customer_id':r['customer_id'],'decision':r['decision'],
                    'customer_story':{k:r['customer_story'][k] for k in ['situation','reason']}}
        # Every covered child customer is a valid source, not just the handful
        # of illustrative full responses retained in a reduction payload.
        legacy_payload=payload
        if children:
            payload=__import__('copy').deepcopy(payload)
            covered_customers=[lookup[cid][0] for cid in covered]
            groups=defaultdict(list)
            for c in covered_customers:groups[c['segment_id']].append(c['customer_id'])
            payload['allowed_customer_references']=[{'customer_id':c['customer_id'],'segment_id':c['segment_id']} for c in covered_customers]
            payload['tested_segments']=[{'segment_id':sid,'source_name':names.get(sid,sid),'tested_customer_ids':ids} for sid,ids in groups.items()]
            payload['counts_computed_by_code']={'evaluated':len(covered),'decisions':dict(Counter(lookup[cid][1]['decision'] for cid in covered))}
            payload['aggregation']['reference_note']='Any listed covered customer ID may support the summary. Full responses are examples; batch coverage and counts include everyone.'
        else:covered_customers=[c for c,_ in selected]
        # Existing pre-fix summaries already received all child feedback and IDs.
        # Reuse only the exact saved old/new input, preserving the original request.
        saved_input=calls.out/(name+'-input.json')
        if saved_input.exists() and (calls.out/(name+'-raw.json')).exists():
            previous=read(saved_input)
            if previous==legacy_payload or previous==payload:payload=previous
            else:raise ValueError('Saved report input mismatch')
        if len(json.dumps(payload).encode())>MAX_REPORT_PAYLOAD_BYTES:raise ValueError('Report node exceeds bounded payload size')
        output_limit=min(24000,max(5000,2000+600*len(payload['tested_segments'])))
        data=calls.invoke(name,'summarize_simulation',payload,'simulation-report',
            lambda value:validate_narrative(value,covered_customers,allow_group_examples=bool(children)),max_output=output_limit)
        save(out/(name+'-coverage.json'),{'covered_customer_ids':covered,'reference_customer_ids':[c['customer_id'] for c,_ in selected],
            'child_nodes':[c['name'] for c in children] if children else []})
        return {'name':name,'covered':covered,'data':data,'representatives':selected}
    if len(customers)<=REPORT_BATCH_SIZE:
        root=node('report',list(zip(customers,results)))
        return root['data'],{'mode':'direct','covered_customer_ids':root['covered'],'root':'report'}
    nodes=[]
    for start in range(0,len(customers),REPORT_BATCH_SIZE):
        selected=list(zip(customers[start:start+REPORT_BATCH_SIZE],results[start:start+REPORT_BATCH_SIZE]))
        nodes.append(node(f'report-batch-{len(nodes)+1:03}',selected))
    level=0
    while len(nodes)>1:
        level+=1;parents=[]
        for start in range(0,len(nodes),REPORT_FAN_IN):
            children=nodes[start:start+REPORT_FAN_IN]
            if len(children)==1:parents.append(children[0]);continue
            # Keep one actual example for each observed segment/decision pair.
            buckets={}
            for child in children:
                for c,r in child['representatives']:buckets.setdefault((c['segment_id'],r['decision']),(c,r))
            selected=list(buckets.values())
            name='report' if len(nodes)<=REPORT_FAN_IN else f'report-reduce-{level:02}-{len(parents)+1:03}'
            parents.append(node(name,selected,children))
        nodes=parents
    root=nodes[0]
    if set(root['covered'])!=set(lookup):raise ValueError('Incomplete final report coverage')
    return root['data'],{'mode':'batched_representative_references','covered_customer_ids':root['covered'],
        'root':root['name'],'batch_size':REPORT_BATCH_SIZE,'fan_in':REPORT_FAN_IN}

class Calls:
    def __init__(self,client,out,total_limit,*,retry_reports=False):self.client=client;self.out=out;self.limit=total_limit;self.tokens=0;self.new_calls=0;self.retry_reports=retry_reports
    def invoke(self,name,stage,payload,schema_name,validator,*,max_output=5000):
        raw=self.out/(name+'-raw.json');usage_path=self.out/(name+'-usage.json');input_path=self.out/(name+'-input.json')
        schema=read(SCHEMAS/(schema_name+'.schema.json'))
        if raw.exists():
            if read(input_path)!=payload:raise ValueError('Saved call input mismatch')
            data=read(raw);usage=read(usage_path)
        else:
            # An ambiguous prior network attempt is never silently billed again.
            ambiguous_retry=False
            if input_path.exists():
                if read(input_path)!=payload:raise ValueError('Saved call input mismatch')
                if not self.retry_reports or stage!='summarize_simulation':raise ValueError('Prior call has no reusable response; inspect it before retrying')
                ambiguous_retry=True
                from uuid import uuid4
                attempt=self.out/'report-retry-attempts';attempt.mkdir(exist_ok=True)
                save(attempt/(name+'-'+uuid4().hex+'.json'),{'stage':stage,'input_sha256':fingerprint(payload),
                    'explicit_resume':True,'previous_response_missing':True,'previous_usage':'unknown; original request may have consumed credits'})

            instructions=self.client.instructions.for_stage(stage)
            reserve=call_reserve(payload,schema,instructions,max_output)
            if self.tokens+reserve>self.limit:raise ValueError('Insufficient remaining token budget')
            save(input_path,payload)
            previous=getattr(self.client,'response_observer',None)
            if hasattr(self.client,'response_observer'):self.client.response_observer=lambda value:save(self.out/(name+'-bridge-response.json'),value)
            try:
                self.new_calls+=1
                response=self.client.call(stage,payload,{'max_tokens':max_output,'max_cost_usd':0.10,'timeout_seconds':100},schema)
            except Exception as error:
                save(self.out/(name+'-call-failure.json'),{'stage':stage,'error_type':type(error).__name__,
                    'transport_category':getattr(error,'category',None),'http_status':getattr(error,'status',None),
                    'response_saved':raw.exists(),'usage':'Unknown if no provider response was received'})
                raise
            finally:
                if hasattr(self.client,'response_observer'):self.client.response_observer=previous
            data=response.data;usage={'input_tokens':response.input_tokens,'output_tokens':response.output_tokens,'metadata':{**response.metadata,**({'previous_attempt_usage_unknown':True} if ambiguous_retry else {})}}
            save(usage_path,usage);save(raw,data)
        self.tokens+=usage['input_tokens']+usage['output_tokens']
        if self.tokens>self.limit:raise ValueError('Token budget exceeded')
        return validator(data)

def run(source,out,client,*,count=5,total_token_limit=None,resume=False):
    source=Path(source);out=Path(out)
    if read(source/'state.json')['status']!='completed':raise ValueError('Population must be completed')
    brief=read(source/'brief.json');evidence=read(source/'evidence.json');population=read(source/'customers.json')
    validate_schema(population,'generated-population')
    if not (brief['product_id']==evidence['product_id']==population['product_id']):raise ValueError('Product mismatch')
    customers=choose_customers(population,count);offers=build_offers(brief,evidence)
    from customer_generation.currency import simulation_currency_check
    simulation_currency_check(customers)
    if population.get('generator_version')=='2.1.0-stratified':
        from customer_generation.population_quality import population_quality,require_population_quality
        require_population_quality(population_quality(read(source/'specification.json'),population,brief))
    plan=execution_plan(customers,offers,evidence,client.instructions)
    if total_token_limit is None:total_token_limit=plan['automatic_token_ceiling']
    if type(total_token_limit) is not int or total_token_limit<1:raise ValueError('Token ceiling must be a positive integer')
    inputs={'version':VERSION,'scenario':SCENARIO,'brief':brief,'evidence':evidence,'customers':customers,'offers':offers,
        'instructions':{s:client.instructions.for_stage(s) for s in ['simulate_concept','summarize_simulation']},
        'schemas':{s:read(SCHEMAS/(s+'.schema.json')) for s in ['customer-concept-decision','simulation-report']}}
    digest=fingerprint(inputs)
    if (out/'manifest.json').exists():
        if not resume:raise ValueError('Output exists; use explicit resume to reuse saved responses')
        if read(out/'manifest.json')['input_sha256']!=digest:raise ValueError('Saved inputs/policy do not match')
    elif out.exists() and any(out.iterdir()):raise ValueError('Output directory is not empty')
    out.mkdir(parents=True,exist_ok=True);save(out/'inputs.json',inputs)
    manifest={'version':VERSION,'input_sha256':digest,'source_run':str(source.resolve()),'status':'running',
        'count':count,'synthetic':True,'assumptions':SCENARIO,'total_token_limit':total_token_limit,'execution_plan':plan}
    save(out/'manifest.json',manifest);calls=Calls(client,out,total_token_limit,retry_reports=resume);results=[]
    try:
        for index,c in enumerate(customers,1):
            payload=customer_payload(c,offers,evidence)
            result=calls.invoke(f'customer-{index:03}','simulate_concept',payload,'customer-concept-decision',
                lambda data:validate_customer(data,c,offers,evidence))
            save(out/f'customer-{index:03}.json',result);results.append(result)
            save(out/'progress.json',{'completed':len(results),'planned':count,'report_ready':False})
        summary=summary_data(results,customers,offers);save(out/'summary.json',summary)
        # Supply only tested groups. Population allocation is not market size.
        spec_path=source/'specification.json';names={s['segment_id']:s['name'] for s in read(spec_path)['segments']} if spec_path.exists() else {}
        narrative,coverage=generate_reports(calls,out,brief,customers,results,names,summary['research_gaps'])
        save(out/'report-narrative.json',{'input_sha256':digest,'data':narrative,'coverage':coverage})
        from .concept_reporting import render_report
        render_report(out,inputs,results,summary,narrative,coverage=coverage)
        manifest.update(status='completed',total_tokens=calls.tokens,new_model_calls=calls.new_calls);save(out/'manifest.json',manifest)
        if (out/'failure.json').exists():(out/'failure.json').unlink()
        save(out/'progress.json',{'completed':count,'planned':count,'report_ready':True})
    except Exception as error:
        manifest.update(status='failed',completed=len(results),total_tokens=calls.tokens,new_model_calls=calls.new_calls);save(out/'manifest.json',manifest)
        save(out/'failure.json',{'error_type':type(error).__name__,'message':str(error)[:300],
            'note':'No automatic retry. Saved valid responses can be reused with explicit --resume and --output.'})
        raise
    return out/'report.html'
