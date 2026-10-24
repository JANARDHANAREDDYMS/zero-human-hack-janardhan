# Deploy concept-interest simulation and conversational report stages

Apply the supplied policy.json, validators.generated.mjs and validators.generated.d.mts to the matching existing customer-generation server directory.

Two additive stages:
- simulate_concept: concept preference under explicit scenario assumptions, conversational customer_story and separate purchase_checks.
- summarize_simulation: evidence-linked overview, complete tested-segment summaries and proposed improvements.

All eight previous stages (including simulate_customer) must remain byte-for-byte equivalent in policy. Existing generation behavior, routes, secrets, runtime integration, model allowlist, authentication, usage reporting, strict wire compiler/decoder, limits and diagnostics must remain unchanged. The handler already selects stages dynamically from policy/validators. Do not substitute a new worker, use a generic untyped schema, disable validation, or add JSON-text parsing.

Each new schema uses closed required objects and ordinary scalar fields/arrays. No new maps, recursion or decoder repairs are needed. Keep the existing global 24,000-token output cap; Python requests 5,000 per new call. Keep gateway JSON schema strict mode and canonical validation.

Run project tests/typecheck, ensure both stages are exported by precompiled validators and available in policy, then rebuild deployment metadata with the existing script. Use a deployment version identifying concept-interest-v2 and conversational-report-v1. Publish, verify the authenticated model-free deployment check, and report the exact live build ID/version. Do not send model requests automatically.

Local tests include full five-customer concept + report envelopes through the actual Python client and actual worker/compiler/decoder/validator, both product and professional-service examples, reference validation, schema checks, authentication and policy mismatch. They do not prove live model reasoning quality or gateway acceptance.

No new secrets, accounts or services are needed.
