# Research and customer generation backend

## Architecture

One agent, multiple focused reasoning stages, one harness controlling progression. Python is the initial implementation language to reuse the existing deterministic sampler. Lovable in-app AI is the intended model-access provider through an authenticated project backend function, with eligibility and connectivity verified when credits arrive. No web framework, agent framework, or provider SDK is selected yet. See [architecture decision](../docs/context/customer-generation-architecture.md).

The workflow is:

1. Interpret a minimal brief: preserve supplied facts, hypotheses, and unknowns.
2. Retrieve competitors and purchasing evidence with Exa; preserve source IDs and retrieval context.
3. Propose category-specific segments, attributes, distributions, and conditional rules.
4. Validate the specification in code, then construct a small pilot.
5. Review coverage, contradictions, source support, and product bias with the same model in a separate bounded call.
6. Permit one validated correction attempt, regenerate if needed, validate the full population, and save the review.

Fifty customers is the current demo target, configurable per run. Neither the number of segments nor the category attributes may be fixed to the six examples.

## Modules

Phases 1–2 implement sampling, validation, the harness, saved state/storage, usage limits, one correction cycle, and an offline CLI. Research/model adapter code and stage prompts are now implemented; deployment and actual model evaluation remain pending. See the [HTML implementation guide and diagram](../docs/context/implementation-and-instructions.html).

| Module | Responsibility |
|---|---|
| `pipeline.py` | Stage order, validation gates, one correction limit, and explicit failure states |
| `state.py` | Typed run state, immutable inputs, stage results, and unresolved questions |
| `storage.py` | Save artifacts under `data/runs/<run-id>/`; leave demo datasets unchanged |
| `sampling.py` | Adapt the existing sampler to a restricted category-independent rule specification |
| `validation.py` | Structural checks, cross-field constraints, source references, diversity, and counts |
| `tools/exa.py` | Research adapter; return source records rather than untraceable text |
| `tools/llm.py` | Model interface injected into stages; provider/runtime configuration comes later |
| `prompts/` | Versioned methodology and five stage instruction bundles |

Prefer plain functions and typed records before a general agent framework. Expose only tools needed for a stage. The model must not execute arbitrary generated code, edit evidence, bypass validation, or assign customer buying outcomes during generation.

## Existing limitations to resolve

The saved six-category templates remain manually authored and use the original local sampler. The new v2 sampler is category-independent and passed a hand-authored keyboard fixture. Automatic research/proposal adapters are implemented, but their output quality on a new category remains unevaluated until live access is configured.

Phase 1 adds a validated rule language for ranges, options, dependencies, units, and provenance, plus a minimal intake contract allowing unknowns. Reuse canonical schemas in `data/schemas/`; do not maintain a second divergent set in the backend.

## Storage boundary

`data/products/` is the versioned demo input library. `data/runs/` holds run-specific inputs, research, proposals, pilots, final profiles, validation, failures, and usage records. Files are sufficient initially; no vector memory service or database is required for this phase. Pass explicit relevant state to each model call instead of continually appending an unbounded conversation.

## Later phases

Shopping journeys, Terac human requests, Whop or Stripe payments, and frontend integration come later. They should consume this component's outputs, not be required to generate a population. Do not add provider credentials or SDK dependencies for those phases now.

Phase 4 adds raw-text intake, instruction-bundle version/hash binding in bridge contract 1.1, and seven-category qualitative reviews. 111 tests pass; these verify software behavior, not real model quality.


### Segmentation quality revision

Research now plans three tracks: offers, buyer situations and counterevidence. New findings may use `observed_report` for unverified buyer reports, with source IDs, and a `track`. Live proposals require a six-part `situation`; each valid candidate saves `segmentation-quality-N.json` and supplies it to the reviewer. Missing buyer support remains provisional and cannot receive a live evidence-support pass. Diagnostics do not establish representativeness or verify source interpretation.

The manually researched Sony candidate is in `data/products/sony-speaker/research-v2/`; its review explains limitations and constructed-sample statistics. Original v1.1 data and simulation fixtures remain intact. Instruction bundle version is now `segmentation-1.1`; bridge envelope remains 1.1. Actual live model quality remains unevaluated; Phase 5 local evaluation tooling is now implemented.


### Phase 5: local evaluation implemented; live execution pending

`evaluation.py` evaluates saved runs through the `evaluate-run` CLI: terminal status, usage reconciliation, configured limits, timings, deterministic replay, research/segment diagnostics, and accepted review references. It creates an optional human audit template bound to the customer hash. All seven human categories start as not evaluated; a model review cannot complete them. Existing outputs are never overwritten.

See [evaluation procedure and rubric](../data/evaluations/README.md). An unseen USB-C hub intake is prepared for eventual live evaluation. A new 50-profile keyboard fixture run and evaluation report demonstrate local readiness only. The user selected local preparation because credentials and the deployed bridge are not available. No live API calls were made for Phase 5.


### Local Codex model bridge

Use `run-live --model-backend codex` to replace the undeployed Lovable function with local Codex CLI calls. This uses existing CLI authentication and the same stage/sampling/review contracts. See [setup and usage limits](src/customer_generation/tools/CODEX_BRIDGE.md). Full research still needs EXA_API_KEY. Codex token usage is recorded, but subscription dollar cost stays unknown; the known-dollar allowance cannot cap it. The original HTTP bridge remains available.


### Live keys and Lovable worker preparation

Private `.env` files are ready (never commit them). Use the CLI's global `--env-file backend/.env` option or the two-product runner, which defaults to plan-only. See `data/evaluations/FIRST_LIVE_SMOKE.md`. `backend/workers/lovable/` contains a tested authenticated worker, exported canonical prompt/schema policy, server secret names, deployment prompt and archive. It is not deployed; selected-model compatibility and runtime credits remain unverified. There are 111 Python tests and 10 mocked Node worker tests.
