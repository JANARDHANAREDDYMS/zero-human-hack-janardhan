"""Draft/manual-selection workflow through documented MCP contracts; no real people or money."""
import copy,io,json,tempfile,unittest
from pathlib import Path
from customer_simulation.pipeline import read,save
from customer_generation.demo import Demo,application
from terac_integration.policy import feasibility_arguments
from terac_integration.review import ExpertReview,register_workspace,ReviewError
from terac_integration.studies import build_draft,validate_draft,TeracStudiesMCP

class MockTerac:
 def __init__(self):
  self.calls=[];self.quote_status='RESPONDED';self.fail_decision=False
  self.op={'id':'op-one','status':'DRAFT','customer_screening_review':'manual_review','links':{'dashboard':{'draft_editor':'https://terac.com/example/draft'}}}
  self.candidates=[{'id':'applicant-one','name':'Test Specialist','screening_answers':{'experience_1':'I shipped paid learning products.','experience_2':'I implemented session credits.'}}]
 def call(self,name,args):
  self.calls.append((name,copy.deepcopy(args)))
  if name=='terac_get_feasibility_request':value={'id':'request-one','status':self.quote_status,'costPerParticipant':25 if self.quote_status=='RESPONDED' else None}
  elif name=='terac_get_filter_options':
   language=args['filter_slug']=='multi_select--language'
   value={'data':[{'id':'english' if language else 'US','name':'English' if language else 'United States'}]}
  elif name=='terac_list_projects':value={'data':[{'id':'project-one','name':'Product improvement expert reviews'}]}
  elif name=='terac_get_opportunity':value=self.op
  elif name=='terac_get_applicants':value={'data':self.candidates,'pagination':{'has_more':False}}
  else:raise AssertionError(name)
  return {'structuredContent':copy.deepcopy(value)}
 def create_project(self,name):raise AssertionError('Existing project should be reused')
 def create_draft(self,args):
  self.calls.append(('create_draft',copy.deepcopy(args)));validate_draft(args)
  self.op.update(args);return {'structuredContent':copy.deepcopy(self.op)}
 def decide_applicant(self,applicant_id,decision,confirmed=False):
  self.calls.append((decision,{'id':applicant_id,'confirmed':confirmed}))
  if self.fail_decision:raise RuntimeError('Ambiguous provider timeout')
  self.candidates=[x for x in self.candidates if x['id']!=applicant_id]
  return {'structuredContent':{'status':'screen_passed' if decision=='invite' else 'screened_out'}}

class ReviewTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.client=MockTerac()
  self.scope={'title':'Unclear practice format','explanation':'Learners cannot tell what mock practice includes.','review_question':'How should its format be explained?',
   'expert_brief':{'role':'Coding-education product marketer','product_domain':'Coding interview practice','work_type':'review',
    'relevant_experience':['Has marketed coding practice.','Has explained mock interview delivery formats.'],
    'qualification_checks':['Describe the related product you marketed and your responsibility.','Describe a product-demo project you personally delivered.'],
    'deliverable':'A short written assessment and proposed demo outline.'}}
  self.plan={'product':{'name':'Learning service','description':'Coding interview practice.'},'concerns':[self.scope]}
  self.feasibility={'requests':[{'response':{'id':'request-one','status':'RESPONDED','costPerParticipant':25,**feasibility_arguments(self.plan['product'],self.scope)}}]}
  register_workspace(self.root,'learning',self.plan,self.feasibility)
  self.manager=ExpertReview(self.root,lambda:self.client)
 def live(self):
  self.manager.prepare_drafts('learning');self.client.op['status']='ACTIVE'
  state=self.manager.get('learning');state.pop('checked_at',None);save(self.manager.path('learning'),state)
  return self.manager.refresh('learning')['jobs'][0]['applicants'][0]
 def test_drafts_are_manual_us_english_and_collect_work(self):
  self.manager.prepare_drafts('learning');self.manager.prepare_drafts('learning')
  args=[v for k,v in self.client.calls if k=='create_draft'];self.assertEqual(len(args),1)
  self.assertEqual(args[0]['customer_screening_review'],'manual_review');self.assertEqual(args[0]['num_participants'],1)
  self.assertEqual(args[0]['filters'],[{'multi_select--country':{'$in':['US']}},{'multi_select--language':{'$in':['english']}}])
  self.assertEqual(args[0]['tasks'][0]['task_type'],'file_upload');self.assertEqual(args[0]['tasks'][0]['review_type'],'manual_review')
  self.assertTrue(any(a['qualify_logic']=='reject' for a in args[0]['screening_questions'][0]['answers']))
  self.assertEqual(self.manager.get('learning')['jobs'][0]['applicants'],[])
  self.assertFalse(any(k in {'invite','launch'} for k,_ in self.client.calls))
 def test_unpriced_requests_cannot_create_drafts(self):
  data=self.manager.get('learning');data['jobs'][0]['feasibility'].update(status='RECEIVED',costPerParticipant=None);save(self.manager.path('learning'),data)
  self.manager.prepare_drafts('learning');self.assertEqual(self.client.calls,[])
 def test_one_reviewed_applicant_can_be_invited(self):
  applicant=self.live()
  result=self.manager.decide('learning','improvement-01',applicant['id'],applicant['snapshot_sha256'],'invite',True)
  self.assertEqual(result['jobs'][0]['decisions'][0]['decision'],'invite')
  with self.assertRaises(ReviewError):self.manager.decide('learning','improvement-01',applicant['id'],applicant['snapshot_sha256'],'invite',True)
  self.assertEqual(sum(k=='invite' for k,_ in self.client.calls),1)
 def test_requires_confirmation_and_current_answers(self):
  applicant=self.live()
  with self.assertRaises(ReviewError):self.manager.decide('learning','improvement-01',applicant['id'],applicant['snapshot_sha256'],'invite',False)
  self.client.candidates[0]['screening_answers']['experience_1']='Changed after you read it'
  with self.assertRaises(ReviewError):self.manager.decide('learning','improvement-01',applicant['id'],applicant['snapshot_sha256'],'invite',True)
  self.assertFalse(any(k=='invite' for k,_ in self.client.calls))
 def test_auto_invite_configuration_blocks_decisions(self):
  applicant=self.live();self.client.op['customer_screening_review']='auto_invite'
  with self.assertRaises(ReviewError):self.manager.decide('learning','improvement-01',applicant['id'],applicant['snapshot_sha256'],'invite',True)
 def test_targeting_drift_and_missing_answers_block_invites(self):
  applicant=self.live();self.client.op['filters']=[{'multi_select--country':{'$in':['CA']}}]
  with self.assertRaises(ReviewError):self.manager.decide('learning','improvement-01',applicant['id'],applicant['snapshot_sha256'],'invite',True)
  self.assertFalse(any(k=='invite' for k,_ in self.client.calls))

 def test_anonymous_records_remain_anonymous(self):
  self.client.candidates[0].pop('name');applicant=self.live();self.assertIsNone(applicant['name'])
 def test_ambiguous_decision_never_sends_twice(self):
  applicant=self.live();self.client.fail_decision=True
  with self.assertRaises(RuntimeError):self.manager.decide('learning','improvement-01',applicant['id'],applicant['snapshot_sha256'],'invite',True)
  self.client.fail_decision=False
  with self.assertRaises(ReviewError):self.manager.decide('learning','improvement-01',applicant['id'],applicant['snapshot_sha256'],'invite',True)
  self.assertEqual(sum(k=='invite' for k,_ in self.client.calls),1)
 def test_unrelated_quote_or_workspace_is_rejected(self):
  bad=copy.deepcopy(self.feasibility);bad['requests'][0]['response']['submissionCount']=2
  with self.assertRaises(ReviewError):register_workspace(self.root,'other',self.plan,bad)
  with self.assertRaises(ReviewError):self.manager.get('../learning')
 def test_launch_tool_is_never_exposed(self):
  client=TeracStudiesMCP('test-only',lambda *x:self.fail('No transport should run'))
  with self.assertRaises(ValueError):client.call('terac_launch_draft_opportunity',{})
  with self.assertRaises(ValueError):client.decide_applicant('applicant-one','invite')
 def request(self,path,body=None,token=None):
  if not hasattr(self,'demo'):self.demo=Demo(self.root/'runs',expert_review_root=self.root,expert_client_factory=lambda:self.client)
  captured={};raw=b'' if body is None else json.dumps(body).encode()
  env={'PATH_INFO':path,'REQUEST_METHOD':'GET' if body is None else 'POST','HTTP_HOST':'127.0.0.1:8082',
   'HTTP_X_DEMO_TOKEN':self.demo.token if token is None else token,'CONTENT_LENGTH':str(len(raw)),'wsgi.input':io.BytesIO(raw)}
  data=b''.join(application(self.demo,8082)(env,lambda s,h:captured.update(code=int(s.split()[0]))))
  return captured['code'],data
 def test_http_requires_local_token_and_opens_review_screen(self):
  code,body=self.request('/expert-review');self.assertEqual(code,200);self.assertIn(b'Invite this expert',body)
  self.assertEqual(self.request('/api/demo/experts',token='wrong')[0],403)
  code,body=self.request('/api/demo/experts');self.assertEqual(code,200);self.assertEqual(len(json.loads(body)['workspaces']),1)
  self.assertEqual(self.request('/api/demo/experts/learning/drafts',{})[0],200)
  self.assertEqual(self.request('/api/demo/experts/learning/launch',{})[0],404)
