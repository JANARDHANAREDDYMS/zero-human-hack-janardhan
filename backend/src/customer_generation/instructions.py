"""Versioned instruction bundles; payload content can never select a prompt path."""
import hashlib
import json
from pathlib import Path

PROMPTS=Path(__file__).with_name('prompts')

class InstructionRegistry:
    def __init__(self):
        manifest=json.loads((PROMPTS/'versions.json').read_text())
        self._bundles={}
        shared=(PROMPTS/manifest['methodology']).read_text()
        for stage,files in manifest['stages'].items():
            text=('' if stage in {'simulate_customer','simulate_concept','summarize_simulation','extract_review_concerns'} else shared+'\n\n')+'\n\n'.join((PROMPTS/f).read_text() for f in files)
            digest=hashlib.sha256((stage+'\n'+manifest['bundle_version']+'\n'+text).encode()).hexdigest()
            self._bundles[stage]={'version':manifest['bundle_version'],'sha256':digest,'system_text':text}
    def for_stage(self,stage):
        if stage not in self._bundles:raise ValueError('Unsupported instruction stage')
        return dict(self._bundles[stage])
    def manifest(self):
        return {stage:{'version':b['version'],'sha256':b['sha256']} for stage,b in self._bundles.items()}

REVIEW_CATEGORIES=('coverage','segment_distinctness','within_segment_variation','evidence_support',
    'assumption_transparency','product_independence','simulation_fit')

def fixture_checks():
    """Explicit non-evaluation, useful only for saved/scripted test backends."""
    return [{'category':c,'status':'warning','rationale':'Offline fixture: qualitative model evaluation was not performed.',
        'segment_ids':[],'customer_ids':[],'source_ids':[]} for c in REVIEW_CATEGORIES]
