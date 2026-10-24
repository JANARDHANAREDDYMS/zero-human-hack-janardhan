"""Local-only demo: file/form -> existing compact research/profile pipeline."""
import base64,hashlib,hmac,io,json,os,re,secrets,threading,uuid,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from .config import AdapterConfig
from .pipeline import run_generation
from .state import RunLimits
from .tools.live import LiveBackend
from .approval import write_summary,summary_lines
from whop_integration.intake import prepare,MAX_MARKDOWN
from .worker_readiness import WorkerNotReady,check_worker

MAX_FILE=1_000_000

def extract_upload(name,raw):
    if not isinstance(name,str) or '/' in name or '\\' in name or len(name)>255:raise ValueError('Invalid filename')
    if len(raw)>MAX_FILE:raise ValueError('File exceeds 1 MB')
    if name.lower().endswith('.md'):
        if len(raw)>MAX_MARKDOWN:raise ValueError('Markdown exceeds 64 KB')
        try:return raw.decode('utf-8-sig')
        except UnicodeError:raise ValueError('Markdown must be UTF-8') from None
    if not name.lower().endswith('.dotm'):raise ValueError('Choose a .md or .dotm file')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            infos=z.infolist()
            if len(infos)>2000 or sum(i.file_size for i in infos)>10_000_000:raise ValueError('Template is too large when expanded')
            docs=[i for i in infos if i.filename=='word/document.xml']
            if len(docs)!=1 or docs[0].file_size>2_000_000 or docs[0].flag_bits&1:raise ValueError('Invalid or encrypted Word template')
            xml=z.read(docs[0])
        if b'<!DOCTYPE' in xml or b'<!ENTITY' in xml:raise ValueError('Unsupported XML declarations')
        root=ET.fromstring(xml);ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        paragraphs=[]
        for p in root.findall('.//w:p',ns):
            text=''.join(p.itertext()) if not p.findall('.//w:t',ns) else ''.join(t.text or '' for t in p.findall('.//w:t',ns))
            style=p.find('w:pPr/w:pStyle',ns)
            label=style.get('{'+ns['w']+'}val','') if style is not None else ''
            heading=re.fullmatch(r'Heading[1-6]',label,re.I)
            prefix='# ' if label.lower()=='title' else '## ' if heading else ''
            if text.strip():paragraphs.append(prefix+text.strip())
        text='\n'.join(paragraphs)
        if len(text.encode())>MAX_MARKDOWN:raise ValueError('Extracted text exceeds 64 KB')
        return text
    except (zipfile.BadZipFile,ET.ParseError,RuntimeError,KeyError):raise ValueError('Cannot read this Word template') from None

