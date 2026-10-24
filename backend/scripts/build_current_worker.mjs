// Offline build of local working-copy validators using existing worker dependencies.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const require=createRequire(path.resolve('backend/workers/lovable/package.json'));
const Ajv=require('ajv/dist/2020').default;
const formats=require('ajv-formats');
const standalone=require('ajv/dist/standalone').default;
const dir='backend/workers/lovable-current';
const policy=JSON.parse(fs.readFileSync(`${dir}/policy.json`));
const ajv=new Ajv({strict:false,allowUnionTypes:true,code:{source:true,esm:true}});formats(ajv);
const map={};
for(const [stage,p] of Object.entries(policy.stages)){ajv.addSchema(p.output_schema,`stage_${stage}`);map[stage]=`stage_${stage}`;}
let code=standalone(ajv,map).replace('require("ajv/dist/runtime/ucs2length").default','__ucs2length').replace('require("ajv-formats/dist/formats").fullFormats','__fullFormats');
if(code.includes('require('))throw Error('Unexpected generated dependency');
code=code.replace('"use strict";','"use strict";\nimport __ucs2lengthMod from "ajv/dist/runtime/ucs2length.js";\nimport {fullFormats as __fullFormats} from "ajv-formats/dist/formats.js";\nconst __ucs2length=__ucs2lengthMod.default ?? __ucs2lengthMod;\n');
fs.writeFileSync(`${dir}/validators.generated.mjs`,'// Generated offline; do not edit.\n'+code);
console.log('Built validators for '+Object.keys(map).length+' stages; no network calls');
