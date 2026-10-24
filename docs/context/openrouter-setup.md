# Direct OpenRouter model access

The local pipeline can call OpenRouter directly without the Lovable worker.

**Current preference:** Lovable remains active (`MODEL_BACKEND=bridge`). OpenRouter credentials and adapter are prepared but inactive. No automatic provider switching is enabled.

To explicitly enable OpenRouter later, configure:

```dotenv
MODEL_BACKEND=openrouter
OPENROUTER_MODEL=openai/gpt-6-luna
OPENROUTER_API_KEY=<your private key, already configured locally>
```

Do not copy the actual key into this document or frontend code.

The selected model was verified against OpenRouter's public catalog on October 24, 2026. The catalog lists GPT-6 Luna, not GPT-6.1 Luna. The key was accepted by the read-only `/api/v1/key` endpoint. No inference request was made.

Restart the local server to load the provider change:

```sh
python3 backend/scripts/run_demo.py
```

Generation, customer simulation, report writing and concern extraction use the selected provider. Exa, Whop and Terac remain separate services. `run_simulation.py` uses the same environment selection. The local server is still localhost-only; this change does not deploy or expose it publicly.

The adapter sends the existing instruction bundle and canonical JSON Schema to OpenRouter with `strict:false`, then enforces the unchanged canonical schema locally. This avoids the Lovable wire encoding entirely. Repository schema references are bundled locally; remote schema URLs are not fetched. Provider parameter support is required; provider fallback and automatic retries are disabled. Invalid JSON, incomplete replies, refusals and schema violations are rejected. Tokens and provider-reported cost are recorded; unavailable cost remains explicitly uncertain. Per-call cost is checked by the existing harness after usage is returned; it is not a hard pre-billing cap. Configure a key spending limit in OpenRouter when a hard account-level cap is required.

Existing completed responses remain reusable with the existing resume contracts; a new provider applies only to additional calls. A mixed-provider recovery is not an all-OpenRouter experiment. Preserve the original model metadata when reviewing results.

To switch back, set `MODEL_BACKEND=bridge` and restart. The original worker URL, token and model configuration have not been removed.

Verification: mocked adapter tests, all repository schemas bundled and checked locally, full backend suite. Live schema acceptance, output quality, latency and billing remain unverified until an explicitly authorized model call.
