# Saturday-Hack

An autonomous customer-research service for the Zero-Human Company Hackathon. The current build scope is competitive research and synthetic customer generation, operated by one LLM agent inside a code-controlled harness.

## Project layout

```text
saturday-hack/
  backend/
    README.md
    src/
      customer_generation/
        README.md
        prompts/                 # Stage instructions for the same agent
        tools/                   # Exa, model access, sampling, and validation boundaries
    tests/                       # Future behavioral and contract tests
  data/
    architecture.md
    population-summary.md
    schemas/                     # Shared product/customer/population contracts
    products/                    # Six prepared demo datasets
    simulation/                  # Contract for tomorrow's shopping simulation
    tools/                       # Existing local sampler and validation utilities
    runs/                        # Future isolated generation runs; no runtime outputs yet
  docs/
    context/                     # Decisions and recovered discussions
    research/                    # Research source snapshots
    data/                        # Earlier reference snapshots
```

## Current status

Phases 1–4 are implemented: generic sampling, staged harness, saved state, Exa/model-function clients, versioned prompts, and structured qualitative-review gates. There are 65 passing offline/mocked tests. No live Exa/model connection, deployed Lovable function, sponsor-credit coverage, or actual model-quality evaluation has been verified.

The six original examples contain 300 synthetic profiles. The new pipeline also has explicitly offline keyboard acceptance runs. See the [living HTML implementation guide and detailed diagram](docs/context/implementation-and-instructions.html) for exact status, files, setup, and commands.

## Sponsor roles

- Exa: competitor and surrounding-market evidence.
- Lovable: intended app construction and runtime model access, subject to available runtime credits.
- Terac: later targeted human feedback on consequential assumptions or results.
- Whop: later payment/access for our customer-research service, not simulated purchases.
- Stripe: possible payment alternative; user details and choice pending.

Only research and customer generation are in the current implementation scope. Payment providers and Terac are not dependencies of population generation.

## Existing utilities

Run from the repository root:

```sh
python3 data/tools/generate_populations.py --product sony-speaker --pilot
python3 data/tools/validate_prepared_data.py
```

The sampler uses the Python standard library; schema validation additionally needs `jsonschema`. Full regeneration overwrites that product's generated population and review. The existing tools remain in place so current paths and reproducibility checks keep working; any reuse from the backend should preserve one implementation rather than copy its sampling logic.
