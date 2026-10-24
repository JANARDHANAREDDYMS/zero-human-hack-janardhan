import base64,copy,io,json,tempfile,time,unittest,zipfile
from pathlib import Path
from customer_generation.demo import Demo,application,extract_upload
from customer_generation.instructions import fixture_checks
from customer_generation.state import StageResponse

ROOT=Path(__file__).resolve().parents[2]

def dotm(xml,macro=b'NEVER EXECUTE'):
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w') as z:
        z.writestr('word/document.xml',xml);z.writestr('word/vbaProject.bin',macro)
    return buffer.getvalue()

XML='''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
<w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr><w:r><w:t>Test speaker</w:t></w:r></w:p>
<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Description</w:t></w:r></w:p>
<w:p><w:r><w:t>Portable audio for travel.</w:t></w:r></w:p></w:body></w:document>'''

class DemoTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.calls=[];test=self
        class Backend:
            name='offline-demo-handoff-test';mode='live'
            def execute(self,stage,payload,limits):
                test.calls.append(stage)
                folder=ROOT/'data/products/sony-speaker/research-v2'
                if stage=='research':
                    data=json.loads((folder/'evidence.json').read_text());data['product_id']=payload['brief']['product_id']
                elif stage=='propose':
                    data=json.loads((folder/'specification.json').read_text());data['product_id']=payload['brief']['product_id']
                elif stage=='review':data={'decision':'accept','summary':'Offline browser handoff fixture only.','checks':fixture_checks(),'findings':[]}
                else:raise AssertionError(stage)
                return StageResponse(data,1,1,0,metadata={'offline_fixture':True})
        self.demo=Demo(Path(self.temp.name),backend_factory=Backend)
    def tearDown(self):self.temp.cleanup()

    def test_markdown_preview_and_missing_details(self):
        raw=b'# Product name\nTest\n## Description\nPortable audio'
        d=self.demo.preview({'filename':'brief.md','file_base64':base64.b64encode(raw).decode()})
        self.assertTrue(d['can_submit']);self.assertEqual(d['brief']['name'],'Test');self.assertEqual(self.calls,[])
        self.assertFalse(self.demo.preview({'fields':{}})['can_submit'])

    def test_dotm_text_extraction_never_reads_macros(self):
        raw=dotm(XML)
        text=extract_upload('brief.dotm',raw)
        self.assertIn('# Test speaker',text);self.assertNotIn('NEVER EXECUTE',text)
        d=self.demo.preview({'filename':'brief.dotm','file_base64':base64.b64encode(raw).decode()})
        self.assertEqual(d['brief']['name'],'Test speaker');self.assertEqual(d['brief']['description'],'Portable audio for travel.')
        self.assertFalse(d['source']['macros_executed']);self.assertEqual(self.calls,[])

    def test_unsafe_or_invalid_uploads_rejected(self):
        for name,raw in [('../a.md',b'x'),('a.exe',b'x'),('a.dotm',b'not zip'),('a.md',b'\xff'),('a.dotm',dotm('<!DOCTYPE x><x/>')),('a.md',b'x'*64001)]:
            with self.subTest(name=name):
                with self.assertRaises(ValueError):extract_upload(name,raw)

    def test_full_background_handoff_without_live_api_calls(self):
        result=self.demo.start({'fields':{'name':'Test speaker','description':'Portable audio for travel.'}})
        stop=time.monotonic()+5
        while time.monotonic()<stop:
            state=self.demo.status(result['run_id'])
            if state['status'] not in {'running'}:break
            time.sleep(.01)
        self.assertEqual(state['status'],'completed',state)
        self.assertEqual(self.calls,['research','propose','review']);self.assertEqual(len(state['summary']),5)
        path=Path(self.temp.name)/result['run_id']/'customers.json'
        self.assertEqual(json.loads(path.read_text())['count'],50)
        inspection=self.demo.inspect(result['run_id'])
        self.assertIsNotNone(inspection['brief']);self.assertIsNotNone(inspection['specification'])
        self.assertEqual(inspection['generation_inputs'][0]['data']['stage'],'propose')
        self.assertTrue(inspection['profiles_file'].endswith('/customers.json'))
        self.assertTrue(inspection['offer_subjects'])
        self.assertEqual(len(self.demo.saved_runs()),1)

    def test_http_requires_loopback_origin_and_demo_token(self):
        def request(path,token='',host='127.0.0.1:8082',method='GET',body=b''):
            env={'PATH_INFO':path,'REQUEST_METHOD':method,'HTTP_HOST':host,'HTTP_X_DEMO_TOKEN':token,'CONTENT_LENGTH':str(len(body)),'wsgi.input':io.BytesIO(body)}
            captured=[]
            raw=b''.join(application(self.demo,8082)(env,lambda status,headers:captured.append(status)))
            return captured[0],raw
        self.assertTrue(request('/')[0].startswith('200'))
        self.assertTrue(request('/','',host='evil.example')[0].startswith('403'))
        self.assertTrue(request('/api/demo/preview',method='POST',body=b'{}')[0].startswith('403'))
        status,_=request('/api/demo/preview',self.demo.token,method='POST',body=b'{"fields":{}}')
        self.assertTrue(status.startswith('200'));self.assertEqual(self.calls,[])

if __name__=='__main__':unittest.main()
