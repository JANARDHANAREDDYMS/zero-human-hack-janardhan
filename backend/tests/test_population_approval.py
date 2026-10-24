import json,shutil,tempfile,unittest
from pathlib import Path
from customer_generation.approval import summary_lines,read_population,write_summary,approval_valid

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'data/runs/sony-compact-20261024-122821-sony-speaker'

class ApprovalTests(unittest.TestCase):
    def test_five_lines_actual_counts_and_hash_bound_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            run=Path(temp)/SOURCE.name;shutil.copytree(SOURCE,run)
            lines=summary_lines(run);self.assertEqual(len(lines),5)
            for count,line in zip([15,12,10,13],lines[1:]):self.assertIn(str(count)+' customers',line)
            write_summary(run);self.assertTrue((run/'population-summary.html').exists())
            approval=Path(temp)/'approval.json';approval.write_text(json.dumps({'run_id':run.name,'scope':'summary_approval_for_simulation','input_hashes':read_population(run)[2]}))
            self.assertTrue(approval_valid(run,approval))
            p=run/'evidence.json';p.write_text(p.read_text()+'\n')
            self.assertFalse(approval_valid(run,approval))

    def test_incomplete_run_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            run=Path(temp);(run/'state.json').write_text('{"status":"incomplete"}')
            with self.assertRaises(ValueError):summary_lines(run)
