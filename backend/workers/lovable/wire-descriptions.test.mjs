import test from 'node:test';
import assert from 'node:assert/strict';
import {describeJSONTextArrays} from './wire-descriptions.mjs';

test('JSON-text array guidance preserves schema and describes encoded list values', () => {
  const schema = {type:'object',properties:{values:{type:'array',items:{type:'string',description:'Return valid JSON text'}}}};
  const updated = describeJSONTextArrays(schema);
  assert.equal(schema.properties.values.description, undefined);
  assert.match(updated.properties.values.description, /Earbuds/);
  assert.deepEqual(updated.properties.values.items, schema.properties.values.items);
});

test('encoded choice options round trip without coercion', () => {
  const values = ['Earbuds',42,true,null,['portable'],{hours:8}];
  assert.deepEqual(values.map(JSON.stringify).map(value => JSON.parse(value)),values);
  assert.throws(() => JSON.parse('Earbuds'));
});

test('ordinary string lists receive no encoding instructions', () => {
  const schema = {type:'array',items:{type:'string'}};
  assert.deepEqual(describeJSONTextArrays(schema),schema);
});
