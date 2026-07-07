# LeadGenius — MVP Roadmap, Scaling Roadmap & Future Expansion

---

## 1. MVP Roadmap (12 weeks, solo-founder-buildable)

**Definition of MVP done:** a stranger uploads 50 leads, gets research briefs with citations and a scored 5-step sequence, reviews and exports to Instantly — without talking to us.

### Phase 0 — Foundations (Week 1–2)
- FastAPI skeleton, SQLite schema + db module, auth (email + Google OAuth), workspaces, Jinja/Tailwind/htmx shell with dark mode
- Jobs table + asyncio worker loop; credits ledger
- Tests wired to run on every change (project rule)

### Phase 1 — Ingest & Research (Week 3–5)
- CSV/Excel upload, column auto-mapping, validation report, dedupe
- Crawler (httpx + trafilatura, robots-respecting, domain cache) + search enrichment
- Extraction pass → findings with citations; analysis pass → ranked hypotheses
- SSE live-research view (**this is the demo that sells — build it well**)

### Phase 2 — Generate & Review (Week 6–8)
- Offer Profile wizard; layered prompt assembly; default 5-step sequence structure
- LinkedIn connect + DM, opener snippets, subject variants
- Scoring (LLM judge + slop lexicon + shape checks), auto-regenerate under threshold
- Review Queue with keyboard flow, evidence-on-hover, bulk approve

### Phase 3 — Export, Billing, Polish (Week 9–10)
- CSV / Instantly / Smartlead export formats; copy-to-clipboard
- Stripe (subscriptions + credit top-ups), usage page, credit meter
- Onboarding flow with sample-leads demo list; empty states; activity log

### Phase 4 — Private Beta (Week 11–12)
- 10 design partners (agency contacts + Upwork clients), white-glove onboarding
- Instrument activation funnel (signup → first export); fix the top 3 drop-offs
- Collect before/after reply-rate stories → first case studies

**Deliberately cut from MVP:** team seats, API, Sheets sync, CRM integrations, campaigns/stats import, prompt-library UI (system defaults only), call scripts. All fast-follows.

### KPIs for MVP success (day 60 of beta)
- Activation (signup → first export): > 40%
- Median time-to-first-export: < 15 min
- Bulk-approve rate at score ≥ 80: > 70% (proxy for output quality)
- ≥ 3 users voluntarily paying · ≥ 1 documented reply-rate case study

---

## 2. Scaling Roadmap (post-MVP, by quarter)

### Q1 after launch — Close the loop
- Instantly + Smartlead API integrations: push campaigns directly, **pull reply stats back**
- Hypothesis leaderboard analytics; prompt auto-tuning from reply data
- Team seats + roles, Google Sheets sync, Zapier/Make, public REST API
- Editable prompt/template library UI

### Q2 — The agency quarter
- White-label audit report generator (PDF, agency branding) — the Agency-tier killer feature
- Client sub-workspaces + client-level analytics rollups
- Comparison landing pages (/vs/clay, /vs/instantly), affiliate program (20% recurring)
- HubSpot + Pipedrive integrations, marketplace listings

### Q3 — Depth & verticals
- Industry research presets (dental, logistics, SaaS, recruiting, real estate…) with vertical-specific hypothesis categories and exemplar sequences
- Competitor-analysis module (prospect vs their 3 competitors → sharper angles)
- Multilingual outreach (Danish first — founder's proven market — then German/Spanish/French)
- Lead scoring + list prioritization ("research these 40 first — highest fit")

### Q4 — Autonomy (earn it, don't lead with it)
- **AI SDR mode:** auto-research → auto-generate → auto-queue to sending tool for leads scoring ≥ threshold; human handles exceptions only
- Reply handling assistant: classify replies, draft responses, meeting-prep note on positive replies
- Enterprise pack: SSO, audit exports, DPA, SOC 2 in progress

### Infra scaling triggers (mirrors technical doc)
SQLite→Postgres at >5k leads/day · dedicated crawl pool at latency complaints · batch/model-routing when LLM spend > 25% of MRR.

---

## 3. Future Expansion Opportunities (ranked by strategic fit)

1. **AI SDR agent (autonomous prospecting)** — natural endpoint; priced $500–1,000/mo undercutting 11x/Artisan with a quality track record.
2. **Website audit product** — the research engine pointed at *one* company produces a sellable audit; standalone $99 product + agency white-label. Near-zero marginal build.
3. **Intent & trigger detection** — monitor prospect domains for changes (new pricing page, hiring spike, funding) → "reach out now" alerts; upgrades us from batch tool to always-on system of action.
4. **Meeting booking + calendar** — after reply handling; completes reply → meeting loop.
5. **Voice AI follow-up** — call scripts already generated; connect to voice agents (founder's agency domain expertise) for call-first verticals like dental/local services.
6. **Proposal generator** — research brief + call transcript → tailored proposal; moves us up-funnel into deal support.
7. **Sales coaching** — score human-written replies with the same rubric; Lavender's market, our evidence-based twist.
8. **Prompt/preset marketplace** — community-created industry packs, 20% rev share; turns power users into distribution.
9. **CRM-native app** (HubSpot first) — research briefs living on CRM contact records; enterprise beachhead.
10. **Pipeline management** — only if pulled by customers; avoid becoming a mediocre CRM.

Sequencing rule: nothing autonomous ships until the feedback loop proves output quality with data; every expansion must reuse the research engine (the core asset).
