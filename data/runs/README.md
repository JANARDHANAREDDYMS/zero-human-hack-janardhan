# Generation run storage

Future runs live in separate `<run-id>/` directories so a new submission never overwrites `data/products/` demo examples.

Each run should preserve minimal input, normalized brief, research sources and extracted findings, proposed segments/rules, pilot, review findings, correction attempt if needed, final customers, validation, prompt/model versions, input hashes, and usage/failure metadata.

Record explicit stage status and partial results. A failed or incomplete run must not look like a completed population. Do not store secrets. Several explicitly offline runs are now saved. The latest Phase 5 readiness run is `phase5-keyboard-offline-readiness`; it has 50 fixture-generated profiles and per-call duration records. Its separate report in `data/evaluations/` is marked `offline_only`. No Phase 5 live run has been performed.
