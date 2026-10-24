// Converts a canonical policy output schema into an OpenAI strict-mode compatible
// "wire" schema, and decodes model output back into the canonical shape.
// The canonical schema (policy.json) is never modified; the decoded output is
// always validated against it afterwards.
//
// Wire rules:
// - every object lists all properties in `required`, additionalProperties:false
// - optional properties that cannot already be null become `anyOf:[X,{type:null}]`
//   and a null value is removed again on decode
// - map objects (additionalProperties: <schema>, or untyped objects) become arrays
//   of {key, value} entries (untyped values use recursive typed values)
// - oneOf -> anyOf; keywords strict mode does not accept are dropped (Ajv still
//   enforces them on the decoded output)

const DROP = new Set(['$schema','$id','title','examples','default','minLength','maxLength','uniqueItems',
  'minProperties','maxProperties','propertyNames','if','then','else','not','dependentRequired',
  'dependentSchemas','unevaluatedProperties','patternProperties','contains','minContains','maxContains','readOnly','writeOnly']);
const FORMATS = new Set(['date-time','time','date','duration','email','hostname','ipv4','ipv6','uuid']);

const isObj = v => v && typeof v === 'object' && !Array.isArray(v);
const resolve = (s, root) => {
  if (isObj(s) && typeof s.$ref === 'string' && s.$ref.startsWith('#/$defs/')) return resolve(root.$defs[s.$ref.slice(8)], root);
  return s;
};
const types = s => (s.type === undefined ? [] : Array.isArray(s.type) ? s.type : [s.type]);
export function acceptsNull(s, root) {
  s = resolve(s, root);
  if (!isObj(s)) return true;
  if (types(s).includes('null')) return true;
  if (Array.isArray(s.enum) && s.enum.includes(null)) return true;
  if ('const' in s && s.const === null) return true;
  const alts = s.anyOf || s.oneOf;
  return Array.isArray(alts) && alts.some(a => acceptsNull(a, root));
}
const isMap = s => isObj(s) && !s.properties && (types(s).includes('object')) &&
  (isObj(s.additionalProperties) || s.additionalProperties === undefined || s.additionalProperties === true);

const STRUCT = ['type','$ref','anyOf','oneOf','allOf','enum','const','properties','items','additionalProperties','prefixItems'];
// Unconstrained canonical node ({} or annotation-only): travels as JSON text,
// the same encoding used for untyped map values (value_json).
export const isUnconstrained = s => isObj(s) && !STRUCT.some(k => k in s);
export const JSON_TEXT_DESC = 'Return valid JSON encoded inside this string. Text values MUST include JSON quotation marks. Examples of the actual wire fields:\n' +
  '{"value":"\\"8 hours\\""}\n{"value":"42"}\n{"value":"true"}\n{"value":"null"}\n{"value":"[\\"portable\\",\\"waterproof\\"]"}\n\n' +
  'Plain text such as {"value":"8 hours"} is invalid for this encoding.';
export const JSON_TEXT_ARRAY_DESC = 'Each item must contain valid JSON text. Text options require embedded JSON quotation marks. Valid wire example: {"values":["\\"Earbuds\\"","\\"Wired headphones\\"","42","true"]}. Invalid example: {"values":["Earbuds","Wired headphones"]}.';
export const TYPED_VALUE_DESC = 'Return a typed value object. Strings go directly in value, without extra JSON quotation marks. Use kind string, number, boolean, null, array, or object; arrays contain typed values and objects contain key/value entries.';

const valueDefinition = (ref, descriptions) => {
  const branch = (kind, value) => ({ type: 'object', properties: { kind: { type: 'string', enum: [kind] }, value }, required: ['kind', 'value'], additionalProperties: false });
  return { description: [TYPED_VALUE_DESC, ...descriptions].join(' '), anyOf: [
    branch('string', { type: 'string' }), branch('number', { type: 'number' }),
    branch('boolean', { type: 'boolean' }), branch('null', { type: 'null' }),
    branch('array', { type: 'array', items: { $ref: ref } }),
    branch('object', { type: 'array', items: { type: 'object', properties: { key: { type: 'string' }, value: { $ref: ref } }, required: ['key', 'value'], additionalProperties: false } }),
  ] };
};

export function decodeTypedValue(v) {
  const fail = () => { throw new Error('wire decode: invalid typed value'); };
  if (!isObj(v) || Object.keys(v).length !== 2 || !Object.hasOwn(v, 'kind') || !Object.hasOwn(v, 'value')) return fail();
  const data = v.value;
  if (v.kind === 'string' && typeof data === 'string') return data;
  if (v.kind === 'number' && typeof data === 'number' && Number.isFinite(data)) return data;
  if (v.kind === 'boolean' && typeof data === 'boolean') return data;
  if (v.kind === 'null' && data === null) return null;
  if (v.kind === 'array' && Array.isArray(data)) return data.map(decodeTypedValue);
  if (v.kind === 'object' && Array.isArray(data)) {
    const out = {};
    for (const entry of data) {
      if (!isObj(entry) || Object.keys(entry).length !== 2 || typeof entry.key !== 'string' || !Object.hasOwn(entry, 'value') || Object.hasOwn(out, entry.key)) return fail();
      Object.defineProperty(out, entry.key, { value: decodeTypedValue(entry.value), enumerable: true, configurable: true, writable: true });
    }
    return out;
  }
  return fail();
}

