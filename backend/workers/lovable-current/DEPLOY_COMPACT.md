# Apply the compact proposal repair in Lovable

Use the attached repair ZIP to update only the corresponding customer-generation server files. Preserve existing route wrappers, auth secrets, runtime integration and safe logs. This is based on the exported current worker, not the obsolete local worker.

Changes:
- Final reviewer calibration: review instruction hash changed. Preserve strict parsing, references, budget constraints and blocking contradictions. Compact constant fields, sparse evidence and compatible workarounds can be warnings. Assess pilot customers jointly with their segment situation. Never auto-convert previous reviews to acceptance. Publish updated policy plus validators and regenerate deployment metadata before the final call.
- Review-size repair: Python deduplicates repeated long text losslessly; the saved review payload is 35% smaller by characters. Compact proposal/correction instructions now require every trigger/current-solution option to agree with its segment situation. Refresh policy and validators together; compact instruction hashes have changed. Original five stage instructions remain unchanged.
- Boundary repair: compact action_budget items are 1–5 and deadline_days items are at least 1, matching customer-v2. Refresh both policy.json and generated validators together. The previous live compact attempt reached decoding successfully but these mismatched bounds prevented profile construction.
- `policy.json` adds `compact_propose` and `compact_correct`; the original five stages and hashes are unchanged.
- Precompiled validators and declarations include the new stages.
- `wire-schema.mjs` fixes optional-null enum branch matching. No JSON-text fallback or duplicate overwriting.
- Compact responses use closed objects and arrays with direct strings, numbers and booleans. They need no maps, recursive tags, refs or model-authored rule expressions. Python constructs the canonical specification.

Run the existing tests. Confirm the worker accepts added policy stages. Regenerate deployment metadata using the existing version-build script and a new version describing the compact policy. Publish and verify the model-free deployment check. Do not make a model call automatically.

Gateway acceptance of new stages is unverified; local passing tests do not prove provider acceptance or output quality. The 24,000 completion-token cap is retained. Generated validators are supplied; rebuild them with the existing validator script if policy changes.

After deployment is confirmed, run from the local repository root:

```sh
python3 backend/scripts/run_smoke_tests.py \
  --model-backend bridge --product sony-speaker \
  --proposal-format compact \
  --reuse-research-run sony-live-v3-sony-speaker \
  --run-prefix "sony-compact-$(date +%Y%m%d-%H%M%S)" --execute
```

No Exa research is repeated. Do not run until the updated policy is live. Invalid compact proposals stop explicitly; there is no fallback to the old format. Review can request one correction using compact_correct.
