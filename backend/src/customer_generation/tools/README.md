# Tool adapters

Reserved for narrow Exa and model-provider adapters when implementation starts. No external API calls or SDK setup are introduced by this directory scaffold.

Exa retrieves evidence. Model access is injected so stages can be evaluated with saved responses and later connected to an affordable runtime. Sampling, validation, and artifact storage stay deterministic Python functions; tool wrappers should not duplicate those implementations.

Credentials will come from environment/configuration, never checked-in product files or prompts. Do not put payment or Terac adapters here in this phase.
