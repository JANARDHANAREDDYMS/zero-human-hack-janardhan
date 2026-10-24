# Prepared demo populations

**Status:** 300 synthetic profiles prepared: 50 per product, five purchasing situations per product, ten profiles per situation. Equal coverage is not a market-share estimate.

Start with [the simulation contract](simulation/contract.md) and [Sony input example](simulation/sony-example-request.json). The runtime simulator and automatic evidence/segment proposal stages are not implemented.

| Product | Profiles | Segments | Review |
|---|---:|---|---|
| [codesensei](products/codesensei/customers.json) | 50 | Candidates with scheduled coding interviews, Students preparing over a semester, Career switchers with limited study time, Candidates seeking interview conversation practice, Existing subscribers evaluating another tool | [Review](products/codesensei/population-review.md) |
| [commuter-backpack](products/commuter-backpack/customers.json) | 50 | Public-transit commuters, Workers moving among desks, Students combining campus and part-time work, Occasional short-trip workers, Owners considering a work-bag upgrade | [Review](products/commuter-backpack/population-review.md) |
| [desk-lamp](products/desk-lamp/customers.json) | 50 | Students at compact study desks, Home-office task workers, Evening readers, People moving between small work areas, Hobbyists doing detailed desk work | [Review](products/desk-lamp/population-review.md) |
| [proofreading](products/proofreading/customers.json) | 50 | Occasional personal-document writers, Students with a writing deadline, Freelancers preparing client documents, People editing recurring work documents, Authors seeking understandable editorial changes | [Review](products/proofreading/population-review.md) |
| [resume-review](products/resume-review/customers.json) | 50 | Students applying for first professional roles, Active applicants tailoring multiple applications, Career changers reframing experience, Experienced candidates considering a small number of roles, DIY applicants checking whether payment adds value | [Review](products/resume-review/population-review.md) |
| [sony-speaker](products/sony-speaker/customers.json) | 50 | Small-bag weekend listeners, Patio and small-group hosts, Home and shared-space listeners, Practical gift buyers, Owners considering replacement | [Review](products/sony-speaker/population-review.md) |

## Sony examples

| Customer | Situation | Budget ceiling | Current solution |
|---|---|---|---|
| sony-speaker-001 | portable-weekend | $108 | Phone speaker |
| sony-speaker-011 | garden-gatherings | $90 | Phone speaker |
| sony-speaker-021 | home-desk | $115 | Working portable speaker |
| sony-speaker-031 | gift-buyers | $164 | Recipient already has a speaker |
| sony-speaker-041 | replace-or-retain | $172 | Working home speaker |

## What was checked

All briefs and population records passed JSON Schema validation. All 300 profiles passed checks for IDs, non-ID uniqueness, segment counts, budget consistency, deadlines, allowed attribute values, source references, and reproducible generation. The Sony input example and model-action contract were also checked. See [saved validation report](simulation/population-validation.json).

Pilot inspection found that proofreading must treat actual document length as a hard requirement. The templates and population were corrected accordingly; no partial edit is silently counted as fulfilling a full-document request.

## What remains uncertain

Segments and numerical distributions were designed in chat. Official provider pages inform attributes and possible situations; they do not establish buyer prevalence or real demand. No human/market validation or live model journeys have occurred. Missing competitor prices and unsupported performance claims remain unresolved.

## Reuse

The sampler reads each product’s saved segment templates and rules; it does not call an LLM or assign outcomes.

```sh
python3 data/tools/generate_populations.py --product sony-speaker --pilot
python3 data/tools/generate_populations.py --product sony-speaker
python3 data/tools/validate_prepared_data.py
```

The generator uses only the Python standard library; the schema validation command additionally needs jsonschema. It was available in this workspace. The schemas contain no external network references. Regenerating a full population replaces that product’s customer file and review; preserve versions before changing templates.
