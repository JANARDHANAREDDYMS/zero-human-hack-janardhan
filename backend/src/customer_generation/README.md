# Customer generation package

Phases 1–4 and Phase 5 local evaluation code are implemented: contracts, generic sampling, harness/state, adapters, versioned stage instructions, raw intake, and qualitative review gates. No live services or actual model quality have been verified. See [living implementation diagram](../../../docs/context/implementation-and-instructions.html).

| File | Responsibility |
|---|---|
| `validation.py` | Local schema resolution, evidence references, allocation checks, rule dependencies, and cycle detection |
| `sampling.py` | Restricted rule interpreter, deterministic generation, consistency checks, and bounded attempts |
| `__main__.py` | Validate input contracts or sample an already-authored specification |
| `pipeline.py` | Harness, validation gates, review acceptance, one correction, terminal states |
| `state.py` | Typed state, usage limits, stage-backend protocol |
| `storage.py` | Exclusive run directories and atomic file writes |
| `tools/fixtures.py` | Explicitly offline saved stage responses |
| `instructions.py` / `prompts/` | Versioned methodology and stage bundles; model-request hash binding |
| `tools/` | Exa, HTTPS transport, authenticated project-function client, live dispatch, explicit fixtures |

Canonical v2 schemas live in `data/schemas/` at the repository root. This initial package runs from a source checkout; standalone wheel distribution and packaged-schema installation are not implemented.

## Run from the repository root

```sh
PYTHONPATH=backend/src python3 -m customer_generation validate \
  --intake backend/tests/fixtures/keyboard/intake.json \
  --evidence backend/tests/fixtures/keyboard/evidence.json \
  --spec backend/tests/fixtures/keyboard/specification.json

PYTHONPATH=backend/src python3 -m customer_generation sample \
  --evidence backend/tests/fixtures/keyboard/evidence.json \
  --spec backend/tests/fixtures/keyboard/specification.json \
  --output data/runs/my-keyboard-check/customers.json

PYTHONPATH=backend/src python3 -m unittest discover -s backend/tests -v
```

Requires Python 3.11+ and jsonschema 4.18–4.x (declared in backend/pyproject.toml). Sampling refuses to overwrite an existing output. The checked example is saved under data/runs/phase1-keyboard-offline/. This fixture does not use live research or a model.

## Contract versions

Existing demo profiles retain their v1.1 format. The new pipeline uses separate v2 intake/evidence/specification/customer/output schemas so the original six populations are preserved. Output includes specification/evidence hashes, a seed, generator version, and explicit synthetic status. A future compatibility adapter will be needed if simulation code assumes only the earlier version.

## Rule language

Every field has a rule and provenance. Supported rules:

- `constant`: an explicit JSON value.
- `choice`: distinct choices with optional positive weights.
- `integer` / `number`: declared bounds; number supports rounding precision.
- `reference`: copy a declared sampled field.
- `scale`: numeric field × factor + optional offset, with optional floor/ceil.
- `conditional`: choose a rule using a declared field comparison.

Fields are evaluated in deterministic dependency order, not JSON insertion order. No arbitrary expressions, executable code, filesystem operations, or network tools are available in this interpreter. Rules and nesting have structural bounds; candidate attempts are capped. Insufficient diversity or contradictory rules fail explicitly instead of copying customers or silently relaxing constraints.

All common profile fields are required in the generation specification; they are not required from the customer at intake. Later model stages propose them with explicit provenance. Category-context fields must be declared in the attribute dictionary. Requirement names, types, units, and operators come from the same dictionary. `contains` currently supports string-list capabilities such as supported operating systems; numeric-range membership and more complex dependencies require future explicit extensions, not invented syntax.

## Quality boundary

Validation checks structure, referential integrity, some cross-field consistency, diversity, and reproducibility. It cannot establish that sources support an interpretation, that segments are complete, that assumptions are realistic, or that a model-generated specification is useful. Qualitative review and live evaluation remain later stages. No buying outcomes are generated.

Bridge contract is now 1.1, requiring instruction version/hash acknowledgement. Reviews must include all seven named checks. Inspect `python3 -m customer_generation show-instructions` with PYTHONPATH set as above. Raw intake may use product_id/text; structured intake still skips the extraction call. There are 111 passing tests.


### Segmentation quality revision

Research now plans three tracks: offers, buyer situations and counterevidence. New findings may use `observed_report` for unverified buyer reports, with source IDs, and a `track`. Live proposals require a six-part `situation`; each valid candidate saves `segmentation-quality-N.json` and supplies it to the reviewer. Missing buyer support remains provisional and cannot receive a live evidence-support pass. Diagnostics do not establish representativeness or verify source interpretation.

The manually researched Sony candidate is in `data/products/sony-speaker/research-v2/`; its review explains limitations and constructed-sample statistics. Original v1.1 data and simulation fixtures remain intact. Instruction bundle version is now `segmentation-1.1`; bridge envelope remains 1.1. Actual live model quality remains unevaluated; Phase 5 local evaluation tooling is now implemented.


Phase 5 adds `evaluation.py` and `evaluate-run --run-dir PATH --output NEW_REPORT [--audit AUDIT] [--audit-template-output NEW_TEMPLATE]`. This is read-only evaluation of saved artifacts; no API calls. Reports keep offline-only, pending human review, failed evaluation and reviewed-with-limitations states distinct. See `data/evaluations/README.md` for live setup, the holdout USB-C hub brief and human rubric. Live evaluation is still pending.


Local Codex access is now available through `tools/codex.py`, selected by `--model-backend codex` or MODEL_BACKEND. Read [Codex bridge instructions](tools/CODEX_BRIDGE.md) for setup, the real smoke-test command, schema boundaries and subscription-usage limitations.


### Live keys and Lovable worker preparation

Private `.env` files are ready (never commit them). Use the CLI's global `--env-file backend/.env` option or the two-product runner, which defaults to plan-only. See `data/evaluations/FIRST_LIVE_SMOKE.md`. `backend/workers/lovable/` contains a tested authenticated worker, exported canonical prompt/schema policy, server secret names, deployment prompt and archive. It is not deployed; selected-model compatibility and runtime credits remain unverified. There are 111 Python tests and 10 mocked Node worker tests.
