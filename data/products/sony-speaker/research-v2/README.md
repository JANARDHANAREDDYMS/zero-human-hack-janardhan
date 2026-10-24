# Revised Sony research candidate

Start with [population-review.md](population-review.md). Then inspect [evidence.json](evidence.json), [specification.json](specification.json), [segmentation-quality.json](segmentation-quality.json), [population-summary.json](population-summary.json), and [customers.json](customers.json).

This directory uses the generic v2 pipeline contracts. The parent Sony files are the original v1.1 demo dataset; they are preserved and remain referenced by older simulation fixtures. Do not concatenate the two populations or describe 100 distinct research participants.

Recheck contracts:

```sh
PYTHONPATH=backend/src python3 -m customer_generation validate --spec data/products/sony-speaker/research-v2/specification.json --evidence data/products/sony-speaker/research-v2/evidence.json --intake data/products/sony-speaker/research-v2/brief.json
```

Reproduce profiles to a new output path using `customer_generation sample --spec … --evidence … --output /tmp/sony-reproduced.json`. The seed and all sampling rules are saved in specification.json; no API is needed. This was manually prepared research, not an executed live pipeline run.
