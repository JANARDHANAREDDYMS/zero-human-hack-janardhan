# Add review-concern generation only

Apply policy.json, validators.generated.mjs and validators.generated.d.mts to the matching existing customer-generation server directory.

One additive stage: extract_review_concerns. All ten existing stage schemas/instruction bundles must remain unchanged. Preserve runtime, existing routes, secrets, model allowlist, authentication, gateway limits, strict wire compiler/decoder, error handling, usage and generation/simulation behavior. Do not add any Terac API/MCP client, expert hiring, messaging, payment or study-launch behavior.

The new schema uses closed required objects and ordinary arrays/scalars. It returns at most ten distinct concern candidates, each with explanation, why human review may help, suggested expertise, a review question, proposed test, success criterion, uncertainty and exact source-objection IDs. It may return fewer, including none, rather than fabricate concerns. Python calculates affected customer/segment counts and ranking from saved non-choosing customers only.

Build/test/typecheck using the existing project workflow. Refresh deployment metadata with a version including review-concerns-v1, publish, and verify via authenticated model-free deployment check. Report the exact live version/build ID and that extract_review_concerns is present in policy and validator exports. Do not send model requests automatically. No secrets are added or changed.
