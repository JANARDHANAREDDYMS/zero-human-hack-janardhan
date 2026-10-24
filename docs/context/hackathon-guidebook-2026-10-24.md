# NYC guidebook: detailed reading notes

Read in full through the end of the public Notion page on 2026-10-24 using the browser. Firecrawl failed DNS resolution; the web reader could not access the page. Browser accessibility text exposed the main page, its tables, and all sections through Solari redemption. No account sign-in or redemption was performed. These are paraphrased notes, not a verbatim export. Quick links were anchors within the same document, not separate guide chapters. Sponsor homepages and Slack invitation were not joined or redeemed.

Source: [Official guidebook](https://app.notion.com/p/GUIDEBOOK-Zero-Human-Company-Hackathon-NYC-by-Terac-4002f66e615381b3adcbf72fe8123955).

## Universal requirements

- Build one or more agents that operate a company autonomously, covering product, marketing/outreach, sales, payments, decisions and related operations.
- All projects must use **Terac MCP**. The criteria also describe calling Terac API/MCP to recruit participants; because the universal rule explicitly names MCP, our plan must include an actual MCP use, not presume API-only suffices.
- Collect real human input during the hackathon and use it to make the project measurably better. Supply something people can use, react to, label, rate, rank or compare. Show a clear before/after improvement. Terac handles recruitment and incentives. General-population studies are encouraged for fast results.
- The agent-run company must be built on **Whop**, and **all payments must go through Whop**. The payments section explicitly rules out setting up Stripe.
- Revenue must be genuine and organic. A test checkout or synthetic purchase cannot count. A technical payment integration alone does not meet the revenue-based track criterion.
- Multiple tracks are permitted when their criteria are met.

## Logistics and schedule

Location: Whop HQ, 300 Kent Ave #501, Brooklyn, NY 11249. A Slack invitation is linked for communications/questions/help. Submission link is described as opening at 5:30 PM; no actual submission form was visible in the guide at reading time.

| Time on October 24 | Activity |
|---|---|
| 8:30–9:00 AM | Check-in/doors |
| 9:00–9:15 AM | Welcome |
| 9:15–9:45 AM | Opening, rules, criteria, tracks, API-key/credit document |
| 9:45 AM–6:45 PM | Build time |
| 11:45 AM–12:15 PM | Lunch |
| 6:45–7:00 PM | Submissions lock window as listed |
| 7:00–8:00 PM | Dinner/explore Williamsburg |
| 8:00–9:00 PM | Closing and winners |

The submission-lock row is a window rather than an unambiguous exact cutoff; plan to finish by 6:45 PM and confirm the organizer's final submission instructions. The guide supplies no detailed submission format or advance-work policy; do not invent one. Earlier references to “tomorrow” are historical conversation context: this guide names October 24, which matches the current local date.

## Current judges, affiliations as listed

| Judge | Current guide affiliation | Additional background listed |
|---|---|---|
| Ilia Bolgov | Co-founder/CEO, Touchmark (YC S26) | Revolut product owner; Imperial maths/finance |
| Vedant Agarwala | Founding engineer, Movo | Co-founder/CTO, CodeParrot (YC W23) |
| Christine Dumont | Engineering, Mirage | Lyft and Spotify engineering |
| Marcel Spisak | Founding engineer, Endeavor | Founder, getdressed |
| Shubh Mittal | Founder, Stealth | xAI MTS; AGI Inc. engineer |
| Anubhav Sigdel | Founding engineer, Lora | No additional line visible |
| Alparslan Cetin | Computer vision researcher, Martinos Center (MGH, Harvard Med & MIT) | MIT CSAIL research; Harvard CS/full ride |

These are the **current guide's** panel, superseding the earlier recap's historical panel for this event. Names/roles are organizer-provided descriptions, not independently verified employment records.

## Tracks and prizes

| Track | Prize | Published emphasis |
|---|---|---|
| Best Overall Project | $1,000 | Creativity, technical skill, overall impressiveness; main panel decision |
| Best Agent-Run Company | $1,000 | Real revenue earned during the event and potential for a successful continuing company |
| Second Best Agent-Run Company | $500 | Guide describes second-most real revenue plus continuing-company potential |
| Best Use of Terac | $500 first prize | Human-in-the-loop demonstrated through Terac MCP |
| Best Use of Exa | $1,000 in Exa credits | Describes Exa as search/research infrastructure for agents; no more specific scoring rubric supplied |
| Best Use of Solari | $600 in Solari credits | Describes fast browser/sandbox/desktop infrastructure; no detailed scoring rubric supplied |

There is no point-based judging weight breakdown, demo-duration rule or explicit Lovable prize listed. Do not infer that the biggest profile count wins or that every integration earns points automatically.

## Sponsors, partners and benefits

Terac hosts; Whop, Lovable, Exa and Solari are listed sponsors/tools. Community partners: 529 Labs (creator residency/community) and Bond AI (in-person AI community).

- Terac: an event redemption link is supplied; exact credit amount is not stated. General-population studies are reiterated.
- Exa: event coupon provides $50 in Search API credits.
- Lovable: code grants Pro Plan 1 with 100 credits and its features. Redeem by event end, and do not share outside the event. Instructions: sign in/create account, Settings → Plans & Credits, select the **monthly** Pro Plan 1, apply the event code at checkout. This document does **not explicitly confirm** that the grant funds runtime model inference through our worker; verify actual workspace AI billing/eligible balance before relying on it.
- Whop: sign up and run ads; no quantified Whop grant is listed.
- Solari: one free Starter month, described as a $20 value.

Event redemption codes and the invitation/redemption tokens are deliberately not republished in these notes. Consult the original guide privately. No benefits were redeemed by the agent.

## Consequences for our build

1. A paid customer-research service delivered via Whop is the company. Our hypothetical Sony and other offers are simulation inputs, not items we actually manufacture or sell.
2. Implement one working simulation/report path, then a real service checkout, payment verification and fulfillment on Whop. Build actual customer acquisition into the demo plan: an available checkout alone cannot produce organic demand.
3. Set up **Terac MCP**, publish a short general-population comparison or usability task with a concrete artifact, and save feedback collected during the event. Apply a specific correction and show before/after results. Merely recording feedback does not meet the stated improvement criterion.
4. A suitable first human test: compare a baseline and revised research report or product presentation; measure comprehension/usefulness or identify a specific misleading assumption. Prespecify what changes, preserve individual responses and avoid claiming the responses calibrate every buyer preference.
5. Exa should preserve offer facts, buyer discussions and source qualifications visibly in the report. That demonstrates a substantive role in the workflow.
6. Remove Stripe from this event's payment plan. Keep legacy environment placeholders inert; do not build a Stripe flow for the event.
7. Lovable remains intended for app/runtime AI, but the event benefit's runtime eligibility is still an integration question, not a verified entitlement.

All mandatory integrations, organic sales and the Terac before/after are still pending live implementation/proof. Reading this guide does not authorize redemption, joining Slack, launching a paid study, publishing or charging anyone.
