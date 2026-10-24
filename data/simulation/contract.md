# Shopping simulation contract v1.0

This defines tomorrow's implementation. There is no live model-driven simulator yet. Prepared populations are synthetic demo inputs, not forecasts.

The implementation decisions and acceptance gates in [simulation-design.md](simulation-design.md) extend this contract. The existing JSON schemas and pilot offer sets remain v1.0 fixtures until the v2 customer adapter and runtime are built; passing their structural checks does not mean the runtime exists.

## Run input
A run supplies run_id, product_id, population_version, customer profile, variant_id, offer snapshots, and the profile-specific current solution. Use the reviewed population and the same offer set across compared variants. Store the seed separately from model settings: a sampling seed cannot reproduce a remote model response.

Each offer has a stable offer_id, name, short neutral description, price (amount, currency, billing period; null when unknown), price terms (mandatory upfront charge and scope), and grouped facts. Every fact has fact_id, attribute, value, unit, source_id, and evidence_status (provided_concept, provider_claim, assumed, unknown). Use the same attribute names across offers. Provider claims are not independently tested facts. Unknown is never false, zero, or missing-as-a-disadvantage.

Only real, observed competitor data and disclosed hypothetical client specifications may be supplied. Do not show the model internal labels such as standout, deliberate negative, intended winner, segment weights, or launch recommendation. Never invent samples, reviews, inventory, or guarantees. Global references such as current price do not imply delivery availability.

## Initial observation
Customer sees their goal, purchasing situation, constraints, existing solution, and a consistently formatted card for every offer: ID, name, neutral category description, headline price with billing period and any mandatory upfront commitment. Detailed features are hidden until inspected. Free/DIY alternatives and keeping the current solution or buying nothing are explicit choices. Profile provenance is retained for audit but designer comments are not behavioral instructions.

Randomize offer order with a saved presentation seed; reuse or counterbalance it when comparing variants. Reveal the same amount of information for client and competitors. No real checkout or product use occurs.

## Actions and step limit
Maximum six model decisions including the terminal decision. On decisions 1–5 allow:

| Action | Arguments | Returned observation |
|---|---|---|
| inspect_offer | offer_id, section: features / pricing / evidence / terms | Facts in that section, with IDs and their qualification |
| compare_offers | two or three offer_ids, one to four attribute names | Only facts already seen; unknown or not-yet-inspected entries stay unknown; no ranked winner supplied |
| view_sample | offer_id | Only an actual saved sample if available; otherwise sample_unavailable; promised free preview is not a fabricated sample |
| decide | choice, offer_id or null | Terminal structured decision |

On decision six, only decide is allowed. Choice: select_offer, keep_current, decline, or insufficient_information. Selecting a named free alternative is select_offer. A step-limit result may be insufficient_information; do not force a purchase.

Each profile's evaluation-time budget limits inspection/compare actions as an additional declared constraint, not wall-clock API latency. An unavailable action consumes a step and returns a structured error. Invalid model JSON gets one schema-repair attempt against the same observation; a second failure ends as model_error, never a fabricated customer choice. Provider/API failure is infrastructure_error. Both error types are excluded from completed-choice denominators and reported separately.

## Enforcement
Code owns immutable profile constraints, available actions, observations, and traces. A known hard requirement violation blocks a selection; unknown facts permit insufficient_information or a selection that names unresolved uncertainty, according to the customer's evidence needs. A model cannot change the profile or competitor facts.

For affordability, compare a complete required purchase scope: product plus chosen add-ons; documents needed at per-document rates; or full upfront subscription commitment. No prorating a yearly plan into a fictitious monthly purchase. Apply both recurring and upfront ceilings where present; do not invent tax/shipping or renewal terms. Mark unknown charges unresolved. If the target is infeasible, alternatives and declining remain valid.

Hardware concepts are hypothetical offers: selecting one is a simulated preference, not an executable order. Unverified battery-life claims are not guaranteed real-world endurance; IP ratings and lumen claims require their source qualification. Evidence-requiring profiles may remain undecided. No usage, hearing tests, placement usability, or post-purchase satisfaction is inferred.

## Saved output
Persist input/version hashes, model/provider/settings, presentation order, timestamps, action history, observations actually shown, validation failures, call count/cost if available, and the terminal result. See result.schema.json. Use short explanations tied to seen fact IDs and the customer's constraints, not hidden reasoning transcripts. Distinguish stated customer explanation from established causal evidence.

Output reports per-segment counts and choices including alternatives and none, unresolved information, and uncertainty. Equal ten-per-segment coverage is not a market-share weighting. Fifty synthetic choices are not fifty observations of real demand. A launch/no-launch suggestion is a hypothesis under the declared assumptions; no predetermined failure or success is embedded.

## First implementation and checks tomorrow
1. One Sony journey using reviewed inputs; no payment integration required inside the simulated purchase.
2. Ten customers via Lovable runtime, measuring failures, duration, and cost before scaling.
3. Inspect fact citations, enforce budget/requirements, allow none, shuffle order, and rerun the same profiles for variants.
4. Add improvement comparisons, targeted Terac human input, and Whop payment-to-report fulfillment once the basic journey works.

Contract is shared across six categories; category-specific requirements live in profiles and offer facts. Keep source facts and client variants immutable within a run.
