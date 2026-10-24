"""Manual selection workflow. Drafts cannot recruit; launch is never exposed."""
import copy
from .mcp import TeracMCP,tool_data
from .policy import expert_policy,validate_expert_brief

class TeracStudiesMCP(TeracMCP):
    ALLOWED=TeracMCP.ALLOWED|{'terac_list_projects','terac_get_opportunity','terac_get_applicants','terac_get_submissions'}
    def _mutation(self,name,args):
        if not self.connected:self.connect()
        if not self.context_read:self.call('terac_get_context',{})
        return self._rpc('tools/call',{'name':name,'arguments':args})
    def create_project(self,name):
        if not isinstance(name,str) or not name.strip():raise ValueError('Project name is required')
        return self._mutation('terac_create_project',{'name':name})
    def create_draft(self,args):
        validate_draft(args)
        if args['filters']!=target_filters(self):raise ValueError('Draft filters must use the verified US and English options only')
        return self._mutation('terac_create_opportunity',args)
    def decide_applicant(self,submission_id,decision,*,confirmed=False):
        if not confirmed or decision not in {'invite','decline'} or not submission_id:raise ValueError('Explicit applicant decision is required')
        return self._mutation('terac_'+decision+'_applicant',{'submissionId':submission_id,'reason':'Customer manually reviewed this applicant against the product-specific qualification criteria.'})

def target_filters(client):
    """Resolve exact provider values; never silently fall back to base audiences."""
    if hasattr(client,'_us_english_filters'):return copy.deepcopy(client._us_english_filters)
    found=[]
    for slug,label,search in [('multi_select--country','United States','United States'),('multi_select--language','English','English')]:
        data=tool_data(client.call('terac_get_filter_options',{'filter_slug':slug,'search':search,'per_page':100}))
        matches=[v for v in data.get('data',[]) if v.get('name','').casefold()==label.casefold()]
        if len(matches)!=1:raise ValueError('Could not uniquely resolve the '+label+' targeting option')
        found.append({slug:{'$in':[matches[0]['id']]}})
    client._us_english_filters=copy.deepcopy(found)
    return found

def build_draft(product,concern,feasibility,project_id,filters):
    expert_policy();brief=validate_expert_brief(concern)
    if feasibility.get('status')!='RESPONDED' or feasibility.get('costPerParticipant') is None:raise ValueError('Terac has not confirmed a price for this scope yet')
    instructions=('Product: '+str(product.get('name') if isinstance(product,dict) else product)+'\nProduct context: '+str(product.get('description','') if isinstance(product,dict) else '')+
        '\nConcern from synthetic feedback (not a verified defect): '+concern['explanation']+
        '\nRequested work type: '+brief['work_type']+'\nDeliverable: '+brief['deliverable']+
        '\nUpload one PDF or plain-text written assessment. State evidence, assumptions, uncertainties and prerequisites. No physical product is supplied. Do not claim testing, implementation or improved sales without evidence. No confidential employer information is requested.')
    if len(instructions)>4000:raise ValueError('Expert brief exceeds the upload instruction limit; shorten it before creating a draft')
    screen=[{'key':'work_location','text':'Where will you be physically based while carrying out this task?','pick':'one','answers':[
        {'text':'United States','qualify_logic':'must'},{'text':'Canada','qualify_logic':'reject'},
        {'text':'United Kingdom','qualify_logic':'reject'},{'text':'Another country or outside the United States','qualify_logic':'reject'}]}]
    for index,question in enumerate(brief['qualification_checks'],1):
        screen.append({'key':f'experience_{index}','text':question,'pick':'text'})
    args={'title':('Expert assessment: '+concern['title'])[:200],'internal_title':concern.get('concern_id',concern['title'])[:200],
        'description':('Seeking '+brief['role']+' for a written assessment of '+str(product.get('name') if isinstance(product,dict) else product)+'. US-based English-speaking specialists only.')[:280],
        'project_id':project_id,'num_participants':1,'business_type':'b2b','customer_screening_review':'manual_review',
        'expected_days_to_complete':7,'feasibility_request_id':feasibility['id'],'filters':copy.deepcopy(filters),
        'screening_questions':screen,'tasks':[{'sequence':1,'task_type':'file_upload','review_type':'manual_review',
            'title':'Submit the written expert assessment','instructions':instructions,'accepted_mime_types':['application/pdf','text/plain'],
            'min_files':1,'max_files':1,'max_file_size_bytes':5_000_000}]}
    return args

def validate_draft(args):
    if args.get('customer_screening_review')!='manual_review' or args.get('num_participants')!=1:
        raise ValueError('Every expert must wait for manual selection; exactly one completion is requested')
    if args.get('unrestricted_audience') or not args.get('filters') or not args.get('feasibility_request_id'):
        raise ValueError('Confirmed pricing and explicit US/English filters are required')
    slugs={slug for f in args['filters'] for slug in f}
    if not {'multi_select--country','multi_select--language'}<=slugs:raise ValueError('US and English targeting filters are required')
    if any(t.get('review_type')!='manual_review' or t.get('task_type')!='file_upload' for t in args.get('tasks',[])):
        raise ValueError('The initial expert flow requires a manually reviewed file deliverable')
    if len(args.get('screening_questions',[]))<3:raise ValueError('Product-specific screening and work-location screening are required')
