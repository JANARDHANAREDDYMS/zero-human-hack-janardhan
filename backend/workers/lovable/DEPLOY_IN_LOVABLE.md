# Paste into the intended Lovable project

Attach the deployment archive or the files in this folder (excluding .env and node_modules), then use this prompt:

Build a private server-side AI worker for my customer-research application using this project's built-in Lovable AI connector and runtime credits. Use the attached customer-generation worker files as the implementation. I do not need a frontend or database changes for this step.

Enable the project's backend/AI connector as needed. Deploy a function named customer-generation. Preserve worker.mjs, policy.json and their authenticated bridge contract; index.ts/deno.json are the Deno hosting entry. Adapt only the runtime wrapper if the project's hosting requires it. Confirm the gateway path and supported JSON/output-limit parameters against this project's generated AI integration; preserve non-streaming JSON responses and do not add provider fallback.

Keep the project-generated LOVABLE_API_KEY server-side. I will set WORKER_SHARED_TOKEN privately in project secrets and ALLOWED_MODEL_IDS to exact IDs available in the workspace. Do not ask me to paste secrets into this chat, print secret values, or put them in frontend code. My local Python client uses the matching MODEL_BRIDGE_TOKEN. If platform JWT verification would reject that opaque bearer token before the handler runs, configure this function to use its own mandatory token validation; do not remove authentication.

Accept only POST bridge contract 1.1. Enforce the attached stage instructions and output-schema allowlist, including exact instruction version/hash/text. Call only an allowed model through the project's AI gateway. Preserve size/output/timeout caps, no retries, schema validation, reported token usage and sanitized error handling. Never invent a dollar cost: return cost_usd:null and cost_basis:unavailable unless the gateway provides an independently supported cost-reporting implementation.

Use a model enabled for this workspace. Tell me its exact gateway model ID and the function's HTTPS endpoint, whether runtime AI is enabled, and where to inspect usage/remaining credits. Do not assert that my hackathon credits cover AI gateway usage until that is verified in this workspace. Deploy the code, then verify unauthorized requests are rejected without calling a model. Authenticated model tests will be initiated by my Python client after I fill the environment settings; do not make those calls during deployment. Leave profiles, products, Whop, Stripe and Terac integrations unchanged.
