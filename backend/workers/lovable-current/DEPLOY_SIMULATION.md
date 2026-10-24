# Add the simulation stage to the existing Lovable worker

Apply the three supplied files to the matching existing customer-generation server directory:
- policy.json
- validators.generated.mjs
- validators.generated.d.mts

Additive stage: simulate_customer. It uses a small, closed customer-decision schema with ordinary text, arrays, and one nullable selected_offer_id. No open maps, JSON-text fields, recursive values, or new wire decoding rules.

Preserve the existing worker, wire compiler/decoder, route wrappers, secrets, model allowlist, authentication, diagnostics, limits, all existing routes and deployment-check endpoint. The existing handler selects stages from policy and validators; do not hard-code a replacement runtime. Preserve existing generation stage schemas and instructions. If the hosted version differs, report the difference rather than silently replacing it.

Run tests and typecheck, rebuild deployment metadata using the hosting project's existing build script, publish, and verify the authenticated model-free deployment check. Report the new build ID and that simulate_customer exists in policy and compiled validators. Do not send authenticated model requests automatically. Local offline tests do not prove gateway acceptance.

No new API key or secret is needed. Do not attach secrets to responses or logs.
