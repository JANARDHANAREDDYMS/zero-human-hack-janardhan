// Apply to the derived strict wire schema, never to canonical policy.json.
export const JSON_TEXT_ARRAY_DESCRIPTION = 'Each item must contain valid JSON text. Text options need embedded JSON quotation marks. Example: {"values":["\\"Earbuds\\"","\\"Wired headphones\\"","42","true"]}. Plain options such as {"values":["Earbuds"]} are invalid.';

export function describeJSONTextArrays(schema) {
  if (!schema || typeof schema !== 'object') return schema;
  if (Array.isArray(schema)) return schema.map(describeJSONTextArrays);
  const result = Object.fromEntries(Object.entries(schema).map(([key, value]) => [key, describeJSONTextArrays(value)]));
  // The wire compiler marks JSON-text string items through their description.
  if (result.type === 'array' && result.items?.type === 'string' && /JSON text/i.test(result.items.description || '')) {
    result.description = [result.description, JSON_TEXT_ARRAY_DESCRIPTION].filter(Boolean).join('\n');
  }
  return result;
}
