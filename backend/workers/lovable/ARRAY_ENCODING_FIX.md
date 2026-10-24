# Apply in the deployed Lovable project

The local worker predates the deployed strict-wire compiler. Do not replace the deployed worker with this older local copy.

1. Import `describeJSONTextArrays` from `wire-descriptions.mjs` and apply it to the compiler's derived strict wire schema immediately before sending `response_format`. It returns a copy and does not mutate canonical policy. It identifies JSON-text array items through their existing JSON-text description; ensure the compiler uses that phrase consistently.
2. Retain the existing item descriptions, wire decoder and canonical validation. Do not accept unquoted text or change canonical instruction/schema hashes.
3. Set `max_completion_tokens` to `Math.min(limits.max_tokens, 24000)` if supported by the gateway/model. Keep the existing total-token and timeout limits. Gateway acceptance of the higher ceiling remains unverified.
4. Test encoded choice lists with text, numbers, booleans, null, arrays and objects; reject plain unquoted text. Verify all stages still compile.
5. Publish and report the deployed version. Do not make an authenticated request automatically.

The local worker's output ceiling is updated to 24,000 and its tests cover the array-description helper. The helper must still be connected to the deployed compiler as described above. Sync the deployed source back into this repository before using it as the deployment source of truth.
