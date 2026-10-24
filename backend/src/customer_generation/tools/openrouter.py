"""Direct OpenRouter access. Canonical JSON, local validation, no repair calls."""
import copy,json,math
from pathlib import Path
from ..instructions import InstructionRegistry
from ..state import StageResponse
from ..validation import SCHEMAS,ContractError,_guard
from .http import JsonTransport
from .llm import ModelResponseError

URL='https://openrouter.ai/api/v1/chat/completions'

def bundled_schema(schema):
    """Bundle only repository schema refs; never fetch remote references."""
    definitions={};loading=set()
    def walk(value,scope=""):
        if isinstance(value,list):return [walk(x,scope) for x in value]
        if not isinstance(value,dict):return value
        result={k:walk(v,scope) for k,v in value.items() if k!='$id'}
        ref=value.get('$ref')
        if ref and ref.startswith('#') and scope:result['$ref']=scope+ref[1:]
        if ref and not ref.startswith('#'):
            filename,_,fragment=ref.partition('#');path=(SCHEMAS/filename).resolve()
            if path.parent!=SCHEMAS.resolve() or not path.is_file():raise ValueError('Only bundled repository schemas may be referenced')
            key='bundled_'+path.stem.replace('.','_')
            if key not in definitions and key not in loading:
                loading.add(key);definitions[key]=walk(json.loads(path.read_text()),'#/$defs/'+key);loading.remove(key)
            result['$ref']='#/$defs/'+key+fragment
        return result
    result=walk(copy.deepcopy(schema))
    if definitions:result.setdefault('$defs',{}).update(definitions)
    return result

class OpenRouterClient:
    def __init__(self,api_key,model_id,transport=None):
        if not api_key or not model_id:raise ValueError('OPENROUTER_API_KEY and OPENROUTER_MODEL are required')
        self._token=api_key;self.model_id=model_id;self.transport=transport or JsonTransport()
        self.instructions=InstructionRegistry();self.response_observer=None
    def call(self,stage,payload,allowances,output_schema):
        instructions=self.instructions.for_stage(stage)
        cap=allowances['max_tokens']
        if type(cap) is not int or cap<1 or not 0<allowances['timeout_seconds']<=900:raise ValueError('Invalid model allowances')
        schema=bundled_schema(output_schema)
        body={'model':self.model_id,'stream':False,'max_tokens':min(cap,24000),
            'provider':{'require_parameters':True,'allow_fallbacks':False},
            'response_format':{'type':'json_schema','json_schema':{'name':stage,'strict':False,'schema':schema}},
            'messages':[{'role':'system','content':instructions['system_text']},
                {'role':'user','content':json.dumps({'stage':stage,'payload':payload},allow_nan=False)}]}
        response=self.transport.post(URL,{'Authorization':'Bearer '+self._token},body,allowances['timeout_seconds'])
        if self.response_observer:self.response_observer(response)
        if response.get('error'):raise ModelResponseError('OpenRouter returned an API error')
        choices=response.get('choices') or []
        if len(choices)!=1:raise ModelResponseError('OpenRouter returned no single completed response')
        choice=choices[0];message=choice.get('message') or {}
        if choice.get('finish_reason')!='stop' or message.get('refusal'):raise ModelResponseError('OpenRouter output was incomplete or refused')
        text=message.get('content')
        if not isinstance(text,str):raise ModelResponseError('OpenRouter returned no JSON text')
        try:data=json.loads(text)
        except (ValueError,TypeError):raise ModelResponseError('OpenRouter returned invalid JSON') from None
        _guard(data)
        from jsonschema import Draft202012Validator
        if next(Draft202012Validator(schema).iter_errors(data),None):raise ContractError('OpenRouter output did not match the canonical schema')
        usage=response.get('usage') or {};incoming=usage.get('prompt_tokens');outgoing=usage.get('completion_tokens')
        if any(type(v) is not int or v<0 for v in [incoming,outgoing]):raise ModelResponseError('OpenRouter omitted valid token usage')
        cost=usage.get('cost')
        if cost is not None and (type(cost) not in (int,float) or not math.isfinite(cost) or cost<0):raise ModelResponseError('OpenRouter returned invalid cost usage')
        return StageResponse(data,incoming,outgoing,cost or 0.0,metadata={'model':response.get('model',self.model_id),
            'requested_model':self.model_id,'request_id':response.get('id'),'cost_basis':'provider_reported' if cost is not None else 'unavailable',
            'cost_uncertain':cost is None,'instruction_version':instructions['version'],'instruction_sha256':instructions['sha256'],
            'output_validation':'canonical_local','schema_mode':'json_schema_non_strict'})
