import tempfile,unittest
from pathlib import Path
from customer_generation.artifact_views import render_artifact
from customer_simulation.pipeline import profile_path

class OutputViews(unittest.TestCase):
    def test_root_alias(self):
        profile={'budget':{'maximum':20},'requirements':[{'attribute':'price','value':20}]}
        self.assertEqual(profile_path(profile,'customer.budget.maximum'),20)
        self.assertEqual(profile_path(profile,'customer.requirements.0.value'),20)
        self.assertEqual(profile_path(profile,'customer.requirements.price.value'),20)
        for path in ['customer.customer.budget.maximum','customer.missing','customer.requirements.9']:
            with self.assertRaises(ValueError):profile_path(profile,path)
    def test_html_escapes_data(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'evidence.json'
            path.write_text('{"sources":[{"title":"<script>bad()</script>","url":"https://example.com"}]}')
            result=render_artifact(path,'evidence')
            self.assertNotIn('<script>',result)
            self.assertIn('&lt;script&gt;',result)
            self.assertIn('href="https://example.com"',result)
