# Expert availability checks

Every product uses `data/terac/expert-policy.json`: one English-speaking expert per improvement, currently residing and performing the work in the United States. No outside-US fallback. Expertise comes from the saved concern; no model calls are needed to apply the targeting policy.

The MCP adapter only exposes read operations and non-binding feasibility requests. Creating studies, launching, recruitment, invites and payments are deliberately absent. A `RECEIVED` response is pending, not an available expert or a quote. `RESPONDED` carries Terac's price; it still does not identify a booked person. `LOST` / `NOT_PURSUED` do not explain why a request closed.

Use the same command for any product's saved `concerns.json`:

```bash
python3 backend/scripts/check_expert_availability.py --concerns PATH_TO_CONCERNS_JSON --output OUTPUT_DIRECTORY
```

The default only prints a local plan. Add `--request-feasibility` to submit the scoped checks; add `--refresh` instead to read existing statuses. The key is loaded privately from `backend/.env`. No automatic feasibility requests are triggered by page loads or concern generation.

Requests are written before sending, responses are retained, repeated commands reuse existing responses, and ambiguous failures require dashboard inspection rather than an automatic resubmission. Status refreshes are bounded to once per two minutes while pending; terminal/quoted results are cached. The command does not monitor in the background.

Current Sony checks: `data/terac/sony-availability-20261024/requests-us-english/`. The returned Terac dashboard URL is preserved verbatim in each response. Future opportunity creation must enforce the verified US residence and English filters plus specialist screening, and requires its own implementation and authorization; it is not included here.


## Product-specific qualification gate

A generic specialty label or US/English eligibility alone cannot be submitted. Each saved improvement must carry an `expert_brief` with a role, product domain, at least two relevant hands-on experience requirements, at least two qualification checks, a work type and a concrete deliverable. Work types distinguish review, implementation planning and implementation; implementation requires confirmed access to the product and a reviewable change request. These structural requirements do not prove that any person is qualified; sourcing and screening must verify the experience.

Existing concerns containing only `suggested_expertise` now require a scoped expert brief before new requests. They are not silently converted into broad expert searches. The CodeSensei scoped example is in `data/terac/codesensei-specialists-20261024/scoped-concerns.json`, prepared from the user's requested specialist categories and saved concern text. This is an explicitly prepared case, not a claim that the model's expert-scoping stage was upgraded. The model-backed automatic generation of these detailed briefs has not been implemented yet. Read-only `--refresh` continues to work on old request records. Earlier Sony requests retain their actual original scope and are not presented as updated or cancelled.

## Manual applicant review

The local demo has a **Review experts** page at `/expert-review`. Reading it makes no Terac or model calls. Workspaces and applicant screening answers are private under `backend/var/expert-review/` (ignored by Git), and the page/API use the existing loopback host/origin and demo-token controls.

Register the saved scoped concerns and existing feasibility summary with `backend/scripts/prepare_expert_review.py --concerns PATH --feasibility PATH --workspace NAME`. The default is local only. `--refresh` reads provider responses; `--create-drafts` additionally prepares only confirmed, priced scopes, with explicit US/English hard filters, work-location screening, product-specific experience questions, manual applicant review, and a manually reviewed PDF/text-file deliverable. Draft creation does not launch recruitment. The proposed recruitment window is seven calendar days and is shown explicitly; it is not a completion guarantee.

After a separate launch in Terac, **Refresh quotes and applicants** reads current applicants. Names are displayed only if actually provided; otherwise an applicant identifier appears. Screen answers and criteria are shown without an AI ranking. You must check the review acknowledgement and explicitly confirm the selected **Invite** or **Decline** action. Invitations let the chosen person start work on an already launched study. Each decision rechecks the opportunity status, one-person target, manual-review mode, exact US/English filters and current applicant snapshot. Changed answers, ambiguous outcomes and duplicate decisions stop rather than silently repeating a mutation.

The launch tool remains absent from both the local API and MCP allowlist. No person has been invited during implementation or tests. The provider has not yet priced the six CodeSensei requests, so no live drafts or applicants were created. Draft creation and applicant decisions are covered by mocked-provider tests; real applicant response compatibility awaits an authorized launched study.