class Demo:
    def __init__(self,run_root,backend_factory=None,*,full_pipeline=False,target_count=50,client_factory=None,simulation_root=None,guided_flow=False,expert_review_root=None,expert_client_factory=None):
        self.full_pipeline=full_pipeline;self.target_count=target_count;self.guided_flow=guided_flow
        self.readiness_check=check_worker if full_pipeline and client_factory is None else None
        self.root=Path(run_root);self.token=secrets.token_urlsafe(32);self.lock=threading.Lock();self.pending={}
        from terac_integration.review import ExpertReview
        from terac_integration.studies import TeracStudiesMCP
        def expert_client():
            import os
            return TeracStudiesMCP(os.environ.get('TERAC_API_KEY'))
        self.expert_reviews=ExpertReview(expert_review_root or Path(__file__).resolve().parents[2]/'var/expert-review',expert_client_factory or expert_client)
        self.backend_factory=backend_factory or (lambda:LiveBackend(AdapterConfig.from_environment(),proposal_format='compact'))

        if full_pipeline:
            from .journey import Journey
            from .tools.llm import ModelBridgeClient
            def model_client():
                c=AdapterConfig.from_environment()
                from .tools.llm import configured_client
                return configured_client(c)
            self.journey=Journey(self.root,simulation_root or self.root.parent/'simulations',self.backend_factory,client_factory or model_client,target_count=target_count,guided_flow=guided_flow)

    def preview(self,payload,identity='demo'):
        if not isinstance(payload,dict) or set(payload)-{'fields','filename','file_base64'}:raise ValueError('Invalid demo input')
        data={'fields':payload.get('fields',{})}
        if 'file_base64' in payload:
            try:raw=base64.b64decode(payload['file_base64'],validate=True)
            except (ValueError,TypeError):raise ValueError('Invalid file encoding') from None
            name=payload.get('filename','');text=extract_upload(name,raw)
            # Existing intake parser accepts Markdown text; .dotm text has been
            # extracted without executing or retaining macros.
            data.update(filename='extracted.md',markdown=text)
        result=prepare(identity,data)
        if 'file_base64' in payload:
            result['source']={'filename':payload['filename'],'extracted_text':data['markdown'],'macros_executed':False}
        return result

    def start(self,payload):
        with self.lock:
            if any(v=='running' for v in self.pending.values()):raise RuntimeError('A demo run is already active')
            run_id='demo-'+uuid.uuid4().hex
            prepared=self.preview(payload,run_id[5:])
            if not prepared['can_submit']:raise ValueError('Add product name and description before starting')
            if self.readiness_check:self.readiness_check()
            backend=self.backend_factory() # Validate credentials before starting.
            self.pending[run_id]='running'
        def work():
            try:
                if self.full_pipeline:
                    self.journey.execute(run_id,prepared['brief'])
                    return
                state=run_generation(prepared['brief'],backend,self.root,run_id,target_count=self.target_count,seed=42,
                    limits=RunLimits(max_tokens_per_call=40000,max_total_tokens=160000,max_cost_usd=1))
                if state.status=='completed':write_summary(self.root/run_id)
            except Exception:
                with self.lock:self.pending[run_id]='failed'
            finally:
                with self.lock:
                    if self.pending[run_id]=='running':self.pending[run_id]='stopped'
        threading.Thread(target=work,daemon=True).start()
        return {'run_id':run_id,'status':'running'}

    def retry_groups(self,run_id):
        """One explicit bounded attempt, reusing research and addressing saved issues."""
        from customer_simulation.pipeline import read,save
        from .state import StageResponse
        state=self.status(run_id)
        source=self.root/run_id;generation=read(source/'state.json')
        replay=(source/'replayed-specification.json').exists()
        if not state.get('quality_review') and not replay:raise ValueError('No saved proposal or customer-group review to recover')
        if (generation.get('error') or {}).get('type')!='ReviewRejected' and not replay:raise ValueError('This failure needs a different recovery')
        brief=read(source/'brief.json');evidence=read(source/'evidence.json')
        revision=generation.get('corrections',0);spec=read(source/'replayed-specification.json') if replay else read(source/f'specification-{revision}.json')
        review=read(source/f'review-{revision}.json') if (source/f'review-{revision}.json').exists() else {}
        issues={'type':'review','message':'Create a richer, internally consistent representation of the customer situations. Fix the cited conflicts without inventing buyer evidence.','findings':review.get('findings',[])}
        issues['sampling_context']={'method':'Fields are independently sampled within each segment; all allowed trigger, current-solution and deadline options can co-occur.',
            'required_repair':'Fix the complete distributions so every combination fits the segment situation. Preserve no-immediate-need customers without urgent triggers or conflicting deadlines. Do not merely change one sampled customer or erase the nonbuyer situation.',
            'pilot':read(source/f'pilot-{revision}.json') if (source/f'pilot-{revision}.json').exists() else {}}
        if evidence['product_id']!=brief['product_id']:raise ValueError('Research product mismatch')
        with self.lock:
            if any(v=='running' for v in self.pending.values()):raise RuntimeError('A demo run is already active')
            if self.readiness_check:self.readiness_check()
            delegate=self.backend_factory();new_id='demo-'+uuid.uuid4().hex
            if replay and hasattr(delegate,'last_compact_proposal'):
                delegate.last_compact_proposal=read(source/'call-02-compact_propose-raw-output.json')
            self.pending[new_id]='running'
        journal={'run_id':new_id,'guided_flow':True,'retry_of':run_id,'status':'running','stage':'research_and_profiles',
            'target_count':state['target_count'],'generation_status':'running','simulation_status':'pending','concerns_status':'pending','events':[],'terac_actions':False}
        save(self.journey.state_path(new_id),journal)
        class RecoveryBackend:
            name=delegate.name;mode=delegate.mode
            instruction_manifest=getattr(delegate,'instruction_manifest',{})
            def execute(self,stage,payload,limits):
                if stage=='research':return StageResponse(evidence,0,0,0,metadata={'reused_from_run':run_id})
                if stage=='propose' and replay:return StageResponse(spec,0,0,0,metadata={'reused_proposal_from_run':run_id})
                if stage=='propose':return delegate.execute('correct',{**payload,'specification':spec,'issues':issues},limits)
                return delegate.execute(stage,payload,limits)
        def work():
            nonlocal journal
            try:
                result=run_generation(brief,RecoveryBackend(),self.root,new_id,target_count=state['target_count'],seed=spec['seed'],
                    limits=RunLimits(max_tokens_per_call=40000,max_total_tokens=160000,max_cost_usd=1),pause_after_segmentation=True)
                journal={'run_id':new_id,'guided_flow':True,'retry_of':run_id,'status':'awaiting_segmentation_approval' if result.status=='awaiting_segmentation_approval' else 'failed',
                    'stage':'segmentation_approval' if result.status=='awaiting_segmentation_approval' else 'research_and_profiles','target_count':state['target_count'],
                    'generation_status':result.status,'simulation_status':'pending','concerns_status':'pending','events':[],'terac_actions':False}
                save(self.journey.state_path(new_id),journal)
            except Exception:
                journal.update(status='failed',generation_status='failed',error={'message':'The improvement attempt could not finish. Saved research and earlier work remain available. Check the service or input error before retrying.'})
                save(self.journey.state_path(new_id),journal)
            finally:
                with self.lock:self.pending[new_id]='stopped'
        threading.Thread(target=work,daemon=True).start()
        return {'run_id':new_id,'status':'running','retry_of':run_id}

    def resume(self,run_id):
        self.status(run_id)
        if not self.full_pipeline:raise ValueError('Full pipeline is not enabled')
        with self.lock:
            if any(v=='running' for v in self.pending.values()):raise RuntimeError('A demo run is already active')
            if not self.journey.state_path(run_id).exists():raise ValueError('Not a connected journey')
            population=self.root/run_id
            generation_status=json.loads((population/'state.json').read_text())['status'] if (population/'state.json').exists() else None
            local_profile_recovery=self.guided_flow and generation_status=='running' and (population/'segmentation-checkpoint.json').exists() and (population/'segmentation-approval.json').exists()
            if generation_status!='completed' and not local_profile_recovery:raise ValueError('Generation must complete before a journey can resume')
            brief=json.loads((population/'brief.json').read_text());self.pending[run_id]='running'
            from customer_simulation.pipeline import save
            journal=json.loads(self.journey.state_path(run_id).read_text());journal.update(status='running',error=None)
            save(self.journey.state_path(run_id),journal)
        def work():
            try:self.journey.execute(run_id,brief,resume=True)
            finally:
                with self.lock:self.pending[run_id]='stopped'
        threading.Thread(target=work,daemon=True).start()
        return {'run_id':run_id,'status':'running'}

    def advance(self,run_id,action):
        if not self.full_pipeline or not self.guided_flow:raise ValueError('Guided flow is not enabled')
        self.status(run_id)
        from customer_simulation.pipeline import read,save
        from .guided import checkpoint_inputs
        from .sampling import fingerprint
        from .state import utc_now
        folder=self.root/run_id
        with self.lock:
            if any(v=='running' for v in self.pending.values()):raise RuntimeError('A demo run is already active')
            journal=read(self.journey.state_path(run_id))
            if action=='approve-segments':
                if journal['status']!='awaiting_segmentation_approval':raise ValueError('Segmentation is not waiting for approval')
                _,_,_,checkpoint=checkpoint_inputs(folder)
                save(folder/'segmentation-approval.json',{'approved_at':utc_now(),'checkpoint_sha256':fingerprint(checkpoint)})
                journal.update(stage='profile_generation',generation_status='running')
            elif action=='start-simulation':
                if journal['status']!='awaiting_simulation':raise ValueError('Profiles must finish before simulation starts')
                save(folder/'simulation-authorization.json',{'approved_at':utc_now(),
                    'input_hashes':{name:fingerprint(read(folder/name)) for name in ['customers.json','specification.json','evidence.json']}})
                journal.update(stage='simulation',simulation_status='running')
            else:raise ValueError('Unknown action')
            journal.update(status='running',error=None);save(self.journey.state_path(run_id),journal)
            self.pending[run_id]='running'
        def work():
            try:self.journey.execute(run_id,read(folder/'brief.json'),resume=True)
            finally:
                with self.lock:self.pending[run_id]='stopped'
        threading.Thread(target=work,daemon=True).start()
        return {'run_id':run_id,'status':'running'}

    def request_expert(self,run_id,body):
        # An explicit UI action scopes one saved concern; never infer qualifications
        # from language/location or reuse another product's sourcing request.
        from terac_integration.policy import validate_expert_brief
        from terac_integration.feasibility import request_improvements
        from terac_integration.review import register_workspace
        self.status(run_id)
        if not isinstance(body,dict) or set(body)!={'concern_id','expert_brief'}:raise ValueError('Provide a concern and its expert brief')
        source=self.journey.paths(run_id)[2]/'concerns.json'
        if not source.exists():raise ValueError('Concern report is not ready')
        data=json.loads(source.read_text());matches=[c for c in data['concerns'] if c['concern_id']==body['concern_id']]
        if len(matches)!=1:raise ValueError('Unknown concern')
        from terac_integration.briefs import prepare_expert_brief
        concern={**matches[0],'expert_brief':body['expert_brief'] or prepare_expert_brief(data['product'],matches[0])}
        try:validate_expert_brief(concern)
        except ValueError as error:
            from terac_integration.review import ReviewError
            raise ReviewError(str(error)) from None
        plan={'product':data['product'],'concerns':[concern]}
        workspace_id=run_id+'-'+concern['concern_id']
        folder=self.expert_reviews.root/workspace_id
        with self.expert_reviews.lock:
            if body['expert_brief'] is None and (folder/'workspace.json').exists():
                existing=self.expert_reviews.get(workspace_id)
                if existing['product'].get('product_id')!=data['product']['product_id']:raise ValueError('Expert workspace product mismatch')
                return {'expert_review_url':'/expert-review?workspace='+workspace_id}
            folder.mkdir(parents=True,exist_ok=True);folder.chmod(0o700)
            request_improvements(plan,folder/'feasibility',self.expert_reviews.client_factory())
            feasibility=json.loads((folder/'feasibility/summary.json').read_text())
            register_workspace(self.expert_reviews.root,workspace_id,plan,feasibility)
        return {'expert_review_url':'/expert-review?workspace='+workspace_id}

    def status(self,run_id):
        if not re.fullmatch(r'demo-[a-f0-9]{32}',run_id):raise ValueError('Invalid demo run ID')
        if self.full_pipeline and self.journey.state_path(run_id).exists():
            state=json.loads(self.journey.state_path(run_id).read_text())
            if state['status']=='running' and self.pending.get(run_id)!='running':state.update(status='interrupted',error={'message':'The local server restarted. Saved outputs remain available; resume does not repeat completed calls.'})
            state['artifacts']=list(self.journey.artifacts(run_id))
            state['guided_flow']=state.get('guided_flow',self.guided_flow)
            state['segmentation_approved']=(self.root/run_id/'segmentation-approval.json').exists()
            state['can_resume_profiles']=self.guided_flow and (self.root/run_id/'segmentation-approval.json').exists()
            from .guided import live_details
            state.update(live_details(self.root/run_id,self.journey.paths(run_id)[1]))
            folder=self.root/run_id
            if (folder/'brief.json').exists():
                brief=json.loads((folder/'brief.json').read_text());product_id=brief['product_id'];state['product_name']=brief['name']
                workspaces=[w for w in self.expert_reviews.list() if isinstance(w['product'],dict) and w['product'].get('product_id')==product_id]
                state['expert_workspaces']=[{'url':'/expert-review?workspace='+w['id'],'id':w['id']} for w in workspaces]
                if workspaces:state['expert_review_url']=state['expert_workspaces'][0]['url']
            concern_file=self.journey.paths(run_id)[2]/'concerns.json'
            state['improvement_concerns']=[]
            if concern_file.exists():
                from terac_integration.briefs import prepare_expert_brief
                concern_data=json.loads(concern_file.read_text())
                state['concern_warnings']=concern_data.get('limitations',[]) if concern_data.get('withheld_concern_count') else []
                state['improvement_concerns']=[{**c,'prepared_expert_brief':prepare_expert_brief(concern_data['product'],c)} for c in concern_data.get('concerns',[])]
            if (folder/'state.json').exists():
                generation=json.loads((folder/'state.json').read_text());state['generation_stage']=generation.get('stage')
                if generation.get('error'):
                    if (folder/'replayed-specification.json').exists():
                        state['quality_recovery_available']=True;state['recovery_label']='Continue with saved proposal (uses model-provider credits for review)'
                    diagnostics=sorted(folder.glob('call-*-diagnostic.json'))
                    state['failure_details']=json.loads(diagnostics[-1].read_text()) if diagnostics else {
                        'stage':generation.get('stage'),'error_type':generation['error'].get('type'),
                        'explanation':'This step could not complete. The saved run details below identify the stage and error category.',
                        'next_step':'Open run details to inspect this attempt. Earlier outputs are preserved.'}
                    state['error']={'message':state['failure_details']['explanation']}

                if (generation.get('error') or {}).get('type')=='ReviewRejected':
                    reviews=sorted(folder.glob('review-*.json'))
                    review=json.loads(reviews[-1].read_text()) if reviews else {}
                    state['quality_recovery_available']=True
                    state['quality_review']={'summary':review.get('summary'),'issues':[f['message'] for f in review.get('findings',[]) if f.get('severity')=='blocking']}
                    state['error']={'message':'We need a richer, more consistent representation of these customers. The quality check found conflicts within the proposed groups. Improve the customer groups using the saved research, then review them again.'}
                if generation['status']=='completed':state['summary']=summary_lines(folder)
            simulation=self.journey.paths(run_id)[1]
            if (simulation/'progress.json').exists():state['simulation_progress']=json.loads((simulation/'progress.json').read_text())
            if state['status']=='failed' and state.get('stage')=='concerns':
                state['error']={'message':'Your simulation report is ready. Preparing the expert-review concerns stopped; the report and customer results remain available.'}
                state['failure_details']={'stage':'expert_review_concerns','error_type':(json.loads(self.journey.state_path(run_id).read_text()).get('error') or {}).get('type'),
                    'explanation':state['error']['message'],'next_step':'Open the simulation report below. Resume reuses completed customer decisions and report outputs.'}
            if state['status']=='failed' and (simulation/'failure.json').exists():
                failure=json.loads((simulation/'failure.json').read_text())
                count=(state.get('simulation_progress') or {}).get('completed',0)
                if count==state.get('target_count') and not (simulation/'report.html').exists():
                    state['error']={'message':'All customer responses are saved. The final report could not finish. Resume saved work retries only unfinished report calls and may use model-provider credits; a previous unanswered request may also have been charged.'}
                    state['failure_details']={'stage':'final_report','error_type':failure.get('error_type'),'explanation':state['error']['message'],
                        'next_step':'Click Resume saved work once. Completed customer responses will be reused; report calls are not automatically retried on another failure.'}

            return state
        path=self.root/run_id/'state.json'
        if not path.exists():return {'status':self.pending.get(run_id,'not_found'),'stage':'starting'}
        state=json.loads(path.read_text());result={k:state.get(k) for k in ['status','stage','total_tokens','corrections','error']}
        if state['status']=='completed':result['summary']=summary_lines(path.parent)
        return result

    def inspect(self,run_id):
        self.status(run_id) # Validate run identifier before any filesystem access.
        folder=self.root/run_id
        def load(name):
            p=folder/name
            return json.loads(p.read_text()) if p.exists() else None
        evidence=load('evidence.json');retrieval=[];generation_inputs=[];proposals=[];model_inputs=[]
        for p in sorted(folder.glob('call-*-input.json')):model_inputs.append({'file':p.name,'data':load(p.name)})
        for p in sorted(folder.glob('call-*-research-retrieval.json')):retrieval.append({'file':p.name,'data':load(p.name)})
        for p in sorted(folder.glob('call-*-request.json')):
            data=load(p.name)
            if data.get('stage') in {'propose','correct'}:generation_inputs.append({'file':p.name,'data':data})
        for p in sorted(folder.glob('call-*-compact_*-raw-output.json')):proposals.append({'file':p.name,'data':load(p.name)})
        subjects={}
        for f in (evidence or {}).get('findings',[]):
            if f.get('track')=='offers':subjects.setdefault(f['subject'],[]).append(f)
        return {'run_id':run_id,'folder':'data/runs/'+run_id,'state':self.status(run_id),'brief':load('brief.json'),
            'retrieval':retrieval,'offer_subjects':subjects,'evidence':evidence,'generation_inputs':generation_inputs,'model_inputs':model_inputs,'compact_outputs':proposals,
            'specification':load('specification.json') or load('specification-1.json') or load('specification-0.json'),
            'reviews':[{'file':p.name,'data':load(p.name)} for p in sorted(folder.glob('review-*.json'))],
            'profiles_file':'data/runs/'+run_id+'/customers.json' if load('customers.json') else None}

    def artifact(self,run_id,name):
        self.status(run_id)
        if not self.full_pipeline:raise ValueError('Connected pipeline is not enabled')
        artifacts=self.journey.artifacts(run_id)
        if name not in artifacts:raise ValueError('Artifact is not ready')
        return artifacts[name]

    def saved_runs(self):
        if not self.root.exists():return []
        folders=sorted((p for p in self.root.glob('demo-*') if p.is_dir()),key=lambda p:p.stat().st_mtime,reverse=True)
        return [{'run_id':p.name,**self.status(p.name)} for p in folders[:30] if re.fullmatch('demo-[a-f0-9]{32}',p.name)]

