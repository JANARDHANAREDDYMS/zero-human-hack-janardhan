"""Explicitly offline stage responses for harness verification; never a live fallback."""
import copy
import json
from pathlib import Path
from ..state import StageResponse
from ..instructions import fixture_checks, InstructionRegistry


class FixtureBackend:
    mode = 'offline_fixture'
    name = 'saved-keyboard-fixtures-v1'

    def __init__(self, directory):
        directory = Path(directory)
        self.instruction_manifest=InstructionRegistry().manifest()
        self.intake = json.loads((directory/'intake.json').read_text())
        self.evidence = json.loads((directory/'evidence.json').read_text())
        self.specification = json.loads((directory/'specification.json').read_text())

    def execute(self, stage, payload, allowances):
        if stage=='intake':
            data = self.intake
        elif stage=='research':
            data = self.evidence
        elif stage in {'propose','correct'}:
            data = self.specification
        elif stage=='review':
            data = {'decision':'accept','summary':'Offline control-flow fixture only; no model judged this population.',
                'checks':fixture_checks(),'findings':[{'code':'fixture-only','severity':'warning',
                    'message':'Segment design and evidence are hand-authored test inputs, not live research or buyer validation.',
                    'source_ids':[]}]}
        else:
            raise ValueError(f'Unsupported fixture stage: {stage}')
        return StageResponse(copy.deepcopy(data),0,0,0.0)
