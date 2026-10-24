# Versioned agent instructions

Implemented: shared methodology and intake_extract, research_extract, propose, review, and correct bundles. The correction stage also includes the population-specification instructions. versions.json defines the mapping and bundle version.

InstructionRegistry snapshots files and computes stage-specific hashes. The model client sends instructions separately from payload; bridge contract 1.1 must acknowledge version and hash. Retrieved text and prior outputs remain untrusted payload data, not prompt-file selectors.

Prompt wiring and review contracts are tested offline. Model obedience, extraction fidelity, coverage quality, and usefulness have not been validated live. See the HTML implementation guide for the full diagram and instructions.
