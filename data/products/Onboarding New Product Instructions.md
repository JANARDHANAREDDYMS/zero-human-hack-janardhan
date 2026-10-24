# Onboarding a New Product

Customers do not need a finished product page, customer data, or competitor research.

## Minimum information

1. **What is the product?** A short description of what it does and the problem it solves. A link or specification sheet can substitute if it explains this.
2. **What do you want to learn?** For example: who might buy it, how it compares with alternatives, or whether the proposed price makes sense. “Help me explore demand” is acceptable.

## Optional — provide whatever you know

- **Price:** planned price or range, and whether it is per purchase or subscription. “Undecided” is fine.
- **Audience:** who you think would use it. “Unsure” is fine.
- **Market:** intended country or region; currency if known.
- **Features:** known capabilities, limitations, dimensions, or other specifications relevant to the product.
- **Selling point:** why someone might choose it. This can be a hypothesis.
- **Existing material:** product link, document, prototype feedback, or customer research.

## Example

> A compact wireless keyboard for working at shared desks. We are considering $60, but the audience is not finalized. Find competing options and explore which buyers might prefer it. Exact dimensions are not available yet.

## What the system does next

Save the supplied information in `brief.json`. Keep missing facts unknown and distinguish supplied specifications from hypotheses. If a missing detail would materially change the comparison, ask one focused follow-up; otherwise proceed with clearly labeled assumptions or exploratory scenarios.

Research alternatives and purchasing situations → define segments → define sampling rules → generate synthetic profiles → review the population → simulate comparisons.

These stages populate `evidence.json`, `segments.json`, `sampling-rules.json`, `customers.json`, and `population-review.md`. Start with a small reviewed population before scaling. Synthetic profiles are hypothetical customers, not actual respondents or validated demand forecasts.

**Implementation status:** This is the intended onboarding workflow. Automatic research and LLM segment proposals have not been implemented yet. A local sampler now constructs profiles from saved segment templates and sampling rules. The product schema will need to support incomplete briefs before customer intake.
