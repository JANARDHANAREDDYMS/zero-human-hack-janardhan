"""Reject-before-inference probes for the existing strict worker contract."""
import json
from .config import AdapterConfig
from .instructions import InstructionRegistry
from .tools.http import JsonTransport,TransportError
from .validation import SCHEMAS

class WorkerNotReady(RuntimeError):pass

def check_worker(config=None,transport=None):
    config=config or AdapterConfig.from_environment()
    if config.model_backend=='openrouter':
        config.validate();return True # Configuration-only; never send a fake zero-token inference to OpenRouter.
    transport=transport or JsonTransport();registry=InstructionRegistry()
    for stage,schema in [('simulate_concept','customer-concept-decision'),('summarize_simulation','simulation-report'),('extract_review_concerns','review-concerns')]:
        body={'contract_version':'1.1','stage':stage,'model':config.model_id,'instructions':registry.for_stage(stage),
            'payload':{},'output_schema':json.loads((SCHEMAS/(schema+'.schema.json')).read_text()),
            'limits':{'max_tokens':0,'max_cost_usd':0.1,'timeout_seconds':10}}
        try:transport.post(config.model_bridge_url,{'Authorization':'Bearer '+config.model_bridge_token},body,15)
        except TransportError as error:
            if error.status==400:continue # Exact policy matched, then zero-token allowance rejected.
            if error.status in {403,409}:raise WorkerNotReady('The Lovable worker is missing an updated stage or policy. Publish lovable-review-concerns-v1.zip before starting the full pipeline. No model calls were made.') from None
            raise WorkerNotReady('Could not verify the Lovable worker. Check the worker URL, token and connection before starting. No pipeline was started.') from None
        raise WorkerNotReady('Worker readiness check returned an unexpected response. The pipeline was not started.')
    return True
