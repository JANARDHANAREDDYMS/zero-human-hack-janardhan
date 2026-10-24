# Current project decisions

Recorded October 23, 2026, America/New_York. User instructions in this chat override older suggestions.

## Goal and scope
Build an autonomous customer-research service for tomorrow's hackathon. A founder submits a prelaunch product and research question; the service researches alternatives, constructs synthetic customers, simulates shopping choices, checks important hypotheses with human input, and delivers findings.

Tonight: six prepared demo concepts, three physical products and three professional/service products. Confirmed concepts: hypothetical Sony speaker and CodeSensei interview-preparation subscription. The other four were subsequently selected: commuter backpack, desk lamp, résumé review, and proofreading. Current specifications and competitor baselines are in docs/data/product.html and docs/data/competitor-baselines.json. These are analysis scenarios; six working businesses or manufactured products are not required.

Prepare one dependable primary scenario first. Review 30–50 profiles before scaling to a target of 500 per product. Tomorrow build one complete journey, benchmark ten customers, then scale within available credits.

## Budget and data
The user reports Terac API access, Whop API access, Lovable credits, and Exa credits. No separate paid LLM API account should be assumed. No credentials or account balances have been inspected.

Demo customers use artificial data, explicit assumed distributions, and reproducible sampling. There is no proprietary customer dataset, trained behavioral model, or established forecast accuracy. Research may inform assumptions without turning synthetic customers into actual respondents.

Lovable is intended to provide both application building and in-app model access. Official documentation at https://docs.lovable.dev/features/ai confirms model calls inside apps without a separate provider account and notes runtime credit charges. Sponsor-credit eligibility for that usage remains unverified. Avoid assuming app-building credits guarantee runtime coverage. If runtime credits are unavailable, a clearly labeled rules-based simulation or prerecorded run is a possible fallback, not an already agreed implementation.

## Current business flow
Paid research request (Whop) → brief and audience intake → market/competitor evidence (Exa) → segment definitions and sampling rules → reviewed synthetic population → bounded shopping journeys → improvement hypotheses → targeted human feedback (Terac) → revised assumptions and rerun → delivered report.

Lovable builds the interface and is the intended model-access layer. Whop sells our analysis service; synthetic product choices are recorded outcomes, never real product revenue. Terac may review profiles or recommendations; one targeted post-simulation review is the proposed MVP.

The earlier autonomous product-change diagram is conceptual background. Later discussion clarified the service business above. Hardware changes are hypothetical comparisons. Real customer behavior and calibration can be added when observations exist; they are not required to pretend this demo has real demand data.

## Simulation boundaries
Simulate purchasing based on available product information, alternatives, and samples. Do not claim to simulate hearing a speaker, experiencing long-term service quality, or post-purchase satisfaction. Support choosing a competitor, keeping the current solution, and buying nothing.

Code enforces available actions, constraints, bounded steps, and trace storage. Model calls can interpret needs and choose actions. Precomputed profiles do not eliminate runtime model costs. A rules-based journey must be labeled as such if used.

## Working agreement
Be pragmatic and candid. Check earlier discussion when uncertain, distinguish user decisions from suggestions, and state gaps rather than invent missing context. Create only docs at this stage. Do not introduce frontend, backend, agents, frameworks, or paid dependencies yet.

## Inspiration and unresolved context
Primitive Labs and Instinct appear in recovered discussions as conceptual inspiration. The user associates the idea with interview preparation for a company referred to as Premier Media Labs AI; whether this is the same company is unconfirmed. Do not silently merge these names. The specific research papers have not been recovered.

Open: final review of the four new offers, primary demo scenario, market/currency assumptions, validated schemas, actual sponsor balances and permitted operations, runtime credit coverage, tomorrow's judges/rubric, and rules concerning advance preparation.

## Preparation update
The user subsequently chose 50 customers per product for the first demo population. Six category-specific populations (300 total) and a six-decision simulation contract are now prepared under data/. Source-linked segment rationale and numerical assumptions are explicit. Structural validation passed; human/market validation and live simulations have not occurred. Sony is the primary input example. The local sampler is implemented; automatic research/LLM segment generation is not.
