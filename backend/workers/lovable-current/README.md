# Local working copy of the imported Lovable worker

Based on the unmodified snapshot in `../lovable-export-2026-10-24/`. Not deployed. The copied deployment-version metadata describes the source snapshot, not these local edits; regenerate it in the full Lovable project before publishing. The original older worker remains in `../lovable/`.

## Verified decoder repair

Strict schemas require optional properties and use null to represent missing non-nullable values. `pickBranch` previously rejected a valid scale rule with missing optional `round`, because the wire field was null and null was not an allowed round enum value. It then fell back to the first rule branch and left the null in canonical output, causing rejection.

Branch matching now recognizes that absence sentinel for optional, non-nullable properties. Decoding then removes it as intended. Required discriminators remain checked. The original export reproduces the failure; this copy passes the same complete Sony proposal unchanged.

This does not resolve model-generated duplicate map keys. Those remain rejected. No canonical policy or instruction hash was changed.

## Complete offline integration tests

From repository root:

```sh
PYTHONPATH=backend/src python3 -m unittest discover -s backend/tests -p test_worker_complete_responses.py -v
```

Requires Node, Python dependencies already used by the backend, and Ajv dependencies in `../lovable/node_modules`. Uses no network, credentials or model. Tests copy this runtime to a temporary directory beside those dependencies and remove it afterward.

Coverage: all five stages through the actual worker handler, strict wire-schema validation with Ajv, imported precompiled canonical validators, saved live research, full manually authored Sony proposal, Python semantic validation, deterministic construction of 50 profiles, duplicate attributes, malformed tags/branches/outer JSON, unknown source references, and mismatched choice weights. An explicit regression runs the original exported decoder to prove the optional-enum failure.

Fixtures are existing saved manual inputs plus a labeled synthetic acceptance review. Test wire responses are constructed by a separate test-only encoder; they do not measure model compliance, gateway compatibility, research quality or real buyer behavior. The complete Sony fixture produces profiles only in a temporary test directory, never as a new live dataset.

The original exported Vitest suite has not been installed/run here. Existing recursion-limit and first-branch fallback concerns remain outside this focused repair for older stages.

## Compact proposal format implemented locally

`compact_propose` and `compact_correct` now use a small static schema with no unconstrained fields, optional properties, maps, refs, or rule unions. Code owns canonical field paths, identifiers and rule construction. Category names are a bounded deterministic catalog: three general buyer-context fields plus up to eight unambiguous scalar evidence attributes. Model supplies values by slot, with no ability to invent/overwrite attribute names. Duplicate/missing/unknown slots and mismatched value types are rejected by Python semantic validation.

This first version uses uniform choices, a uniform budget range and comfortable budget = 75% of maximum. Only comparable price is a hard requirement. Complex correlations and category-specific hard constraints are intentionally unsupported and disclosed to review. Catalog coverage is limited by retrieved attributes; buyer-only missing dimensions must be reported in limitations. Do not equate this format's reliability with validated segmentation quality.

Five additional tests cover complete compact proposal/correction responses through the actual handler, schema shape, construction of 50 reproducible profiles, semantic rejections, and the full adapter/harness with a reviewer-requested correction. Fixtures are synthetic. No live calls or publishing occurred.

Export/build commands from repository root:

```sh
python3 backend/scripts/export_worker_policy.py
node backend/scripts/build_current_worker.mjs
PYTHONPATH=backend/src python3 -m unittest discover -s backend/tests -p 'test_*.py'
```

See `DEPLOY_COMPACT.md` for the required Lovable update before using `--proposal-format compact`. The default remains canonical to avoid silently changing requests against the currently deployed policy. Original five stage policies remain unchanged.
