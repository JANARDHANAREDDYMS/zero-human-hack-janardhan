# Customer simulation design decision, 2026-10-24

Status: design agreed for implementation; no model-driven shopping journey has run. This document incorporates the user's pasted research note, checks its main claims against the cited primary papers, and specifies what we will build first. The [v1.0 interaction contract](contract.md) remains the detailed action and observation contract.

## Purpose and claim

Use a reviewed synthetic population to find plausible objections, missing information, and directions for product experiments. A simulated choice is a **model output under declared assumptions**, never a real buyer, conversion forecast, or measured market share. The six prepared populations have 50 profiles each; their segment counts were authored for coverage, not estimated prevalence. A price test may identify a useful hypothesis but cannot establish willingness to pay.

The loop is: evidence and explicit assumptions → sampled profile → bounded shopping journey → trace and consistency checks → paired product intervention → hypothesis and uncertainty → targeted human feedback (Terac, later) → actual behavior where available → revise assumptions. Keep simulation, human feedback, and observed behavior in separately labeled datasets.

## One customer journey

Code loads one immutable profile, its current solution, one immutable offer snapshot per alternative, and a presentation seed. Initial cards show the same categories of information for every offer: name, neutral description, headline price, billing period, and mandatory upfront commitment. Available choices include free or DIY alternatives when documented, keeping the current solution, declining, and insufficient information. Shuffle offer order with a saved seed.

At each step the **Lovable-hosted model worker** receives the profile's shopping-relevant fields, the current visible observation, previously revealed facts, allowed actions, and remaining decision budget. It returns exactly one structured action. Code validates the action, reveals only requested saved facts, and appends the observation to the trace. At most six model decisions occur, including the terminal decision. On the sixth, only a terminal decision is allowed. A model cannot edit the customer, fabricate reviews, alter an offer, or cite a fact the customer did not see. An invalid action gets one repair call using the same observation; a second failure is `model_error`. Provider failure is `infrastructure_error`, excluded from completed-choice denominators.

The runtime state is deliberately small: `visible_fact_ids`, action/observation trace, remaining steps, remaining profile research actions, open questions, and terminal status. These are externally checkable. The model may explain its subjective assessment in a short final reason, but we do not persist invented numeric belief or purchase-intent scores as measurements. The current profile already carries goals, trigger, budget, requirements, tradeoffs, evidence need, research effort, familiarity, switching barriers, and category context. We will add new fields only when a concrete scenario needs them and their sampling basis is declared.

## Code-owned enforcement

Selection is disallowed when a known hard requirement fails, when a known complete purchase commitment exceeds a hard budget, or when the selected offer does not exist. Offer facts have source IDs and qualifications. Unknown is unresolved, not false and not a zero-dollar price. Provider claims stay marked as claims. A selected hypothetical offer is a preference in a simulated scenario, not a real purchase.

Price checks use the customer's scope: whole device and required add-ons, documents needed at per-document rates, or a full mandatory upfront subscription. The code must not convert an annual plan to a purchasable month or omit a required spare battery to make an offer appear affordable. Unknown tax, shipping, delivery, compatibility, performance or terms remain visible uncertainty. A customer with a strong evidence requirement may choose insufficient information. The hard budget rule is an **authored simulation assumption**, not a claim that all actual people obey an exact threshold.

Offer snapshots must be frozen before a paired comparison. Compare the same profile and same non-target offers under baseline and intervention, with the same presentation order or a documented counterbalance. Only the intended offer facts may change. If a variant adds a price increase, reduce it by changing the saved price fact and headline consistently. Record a content hash of each snapshot; never quietly refresh competitor prices between paired runs.

## Model interface and budget

Use the existing authenticated Lovable project function for model calls once it is deployed and passes an integration smoke test. The Python simulation controller owns the loop and persistence; the worker is a bounded model caller. One LLM call per decision means at most six normal calls per customer, plus one repair call when needed. Ten pilot customers could therefore use up to 70 calls; 50 could use up to 350. This is a **call ceiling**, not a credit estimate. Rate limits, per-call token usage, wall time, and Lovable runtime credits must be observed in the actual workspace. Do not launch 500 journeys based on a mocked worker test.

