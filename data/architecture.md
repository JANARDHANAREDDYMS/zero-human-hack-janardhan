# Hackathon data architecture

Canonical structured preparation data lives in `data/` at the project root. `docs/` retains readable research, source snapshots, and historical context. The backend now implements local customer-generation stages and evaluation; full Exa-to-profiles live quality and the model-driven shopping simulator remain unverified or unbuilt. Frontend and business integrations are pending.

## Business flow
Whop order for our research service → client brief → Exa market evidence → category-specific segments → conditional sampling rules → reviewed synthetic customers → shopping/comparison simulation → targeted Terac feedback → rerun and deliver report. Lovable is intended for application creation and runtime AI, subject to sponsor-credit coverage.

For the hackathon, both integrations are important outcomes: **verify a genuine paid Whop order and fulfill the research service**, and **use Terac for a targeted human question prompted by simulation uncertainty**. Keep the paid order, human feedback, and synthetic choices as separate records. A simulation choice or unpaid/test checkout is not revenue. API integrations and these live proof points remain pending.

## Data layout
`schemas/` contains JSON Schema contracts for products, population preparation records, and customer profiles. `products/<id>/` contains exactly these six files:

| File | Purpose | Current status |
|---|---|---|
| brief.json | Product specifications, pricing, marketed feature, and tradeoffs | Filled for six concepts |
| evidence.json | Sources, competitors, sample medians, assumptions, and limitations | Initial source-linked research for all six; limitations retained |
| segments.json | Category-specific purchasing situations and rationale | Specified for all six |
| sampling-rules.json | Conditional variation, allocations, seed, and target counts | Specified for all six |
| customers.json | Reproducible population with stable IDs | 50 synthetic profiles per product; 300 total |
| population-review.md | Findings and consistency/coverage review | Structural review completed; human/market review pending |

Concepts: sony-speaker, codesensei, commuter-backpack, desk-lamp, resume-review, proofreading. Latest four-product specifications are proposals; Sony and CodeSensei preserve the original agreed briefs.

## Population process
Brief → surrounding-market evidence → segments → conditional distributions → sample 30–50 → review → scale toward 500. Category-specific needs and constraints take precedence over the early generic eight-score sketch. Draft schemas will be refined as segment rules are finalized.

Profiles remain artificial; hard-coded sampling assumptions are disclosed. Numeric medians use comparable units; deliberate negatives are exceptions, not medians. Competitor sources do not establish market shares. Preserve no-purchase and free/DIY alternatives. Do not expose designer labels such as negative or standout to simulated customers as behavioral instructions.

## Reproducibility and boundaries
Store seeds, population/rule versions, stable IDs, and provenance before generation. Keep journey state and run outcomes separate from profiles. Never claim simulation choices are real purchases, trained human models, or validated conversion forecasts. No runtime outputs have been created.

## Reference material
See ../docs/context/customer-population-process.md, ../docs/context/project-decisions.md, and ../docs/context/hackathon.md. The old ../docs/data/product.html and research JSON are retained reference snapshots; future canonical product edits belong in data/products/*/brief.json.

## Prepared inputs
See [population summary](population-summary.md), [simulation contract](simulation/contract.md), and [validation report](simulation/population-validation.json). data/tools contains the local deterministic sampler and validation utilities, not a runtime app or LLM-driven research pipeline. The contract uses a six-decision bound including the final choice.

## Backend structure
See [backend design](../backend/README.md) for the one-agent harness and current phase boundary. Run state belongs in data/runs/; the six demo datasets stay in data/products/. Whop payment verification and Terac human feedback are required demo milestones after the narrow simulation loop works.

## Mandatory event integration update

The [official guidebook reading](../docs/context/hackathon-guidebook-2026-10-24.md) requires Terac MCP, human input collected during the event and a measurable improvement, plus a company built on Whop with all payments through Whop. No Stripe setup for this event. Real revenue must be organic, not test/simulated transactions. These are organizer requirements, not inferred recommendations.
