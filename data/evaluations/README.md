# Phase 5: evaluation, separate from generation acceptance

The evaluator checks saved runs without calling services. The initial live case is `cases/usb-c-hub.json`, a category outside the six prepared products and the keyboard fixture. No prewritten segments or expected customer choices are supplied. This is a manually designed holdout scenario, not a statistically independent benchmark.

## Live procedure

1. Configure EXA_API_KEY, MODEL_BRIDGE_URL, MODEL_BRIDGE_TOKEN, MODEL_ID in the environment. The bridge must be deployed and allow the current instruction manifest. `check-config` checks structure only; it does not verify access or credits.
2. Run the unseen case using the command below. Default cost/token limits remain unchanged. If they are too small, inspect the saved failure and explicitly choose new limits and a new run ID. Never silently raise them or retry billed calls.
3. Evaluate the saved run and create an audit template. Inspect the actual evidence, specification and all 50 profiles, including the model's pilot review. Complete the audit yourself; the generation model cannot provide an independent human verdict.
4. Re-evaluate with the completed audit into a new report. Keep failed runs and reports. Do not tune only toward acceptance or compare costs across different counts/models without reporting the differences.

```sh
PYTHONPATH=backend/src python3 -m customer_generation check-config
PYTHONPATH=backend/src python3 -m customer_generation run-live \
  --intake data/evaluations/cases/usb-c-hub.json \
  --run-id phase5-usb-c-hub-live --count 50 --seed 42
PYTHONPATH=backend/src python3 -m customer_generation evaluate-run \
  --run-dir data/runs/phase5-usb-c-hub-live \
  --output data/evaluations/phase5-usb-c-hub-report.json \
  --audit-template-output data/evaluations/phase5-usb-c-hub-audit.json
# After actually inspecting and editing the audit:
PYTHONPATH=backend/src python3 -m customer_generation evaluate-run \
  --run-dir data/runs/phase5-usb-c-hub-live \
  --audit data/evaluations/phase5-usb-c-hub-audit.json \
  --output data/evaluations/phase5-usb-c-hub-reviewed.json
```

## Human rubric for the hub case

- Coverage: work/travel constraints and existing adequate solutions; research may suggest other situations. Do not demand a fixed list or five groups.
- Distinctness: groups differ in triggers/current solutions/constraints rather than copied biographies. Explain overlap.
- Variation: dependent laptop/OS, ports, required displays, power requirements, deadlines and budget scope agree. Unknown product capabilities stay unknown.
- Evidence: distinguish official capability claims from first-person reports. Verify interpretations against sources; inspect counterevidence, source age, truncated context and duplicated discussions.
- Assumptions: profile ranges, allocation, market geography and weights remain labeled unless evidence supports the particular quantity.
- Independence: no client-product preference, prescribed conversion, or requirements copied to make the $39 offer win. Direct ports or an existing dock can be sufficient.
- Simulation fit: a connector shape does not guarantee display/charging support. Units, billing scope and compatible device requirements must be precise enough to compare without inventing product facts.

## Interpretation

Reports separate run completion, deterministic replay, usage reconciliation, evidence diagnostics, model review format and human review. Cost is reported/estimated, not a verified bill. Stage duration is recorded for new runs; older runs can have unknown stage timing. Human audits bind to the customer artifact hash; reviewer identity remains self-declared.

Statuses: `run_not_completed`, `evaluation_failed`, `offline_only`, `needs_human_review`, `reviewed_with_limitations`. No status means real-buyer validation. Offline fixtures cannot become live evaluation merely by supplying an audit. A backend's live label is not independent proof that it contacted a network service.

Local readiness samples use explicit fixture mode. They establish evaluator operation only, not the quality of automatic segmentation. Actual live evaluation remains pending until credentials and a deployed bridge are available.


## Local Codex alternative

A deployed Lovable HTTP function is optional when using `run-live --model-backend codex`. The local adapter uses the existing Codex CLI login. It still needs EXA_API_KEY for research. Run `codex-smoke --output NEW_PATH` first to test model access and structured intake without Exa. See `backend/src/customer_generation/tools/CODEX_BRIDGE.md`. Model dollar cost remains unknown, so report subscription usage separately from the known Exa dollar subtotal. Local read-only runtime restrictions can prevent CLI startup even when login status succeeds.