Pin the model ID and prompt/instruction version for each batch. Ask for low randomness where the selected model supports it, but do not assume identical reruns are guaranteed. Save model ID, settings, prompt hash, inputs/outputs or privacy-safe equivalents, timestamps, token counts where reported, errors, and the Lovable dashboard's actual credit spend when available. Keep the worker credential server-side. The existing generation worker's allowlist currently covers **generation stages only**; simulation needs a separately versioned action stage, its JSON schema, and deployment policy update before it can be called.

## Data compatibility work before a live journey

The current `request.schema.json` points at the old `customer.schema.json`; the newer Sony population is generated under `customer-v2.schema.json`. The sample Sony request and six pilot offer sets still use legacy v1.1 customers. The first implementation must load one accepted v2 profile directly, validate it against `customer-v2.schema.json`, and build a run request through a deterministic adapter. Do not merge the old and new Sony populations or silently coerce missing fields. If a profile requires an attribute absent from all offers, expose that as unresolved and include it in the result.

The first Sony run must use the refreshed research-v2 profile and refreshed, reviewed competitor offer snapshots. The legacy Sony example is a schema illustration, not the input for the first quality claim. For the USB-C hub, create an offer set from current sourced facts after the planned Exa research smoke; connector shape alone cannot establish charging or video support. Preserve source capture date and contested facts.

## What the result should show

For each journey save: customer and offer hashes, presentation order, visible fact IDs by step, action and structured validation outcome, observation returned, terminal selection or non-selection, short reason with only seen fact IDs, unresolved attributes, usage, timing, and error status. A report groups completed outcomes by segment and alternative, shows counts and denominators, and lists common objections and information gaps. It must prominently show that the sample is synthetic, coverage-weighted, and not calibrated to market demand. Infrastructure/model errors get a separate count.

For an intervention, compare **paired customer outcomes**: which profiles changed choice, which stayed, and what facts they saw. Prefer the switch matrix and examples of changed journeys over a single conversion percentage. Show seed, model, order policy, and number of repeat runs. A launch/no-launch recommendation is a reviewable hypothesis with limitations and proposed human test, not an automatic sales prediction.

## Evaluation gates

1. **Software integrity:** schema validation, stable snapshots/hashes, trace replay, six-decision cap, no unseen fact citations, no fabricated samples, and clean error accounting. Check hard budgets and known hard requirements in code, including service billing scope and physical compatibility. These are deterministic tests.
2. **Behavioral consistency:** on a small prespecified set of profiles, check whether actions respect their budget, evidence need, research budget, current solution and requirements. Inspect where the model changes preferences without receiving new information. Record violations, not just fluent explanations. The paper motivating this check reports substantial persona drift even for strong models; prompt quality alone is insufficient.
3. **Paired direction checks:** vary one fact at a time (price, documented evidence, guarantee/terms, etc.) while holding profiles and other offers fixed. Check whether outcomes move in the expected direction for relevant profiles, with repeated runs and uncertainty shown. A single customer's response is not required to be monotonic; even aggregate monotonicity is a diagnostic rather than a guarantee of human realism. Never hard-code the desired choice into the prompt or score.
4. **Human relevance:** review the actual evidence and customer situations. A Terac interview or observed transaction later can test a narrow hypothesis and change an explicit assumption. Do not relabel synthetic profiles as trained on that feedback without an actual update method and held-out check.

Implementation sequence: one refreshed Sony journey → deterministic enforcement tests → ten customer Lovable pilot with measured credits/latency/failure rate → paired intervention and consistency checks → 50 profiles per product only if the pilot passes → targeted human validation. The USB-C hub is the holdout for **population generation**; it becomes a simulation case only after its profiles and offer evidence pass review. The $20/document proofreading concept remains a legitimate potential negative result; no simulator instruction should steer it toward failure.

## Hackathon business-loop milestones

The project is a **paid research service**. Whop should sell access to that service or one research report. A simulated `select_offer` is never a Whop purchase. A demo may claim real revenue only after a genuine Whop checkout is paid and its payment status is verified through an authenticated server-side event or API read, tied to an order and report fulfillment. A created checkout link, test payment, mock event, or simulated customer choice is not revenue. Store payment/order identifiers and fulfillment state separately from simulation traces; keep secrets and payment verification server-side. The official event guide requires all payments through Whop and explicitly says not to set up Stripe; Stripe is excluded from this hackathon implementation.

Terac is the **human-signal step** after the simulator surfaces a specific uncertainty or disagreement. The first integration should send one narrow question about a real product assumption or offer tradeoff, save the question and returned human feedback with timestamps/source IDs, and compare it with the simulator's prior hypothesis. Do not treat a Terac response as a transaction or silently rewrite historical profiles. A later version may update an explicit assumption and rerun the same scenario, keeping before/after artifacts. The demo should visibly distinguish synthetic trajectories, Terac human input, and Whop verified revenue.