function wire(s, root, ref, state) {
  if (!isObj(s)) return s;
  if (s.$ref) return { $ref: s.$ref };
  if (isUnconstrained(s)) {
    state.used = true;
    if (typeof s.description === 'string') state.descriptions.add(s.description);
    return { $ref: ref };
  }
  if (isMap(s)) {
    const typed = isObj(s.additionalProperties);
    const keySchema = { type: 'string' };
    if (isObj(s.propertyNames) && typeof s.propertyNames.pattern === 'string') keySchema.pattern = s.propertyNames.pattern;
    const entry = { type: 'object',
      properties: { key: keySchema, value: wire(typed ? s.additionalProperties : {}, root, ref, state) },
      required: ['key','value'], additionalProperties: false };
    const out = { type: types(s).includes('null') ? ['array','null'] : 'array', items: entry };
    if (s.description) out.description = s.description;
    return out;
  }
  const out = {};
  for (const [k, v] of Object.entries(s)) {
    if (DROP.has(k)) continue;
    if (k === 'format') { if (FORMATS.has(v)) out.format = v; continue; }
    if (k === 'const') { out.enum = [v]; continue; }
    if (k === 'oneOf' || k === 'anyOf') { out.anyOf = v.map(x => wire(x, root, ref, state)); continue; }
    if (k === 'allOf') { out.allOf = v.map(x => wire(x, root, ref, state)); continue; }
    if (k === 'items') {
      out.items = wire(v, root, ref, state);
      continue;
    }
    if (k === 'prefixItems') continue;
    if (k === '$defs') { out.$defs = Object.fromEntries(Object.entries(v).map(([n, d]) => [n, wire(d, root, ref, state)])); continue; }
    if (k === 'properties' || k === 'required' || k === 'additionalProperties') continue;
    out[k] = v;
  }
  if (isUnconstrained(s.items)) out.description = s.description ? `${s.description} Each item is a typed value. ${TYPED_VALUE_DESC}` : `Each item is a typed value. ${TYPED_VALUE_DESC}`;
  if (isObj(s.properties)) {
    const req = new Set(s.required || []);
    out.properties = {};
    for (const [name, p] of Object.entries(s.properties)) {
      const w = wire(p, root, ref, state);
      out.properties[name] = req.has(name) || acceptsNull(p, root) ? w : { anyOf: [w, { type: 'null' }] };
    }
    out.required = Object.keys(s.properties);
    out.additionalProperties = false;
    if (!out.type) out.type = 'object';
  }
  return out;
}
export const toWireSchema = schema => {
  let name = 'WireValue';
  while (Object.hasOwn(schema.$defs || {}, name)) name += '_';
  const ref = `#/$defs/${name}`, state = { used: false, descriptions: new Set() };
  const out = wire(schema, schema, ref, state);
  if (state.used) out.$defs = { ...out.$defs, [name]: valueDefinition(ref, state.descriptions) };
  return out;
};

function pickBranch(alts, data, root) {
  const rs = alts.map(a => resolve(a, root));
  const fits = r => {
    const t = types(r);
    if (data === null) return acceptsNull(r, root);
    if (Array.isArray(data)) return t.includes('array') || isMap(r);
    if (isObj(data)) {
      if (!isObj(r.properties)) return t.includes('object');
      const keys = Object.keys(r.properties);
      if (Object.keys(data).length !== keys.length || !keys.every(k => k in data)) return false;
      return keys.every(k => { const p = resolve(r.properties[k], root);
        // Strict wire schemas require optional fields too, using null as the
        // absence sentinel. Do not reject the right branch for that sentinel.
        if (data[k] === null && !(r.required || []).includes(k) && !acceptsNull(p, root)) return true;
        if (isObj(p) && 'const' in p) return data[k] === p.const;
        if (isObj(p) && Array.isArray(p.enum) && !acceptsNull(p, root)) return p.enum.includes(data[k]);
        return true; });
    }
    if (!t.length) return true;
    return t.includes(typeof data) || (typeof data === 'number' && t.includes('integer'));
  };
  return alts[rs.findIndex(fits)] ?? alts[0];
}

function decode(data, s, root) {
  s = resolve(s, root);
  if (isUnconstrained(s)) return decodeTypedValue(data);
  if (!isObj(s) || data === null) return data;
  const alts = s.anyOf || s.oneOf;
  if (Array.isArray(alts)) return decode(data, pickBranch(alts, data, root), root);
  if (isMap(s) && Array.isArray(data)) {
    const typed = isObj(s.additionalProperties); const out = {};
    for (const e of data) {
      if (!isObj(e) || typeof e.key !== 'string') throw new Error('map entry');
      if (Object.hasOwn(out, e.key)) throw new Error('wire decode: duplicate map key');
      Object.defineProperty(out, e.key, { value: typed ? decode(e.value, s.additionalProperties, root) : decodeTypedValue(e.value), enumerable: true, configurable: true, writable: true });
    }
    return out;
  }
  if (isObj(s.properties) && isObj(data)) {
    const req = new Set(s.required || []); const out = {};
    for (const [k, v] of Object.entries(data)) {
      const p = s.properties[k];
      if (p === undefined) { out[k] = v; continue; }
      if (v === null && !req.has(k) && !acceptsNull(p, root)) continue;
      out[k] = decode(v, p, root);
    }
    return out;
  }
  if (Array.isArray(data) && isObj(s.items)) return data.map(x => decode(x, s.items, root));
  return data;
}
export const fromWireOutput = (data, schema) => decode(data, schema, schema);
