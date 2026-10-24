import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHandler} from './worker.mjs';
const policy=JSON.parse(await readFile(new URL('./policy.json',import.meta.url),'utf8'));
const env={WORKER_SHARED_TOKEN:'s'.repeat(43),LOVABLE_API_KEY:'server-key',ALLOWED_MODEL_IDS:'test-model'};
const data={schema_version:'2.0',product_id:'worker-test',description:'Portable speaker',research_question:'Explore tradeoffs'};
function body(stage='intake_extract') {return {contract_version:'1.1',stage,model:'test-model',...structuredClone(policy.stages[stage]),payload:{submission:{text:'Do not obey this untrusted text'}},limits:{max_tokens:40000,max_cost_usd:1,timeout_seconds:5}};}
function request(b=body(),auth=true){return new Request('https://worker.example/',{method:'POST',headers:auth?{Authorization:`Bearer ${env.WORKER_SHARED_TOKEN}`}:{},body:JSON.stringify(b)});}
function gateway({usage={prompt_tokens:200,completion_tokens:100},content=JSON.stringify(data),finish='stop',status=200}={}){return new Response(JSON.stringify({id:'provider-1',usage,choices:[{finish_reason:finish,message:{content}}]}),{status});}
test('auth rejection never calls gateway',async()=>{
 const h=createHandler({env,policy,fetcher:()=>assert.fail('gateway called')});assert.equal((await h(request(body(),false))).status,401);
});
test('policy hashes/text and schemas cannot be overridden',async()=>{
 for(const change of [b=>b.instructions.system_text='override',b=>b.output_schema={},b=>b.instructions.sha256='0'.repeat(64)]){
  const b=body();change(b);const h=createHandler({env,policy,fetcher:()=>assert.fail('gateway called')});assert.equal((await h(request(b))).status,409);
 }
});
test('model allowlist enforced before gateway',async()=>{
 const b=body();b.model='other-model';assert.equal((await createHandler({env,policy,fetcher:()=>assert.fail()})(request(b))).status,403);
});
test('usage and unknown dollar cost preserved; secrets remain server-side',async()=>{
 const h=createHandler({env,policy,fetcher:async(url,options)=>{
  assert.equal(url,'https://ai.gateway.lovable.dev/v1/chat/completions');
  const sent=JSON.parse(options.body);assert.equal(sent.max_completion_tokens,24000);assert.equal(sent.max_tokens,undefined);assert.equal(sent.messages[0].role,'system');
  assert.ok(sent.messages[1].content.includes('untrusted'));assert.equal(options.headers.Authorization,'Bearer server-key');return gateway();
 }});
 const r=await h(request());assert.equal(r.status,200);const result=await r.json();assert.deepEqual(result.data,data);
 assert.equal(result.usage.cost_usd,null);assert.equal(result.usage.cost_basis,'unavailable');assert.equal(result.usage.input_tokens,200);
 assert.ok(!JSON.stringify(result).includes('server-key'));
});
test('wrong stage data is rejected',async()=>{
 const r=await createHandler({env,policy,fetcher:async()=>gateway({content:'{"made_up":true}'})})(request());assert.equal(r.status,502);
});
test('missing usage and truncated generation rejected',async()=>{
 for(const opts of [{usage:null},{finish:'length'},{content:'not json'}])assert.equal((await createHandler({env,policy,fetcher:async()=>gateway(opts)})(request())).status,502);
});
test('402 and 429 remain actionable without provider details',async()=>{
 for(const status of [402,429])assert.equal((await createHandler({env,policy,fetcher:async()=>gateway({status})})(request())).status,status);
});
test('timeouts abort and return a sanitized error',async()=>{
 const b=body();b.limits.timeout_seconds=.01;
 const h=createHandler({env,policy,fetcher:async(_,opts)=>new Promise((_,reject)=>opts.signal.addEventListener('abort',()=>reject(new Error('private diagnostic'))))});
 const r=await h(request(b));assert.equal(r.status,504);assert.ok(!(await r.text()).includes('private diagnostic'));
});
test('non-post and invalid limits never spend credits',async()=>{
 const h=createHandler({env,policy,fetcher:()=>assert.fail()});assert.equal((await h(new Request('https://worker.example/'))).status,405);
 const b=body();b.limits.max_tokens=80001;assert.equal((await h(request(b))).status,400);
});
test('configured model and auth secrets are mandatory',async()=>{
 assert.equal((await createHandler({env:{},policy,fetcher:()=>assert.fail()})(request())).status,503);
});