These are required end-to-end demonstration outcomes, but the Whop and Terac API integrations are **not implemented or verified yet**. After the one-customer simulation works, build the narrow Terac feedback loop and a real Whop service checkout/verified fulfillment path before calling the company loop complete.

## Research basis and limits

- [CustomerSim (2026)](https://arxiv.org/abs/2605.08334) benchmarks multi-turn retail customer simulators using 360 curated personas across five categories, with action/persona alignment as a key measure. It supports our consistency checks; its personas and benchmark scores do not validate our buyers.
- [Generative Agent Simulations of 1,000 People](https://arxiv.org/abs/2411.10109) grounds agents in interviews with actual people. It suggests rich behavioral context matters; our constructed profiles lack those interviews, so its reported replication performance does **not** transfer to this project.
- [Homo Silicus](https://www.nber.org/papers/w31122) frames LLMs as simulated agents given preferences, information and resources. It motivates explicit state and constraints; it does not prove buyer prediction.
- [Silicon samples in consumer and marketing research](https://doi.org/10.1002/mar.21982) discusses pretesting value and human benchmarking needs. Our reports should be hypothesis-generating until validated.
- [Nature Human Behaviour (2026)](https://www.nature.com/articles/s41562-026-02611-4) finds weak proxies for human economic preferences across 74 countries, especially cultural patterns. This is a strong limit on external-validity claims.
- [Persona Hub](https://arxiv.org/abs/2406.20094) is about broad synthetic data/persona diversity; it does not provide evidence that our segment proportions or buying choices are real.

The pasted note's illustrative percentages and conversion curves are examples, not source data or acceptance targets. We will not encode them as priors or show them as findings.

## Official guidebook update

The [October 24 guidebook notes](../../docs/context/hackathon-guidebook-2026-10-24.md) supersede earlier assumptions about optional integrations. Use **Terac MCP**, gather human input during the hackathon, apply it and demonstrate measurable before/after improvement. Build the company on Whop and route all payments through Whop; revenue must be organic. API-only Terac use is not presumed sufficient because the universal rule explicitly names MCP. General-population tasks are recommended. The Lovable 100-credit Pro benefit does not itself establish worker runtime-credit coverage.

## Terac study routing

Use Terac only after the simulator produces a concrete uncertainty, disagreement, or usability problem. The first study should recruit a small general-population sample because the event explicitly recommends it for speed and credit efficiency. Ask participants to react to a real artifact: the product comparison, research report, offer page, or working interface. Save the baseline artifact and prespecify a simple outcome such as task completion, correct comprehension, preference/ranking, confidence, or a structured severity rating. Apply one change and repeat the same task or show an equivalent comparison. Preserve the before/after artifacts, questions, submissions, counts and limitations.

Choose people based on the question:

| Question | First human signal | Specialist follow-up when justified |
|---|---|---|
| Does the speaker offer make sense and feel valuable? | General consumers who use or have considered portable speakers | Consumer-audio product marketer, electronics retailer/category buyer, or audio-product reviewer |
| Is the proposed speaker technically credible? | Do not ask general consumers to validate engineering | Acoustic/electrical engineer or consumer-electronics product engineer |
| Is the resume service useful and trustworthy? | Recent job seekers or general participants with resume experience | Recruiter, hiring manager, certified resume writer, or career coach |
| Is proofreading valuable and clearly scoped? | People who submit work/school/client documents | Professional copy editor or editorial operations specialist |
| Is the UI confusing? | Intended users completing a concrete task while reporting friction | UX researcher/product designer to diagnose the flow; frontend engineer for implementation; accessibility specialist for accessibility findings |

Do not use an expert opinion as proof of customer demand. Real users establish the observed usability or comprehension problem; an expert can recommend a repair. With only a three-to-four-hour access window, launch the general-population study first. Add an expert task only if the first result identifies a technical or professional question that ordinary users cannot answer and sufficient time/credits remain.

For the first demo, use one narrow study: participants inspect the baseline report or product comparison and complete a decision/comprehension task; the system identifies the largest recurring issue; we revise one artifact; then report the same metric before and after. This satisfies the human-input loop more directly than commissioning a broad marketing consultation.
