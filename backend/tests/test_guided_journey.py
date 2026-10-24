"""Human gates and polling results through the real HTTP app, mocked providers."""
import copy,json,time,unittest
from pathlib import Path
import test_connected_journey
from customer_generation.sampling import fingerprint
from customer_simulation.pipeline import save

class GuidedJourneyTests(unittest.TestCase):
 wait=test_connected_journey.ConnectedJourneyTests.wait
 start=test_connected_journey.ConnectedJourneyTests.start
 request=test_connected_journey.ConnectedJourneyTests.request
 def setUp(self):
  test_connected_journey.ConnectedJourneyTests.setUp(self);self.demo.guided_flow=True;self.demo.journey.guided_flow=True
 def approve(self,run_id):
  response,body=self.request(f'/api/demo/runs/{run_id}/approve-segments',method='POST',body=b'{}')
  self.assertEqual(response['status'],202,body)
  return self.wait(run_id)
 def simulate(self,run_id):
  response,body=self.request(f'/api/demo/runs/{run_id}/start-simulation',method='POST',body=b'{}')
  self.assertEqual(response['status'],202,body)
  return self.wait(run_id)
 def test_guided_flow_requires_both_explicit_actions(self):
  run_id=self.start();state=self.wait(run_id)
  self.assertEqual(state['status'],'awaiting_segmentation_approval',state)
  self.assertTrue(state['segments']);self.assertEqual(state['profile_cards'],[])
  self.assertFalse((self.root/'runs'/run_id/'customers.json').exists())
  self.assertEqual(self.transport.calls,[]);self.assertEqual(self.concern_transport.calls,0)
  state=self.approve(run_id)
  self.assertEqual(state['status'],'awaiting_simulation',state)
  self.assertEqual(len(state['profile_cards']),25)
  self.assertEqual(sum(state['profile_progress']['segments'].values()),25)
  self.assertEqual(self.transport.calls,[])
  state=self.simulate(run_id)
  self.assertEqual(state['status'],'completed',state)
  self.assertEqual(len(state['simulation_customers']),25)
  self.assertIn('simulation-report',state['artifacts']);self.assertIn('run-details',state['artifacts'])
 def test_approval_is_durable_and_does_not_repeat_research(self):
  run_id=self.start();self.wait(run_id);before=list(self.generation_calls)
  self.demo.pending={}
  self.assertEqual(self.demo.status(run_id)['status'],'awaiting_segmentation_approval')
  state=self.approve(run_id);self.assertEqual(state['status'],'awaiting_simulation')
  self.assertEqual(self.generation_calls,before)
  self.demo.pending={};self.assertEqual(self.demo.status(run_id)['status'],'awaiting_simulation')
 def test_cannot_skip_or_duplicate_approvals(self):
  run_id=self.start();self.wait(run_id)
  response,_=self.request(f'/api/demo/runs/{run_id}/start-simulation',method='POST',body=b'{}');self.assertEqual(response['status'],400)
  self.approve(run_id)
  response,_=self.request(f'/api/demo/runs/{run_id}/approve-segments',method='POST',body=b'{}');self.assertEqual(response['status'],400)
  self.assertEqual(self.transport.calls,[])
 def test_mutated_segmentation_cannot_be_approved(self):
  run_id=self.start();self.wait(run_id);path=self.root/'runs'/run_id/'specification.json'
  data=json.loads(path.read_text());data['segments'][0]['name']='Changed after review';save(path,data)
  response,_=self.request(f'/api/demo/runs/{run_id}/approve-segments',method='POST',body=b'{}');self.assertEqual(response['status'],400)
  self.assertFalse((path.parent/'segmentation-approval.json').exists());self.assertEqual(self.transport.calls,[])
 def test_actions_require_local_token(self):
  run_id=self.start();self.wait(run_id)
  response,_=self.request(f'/api/demo/runs/{run_id}/approve-segments',token='wrong',method='POST',body=b'{}');self.assertEqual(response['status'],403)
 def test_simulation_input_changes_invalidate_authorization(self):
  run_id=self.start();self.wait(run_id);self.approve(run_id)
  folder=self.root/'runs'/run_id
  save(folder/'simulation-authorization.json',{'input_hashes':{name:fingerprint(json.loads((folder/name).read_text())) for name in ['customers.json','specification.json','evidence.json']}})
  path=folder/'customers.json';data=json.loads(path.read_text());data['customers'][0]['goal']='Changed';save(path,data)
  self.demo.journey.execute(run_id,json.loads((folder/'brief.json').read_text()),resume=True)
  self.assertEqual(self.demo.status(run_id)['status'],'failed');self.assertEqual(self.transport.calls,[])

 def test_completed_report_exposes_saved_concerns_without_provider_calls(self):
  run_id=self.start();self.wait(run_id);self.approve(run_id);state=self.simulate(run_id)
  self.assertTrue(state['improvement_concerns']);self.assertIn('product_name',state)
  before=(len(self.transport.calls),self.concern_transport.calls)
  self.demo.status(run_id);self.assertEqual(before,(len(self.transport.calls),self.concern_transport.calls))
 def test_quality_rejection_shows_blocking_reason(self):
  run_id=self.start();self.wait(run_id);folder=self.root/'runs'/run_id
  state=json.loads((folder/'state.json').read_text());state.update(status='incomplete',error={'type':'ReviewRejected'})
  save(folder/'state.json',state);save(folder/'review-99.json',{'summary':'A customer conflicts with their segment.','findings':[{'severity':'blocking','message':'Deadline conflicts with no near-term need.'}]})
  result=self.demo.status(run_id)
  self.assertEqual(result['quality_review']['issues'],['Deadline conflicts with no near-term need.'])
  self.assertIn('richer',result['error']['message']);self.assertTrue(result['quality_recovery_available'])
 def test_request_expert_is_scoped_to_saved_concern_and_idempotent(self):
  from terac_integration.mcp import tool_data
  run_id=self.start();self.wait(run_id);self.approve(run_id);state=self.simulate(run_id)
  concern=state['improvement_concerns'][0];calls=[]
  class Client:
   def call(self,name,args):
    calls.append(name);return {'structuredContent':{'id':'request-offline','status':'RECEIVED',**args}}
  self.demo.expert_reviews.root=self.root/'private-experts';self.demo.expert_reviews.client_factory=Client
  body={'concern_id':concern['concern_id'],'expert_brief':{'role':'Audio product specialist','product_domain':'Portable speakers','work_type':'review','relevant_experience':['Designed speakers','Tested battery-powered audio'],'qualification_checks':['Which audio products did you design?','What battery tests did you conduct?'],'deliverable':'Written assessment of the saved concern.'}}
  result=self.demo.request_expert(run_id,body);self.assertIn('/expert-review?workspace=',result['expert_review_url'])
  self.assertEqual(self.demo.request_expert(run_id,body),result)
  self.assertEqual(calls,['terac_request_feasibility'])
  self.assertEqual(self.demo.request_expert(run_id,{'concern_id':concern['concern_id'],'expert_brief':None}),result)
  self.assertEqual(calls,['terac_request_feasibility'])
  response,_=self.request(f'/api/demo/runs/{run_id}/expert-request',token='wrong',method='POST',body=json.dumps(body).encode());self.assertEqual(response['status'],403)
  body['concern_id']='unknown'
  with self.assertRaises(ValueError):self.demo.request_expert(run_id,body)
  self.assertEqual(len(calls),1)

 def test_group_retry_reuses_research_and_returns_to_human_approval(self):
  from customer_generation.state import StageResponse
  from customer_generation.instructions import fixture_checks
  run_id=self.start();self.wait(run_id);folder=self.root/'runs'/run_id
  spec=json.loads((folder/'specification.json').read_text());save(folder/'specification-0.json',spec)
  save(folder/'review-0.json',{'summary':'Improve variation','findings':[{'code':'within_segment_variation','severity':'blocking','message':'Fix inconsistent triggers','source_ids':[]}]})
  state=json.loads((folder/'state.json').read_text());state.update(status='incomplete',corrections=0,error={'type':'ReviewRejected'});save(folder/'state.json',state)
  calls=[];self_test=self
  class Backend:
   name='offline-recovery';mode='offline_fixture'
   def execute(self,stage,payload,limits):
    calls.append(stage)
    if stage=='correct':
     self_test.assertIn('sampling_context',payload['issues']);self_test.assertIn('pilot',payload['issues']['sampling_context']);return StageResponse(spec,1,1,0)
    if stage=='review':return StageResponse({'decision':'accept','summary':'Corrected','checks':fixture_checks(),'findings':[]},1,1,0)
    raise AssertionError(stage)
  self.demo.backend_factory=Backend;self.demo.readiness_check=None
  new_id=self.demo.retry_groups(run_id)['run_id'];result=self.wait(new_id)
  self.assertEqual(result['status'],'awaiting_segmentation_approval',result)
  self.assertEqual(calls,['correct','review']);self.assertEqual(result['retry_of'],run_id)
  self.assertFalse((self.root/'runs'/new_id/'customers.json').exists())

 def test_recovered_proposal_skips_research_and_proposal_calls(self):
  from customer_generation.state import StageResponse
  from customer_generation.instructions import fixture_checks
  run_id=self.start();self.wait(run_id);folder=self.root/'runs'/run_id
  spec=json.loads((folder/'specification.json').read_text());save(folder/'replayed-specification.json',spec)
  state=json.loads((folder/'state.json').read_text());state.update(status='failed',error={'type':'AdapterFailure'});save(folder/'state.json',state)
  calls=[]
  class Backend:
   mode='offline_fixture';name='offline-replay'
   def execute(self,stage,payload,limits):
    calls.append(stage)
    if stage!='review':raise AssertionError(stage)
    return StageResponse({'decision':'accept','summary':'Offline replay accepted','checks':fixture_checks(),'findings':[]},1,1,0)
  self.demo.backend_factory=Backend;self.demo.readiness_check=None
  self.assertIn('Continue with saved',self.demo.status(run_id)['recovery_label'])
  new=self.demo.retry_groups(run_id)['run_id'];result=self.wait(new)
  self.assertEqual(result['status'],'awaiting_segmentation_approval',result);self.assertEqual(calls,['review'])
  self.assertFalse((self.root/'runs'/new/'customers.json').exists())
