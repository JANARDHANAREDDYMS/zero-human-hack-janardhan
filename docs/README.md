# Saturday-Hack preparation

Goal: prepare a focused demo for the Zero-Human Company Hackathon on October 24, 2026. This is a hackathon prototype, not a trained customer-behavior model.

Structured product records now live in ../data/ using the restored layout. This docs directory retains readable context and research snapshots. Frontend, backend, and agent tooling come later.

## Contents
- context/project-decisions.md: current scope, budget, architecture, and open questions.
- context/customer-population-process.md: recovered profile-generation decisions.
- context/hackathon.md: event, prior judges, showcased projects, and demo implications.
- context/recovered-population-discussion.md: selected original messages from the older hosted chat.
- context/product-briefs-pasted.txt: the user's supplied product context, preserved verbatim.
- research/sources/: previously retrieved event pages, with source URLs in context/hackathon.md.
- products/: product-specific JSON inputs and readable review notes.
- schemas/: reserved for shared machine-readable contracts after the fields are finalized.

## Product data convention
Each confirmed product will have brief.json, evidence.json, segments.json, sampling-rules.json, customers.json, and population-review.md. Research and profiles have not yet been generated. Missing files mean work is pending, not that empty datasets are complete.

Use Markdown for decisions and reviews, JSON for structured inputs. Keep source IDs, assumption labels, population versions, and seeds. Freeze reviewed populations for comparisons. Store journey histories separately from customer profiles when the simulation is built. Real observations and synthetic results must remain distinguishable.

## Canonical data
See [data architecture](../data/architecture.md). Update product briefs in ../data/products/; docs/data/product.html is the preserved earlier snapshot.
