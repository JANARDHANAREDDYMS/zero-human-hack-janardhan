"""Export canonical prompt/schema policy for the Lovable worker; no secrets."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend/src'))
from customer_generation.instructions import InstructionRegistry


def build_policy():
    registry=InstructionRegistry()
    schema_names={'intake_extract':'intake','research_extract':'evidence','propose':'population-specification','correct':'population-specification','review':'population-review','compact_propose':'compact-proposal','compact_correct':'compact-proposal','simulate_customer':'customer-decision','simulate_concept':'customer-concept-decision','summarize_simulation':'simulation-report','extract_review_concerns':'review-concerns'}
    return {'contract_version':'1.1','stages':{s:{'instructions':registry.for_stage(s),'output_schema':json.loads((ROOT/'data/schemas'/f'{name}.schema.json').read_text())} for s,name in schema_names.items()}}

if __name__=='__main__':
    target=ROOT/'backend/workers/lovable-current/policy.json'
    target.write_text(json.dumps(build_policy(),indent=2)+'\n')
    print('Exported worker instruction/schema policy; no secrets included.')
