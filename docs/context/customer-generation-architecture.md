# Customer generation architecture decision

## Decision

One agent operating through a Python harness with staged model calls, Exa research, deterministic sampling, schema validation, and saved run state. Fifty profiles per product is the configurable initial target. Segment count and category attributes are dynamic.

Lovable's in-app AI connector is the intended model provider. No separately purchased OpenAI/Anthropic account is required by this design. Official documentation: https://docs.lovable.dev/features/ai

## Execution boundary

Python owns the workflow, prompt versions, schemas, Exa retrieval, sampling, validation, and run files. Model access is an injected adapter, not embedded throughout the pipeline.

Intended live model path:

Python stage request → authenticated project backend function → Lovable built-in AI → structured response → Python validation.

The project backend function must be created and its accessibility to the Python process verified. The documentation establishes secure in-app backend calls; it does not by itself establish that this Python process can use the user's sponsor allocation or directly reuse a project key. Do not assume either. Keep the project key in the backend; the function must authenticate callers and restrict request size, stage/model choices, and usage. It must not be an unrestricted public model proxy.

A workspace key for Lovable's app-building API is not the same as the project's managed AI credential. Lovable's build agent is not our running customer-generation agent.

## Workflow

1. Intake: model extracts product facts, audience hypotheses, research goal, and unknowns from minimal input.
2. Research: code executes bounded Exa queries and preserves sources; model organizes supported findings and purchasing situations.
3. Population specification: model proposes segments, category fields, distributions, dependencies, and evidence references using a restricted rule vocabulary.
4. Pilot: code validates the specification and samples a small population with a saved seed.
5. Review: a separate focused call to the same model checks coverage, unsupported assumptions, contradictions, and product favoritism.
6. Completion: allow one correction cycle; code revalidates and generates the requested population, saving all artifacts. Unresolved failures leave an explicit incomplete status.

Code controls progression and call/search/token limits. Model judgments cannot bypass validation. Evidence and profile assumptions remain distinguishable. Population generation never preassigns buying choices or launch recommendations.

## State and storage

Use data/runs/<run-id>/ for inputs, stage outputs, research, rule proposals, pilot, review, final customers, validation, prompt/model versions, and usage/failures. Preserve data/products/ as the six existing demo examples. No database or separate memory service is needed initially.

## What can be built before credits arrive

Implement schemas, rule interpreter, sampling, source-reference checks, staged harness, prompts, storage, and provider interfaces. Use explicitly labeled offline fixtures to test control flow and validation. Offline fixture success does not prove model quality or live integration. Do not silently switch providers or incur paid model usage.

## Live activation check

When credits arrive, verify sponsor runtime eligibility and the backend-function route, run one small generation, inspect returned structure and content, and measure usage. Start with one category and a small pilot. Choose the actual model from the workspace's available models after checking quality and cost; do not hard-code an unverified model.

The first category-generalization acceptance case is a new keyboard brief, without adding keyboard-specific sampling code. Run ten shopping journeys only after generation works; those belong to the later simulation component.

## Deferred

Whop and Stripe payment integration, Terac human requests, frontend implementation, and shopping-journey simulation are outside this implementation phase.

## Current uncertainty

The built-in connector can run models without a separate provider account, and runtime consumes credits. The user's actual sponsor allocation and authenticated backend deployment have not been inspected. Therefore model access is an intended architecture boundary, not an already working connection.
