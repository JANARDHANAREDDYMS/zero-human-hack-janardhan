"""Private persistent workspaces for human review; zero automatic recruitment."""
import json,re,threading
from pathlib import Path
from datetime import datetime,timezone
from customer_simulation.pipeline import read,save,fingerprint
from .mcp import tool_data
from .policy import expert_policy,validate_expert_brief,feasibility_arguments
from .studies import build_draft,target_filters

def now():return datetime.now(timezone.utc).isoformat()

class ReviewError(ValueError):pass

def rows(data):
    values=data.get('data',[])
    if not isinstance(values,list):raise ReviewError('Unexpected Terac list response')
    return values

def register_workspace(root,workspace_id,plan,feasibility):
    if not re.fullmatch('[a-z0-9][a-z0-9-]{0,79}',workspace_id):raise ReviewError('Invalid expert workspace name')
    root=Path(root);root.mkdir(parents=True,exist_ok=True);root.chmod(0o700)
    folder=root/workspace_id;folder.mkdir(exist_ok=True)
    scopes=plan.get('concerns',plan.get('improvements',[]));requests=feasibility['requests']
    if len(scopes)!=len(requests):raise ReviewError('Scope/request counts differ')
    source={'plan':plan,'feasibility_ids':[r['response']['id'] for r in requests]}
    path=folder/'workspace.json'
    if path.exists():
        if read(path)['source_sha256']!=fingerprint(source):raise ReviewError('Workspace already holds different scopes')
        return read(path)
    jobs=[]
    for index,(scope,request) in enumerate(zip(scopes,requests),1):
        validate_expert_brief(scope)
        if feasibility_arguments(plan['product'],scope)!= {k:request['response'].get(k) for k in ['submissionCount','panelDescription','taskDescription']}:
            raise ReviewError('Feasibility was requested for a different scope; do not reuse its quote')
        jobs.append({'id':f'improvement-{index:02}','scope':scope,'feasibility':request['response'],
            'draft':None,'applicants':[],'decisions':[],'status':'awaiting_quote'})
    value={'id':workspace_id,'product':plan['product'],'policy':expert_policy(),'source_sha256':fingerprint(source),
        'jobs':jobs,'created_at':now(),'project_id':None,'recruitment_started_by_this_app':False}
    save(path,value);return value

