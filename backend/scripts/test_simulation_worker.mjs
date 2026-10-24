// Offline full-envelope test against the actual current worker/compiler/decoder.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {createHandler} from '../workers/lovable-current/worker.mjs';
import {toWireSchema,fromWireOutput} from '../workers/lovable-current/wire-schema.mjs';
const require=createRequire(new URL('../workers/lovable/package.json',import.meta.url));
const Ajv=require('ajv/dist/2020').default;
const policy=JSON.parse(fs.readFileSync('backend/workers/lovable-current/policy.json'));
const stage=policy.stages.simulate_customer;
const ajv=new Ajv({strict:false});const validate=ajv.compile(stage.output_schema);
const wire=toWireSchema(stage.output_schema);
function check(node){if(!node||typeof node!=='object')return;if(node.type==='object'){assert.equal(node.additionalProperties,false);assert.deepEqual([...node.required].sort(),Object.keys(node.properties).sort());}if(node.$ref)assert.deepEqual(Object.keys(node),['$ref']);for(const v of Object.values(node))if(typeof v==='object')Array.isArray(v)?v.forEach(check):check(v);}
check(wire);
const env={WORKER_SHARED_TOKEN:'x'.repeat(40),LOVABLE_API_KEY:'offline-only',ALLOWED_MODEL_IDS:'offline-model'};
for(const decision of ['choose_product','choose_alternative','keep_current','defer']){
 const output={customer_id:'fixture-customer',decision,selected_offer_id:decision==='choose_product'?'target':decision==='choose_alternative'?'alternative-fixture':null,
 headline:'A specific offer comparison',reasons:[{explanation:'Budget and switching barriers matter.',profile_fields:['budget.maximum'],finding_ids:['fixture-price']}],
 objections:[{category:'missing_information',concern:'Measured battery life is unknown.',suggested_change:'Provide a measured result.',finding_ids:[]}],
 missing_information:['Measured battery life'],change_that_might_help:'Provide an independent test.',limitations:['Synthetic result; no physical test.']};
 assert.ok(validate(output),JSON.stringify(validate.errors));assert.deepEqual(fromWireOutput(output,stage.output_schema),output);
 let calls=0;
 const handler=createHandler({env,policy,validators:{simulate_customer:validate},fetcher:async(_url,options)=>{
   calls++;const sent=JSON.parse(options.body);assert.equal(sent.max_completion_tokens,3000);assert.deepEqual(sent.response_format.json_schema.schema,wire);
   return new Response(JSON.stringify({id:'offline',usage:{prompt_tokens:100,completion_tokens:200},choices:[{finish_reason:'stop',message:{content:JSON.stringify(output)}}]}),{status:200});
 }});
 const body={contract_version:'1.1',stage:'simulate_customer',model:'offline-model',instructions:stage.instructions,payload:{customer:{customer_id:'fixture-customer'}},limits:{max_tokens:3000,max_cost_usd:0.1,timeout_seconds:100},output_schema:stage.output_schema};
 const response=await handler(new Request('https://example.test/api',{method:'POST',headers:{authorization:`Bearer ${env.WORKER_SHARED_TOKEN}`},body:JSON.stringify(body)}));
 assert.equal(response.status,200);assert.deepEqual((await response.json()).data,output);assert.equal(calls,1);
}
console.log('PASS: all four decisions traverse the actual worker, strict schema, decoder and canonical validator offline.');

// Full five-customer concept + report fixtures, generated through the real Python client.
const {execFileSync}=await import('node:child_process');
const fixtures=JSON.parse(execFileSync('python3',['backend/scripts/simulation_worker_fixtures.py'],{encoding:'utf8'}));
assert.equal(fixtures.length,7);
for(const fixture of fixtures){
 const maxOutput=fixture.stage==='extract_review_concerns'?8000:5000;
 const p=policy.stages[fixture.stage],validate=new Ajv({strict:false}).compile(p.output_schema),wire=toWireSchema(p.output_schema);
 check(wire);assert.ok(validate(fixture.data),JSON.stringify(validate.errors));
 assert.deepEqual(fromWireOutput(fixture.data,p.output_schema),fixture.data);
 let calls=0;
 const handler=createHandler({env,policy,validators:{[fixture.stage]:validate},fetcher:async(_url,opts)=>{
   calls++;const sent=JSON.parse(opts.body);assert.equal(sent.max_completion_tokens,maxOutput);assert.deepEqual(sent.response_format.json_schema.schema,wire);
   return new Response(JSON.stringify({id:'offline',usage:{prompt_tokens:100,completion_tokens:200},choices:[{finish_reason:'stop',message:{content:JSON.stringify(fixture.data)}}]}),{status:200});
 }});
 const body={contract_version:'1.1',stage:fixture.stage,model:'offline-model',instructions:p.instructions,payload:fixture.payload,limits:{max_tokens:maxOutput,max_cost_usd:0.1,timeout_seconds:100},output_schema:p.output_schema};
 const request=(token=env.WORKER_SHARED_TOKEN)=>new Request('https://example.test/api',{method:'POST',headers:{authorization:`Bearer ${token}`},body:JSON.stringify(body)});
 assert.equal((await handler(request('bad-token'))).status,401);assert.equal(calls,0);
 const response=await handler(request());assert.equal(response.status,200);assert.deepEqual((await response.json()).data,fixture.data);assert.equal(calls,1);
 const bad=structuredClone(body);bad.instructions.sha256='0'.repeat(64);
 const rejected=await handler(new Request('https://example.test/api',{method:'POST',headers:{authorization:`Bearer ${env.WORKER_SHARED_TOKEN}`},body:JSON.stringify(bad)}));
 assert.equal(rejected.status,409);assert.equal(calls,1);
}
console.log('PASS: full five-customer concept + narrative fixtures traverse worker/compiler/decoder/validator; authentication and stale-policy rejection preserve zero calls.');
