import tempfile,unittest
from pathlib import Path
from terac_integration.policy import expert_policy,feasibility_arguments
from terac_integration.feasibility import request_improvements,refresh_improvements
from terac_integration.mcp import TeracMCP
class FakeTerac:
    def __init__(self):self.calls=[]
    def call(self,name,args):
        self.calls.append((name,args));return {'structuredContent':{'id':'request-1','status':'RECEIVED','costPerParticipant':None}}
class TeracTests(unittest.TestCase):
    def plan(self,product):return {'product':product,'concerns':[{'title':'Unclear value','suggested_expertise':'Relevant product researcher','explanation':'Some simulated buyers prefer their existing solution.','review_question':'What evidence would justify switching?','customer_ids':['customer-1'],'expert_brief':{'role':'Product researcher','product_domain':product,'work_type':'review','relevant_experience':['Has worked on this product category.','Has investigated switching decisions in this category.'],'qualification_checks':['Ask which relevant product they worked on.','Ask which investigation they personally performed.'],'deliverable':'One testable recommendation with evidence limits.'}}]}
    def test_policy_generalizes_without_country_fallback(self):
        for name in ['Speaker','Keyboard','Coaching','Resume review']:
            args=feasibility_arguments(name,self.plan(name)['concerns'][0])
            self.assertEqual(args['submissionCount'],1)
            self.assertIn('CURRENTLY RESIDES IN the United States',args['panelDescription'])
            self.assertIn('PHYSICALLY BASED IN the United States',args['panelDescription'])
            self.assertIn('English-speaking',args['panelDescription'])
            self.assertIn(name,args['taskDescription'])
        self.assertFalse(expert_policy()['allow_outside_us'])
    def test_generic_role_without_product_experience_is_blocked(self):
        row=self.plan('A learning service')['concerns'][0];del row['expert_brief']
        with self.assertRaises(ValueError):feasibility_arguments('A learning service',row)

    def test_implementation_requires_access(self):
        row=self.plan('Learning app')['concerns'][0];row['expert_brief']['work_type']='implementation'
        with self.assertRaises(ValueError):feasibility_arguments('Learning app',row)

    def test_saved_response_prevents_duplicate_request(self):
        with tempfile.TemporaryDirectory() as folder:
            client=FakeTerac();plan=self.plan('Any product')
            first=request_improvements(plan,folder,client)
            self.assertEqual(first,request_improvements(plan,folder,client));self.assertEqual(len(client.calls),1)
            plan['concerns'][0]['explanation']='Changed'
            with self.assertRaises(ValueError):request_improvements(plan,folder,client)
            self.assertEqual(len(client.calls),1)
    def test_ambiguous_network_failure_is_not_automatically_retried(self):
        class Failed(FakeTerac):
            def call(self,*args):raise RuntimeError('Network interruption')
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(RuntimeError):request_improvements(self.plan('Coaching'),folder,Failed())
            client=FakeTerac()
            with self.assertRaises(ValueError):request_improvements(self.plan('Coaching'),folder,client)
            self.assertEqual(client.calls,[])
    def test_status_read_reuses_requests_and_obeys_backoff(self):
        with tempfile.TemporaryDirectory() as folder:
            client=FakeTerac();request_improvements(self.plan('Any service'),folder,client)
            first=refresh_improvements(folder,client)
            second=refresh_improvements(folder,client)
            self.assertEqual(first,second)
            self.assertEqual([name for name,_ in client.calls],['terac_request_feasibility','terac_get_feasibility_request'])
            self.assertIsNone(second[0]['response']['costPerParticipant'])

    def test_launch_create_and_invite_are_not_callable(self):
        client=TeracMCP('test-only',lambda *args:self.fail('No network expected'))
        for name in ['terac_launch_draft_opportunity','terac_create_opportunity','terac_invite_applicant']:
            with self.assertRaises(ValueError):client.call(name,{})
    def test_mcp_protocol_and_context_first(self):
        calls=[]
        def transport(body,headers):
            import json
            calls.append(body)
            result={'protocolVersion':'2025-03-26'} if body['method']=='initialize' else {'structuredContent':{'status':'RECEIVED'}}
            return json.dumps({'jsonrpc':'2.0','id':body.get('id'),'result':result}),{}
        client=TeracMCP('test-key',transport);client.call('terac_request_feasibility',{'taskDescription':'Test','panelDescription':'US only','submissionCount':1})
        tools=[x['params']['name'] for x in calls if x['method']=='tools/call']
        self.assertEqual(tools,['terac_get_context','terac_request_feasibility'])