class ExpertReview:
    def __init__(self,root,client_factory):self.root=Path(root);self.client_factory=client_factory;self.lock=threading.Lock()
    def path(self,workspace_id):
        if not re.fullmatch('[a-z0-9][a-z0-9-]{0,79}',workspace_id):raise ReviewError('Invalid expert workspace')
        path=self.root/workspace_id/'workspace.json'
        if not path.is_file():raise ReviewError('Expert workspace does not exist')
        return path
    def get(self,workspace_id):return read(self.path(workspace_id))
    def list(self):
        if not self.root.exists():return []
        return [{'id':d['id'],'product':d['product'],'jobs':len(d['jobs'])} for p in self.root.glob('*/workspace.json') for d in [read(p)]]
    def _once(self,folder,label,args,operation):
        request=folder/(label+'-request.json');response=folder/(label+'-response.json')
        if request.exists():
            if read(request)!=args:raise ReviewError('Saved operation has different inputs')
            if not response.exists():raise ReviewError('A previous operation has no recorded response. Inspect the Terac dashboard before retrying.')
            return read(response)
        with request.open('x') as f:json.dump(args,f,indent=2)
        result=operation();save(response,result);return result
    def refresh(self,workspace_id):
        with self.lock:
            path=self.path(workspace_id);data=read(path)
            if data.get('checked_at') and (datetime.now(timezone.utc)-datetime.fromisoformat(data['checked_at'])).total_seconds()<120:return data
            client=self.client_factory()
            for job in data['jobs']:
                f=job['feasibility']
                if f.get('status')=='RECEIVED':
                    current=tool_data(client.call('terac_get_feasibility_request',{'requestId':f['id']}))
                    if current.get('id')!=f['id']:raise ReviewError('Feasibility ID mismatch')
                    job['feasibility']=current
                if job['draft']:
                    oid=job['draft']['id'];op=tool_data(client.call('terac_get_opportunity',{'opportunityId':oid}))
                    if op.get('id')!=oid:raise ReviewError('Opportunity ID mismatch')
                    job['draft']=op
                    if op.get('customer_screening_review')!='manual_review':
                        job.update(status='manual_review_not_confirmed',applicants=[]);save(path,data);continue
                    provider_status=str(op.get('status','')).upper()
                    result=self._applicants(client,oid) if provider_status=='ACTIVE' else []
                    job['applicants']=result
                    job['status']='waiting_for_launch' if provider_status in {'DRAFT','CREATING'} else 'review_applicants' if provider_status=='ACTIVE' else 'study_not_recruiting'
                else:
                    fs=job['feasibility'].get('status')
                    job['status']='quote_ready' if fs=='RESPONDED' else 'feasibility_closed' if fs in {'LOST','NOT_PURSUED','WON'} else 'awaiting_quote'
                save(path,data)
            data['checked_at']=now();save(path,data);return data
    def _applicants(self,client,opportunity_id):
        result=[];cursor=None;seen=set()
        for _ in range(20):
            args={'opportunityId':opportunity_id,'limit':100}
            if cursor:args['cursor']=cursor
            response=tool_data(client.call('terac_get_applicants',args))
            for item in rows(response):
                if not isinstance(item,dict) or not isinstance(item.get('id'),str):raise ReviewError('Invalid applicant record')
                name=next((item.get(key) for key in ['name','full_name','display_name'] if isinstance(item.get(key),str)),None)
                if name is None:
                    for nested in ['participant','expert']:
                        profile=item.get(nested)
                        if isinstance(profile,dict):name=next((profile.get(key) for key in ['name','full_name','display_name'] if isinstance(profile.get(key),str)),None)
                        if name is not None:break
                view={'id':item['id'],'name':name,'screening_answers':item.get('screening_answers',[])}
                view['profile_summary']=next((item.get(key) for key in ['bio','professional_summary','headline'] if isinstance(item.get(key),str)),None)
                view['snapshot_sha256']=fingerprint(view);result.append(view)
            pagination=response.get('pagination',{})
            if not pagination.get('has_more'):return result
            cursor=pagination.get('next_cursor')
            if not cursor or cursor in seen:raise ReviewError('Invalid applicant pagination')
            seen.add(cursor)
        raise ReviewError('Applicant list exceeds the bounded page limit')
    def prepare_drafts(self,workspace_id):
        with self.lock:
            path=self.path(workspace_id);data=read(path);client=self.client_factory()
            ready=[j for j in data['jobs'] if not j['draft'] and j['feasibility'].get('status')=='RESPONDED' and j['feasibility'].get('costPerParticipant') is not None]
            if not ready:return data
            filters=target_filters(client)
            if not data['project_id']:
                projects=rows(tool_data(client.call('terac_list_projects',{'limit':100})))
                matches=[p for p in projects if p.get('name')=='Product improvement expert reviews']
                if matches:data['project_id']=matches[0]['id']
                else:
                    result=tool_data(self._once(path.parent,'create-project',{'name':'Product improvement expert reviews'},lambda:client.create_project('Product improvement expert reviews')))
                    data['project_id']=result['id']
                save(path,data)
            for job in ready:
                # Re-read quote: never attach an unpriced, spent or closed request.
                current=tool_data(client.call('terac_get_feasibility_request',{'requestId':job['feasibility']['id']}))
                if current.get('id')!=job['feasibility']['id']:raise ReviewError('Feasibility ID mismatch')
                args=build_draft(data['product'],job['scope'],current,data['project_id'],filters)
                result=tool_data(self._once(path.parent,'create-'+job['id'],args,lambda:client.create_draft(args)))
                if not result.get('id') or result.get('status') not in {'DRAFT','CREATING'}:raise ReviewError('Provider did not return a draft; inspect the dashboard')
                job.update(draft=result,draft_terms={'expected_days_to_complete':args['expected_days_to_complete'],'tasks':args['tasks']},status='waiting_for_launch');save(path,data)
                confirmed=tool_data(client.call('terac_get_opportunity',{'opportunityId':result['id']}))
                if confirmed.get('id')!=result['id']:raise ReviewError('Draft confirmation ID mismatch')
                job.update(draft=confirmed,status='waiting_for_launch' if confirmed.get('customer_screening_review')=='manual_review' else 'manual_review_not_confirmed');save(path,data)
            return data
    def decide(self,workspace_id,job_id,applicant_id,snapshot,decision,confirmed):
        if confirmed is not True or decision not in {'invite','decline'}:raise ReviewError('Review and confirm the specific applicant decision first')
        with self.lock:
            path=self.path(workspace_id);data=read(path)
            jobs=[j for j in data['jobs'] if j['id']==job_id]
            if len(jobs)!=1:raise ReviewError('Unknown improvement')
            job=jobs[0]
            if not job['draft']:raise ReviewError('No study exists for this improvement')
            if any(d['decision']=='invite' for d in job['decisions']):raise ReviewError('An expert has already been invited for this improvement')
            match=[a for a in job['applicants'] if a['id']==applicant_id]
            if len(match)!=1 or match[0]['snapshot_sha256']!=snapshot:raise ReviewError('Applicant changed; refresh and review again')
            client=self.client_factory();oid=job['draft']['id']
            opportunity=tool_data(client.call('terac_get_opportunity',{'opportunityId':oid}))
            if opportunity.get('id')!=oid or opportunity.get('customer_screening_review')!='manual_review' or str(opportunity.get('status','')).upper()!='ACTIVE':
                raise ReviewError('Study must be recruiting with manual applicant review enabled')
            if opportunity.get('num_participants')!=1:raise ReviewError('Study participant count changed; exactly one expert is permitted per improvement')
            if opportunity.get('filters')!=target_filters(client):raise ReviewError('Study targeting changed; verified US-only and English filters are required before inviting')
            latest=[a for a in self._applicants(client,oid) if a['id']==applicant_id]
            if len(latest)!=1 or latest[0]['snapshot_sha256']!=snapshot:raise ReviewError('Applicant is no longer waiting or their answers changed; refresh before deciding')
            if not latest[0]['screening_answers']:raise ReviewError('Screening answers are missing; do not decide without qualifications to review')
            args={'applicant_id':applicant_id,'snapshot':snapshot,'decision':decision}
            # One slot per applicant prevents conflicting or duplicated decisions.
            label='decision-'+fingerprint(applicant_id)[:20]
            self._once(path.parent,label,args,lambda:client.decide_applicant(applicant_id,decision,confirmed=True))
            job['decisions'].append({**args,'decided_at':now()});job['applicants']=[a for a in job['applicants'] if a['id']!=applicant_id]
            save(path,data);return data