def application(demo,port):
    from terac_integration.review import ReviewError
    from terac_integration.mcp import TeracError
    origin=f'http://127.0.0.1:{port}'
    def app(env,start):
        code=200;content_type='application/json';result={};extra_headers=[]
        try:
            path=env.get('PATH_INFO','');method=env.get('REQUEST_METHOD')
            if env.get('HTTP_HOST')!=f'127.0.0.1:{port}' or env.get('HTTP_ORIGIN') not in {None,origin}:raise PermissionError()
            if path in {'/','/expert-review'} and method=='GET':
                content_type='text/html; charset=utf-8'
                result=Path(__file__).with_name('expert-review.html' if path=='/expert-review' else 'demo.html').read_text().replace('__DEMO_TOKEN__',demo.token).replace('__TARGET_COUNT__',str(demo.target_count)).replace('__MODEL_PROVIDER__','OpenRouter' if os.environ.get('MODEL_BACKEND')=='openrouter' else 'Lovable')
            else:
                if not hmac.compare_digest(env.get('HTTP_X_DEMO_TOKEN',''),demo.token):raise PermissionError()
                expert=re.fullmatch(r'/api/demo/experts/([a-z0-9][a-z0-9-]{0,79})(?:/(refresh|drafts|decision))?',path)
                artifact=re.fullmatch(r'/api/demo/runs/(demo-[a-f0-9]{32})/(artifacts|views)/([a-z-]+)',path)
                retry_groups=re.fullmatch(r'/api/demo/runs/(demo-[a-f0-9]{32})/retry-groups',path)
                advance=re.fullmatch(r'/api/demo/runs/(demo-[a-f0-9]{32})/(approve-segments|start-simulation)',path)
                expert_request=re.fullmatch(r'/api/demo/runs/(demo-[a-f0-9]{32})/expert-request',path)
                resume=re.fullmatch(r'/api/demo/runs/(demo-[a-f0-9]{32})/resume',path)
                if method=='POST' and expert_request:
                    size=int(env.get('CONTENT_LENGTH') or 0)
                    if not 1<=size<=16000:raise ValueError('Invalid expert brief size')
                    result=demo.request_expert(expert_request[1],json.loads(env['wsgi.input'].read(size)))
                elif method=='GET' and path=='/api/demo/experts':result={'workspaces':demo.expert_reviews.list()}
                elif method=='GET' and expert and not expert[2]:result=demo.expert_reviews.get(expert[1])
                elif method=='POST' and expert and expert[2]:
                    size=int(env.get('CONTENT_LENGTH') or 0)
                    if not 1<=size<=4000:raise ValueError('Invalid expert action')
                    body=json.loads(env['wsgi.input'].read(size))
                    if expert[2] in {'refresh','drafts'}:
                        if body!={}:raise ValueError('This action takes an empty object')
                        result=demo.expert_reviews.refresh(expert[1]) if expert[2]=='refresh' else demo.expert_reviews.prepare_drafts(expert[1])
                    else:
                        if not isinstance(body,dict) or set(body)!={'job_id','applicant_id','snapshot','decision','confirmed'}:raise ValueError('Invalid applicant decision')
                        result=demo.expert_reviews.decide(expert[1],**body)
                elif method=='GET' and artifact:
                    file=demo.artifact(artifact[1],artifact[3]);result=file.read_bytes()
                    if artifact[2]=='views':
                        from .artifact_views import render_artifact
                        result=render_artifact(file,artifact[3]).encode()
                    if file.suffix=='.html' or artifact[2]=='views':extra_headers.append(('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'"))
                    content_type='text/html; charset=utf-8' if file.suffix=='.html' or artifact[2]=='views' else 'text/markdown; charset=utf-8' if file.suffix=='.md' else 'application/json'
                elif method=='POST' and retry_groups:
                    size=int(env.get('CONTENT_LENGTH') or 0)
                    if size>100 or json.loads(env['wsgi.input'].read(size) or b'{}')!={}:raise ValueError('Retry takes no modified inputs')
                    result=demo.retry_groups(retry_groups[1]);code=202
                elif method=='POST' and advance:
                    size=int(env.get('CONTENT_LENGTH') or 0)
                    if size>100 or json.loads(env['wsgi.input'].read(size) or b'{}')!={}:raise ValueError('Action accepts no modified inputs')
                    result=demo.advance(advance[1],advance[2]);code=202
                elif method=='POST' and resume:
                    size=int(env.get('CONTENT_LENGTH') or 0)
                    if size>100:raise ValueError('Invalid resume payload')
                    if json.loads(env['wsgi.input'].read(size) or b'{}')!={}:raise ValueError('Resume accepts no modified inputs')
                    result=demo.resume(resume[1]);code=202
                elif method=='POST' and path in {'/api/demo/preview','/api/demo/start'}:
                    size=int(env.get('CONTENT_LENGTH') or 0)
                    if size<1 or size>1_500_000:raise ValueError('Request exceeds upload limit')
                    payload=json.loads(env['wsgi.input'].read(size))
                    result=demo.preview(payload) if path.endswith('preview') else demo.start(payload)
                    if path.endswith('start'):code=202
                elif method=='GET' and path=='/api/demo/runs':result={'runs':demo.saved_runs()}
                elif method=='GET' and re.fullmatch('/api/demo/runs/demo-[a-f0-9]{32}(?:/(?:customers|inspection))?',path):
                    run_id=path.split('/')[4]
                    result=demo.status(run_id)
                    if path.endswith('/customers'):
                        if not (demo.root/run_id/'state.json').exists() or json.loads((demo.root/run_id/'state.json').read_text())['status']!='completed':raise ValueError('Profiles are not accepted yet')
                        result=json.loads((demo.root/run_id/'customers.json').read_text())
                    elif path.endswith('/inspection'):result=demo.inspect(run_id)
                else:code=404;result={'error':'Not found'}
        except ReviewError as error:code=400;result={'error':str(error)}
        except TeracError as error:code=502;result={'error':str(error)}
        except WorkerNotReady as error:code=409;result={'error':str(error)}
        except PermissionError:code=403;result={'error':'Local demo access only'}
        except (ValueError,TypeError):code=400;result={'error':'Invalid input. Check file type, size, required fields and credentials.'}
        except RuntimeError:code=409;result={'error':'A demo run is already active'}
        except Exception:code=503;result={'error':'Demo service unavailable'}
        raw=result if isinstance(result,bytes) else (result if content_type.startswith('text/html') else json.dumps(result)).encode()
        start(f"{code} "+{200:'OK',202:'Accepted',400:'Bad Request',403:'Forbidden',404:'Not Found',409:'Conflict',502:'Bad Gateway',503:'Service Unavailable'}[code],
            [('Content-Type',content_type),('Cache-Control','no-store'),('Content-Length',str(len(raw))),('X-Content-Type-Options','nosniff')]+extra_headers)
        return [raw]
    return app
