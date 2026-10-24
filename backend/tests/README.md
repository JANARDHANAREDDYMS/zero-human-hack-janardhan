# Phase 1 tests

Run from the repository root:

```sh
PYTHONPATH=backend/src python3 -m unittest discover -s backend/tests -v
```

Nineteen tests currently pass. They cover minimal intake, unknowns and unsupported claims, missing sources, assumption laundering, allocations, rule cycles, undeclared fields, invalid distributions, conditional relationships, contradictory constraints, duplicate profiles, seed reproducibility, product renaming, 500-profile sampling, forbidden executable rules/outcome fields, and refusal to overwrite existing output.

`fixtures/keyboard/` is a hand-authored offline specification with two segments. It demonstrates category-independent construction without keyboard-specific sampler code or a mandatory five-segment design. It does not demonstrate automatic research, automatic segment design, or live model quality.

The original six demo populations retain their separate validator: `python3 data/tools/validate_prepared_data.py`.
