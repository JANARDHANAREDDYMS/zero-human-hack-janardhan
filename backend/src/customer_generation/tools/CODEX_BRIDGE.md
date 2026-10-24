# Local Codex model bridge

`CodexModelClient` implements the existing model adapter’s `call(stage, payload, allowances, output_schema)` interface. It launches the installed Codex CLI with its existing authentication. It does not deploy a server, expose an HTTP port, extract authentication tokens, or call private endpoints. The Lovable HTTP adapter remains available.

## Use

```sh
# Codex CLI must already be installed and logged in.
codex login status
# Small real intake call, no Exa key needed. Output path must not exist.
PYTHONPATH=backend/src python3 -m customer_generation codex-smoke \
  --output data/evaluations/codex-smoke.json

# Full generation still requires Exa. Export its key privately into the shell.
# CODEX_MODEL is optional when ~/.codex/config.toml already names a model.
PYTHONPATH=backend/src python3 -m customer_generation check-config --model-backend codex
PYTHONPATH=backend/src python3 -m customer_generation run-live \
  --model-backend codex \
  --intake data/evaluations/cases/usb-c-hub.json \
  --run-id phase5-usb-c-hub-codex --count 50 --seed 42 \
  --max-tokens-per-call 40000 --max-total-tokens 160000
```

Alternatively set `MODEL_BACKEND=codex`. This mode requires EXA_API_KEY and either CODEX_MODEL or a configured local Codex model. It does not require MODEL_BRIDGE_URL, MODEL_BRIDGE_TOKEN or MODEL_ID. The optional CODEX_MODEL overrides only this adapter; the application does not rewrite the user's Codex configuration. The smoke command accepts `--model` for a one-off override.

## Call boundaries

- One fresh ephemeral session per stage; no conversation continuation. The code selects the stage’s canonical instruction bundle and records its version/hash.
- Uses an isolated temporary working directory, `--ignore-user-config`, read-only sandbox, disabled web search, and disabled shell/app features. Authentication still comes from the normal CLI. A parent process may need local Codex runtime filesystem access to initialize; no bypass-sandbox flag is used.
- Stage instructions, untrusted payload and complete output schema are passed over stdin. The instruction text is a prompt, not a separately guaranteed system-role API message. Model compliance still needs evaluation.
- Strict CLI output uses a small `result_json` string envelope, allowing dynamic category attributes and conditional rule schemas. The decoded stage object is validated against the actual canonical schema in Python. The ordinary pipeline semantic gates still run afterward.
- JSONL usage and final data are parsed; missing usage, malformed data, failed turns and tool-action events are rejected. Raw CLI diagnostics and reasoning logs are not saved. Version/hash metadata records what was sent, not a model attestation.
- No shell interpolation. Temporary logs have size checks. Timeout kills the local process group; cancellation cannot undo service-side usage already consumed.

## Usage limits and cost

CLI token usage is recorded, including input/output and cached-input metadata. The configured model name is recorded as **requested**, since the CLI response does not attest the actual serving model. Codex can have substantial instruction overhead beyond our prompt.

There is no hard per-call token cap exposed here. Token limits are checked after execution by the harness; an over-limit call is recorded and the run stops. The smoke test has an explicit 40,000-token reporting allowance and 60-second timeout. The bridge-mode defaults remain 6,000 tokens per stage, 40,000 total, and $1 known-cost allowance. Codex generation requires explicit per-stage and total token limits before making research/model calls. The example chooses 40,000/160,000; these are allowances, not a forecast or guaranteed sufficient limits. Measure usage, then deliberately choose different limits if needed; do not automatically retry or raise them.

ChatGPT-authenticated CLI usage does not provide a reliable dollar quote. `cost_usd=0` means **no known dollar amount from this model call**, not free usage. `cost_uncertain=true` and `subscription_usage_unknown_dollars` remain attached. Full-run known dollars include Exa estimates, while Codex subscription usage remains unpriced. The dollar allowance cannot cap subscription usage. No model/provider fallback is performed.

## References

[Official non-interactive Codex documentation](https://learn.chatgpt.com/docs/non-interactive-mode) documents JSONL events, usage and structured output. [Official CLI reference](https://learn.chatgpt.com/docs/cli/reference) documents ephemeral sessions, configuration isolation and authentication behavior.

## Verified smoke result

The real intake smoke test succeeded on October 24, 2026 using the locally configured `gpt-6-luna` model request. It reported 14,312 input and 115 output tokens. The saved result is `data/evaluations/codex-smoke.json`. It preserved the supplied product ID and $119 price; unspecified capabilities remained unknown. This proves one structured intake call, not research, profile generation, or model quality across all stages. The initial attempt was prevented by workspace runtime-file restrictions; the same test succeeded with required local runtime access. No Exa call was made.
