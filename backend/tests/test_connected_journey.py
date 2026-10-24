"""Upload -> 25 profiles -> simulation -> concerns, entirely offline."""
import io,json,tempfile,time,unittest
from pathlib import Path
from customer_generation.demo import Demo,application
from customer_generation.state import StageResponse
from customer_generation.instructions import fixture_checks
from customer_generation.tools.llm import ModelBridgeClient
import test_concept_simulation as concept_fixtures
import test_review_concerns as concern_fixtures
ROOT=Path(__file__).resolve().parents[2]

class ConnectedJourneyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.generation_calls=[];self.transport=concept_fixtures.Transport();self.concern_transport=concern_fixtures.ConcernTransport();test=self
        class Backend:
            name='offline-journey';mode='offline_fixture'
            def execute(self,stage,payload,limits):
                test.generation_calls.append(stage);folder=ROOT/'data/products/sony-speaker/research-v2'
                if stage=='research':data=json.loads((folder/'evidence.json').read_text());data['product_id']=payload['brief']['product_id']
                elif stage=='propose':
                    data=json.loads((folder/'specification.json').read_text());data['product_id']=payload['brief']['product_id']
                    count=payload['target_count'];data['target_count']=count
                    for n,segment in enumerate(data['segments']):segment['count']=count//len(data['segments'])+(1 if n<count%len(data['segments']) else 0)
                elif stage=='review':data={'decision':'accept','summary':'Offline end-to-end fixture','checks':fixture_checks(),'findings':[]}
                else:raise AssertionError(stage)
                return StageResponse(data,1,1,0)
        class Transport:
            def post(self,url,headers,body,timeout):
                transport=test.concern_transport if body['stage']=='extract_review_concerns' else test.transport
                return transport.post(url,headers,body,timeout)
        factory=lambda:ModelBridgeClient('https://offline.example/model','offline-token','offline-model',Transport())
        self.demo=Demo(self.root/'runs',backend_factory=Backend,full_pipeline=True,target_count=25,client_factory=factory)
    def wait(self,run_id):
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            state=self.demo.status(run_id)
            if state['status']!='running':return state
            time.sleep(.01)
        self.fail('Journey did not finish')
    def start(self):return self.demo.start({'fields':{'name':'CodeSensei demo','description':'Personal coding help for learners.'}})['run_id']
    def request(self,path,token=None,method='GET',body=b''):
        captured={};env={'PATH_INFO':path,'REQUEST_METHOD':method,'HTTP_HOST':'127.0.0.1:8082','HTTP_X_DEMO_TOKEN':self.demo.token if token is None else token,
            'CONTENT_LENGTH':str(len(body)),'wsgi.input':io.BytesIO(body)}
        result=b''.join(application(self.demo,8082)(env,lambda s,h:captured.update(status=int(s.split()[0]),headers=dict(h))))
        return captured,result
    def test_upload_runs_all_stages_and_delivers_outputs_for_25(self):
        run_id=self.start();state=self.wait(run_id)
        self.assertEqual(state['status'],'completed',state)
        population=json.loads((self.root/'runs'/run_id/'customers.json').read_text());self.assertEqual(population['count'],25)
        self.assertEqual(self.generation_calls,['research','propose','review'])
        self.assertEqual(self.transport.calls.count('simulate_concept'),25)
        self.assertEqual(self.transport.calls.count('summarize_simulation'),3)
        self.assertGreater(self.concern_transport.calls,0)
        self.assertTrue({'profiles','evidence','simulation-report','concern-report'}<=set(state['artifacts']))
        self.assertEqual(state['target_count'],25);self.assertFalse(state['terac_actions'])
        for part in ['simulation-report','concern-report']:
            response,body=self.request(f'/api/demo/runs/{run_id}/artifacts/{part}')
            self.assertEqual(response['status'],200);self.assertIn(b'<!doctype html>',body)
            self.assertIn('Content-Security-Policy',response['headers'])
    def test_outputs_are_local_token_protected_and_paths_allowlisted(self):
        run_id=self.start();self.wait(run_id)
        response,_=self.request(f'/api/demo/runs/{run_id}/artifacts/profiles',token='wrong');self.assertEqual(response['status'],403)
        response,_=self.request(f'/api/demo/runs/{run_id}/artifacts/secrets');self.assertEqual(response['status'],400)
        response,_=self.request(f'/api/demo/runs/{run_id}/artifacts/../../.env');self.assertEqual(response['status'],404)
    def test_resume_does_not_repeat_completed_generation_or_simulation(self):
        original=self.demo.journey.concerns
        self.demo.journey.concerns=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('Offline concern stop'))
        run_id=self.start();state=self.wait(run_id)
        self.assertEqual(state['status'],'failed');self.assertEqual(state['simulation_status'],'completed')
        self.assertIn('simulation-report',state['artifacts'])
        before=len(self.transport.calls);self.demo.journey.concerns=original
        self.demo.resume(run_id);state=self.wait(run_id)
        self.assertEqual(state['status'],'completed',state);self.assertEqual(len(self.transport.calls),before)
        self.assertEqual(self.generation_calls,['research','propose','review'])
    def test_missing_worker_stage_stops_before_generation_with_actionable_message(self):
        from customer_generation.worker_readiness import WorkerNotReady
        self.demo.readiness_check=lambda:(_ for _ in ()).throw(WorkerNotReady('Publish the worker update before starting.'))
        response,body=self.request('/api/demo/start',method='POST',body=json.dumps({'fields':{'name':'CodeSensei','description':'Coding help'}}).encode())
        self.assertEqual(response['status'],409);self.assertIn('Publish',json.loads(body)['error'])
        self.assertEqual(self.generation_calls,[]);self.assertEqual(self.transport.calls,[])
    def test_readiness_probes_reject_before_model_calls(self):
        from customer_generation.worker_readiness import check_worker,WorkerNotReady
        from customer_generation.config import AdapterConfig
        from customer_generation.tools.http import TransportError
        config=AdapterConfig('offline-exa','https://offline.example/model','offline-token','offline-model')
        class Transport:
            def __init__(self,status):self.status=status;self.calls=[]
            def post(self,url,headers,body,timeout):
                self.calls.append(body);self_test.assertEqual(body['limits']['max_tokens'],0)
                raise TransportError('offline',self.status)
        self_test=self;transport=Transport(400)
        self.assertTrue(check_worker(config,transport));self.assertEqual(len(transport.calls),3)
        with self.assertRaises(WorkerNotReady):check_worker(config,Transport(403))
    def test_restarting_server_keeps_saved_reports_available(self):
        run_id=self.start();self.wait(run_id)
        self.demo.pending={}
        self.assertEqual(self.demo.status(run_id)['status'],'completed')
        self.assertTrue(self.demo.artifact(run_id,'simulation-report').is_file())
        self.assertEqual(self.demo.saved_runs()[0]['run_id'],run_id)
    def test_simulation_failure_does_not_start_concerns_or_hide_profiles(self):
        self.demo.journey.simulation=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('Offline simulation stop'))
        run_id=self.start();state=self.wait(run_id)
        self.assertEqual(state['status'],'failed');self.assertEqual(state['generation_status'],'completed')
        self.assertEqual(self.concern_transport.calls,0);self.assertIn('profiles',state['artifacts'])
        response,body=self.request(f'/api/demo/runs/{run_id}/customers')
        self.assertEqual(response['status'],200);self.assertEqual(json.loads(body)['count'],25)
if __name__=='__main__':unittest.main()
