// Offline test oracle: constructs wire fixtures from known canonical fixtures.
// This is not model generation and cannot establish gateway acceptance.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const require=createRequire(path.resolve('backend/workers/lovable/package.json'));
const Ajv=require('ajv/dist/2020').default;
const formats=require('ajv-formats');
const ajv=new Ajv({strict:false,allowUnionTypes:true});formats(ajv);
const base=pathToFileURL(path.resolve(input.runtime)+'/');
const {toWireSchema,fromWireOutput,isUnconstrained}=await import(new URL('wire-schema.mjs',base));
const {createHandler}=await import(new URL('worker.mjs',base));
const validators=await import(new URL('validators.generated.mjs',base));
const policy=JSON.parse(fs.readFileSync(input.policy));
const root=policy.stages[input.stage].output_schema;
const resolve=s=>s.$ref?resolve(root.$defs[s.$ref.slice(8)]):s;
const typed=v=>v===null?{kind:'null',value:null}:Array.isArray(v)?{kind:'array',value:v.map(typed)}:typeof v==='object'?{kind:'object',value:Object.entries(v).map(([key,value])=>({key,value:typed(value)}))}:{kind:typeof v,value:v};
const map=s=>s.type==='object'&&!s.properties&&(s.additionalProperties===undefined||s.additionalProperties===true||typeof s.additionalProperties==='object');
function encode(v,s){
  s=resolve(s);
  if(isUnconstrained(s))return typed(v);
  if(v===null)return null;
  if(s.oneOf||s.anyOf){
    const branches=s.oneOf||s.anyOf;
    const selected=branches.find(b=>ajv.compile({...b,$defs:root.$defs})(v));
    if(!selected)throw Error('No canonical branch matches test fixture');
    return encode(v,selected);
  }
  if(map(s))return Object.entries(v).map(([key,value])=>({key,value:encode(value,typeof s.additionalProperties==='object'?s.additionalProperties:{})}));
  if(s.properties)return Object.fromEntries(Object.entries(s.properties).map(([k,p])=>[k,Object.hasOwn(v,k)?encode(v[k],p):null]));
  if(Array.isArray(v)&&s.items)return v.map(x=>encode(x,s.items));
  return v;
}
let wire=encode(input.data,root);
if(input.mutation==='duplicate_attribute')wire.attributes.push(structuredClone(wire.attributes[0]));
if(input.mutation==='invalid_tag'){
  function mutate(v){if(v&&typeof v==='object'){if(v.kind==='string'){v.kind='bogus';return true;}return Object.values(v).some(mutate);}return false;}
  if(!mutate(wire))throw Error('No tagged value found');
}
if(input.mutation==='wrong_rule_branch')wire.segments[0].fields[0].value.rule={kind:'bogus'};
const validWire=ajv.compile(toWireSchema(root))(wire);
let decoded=null,decodeError=null;
try{decoded=fromWireOutput(wire,root);}catch(e){decodeError=e.message;}
const token='offline-test-token-'.repeat(3);
let calls=0;
const handler=createHandler({env:{WORKER_SHARED_TOKEN:token,LOVABLE_API_KEY:'offline-fake-key',ALLOWED_MODEL_IDS:'offline-model'},policy,validators,
 fetcher:async()=>{calls++;return new Response(JSON.stringify({id:'offline-fixture',usage:{prompt_tokens:1,completion_tokens:1},choices:[{finish_reason:'stop',message:{content:input.mutation==='outer_json'?'not json':JSON.stringify(wire)}}]}));}});
const response=await handler(new Request('https://offline.invalid/worker',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({contract_version:'1.1',stage:input.stage,model:'offline-model',...policy.stages[input.stage],payload:{offline_fixture:true},limits:{max_tokens:40000,max_cost_usd:1,timeout_seconds:5}})}));
console.log(JSON.stringify({wire_valid:validWire,decoded,decode_error:decodeError,canonical_errors:validators[input.stage].errors,status:response.status,response:await response.json(),mock_gateway_calls:calls}));
