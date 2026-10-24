"""Client for our authenticated project function, not a public Lovable API.

The server function is not deployed by this module. It must implement the
bridge contract, own the project AI credential, stage instructions, model
allowlist, and actual usage accounting. No fallback provider is selected.
"""
import math
from ..state import StageResponse
from ..instructions import InstructionRegistry
from ..validation import validate_schema
from .http import JsonTransport,validate_endpoint


class ModelResponseError(RuntimeError):
    pass


class ModelBridgeClient:
    def __init__(self,url,token,model_id,transport=None,*,response_observer=None):
        validate_endpoint(url)
        self.url=url;self._token=token;self.model_id=model_id
        self.transport=transport or JsonTransport()
        self.instructions=InstructionRegistry()
        self.response_observer=response_observer
    def call(self,stage,payload,allowances,output_schema):
        if stage not in self.instructions.manifest():
            raise ValueError('Unsupported bridge stage')
        instructions=self.instructions.for_stage(stage)
        response=self.transport.post(self.url,{'Authorization':'Bearer '+self._token},
            {'contract_version':'1.1','stage':stage,'model':self.model_id,
                'instructions':instructions,'payload':payload,'limits':allowances,'output_schema':output_schema},allowances['timeout_seconds'])
        if self.response_observer is not None:self.response_observer(response)
        validate_schema(response,'model-bridge-response')
        usage=response['usage']
        # Unknown billing must not quietly look like a zero-cost model call.
        if response['model']!=self.model_id:raise ModelResponseError('Bridge returned a different model')
        if response['stage']!=stage:raise ModelResponseError('Bridge returned a different stage')
        if response['instruction_version']!=instructions['version'] or response['instruction_sha256']!=instructions['sha256']:
            raise ModelResponseError('Bridge did not acknowledge the expected instruction bundle')
        return StageResponse(response['data'],usage['input_tokens'],usage['output_tokens'],usage['cost_usd'] if usage['cost_usd'] is not None else 0.0,
            metadata={'model':response['model'],'request_id':response['request_id'],'cost_basis':usage['cost_basis'],'cost_uncertain':usage['cost_usd'] is None,'instruction_version':response['instruction_version'],'instruction_sha256':response['instruction_sha256']})


def configured_client(config=None):
    if config is None:
        import os
        backend=os.environ.get('MODEL_BACKEND','bridge')
        if backend=='openrouter':
            from .openrouter import OpenRouterClient
            return OpenRouterClient(os.environ.get('OPENROUTER_API_KEY',''),os.environ.get('OPENROUTER_MODEL',''))
        if backend=='codex':
            from .codex import CodexModelClient,configured_model
            return CodexModelClient(os.environ.get('CODEX_MODEL','').strip() or configured_model())
        if backend!='bridge':raise ValueError('Unsupported model backend')
        return ModelBridgeClient(*(os.environ.get(k,'') for k in ['MODEL_BRIDGE_URL','MODEL_BRIDGE_TOKEN','MODEL_ID']))
    if config.model_backend=='openrouter':
        from .openrouter import OpenRouterClient
        return OpenRouterClient(config.model_bridge_token,config.model_id)
    if config.model_backend=='codex':
        from .codex import CodexModelClient
        return CodexModelClient(config.model_id)
    return ModelBridgeClient(config.model_bridge_url,config.model_bridge_token,config.model_id)
