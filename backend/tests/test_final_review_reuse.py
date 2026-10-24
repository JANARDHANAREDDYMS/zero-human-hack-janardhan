"""Review-only replay wiring, with an explicitly synthetic reviewer; no network."""
import contextlib,io,json,runpy,shutil,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from customer_generation.instructions import InstructionRegistry
from customer_generation.state import StageResponse

ROOT=Path(__file__).resolve().parents[2]
SOURCE='sony-compact-20261024-121412-sony-speaker'

class FinalReviewReplayTests(unittest.TestCase):
    def run_case(self,count=50):
        scope=runpy.run_path(str(ROOT/'backend/scripts/run_smoke_tests.py'))
        calls=[]
        class ReviewOnly:
            name='offline-test-review-only';mode='live'
            instruction_manifest=InstructionRegistry().manifest()
            def __init__(self,*a,**kw):pass
            def execute(self,stage,payload,allowances):
                calls.append(stage)
                if stage!='review':raise AssertionError('Research/proposal must be reused')
                data=json.loads((ROOT/'data/runs/phase4-keyboard-offline/review-0.json').read_text())
                data['summary']='Synthetic acceptance fixture for replay control-flow test only.'
                return StageResponse(data,1,1,0,metadata={'offline_test':True})
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            shutil.copytree(ROOT/'data/runs'/SOURCE,root/'data/runs'/SOURCE)
            globals_=scope['main'].__globals__;globals_['ROOT']=root;globals_['LiveBackend']=ReviewOnly
            globals_['load_environment']=lambda *a:None
            globals_['AdapterConfig']=type('Config',(),{'from_environment':staticmethod(lambda **kw:object())})
            args=['runner','--product','sony-speaker','--proposal-format','compact','--reuse-research-run',SOURCE,
                '--reuse-proposal-run',SOURCE,'--max-corrections','0','--run-prefix','final-offline','--count',str(count),'--execute']
            with patch.object(sys,'argv',args),contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):status=scope['main']()
            if status==0:
                population=json.loads((root/'data/runs/final-offline-sony-speaker/customers.json').read_text())
                self.assertEqual(population['count'],50)
            return status,calls

    def test_one_review_call_reuses_evidence_and_corrected_proposal(self):
        status,calls=self.run_case();self.assertEqual(status,0);self.assertEqual(calls,['review'])

    def test_count_mismatch_stops_before_any_call(self):
        status,calls=self.run_case(49);self.assertEqual(status,1);self.assertEqual(calls,[])
