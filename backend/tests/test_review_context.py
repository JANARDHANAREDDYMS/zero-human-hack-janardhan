import json
from pathlib import Path
import unittest
from customer_generation.review_context import compact_review_context,expand_review_context

ROOT=Path(__file__).resolve().parents[2]

class ReviewContextTests(unittest.TestCase):
    def test_full_saved_review_context_is_lossless_and_smaller(self):
        p=ROOT/'data/runs/sony-compact-20261024-120617-sony-speaker/call-03-request.json'
        payload=json.loads(p.read_text())['payload']
        result=compact_review_context(payload)
        self.assertEqual(expand_review_context(result),payload)
        before=len(json.dumps(payload));after=len(json.dumps(result))
        self.assertLess(after,before*.8)

    def test_plain_values_and_reference_like_text_remain_exact(self):
        payload={'a':['$review_text',0,False,None],'b':'long repeated text '*15,'c':'long repeated text '*15}
        self.assertEqual(expand_review_context(compact_review_context(payload)),payload)
