"""Evaluation behavior only: fixtures and mocked live adapters never test model quality."""
import copy,json,tempfile,unittest
from pathlib import Path
from customer_generation.evaluation import evaluate_run,audit_template,write_new
from customer_generation.pipeline import run_generation
from customer_generation.tools.fixtures import FixtureBackend
from customer_generation.validation import ContractError
from test_phase3 import config,FakeModel,FakeTransport,result,FIX
from customer_generation.tools.live import LiveBackend
from customer_generation.tools.exa import ExaClient

class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.intake=json.loads((FIX/'intake.json').read_text())
    def tearDown(self):self.temp.cleanup()
    def run_case(self,live=False):
        backend=LiveBackend(config(),exa=ExaClient('x',FakeTransport([result()]*3)),model=FakeModel()) if live else FixtureBackend(FIX)
        run_generation(self.intake,backend,self.root,'run')
        return self.root/'run'
    def edit(self,path,fn):
        data=json.loads(path.read_text());fn(data);path.write_text(json.dumps(data))
    def test_offline_success_stays_offline_and_has_call_timings(self):
        report=evaluate_run(self.run_case())
        self.assertEqual(report['status'],'offline_only')
        self.assertEqual(report['measurements']['total_tokens'],0)
        self.assertTrue(all(c['duration_seconds']>=0 for c in report['measurements']['calls']))
        self.assertEqual(report['checks'][-1]['status'],'not_evaluated')
    def test_recorded_live_success_requires_human_review(self):
        report=evaluate_run(self.run_case(True))
        self.assertEqual(report['status'],'needs_human_review')
        self.assertAlmostEqual(report['measurements']['known_cost_usd'],.033)
        self.assertEqual(report['measurements']['total_tokens'],90)
    def test_changed_profile_fails_replay(self):
        directory=self.run_case();self.edit(directory/'customers.json',lambda p:p['customers'][0]['budget'].update(maximum=999))
        self.assertEqual(evaluate_run(directory)['status'],'evaluation_failed')
    def test_missing_final_population_fails(self):
        directory=self.run_case();(directory/'customers.json').unlink()
        self.assertEqual(evaluate_run(directory)['status'],'evaluation_failed')
    def test_usage_totals_must_reconcile(self):
        directory=self.run_case();self.edit(directory/'state.json',lambda p:p.update(total_tokens=123))
        self.assertEqual(evaluate_run(directory)['status'],'evaluation_failed')
    def test_incomplete_run_cannot_become_success(self):
        directory=self.run_case();self.edit(directory/'state.json',lambda p:p.update(status='incomplete'))
        self.assertEqual(evaluate_run(directory)['status'],'run_not_completed')
    def test_existing_output_cannot_be_overwritten(self):
        output=self.root/'report.json';write_new(output,{'original':True})
        with self.assertRaises(FileExistsError):write_new(output,{'original':False})
        self.assertEqual(json.loads(output.read_text()),{'original':True})
    def test_template_is_unassigned_and_not_evaluated(self):
        report=evaluate_run(self.run_case());audit=audit_template(report)
        self.assertEqual(audit['reviewer'],'UNASSIGNED')
        self.assertTrue(all(c['status']=='not_evaluated' for c in audit['checks']))
        self.assertEqual(evaluate_run(self.root/'run',audit)['status'],'offline_only')
    def test_audit_binds_exact_population_and_run(self):
        directory=self.run_case();audit=audit_template(evaluate_run(directory))
        for key,value in [('run_id','another'),('customers_sha256','0'*64)]:
            bad=copy.deepcopy(audit);bad[key]=value
            with self.assertRaises(ContractError):evaluate_run(directory,bad)
    def test_duplicate_audit_categories_rejected(self):
        directory=self.run_case();audit=audit_template(evaluate_run(directory));audit['checks'][1]=copy.deepcopy(audit['checks'][0])
        with self.assertRaises(ContractError):evaluate_run(directory,audit)
    def test_human_rejection_is_recorded(self):
        directory=self.run_case(True);audit=audit_template(evaluate_run(directory));audit['reviewer']='Test reviewer'
        for c in audit['checks']:c.update(status='warning',rationale='Test judgment, not actual evaluation.')
        audit['checks'][0]['status']='fail'
        self.assertEqual(evaluate_run(directory,audit)['status'],'evaluation_failed')
    def test_partial_human_audit_stays_pending(self):
        directory=self.run_case(True);audit=audit_template(evaluate_run(directory));audit['reviewer']='Test reviewer'
        audit['checks'][0]['status']='warning'
        self.assertEqual(evaluate_run(directory,audit)['status'],'needs_human_review')
    def test_completed_human_audit_records_limitations(self):
        directory=self.run_case(True);audit=audit_template(evaluate_run(directory));audit['reviewer']='Test reviewer'
        for c in audit['checks']:c.update(status='warning',rationale='Scripted test judgment only.')
        self.assertEqual(evaluate_run(directory,audit)['status'],'reviewed_with_limitations')
    def test_audit_cannot_upgrade_offline_to_live(self):
        directory=self.run_case();audit=audit_template(evaluate_run(directory));audit['reviewer']='Test reviewer'
        for c in audit['checks']:c.update(status='pass',rationale='Test judgment only.')
        self.assertEqual(evaluate_run(directory,audit)['status'],'offline_only')
    def test_missing_reviewer_cannot_record_judgments(self):
        directory=self.run_case();audit=audit_template(evaluate_run(directory));audit['checks'][0]['status']='pass'
        with self.assertRaisesRegex(ContractError,'reviewer'):evaluate_run(directory,audit)
    def test_review_unknown_references_fail(self):
        directory=self.run_case()
        self.edit(directory/'review-0.json',lambda p:p['checks'][0].update(source_ids=['invented']))
        self.assertEqual(evaluate_run(directory)['status'],'evaluation_failed')
    def test_older_runs_can_have_unknown_stage_timing(self):
        directory=self.run_case()
        for p in directory.glob('call-*-response.json'):self.edit(p,lambda d:d.pop('duration_seconds'))
        report=evaluate_run(directory)
        self.assertEqual(report['status'],'offline_only')
        self.assertTrue(all(c['duration_seconds'] is None for c in report['measurements']['calls']))

if __name__=='__main__':unittest.main()
