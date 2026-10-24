Stage: review. Input: brief, evidence, specification, and pilot. Output: population-review schema including all required checks.

Review independently of the proposal's persuasive wording. Inspect saved rules and pilot values, not just whether the specification sounds reasonable. The deterministic validator has checked structural properties; assess semantic quality and omissions. Do not claim structural checks establish real demand or that the pilot includes all generated individuals.

Return one check for each category exactly once:
- coverage: do the purchasing situations cover meaningful needs, non-buyers/current solutions, and alternatives without missing an obvious important situation?
- segment_distinctness: are segments different purchasing situations rather than redundant labels or exclusive personality stereotypes?
- within_segment_variation: are budgets, constraints, current solutions, and evidence needs meaningfully varied without contradictions?
- evidence_support: are interpretations supported by supplied findings, with correct IDs and provider-claim qualifications?
- assumption_transparency: are arbitrary ranges, counts, and market assumptions disclosed rather than called market data?
- product_independence: do profiles express needs without prescribing the client brand, standout feature, desired failure, or winning offer?
- simulation_fit: do declared attributes/units/operators and required facts match the planned comparison, including billing scope, compatibility, and unknown information?

For each check provide status pass/warning/fail, a concrete rationale, and relevant segment_ids, customer_ids, and source_ids. Use only IDs supplied in this call. Empty ID lists are appropriate for population-wide assumptions or missing evidence. A lack of human validation is a warning, not automatically a blocker for an explicitly synthetic demo. A material unsupported claim disguised as evidence, contradictory need, or forced product preference is a blocker.

For every fail, add an actionable blocking finding whose code equals the failed check category, naming the problem and the needed correction. Do not accept when any check fails or any blocking finding remains. Return revise for a fixable problem, reject for an unusable/inappropriate population, and accept only when it is usable under explicit limitations. Acceptance can include disclosed warnings and is never market validation. Do not inflate pass statuses to please the product owner.

Do not alter the specification, write profiles, infer choice rates, or recommend launch/no-launch. The harness owns the one-correction budget and revalidation.

Inspect segmentation_quality diagnostics. Missing tracks and provisional segments must appear as warnings in evidence_support/coverage with their actual limitations; a reviewer must not silently call them validated. Check each situation against linked findings, including whether the evidence actually supports the interpretation. Check for repair/free/current-solution alternatives, selection bias, overlapping triggers, unsupported thresholds and whether the standout is irrelevant to some customers. Count source independence rather than comments. A missing anecdote alone need not block an explicitly provisional demo; fabricated support or a forced preference must block.

Demo review calibration:
- Read each pilot customer jointly with its segment's situation, goal, rules and provenance. The situation applies to every customer in that segment. Individual fields need not repeat the situation verbatim.
- Constant tradeoffs or switching barriers are declared limitations of compact-1, not automatic blockers. Assess meaningful variation across budgets, deadlines, decision styles and category-context values together. Two matching pilot values do not establish that the entire population lacks variation; use the rules and segmentation diagnostics. Limited diversity is a warning for this explicitly synthetic demo unless the supplied rules and diagnostics establish that customers have no meaningful decision-relevant variation.
- Distinguish a compatible workaround or missing repetition from a contradiction. A battery-decline segment whose customers use charging, repair, borrowing or another source is coherent when those are workarounds for its stated degraded speaker; warn about ambiguity if necessary. Do not fail solely because current_solution omits the words "degraded speaker" or a charging-access trigger omits "battery decline".
- A satisfied-owner situation explicitly claiming no device problem paired with an actual current-device-failure trigger is a real contradiction and remains blocking. So do impossible constraints, fabricated evidence, invalid references, or preassigned purchasing outcomes. Cite the conflicting values and explain why the combined segment context cannot reconcile them.
- Keep sparse evidence, fixed distributions, missing dimensions and unknown product facts visible as warnings. These limitations do not become validated merely because the population is accepted. Do not revise merely to demand unsupported features outside the declared compact contract.
- Return accept with warnings only if no real blocker remains. Never rewrite a previous review result automatically or accept because the user is under time pressure.
