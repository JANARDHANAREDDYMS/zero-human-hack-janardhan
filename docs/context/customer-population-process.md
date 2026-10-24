# Customer population preparation

Source: recovered older hosted chat, especially turns 01a16b98-3e18-7589-8436-3d31bad8360e and 01a16b86-0141-76b6-a3bc-191a1369f4b5. These later decisions refine the earlier generic five-archetype/eight-score sketch.

## Reusable process
Client brief → surrounding-market evidence → purchasing situations → segment specification → conditional sampling rules → reproducible profiles → population review → simulation.

Tonight the assistant and user can design the briefs, evidence interpretation, segments, and rules in chat; code can sample profiles without purchasing a model API. The future automated service may use model calls for extraction and segment proposals, with code constructing and validating populations.

## Intake
Accept descriptions/specifications/uploads as well as URLs. Capture product, intended audience (including unsure), problem, market/country/language/currency, price and billing period, differentiator, research question, and optional client evidence. Separate supplied specifications, client hypotheses, external findings, and assumptions.

For unreleased products, research competitors, substitutes, reviews of alternatives, and discussions of the problem. There cannot be reviews of a product that has not launched. Preserve source links and unknowns. Review frequency does not establish market proportions.

## Customer fields
- customer_id: stable identity.
- segment_id: primary purchasing situation.
- market: geography, language, currency.
- goal and purchase_trigger: desired outcome and why now.
- current_solution: existing product, free alternative, or doing nothing.
- budget: comfortable and maximum spend with billing period.
- urgency: deadline/time horizon.
- requirements: category-specific hard and flexible constraints.
- tradeoffs: priorities and acceptable compromises.
- decision_style: research effort, evidence needs, familiarity.
- switching_barriers: cost and inconvenience of changing.

Store provenance in linked records. Keep immutable profile needs separate from changing journey state (information seen, actions, shortlist, final decision).

## Segments and variation
Segments vary by category and purchasing situation; do not force every product into bargain hunter/researcher/impulse/premium archetypes. Decision traits can overlap across segments.

Sample conditionally: segment → situation → related constraints and preferences → decision behavior. Do not independently randomize every attribute or ask a model for 500 unrelated biographies. One agent implementation uses many separate profiles and journey states.

Without credible audience proportions, equal counts per segment provide coverage. Five segments × 100 is an example, not a mandatory structure or 20% market-share claim. Show segment-level outcomes and test different weightings before presenting an aggregate.

## Review and reproducibility
Start with 30–50 profiles, inspect and fix rules, then scale to 500. Check contradictions, duplicates, meaningful within-segment diversity, missing situations, budget/requirement consistency, and traceable assumptions. Generate needs independently of the desired winner, then freeze profiles before comparing offers.

Preserve population version, schema version, seed, rule version, source references, and stable IDs. A seed reproduces sampled profiles; it does not guarantee identical LLM decisions.

## Simulation contract to finalize
Define initial visible information, explicit actions, returned evidence, step limit, and required output. An earlier proposal used approximately five steps; this is not finalized. Actions include inspect, compare, view an available sample, choose an offer, keep current solution, or decline. Missing information stays unknown.

Save action traces and short explanations linked to observed evidence. Reuse the same profiles and competitors for variants. Test product-order sensitivity, repeated runs, missing required features, price changes, and the ability to reject every offer.

## Honest demo interpretation
Synthetic choices rank hypotheses under assumptions; they are not calibrated conversion forecasts. A few Terac responses can challenge particular assumptions without validating the entire population. Artificial profiles and hard-coded rules are acceptable disclosed demo inputs; hard-coding a winning outcome is not useful evidence.
