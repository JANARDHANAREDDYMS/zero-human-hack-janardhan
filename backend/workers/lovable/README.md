# Lovable customer-generation worker

This folder contains the local server-side implementation for the Python bridge contract. A corresponding private server route is deployed in the Lovable project at `https://budget-model-beacon.lovable.app/api/public/customer-generation`. An authenticated `intake_extract` smoke test succeeded on October 24, 2026 using `openai/gpt-6-luna`; see `data/evaluations/first-lovable-intake.json`. This verifies the live route, authentication, gateway request, intake wire-schema handling, canonical validation and result persistence. It does not verify the larger `propose`/`correct` schemas, full profile generation, or the actual credit charge.

The intended path is:

`Python harness → authenticated project function → Lovable AI gateway → JSON response → Python semantic checks`

Lovable's built-in AI connector generates a project-managed LOVABLE_API_KEY and keeps model calls server-side. A workspace API key is different. Verify that the hackathon grant covers runtime AI gateway usage before the first paid run; sponsor eligibility is not established by this code.

## Files

- `worker.mjs`: authenticated handler with canonical policy checks, a model allowlist, JSON/schema validation, bounded request/response bodies, one gateway request, timeout, sanitized errors and usage reporting.
- `index.ts`: Deno edge-function entry. Adapt its hosting wrapper if your Lovable project uses another server runtime; retain the handler and contract.
- `policy.json`: generated instructions plus output schemas. Rebuild with `python3 backend/scripts/export_worker_policy.py` whenever prompts/schemas change, and redeploy the function.
- `deno.json`: pinned npm import mappings for Deno.
- `package.json`/lock: pinned dependencies for Node-based local tests.
- `.env.example`: server secret names. Actual `.env` is private and ignored.
- `DEPLOY_IN_LOVABLE.md`: prompt to use in your Lovable project with these files.

## Configure in Lovable

1. Enable the built-in backend and AI connector in the intended project. Lovable provisions LOVABLE_API_KEY; keep it in project secrets. Do not use a workspace API key as a replacement or put this key in Python/frontend configuration.
2. Privately copy WORKER_SHARED_TOKEN from this folder's local `.env` into the same named project secret. It already matches backend/.env MODEL_BRIDGE_TOKEN. Set ALLOWED_MODEL_IDS to one or more exact gateway IDs actually enabled for the workspace; use the same selected ID as local MODEL_ID. No model is hard-coded or silently substituted.
3. Deploy the function as `customer-generation` using the prompt and attached files. If Supabase platform JWT verification is enabled, configure this function to use its own bearer-token validation (`verify_jwt=false` for this one function); otherwise the private opaque token will be rejected before our handler. **The handler's own token authentication remains mandatory.** Do not expose the endpoint as an unauthenticated frontend model proxy.
4. Copy the function's HTTPS URL to backend/.env MODEL_BRIDGE_URL. Set MODEL_BACKEND=bridge and MODEL_ID to the allowed exact model ID.
5. Check runtime AI credits in the project dashboard. The small intake request has passed; the next boundary is the two-product smoke runner. The deployed route uses strict JSON Schema output and `max_completion_tokens`. Check Lovable's AI activity for the actual credit charge because the bridge deliberately reports that dollar cost as unavailable.

## Local checks

```sh
npm ci --ignore-scripts --prefix backend/workers/lovable
npm test --prefix backend/workers/lovable
python3 backend/scripts/export_worker_policy.py
```

After deployment, one small authenticated model-only test can run without an Exa key:

```sh
PYTHONPATH=backend/src python3 -m customer_generation --env-file backend/.env bridge-smoke \
  --output data/evaluations/first-lovable-intake.json
```

Tests mock fetch; they never spend Lovable credits. They verify authentication, immutable instructions/schema, model allowlist, output schema, usage accounting, invalid output, credit/rate errors and timeout behavior. The separate live intake smoke reported 1,285 input and 189 output tokens. The local worker source does not yet contain every strict-schema conversion made in the deployed Lovable project, so sync the deployed source before treating this folder as a byte-for-byte deployment record.

## Limits and reporting

Each request is at most 1 MB. Upstream response is at most 2 MB. The local function caps requested output at 24,000 completion tokens and timeout at 100 seconds, with no retries. Gateway support for that higher ceiling is not yet verified. See `ARRAY_ENCODING_FIX.md` for applying the JSON-text array descriptions to the deployed strict-wire compiler. Input/output totals are checked afterward by Python; timeouts may still consume gateway credits. max_cost_usd cannot be converted reliably to runtime credits, so it is not a hard Lovable spend cap. Use the platform's actual balance/usage limits as well.

The current response explicitly returns `cost_usd:null,cost_basis:unavailable`. Python preserves reported tokens, records only known dollar subtotals and marks cost_uncertain. It does not equate unknown cost to free usage. Contract 1.1 accepts this explicit unknown-cost extension; numeric-cost bridge responses remain compatible. Failed calls can have unreported usage, which remains uncertain and needs checking in Lovable's dashboard. No raw model payloads or keys are logged by this handler; platform AI logging has its own settings.

The allowlist and token are suitable for our private demo client. Global quotas, multi-tenant authorization, distributed rate limiting and durable job processing are not implemented. This is a bounded synchronous model worker, not a queue or autonomous agent service.

The gateway request uses `redirect: "manual"` because Lovable's published server runtime does not accept `redirect: "error"`. Any 3xx response is rejected as a gateway failure and is never followed, so credentials are not forwarded to a redirected destination.

## Sources verified for this setup

- [Lovable AI features](https://docs.lovable.dev/features/ai): project-managed key, server-side calls, enabled models and runtime credit usage.
- [Lovable edge functions](https://docs.lovable.dev/features/edge-functions): create/deploy via project chat, copy endpoint and inspect logs.
- [TanStack Lovable adapter](https://tanstack.com/ai/latest/docs/adapters/lovable): gateway base URL, Chat Completions option, project-key headers and 402/429 behavior. This is adapter-maintainer documentation, not a guarantee for every Lovable workspace/model.
- [Supabase function authentication](https://supabase.com/docs/guides/functions/auth): platform verification versus custom function authentication.
