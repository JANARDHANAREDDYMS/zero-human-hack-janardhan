> The living implementation record and detailed diagram are now in [implementation-and-instructions.html](implementation-and-instructions.html). This Markdown file preserves the Phase 1 history. Phase 2 is documented in the HTML guide.

# Customer generation implementation progress

## Phase 1 — contracts and generic sampling

Status: Complete — October 24, 2026.

Scope: minimal intake, evidence provenance, category-independent population specification, bounded deterministic sampler, and an unseen-keyboard acceptance example. No live model/Exa calls, orchestration, payments, or simulation execution in this phase.

### Stage 1: contracts

Complete. Added v2 intake, evidence, population-specification, customer, and generated-population contracts alongside the existing demo schemas. Missing optional intake fields stay unknown; evidence and assumptions are separate.

### Stage 2: generic sampler

Complete. Rules support constants, weighted choices, numeric ranges, references, scaling, and conditionals. Dependencies are ordered, cycles rejected, attempts bounded, and no product-name branches are used.

### Stage 3: verification

Complete. Nineteen tests passed, including sparse intake, evidence provenance, cyclic/missing dependencies, contradictory constraints, duplicates, reproducibility, no executable rules, 500-profile sampling, and safe output handling. The hand-authored keyboard fixture generated 50 profiles across two segments. The original six-product validator also passed. This checks sampler generality, not autonomous LLM segment generation.

## Later phases

2. Harness, explicit state, storage, limits, and bounded correction.
3. Exa and model adapters, with Lovable runtime connected when access is available.
4. Stage prompts and qualitative review.
5. End-to-end live evaluation on an unseen product.

## Phase 1 deliverables

- New versioned schemas in data/schemas/: intake, evidence, population-specification, customer-v2, and generated-population.
- backend/src/customer_generation/: validation.py, sampling.py, CLI, and package exports.
- backend/tests/test_phase1.py and fixtures/keyboard/.
- data/runs/phase1-keyboard-offline/: generated acceptance example, explicitly not live research/model output.
- Dependency declaration in backend/pyproject.toml.

See [package instructions](../../backend/src/customer_generation/README.md) for commands and supported rule syntax. The six demo datasets and original contracts are preserved. No paid API calls occurred.

## Remaining limitations

The sampler accepts already-authored rules. It does not discover competitors, infer segments, judge source meaning, or ensure market realism. Qualitative prompts, model calls, stage orchestration, and Lovable connectivity remain unimplemented. V2 data is separate from the legacy demo format; downstream version handling must be explicit. The next step is Phase 2, not another population-generation claim.
