# LeadGenius — Build Phases (implemented)

The MVP is built and passing tests. This maps the master-prompt scope onto shippable phases and records what each one delivers in code. Stack per CLAUDE.md: Python 3.10+, FastAPI, SQLite behind an isolated `app/db` layer, Jinja2 + Tailwind-style CSS + htmx, tests per backend unit, no logic comments.

LLM and network calls run through stub fallbacks when no LLM key / `SEARCH_API_KEY` is present, so the whole product runs and tests deterministically offline. Set a free-tier key (`GROQ_API_KEY`, `GEMINI_API_KEY`, or `OPENROUTER_API_KEY`) or `ANTHROPIC_API_KEY` to switch to live generation + web research with zero code change; free-tier providers are preferred over Anthropic when both are set.

## Phase 0 — Foundations
- `app/config.py` — env-driven config, stub flags, slop lexicon
- `app/db/` — `schema.sql` (full schema), `core.py` (WAL SQLite, thread-local conn), `queries.py` (all data access)
- `app/security.py` — pbkdf2 password hashing, signed session cookies
- Auth + workspaces + credits ledger + jobs table
- **Tests:** `test_auth_routes.py`, `test_credits.py`

## Phase 1 — Ingest & Research
- `app/services/ingest.py` — CSV parse, column auto-mapping, domain derivation, dedupe
- `app/fetch/crawl.py`, `app/fetch/search.py` — crawler + web search with caching and stubs
- `app/services/research.py` — findings with mandatory source citations, tech detection, brief digest
- `app/services/analyze.py` — ranked pain/opportunity hypotheses with evidence + confidence
- **Tests:** `test_ingest.py`, `test_research_analyze.py`

## Phase 2 — Generate, Score & Review
- `app/llm/prompts.py` — layered prompt assembly (system voice + offer + research + task + exemplar)
- `app/services/write.py` — proven 5-step sequence, LinkedIn connect/DM, step-5 pivot
- `app/llm/score.py` — 0–100 rubric (specificity, evidence, slop, brevity, CTA) + auto-critique
- `app/routers/review.py` + `templates/review.html` — keyboard review queue, evidence display, edit/approve/regenerate
- **Tests:** `test_write_generate.py`, `test_score.py`

## Phase 3 — Pipeline, Export & Billing
- `app/jobs/pipeline.py`, `app/jobs/worker.py` — job orchestration (research → analyze → write), SQLite-as-queue worker, synchronous `process_list_now`
- `app/services/export.py` — CSV / Instantly / Smartlead formats (full sequence in columns)
- Credit charging per lead, usage ledger
- **Tests:** `test_pipeline.py`, `test_export.py`

## Phase 4 — UI & API
- `app/templates/` — dashboard, lists, list detail, onboarding, review, exports, auth (dark-mode default, theme toggle)
- `app/routers/api_v1.py` — REST endpoints (lists, leads, export, usage)
- `app/main.py` — app wiring, lifespan worker, static files
- **Tests:** `test_flow_routes.py` (full upload→research→review→approve→export)

## Phase 5 — Live Research Streaming
Research is now a real background job with a watch-it-happen view (the activation "magic moment").
- `app/jobs/pipeline.py` — `enqueue_research` queues a job and marks the list `researching`; `_run_research` emits a `research_events` row at each stage (start → researching → found → analyzed → written → complete) with a running `done/total`
- `app/routers/research.py` — live view page + `/research/{id}/stream` SSE endpoint (polls `research_events`, streams `data:` frames, ends on `complete`, honors client disconnect)
- `app/templates/research.html` — `EventSource` client: live findings feed, animated progress bar, "Open review queue" on completion, reconnect fallback
- DB-backed events (not in-memory) so a mid-run reload replays cleanly and survives across the worker's thread boundary
- The research route now redirects to `/research/{id}` instead of blocking; the worker (started in `lifespan`) drains the queue
- **Tests:** `test_research_stream.py` (enqueue, worker drain, event phases, incremental `events_since`); updated `test_flow_routes.py`. Verified live over HTTP with `scripts/smoke_stream.py`.

## Phase 6 — Campaign Feedback Loop & Hypothesis Leaderboard
The defensibility moat: reply data flows back in and tunes which angles the AI reaches for.
- `campaigns` + `campaign_stats` tables (unique per campaign+lead); a campaign is recorded on export
- `app/services/feedback.py` — parse a results CSV (email + sent/opened/replied/meeting, booleans or 0/1), match rows to leads by email, tag each with the hypothesis **category** that lead's Email 1 actually used, aggregate into a reply-rate leaderboard, and derive per-category tuning weights (only categories with 5+ sends count, so noise can't move rankings)
- `app/services/analyze.py` — `_reweight` re-ranks each new lead's hypotheses by `confidence × (1 + category_weight)`, so angles that earn replies in this workspace float to the top automatically
- `app/routers/analytics.py` + `analytics.html` — funnel (researched → approved → sent → replied), hypothesis leaderboard with reply-rate bars, results-CSV import
- API: `/api/v1/leaderboard`, `/api/v1/campaigns`
- **Tests:** `test_feedback.py` (parse, match, leaderboard ordering, weight threshold, re-rank promotion, funnel), `test_analytics_routes.py`. Verified live with `scripts/smoke_feedback.py`.

## Phase 7 — White-label AI Opportunity Audit
The Agency-tier revenue feature: point the research engine at one company and produce a client-facing report agencies resell.
- `audit_reports` table; `app/services/audit.py` runs research + analysis on a single domain (via a hidden per-workspace `source='audit'` list so it never pollutes lists or funnel counts) and composes an evidence-backed audit — exec summary + ranked opportunities, each with plain-language impact, a concrete recommendation, and source-cited evidence
- `app/branding.py` + `/settings` — per-workspace white-label branding (brand name, accent color, report title, contact line) stored in `workspaces.settings_json`
- `app/templates/audit_report.html` — a **standalone** client-facing page (no app chrome), styled with the agency's branding, print-to-PDF via `window.print()` with a dedicated `@media print` stylesheet
- Charges 1 credit per audit; API `/api/v1/audits/{id}`
- **Tests:** `test_audit.py` (report generation, evidence, hidden list, branding defaults/overrides), `test_audit_routes.py` (flow, branding-on-report, API). Verified live with `scripts/smoke_audit.py`.

## Phase 8 — Team Seats, Roles & Invites
The collaboration layer the Agency tier sells (multi-seat workspaces).
- `invites` table (single-use tokens, 14-day expiry); membership queries (role lookup, add/update/remove, seat counting including pending invites)
- Roles with strict ordering: **owner** > **admin** (manages team + settings) > **member** (runs research, exports, audits) > **reviewer** (review/approve only). Helpers in `deps.py` (`ROLE_RANK`, `has_min_role`, `forbid`)
- Route enforcement: reviewers get 403 on list creation, research runs, exports, stats import, and audit generation; settings and team management require admin+; owner can never be demoted or removed
- Plan-based seat limits from `config.PLAN_SEATS` (trial/starter 1, pro 3, agency 10, enterprise unlimited) — invite blocked with 402 when full
- `/team` page: member list with inline role change/removal, invite-link creation (shareable URL, no email dependency), pending-invite revocation, workspace switcher
- `/join/{token}`: logged-in users join instantly; new users sign up straight into the workspace with the invited role
- **Tests:** `test_team.py` (role rank, membership helpers, seat count, token expiry), `test_team_routes.py` (invite→join lifecycle, seat-limit 402, reviewer/member/admin permission walls, owner protection, workspace-switch membership check). Verified live with `scripts/smoke_team.py`.

## Phase 9 — Editable Prompt Library
The master prompt's "AI Prompt System": every prompt the engine uses is modular and editable per workspace.
- `prompt_templates` table (unique per workspace+slot); override CRUD in `queries.py`
- `app/llm/prompt_library.py` — slot registry (11 slots: voice, research, analysis, email steps 1–5, li_connect, li_dm, audit) with labels/groups/descriptions; `resolve(ws_id, key)` returns the workspace override or the default from `prompts.py`; saving blank content or the unchanged default clears the override
- `prompts.py` refactored: step specs live in `EMAIL_STEP_SPECS` / `LINKEDIN_SPECS`; `email_user`/`linkedin_user` accept an optional custom spec
- All four generation call sites resolve overrides: `write.py` (voice + per-step + LinkedIn specs, including the low-score auto-fix retry), `research.py` (extraction system prompt, workspace derived from the lead's list), `analyze.py` (analysis system prompt), `audit.py` (audit voice)
- `/prompts` page: grouped cards with Customized/Default pills, edit + save, reset-to-default; admins edit, members/reviewers get read-only textareas; API `GET /api/v1/prompts`
- **Tests:** `test_prompt_library.py` (default/override/reset, blank-clears, unknown-slot rejection, per-workspace scoping, generation actually uses overridden voice+specs via a complete_json spy), `test_prompts_routes.py` (page, save/reset, 404 unknown slot, member/reviewer 403 walls, API flags). Verified live with `scripts/smoke_prompts.py`.

## Phase 10 — Native Instantly / Smartlead Campaign Push
No more CSV round-trips: one click creates the campaign in the sending tool with the full personalized sequence.
- `integration_pushes` table; per-workspace API keys stored in `workspaces.settings_json` via new Settings fields (admin-only)
- `app/services/sender.py` — builds per-lead variable maps (`email_1_subject` … `email_5_body`) from approved assets only, then: **Instantly** (v2 API, Bearer auth) creates the campaign with a 5-step sequence templated on `{{custom_variables}}` and uploads each lead; **Smartlead** creates campaign → uploads sequences (subjects only on steps 1 and 3, matching the threaded-reply structure) → bulk-adds `lead_list` with `custom_fields`. Delays follow the proven cadence (0/2/3/3/4 days)
- Pushing records the push, ties into the feedback loop (`get_or_create_campaign(exported_to=provider)`), marks leads + list `exported`
- Exports page: Push buttons when a key is configured, Connect links to Settings otherwise, success/error banners, Recent pushes history
- `LEADGENIUS_SENDER_STUB=1` (default) short-circuits HTTP with canned responses so the whole flow runs offline
- **Tests:** `test_sender.py` (key/approval guards, full recording, exact Instantly + Smartlead payload shapes via `_post` spy, no-email skip), `test_push_routes.py` (error redirect, success + history, connect-vs-push UI states, foreign-list/provider 404s, reviewer 403, settings key save). Verified live with `scripts/smoke_push.py`.

## Phase 11 — Stripe Billing
Self-serve upgrades: the credit plans from `docs/03` become purchasable.
- `app/services/billing.py` — plan catalog (Starter $49/250 · Professional $149/1k · Agency $399/4k, seats from `config.PLAN_SEATS`); `checkout_url` creates a Stripe subscription Checkout Session with inline `price_data` (no dashboard setup needed) and workspace/plan metadata; `apply_plan` sets the plan and grants credits through the ledger; `handle_event` applies `checkout.session.completed` (purchase) and `invoice.paid` with `billing_reason=subscription_cycle` (monthly refresh — first invoice is skipped so the purchase never double-grants); metadata is read from the invoice's `subscription_details` fallback
- `/billing` page: current plan / credits / seats, plan cards with upgrade buttons (admin+), credit-history ledger; `POST /billing/webhook` verifies Stripe signatures in live mode
- Stub mode (`USE_BILLING_STUB` when no `STRIPE_SECRET_KEY`): checkout redirects to a mock Stripe page whose Pay button applies the plan for real, so the entire upgrade flow is demoable offline
- **Tests:** `test_billing.py` (apply/grant/ledger, unknown-plan rejection, event handling incl. renewal refresh and first-invoice dedupe), `test_billing_routes.py` (page, checkout redirect, mock payment, member 403, webhook 400 in stub mode, and upgrade lifting the team seat-limit 402). Verified live with `scripts/smoke_billing.py`.

## Phase 12 — Close the data-in / data-out loop
Many sources in, stats back automatically — the feedback loop no longer needs manual CSVs.
- **Ingest (12a):** `ingest.py` refactored around one shared row path (`_rows_from_dicts`) so validation + dedupe are identical for every source. Added: `parse_xlsx` (openpyxl, blank-row tolerant, cells coerced to strings), `parse_google_sheet` (accepts full URL or bare ID; live mode reads the link-shared CSV export endpoint — documented auth path is share → "Anyone with the link — Viewer"; `USE_FETCH_STUB` returns canned rows), and Apollo/Clay alias maps. Header normalization now folds underscores (fixes snake_case exports never mapping) and First/Last Name columns combine into `contact_name`. Upload form takes CSV/XLSX or a pasted Sheets link; list `source` records csv/xlsx/gsheets.
- **Stats pull (12b):** `sender.pull_stats(ws, list_id, provider)` finds the latest push (`latest_push_for_list`), fetches per-lead stats from Instantly (`GET /leads?campaign=`) or Smartlead (`GET /campaigns/{id}/statistics`), maps them to the stats-row shape, and feeds `feedback.import_stats` — same matching, same campaign row (`get_or_create_campaign`), same leaderboard and `_reweight` tuning as the CSV import. One "↓ Pull stats" button per row in the Exports push history; redirects to `/analytics?pulled=…` with a Synced banner. Stub mode returns deterministic stats (all sent, alternating opens, first lead replied), so the whole loop runs offline. Pulls are idempotent (stats upsert per campaign+lead).
- **Tests:** `test_ingest_sources.py` (Apollo/Clay mapping, xlsx parse + garbage rejection, sheet stub + ID forms, cross-source dedupe equality), `test_stats_pull.py` (guards, pull→leaderboard/funnel, idempotency, campaign reuse, route redirect, reviewer 403). Verified live with `scripts/smoke_roundtrip.py` (xlsx+sheet in → research → push → pull → leaderboard).

## Fix 1 — API-key authentication for /api/v1 (post-audit)
The public API previously accepted only the browser session cookie; programmatic access now works.
- `api_keys` table (workspace_id, name, `hashed_key`, created/last_used/revoked timestamps). Keys are `lg_` + 256-bit `secrets.token_urlsafe`, stored only as SHA-256 (`security.hash_api_key`) — high-entropy tokens need no slow KDF and the deterministic hash gives O(1) lookup. The raw key is shown exactly once.
- Settings → "API keys" panel: generate (admin+, named), one-time raw display with copy button and "you won't see this key again" notice, list with created/last-used, revoke button. Revoked keys 401 on next use.
- `api_v1._auth` accepts `Authorization: Bearer <key>` alongside the unchanged session-cookie path; resolves to the owning workspace, stamps `last_used_at`, and rate-limits key traffic per workspace (`LEADGENIUS_API_PER_WINDOW`, default 120/10 min → 429). Also closed a latent hole: `/api/v1/leads/{id}` now verifies workspace ownership like every other endpoint.
- **Tests:** `test_api_keys.py` (issuance produces a usable key shown once; Bearer succeeds on all 9 endpoints; missing/malformed/revoked → 401; last_used_at updates; per-workspace 429; cross-workspace 404s; only the hash is stored; reviewer role 403 on key management; session-cookie auth verified unchanged on all 9 endpoints).

## Fix 2 — Doc/field-name drift (post-audit)
The audit-claimed names `research_quality`/`quality_reason` appear nowhere in docs or code; the real drift was in `docs/02-technical-architecture.md`: a `thin_research` flag (actual: `thin`, `quality`, `thin_reason` on `research_briefs`) and an `llm_calls` metering table (actual: `spend_ledger`). Both corrected; `docs/06` and `README.md` already used the real names.

## Fix 3 — Live verification with active keys (Groq + Tavily, fetch stub off)
`scripts/verify_live.py <domain> [company]` runs one lead through the real pipeline against an isolated `data/live_verify` DB and prints pages, search hits, grounded findings with evidence, quality/thin verdict, and the generated email. Live results (2026-07-07):
- **posthog.com** (happy path): 5 pages crawled, 6 search hits, **10 grounded findings, quality 100/100, email scored 93** — every claim traced to a verbatim on-page snippet (pricing tiers, $100bn ambition, YC testimonial, LinkedIn/Indeed hiring). First attempt hit transient Groq free-tier 429s on extraction and degraded to 0 findings without crashing; retry succeeded.
- **zzqwv-freightworks-void.example** (thin gate): DNS failure caught before any crawl spend; Tavily returned 6 junk results, grounding dropped all of them; quality 15/100 → thin, reason "domain does not resolve (dead or mistyped)", lead `needs_review`, and the generated email was the honest fallback ("I couldn't find enough public detail… I'd rather not invent it"), not a fabrication.
- **flexport.com** (grounding audit): 4 pages, 14 findings, quality 100/100, email 93. 12/14 evidence snippets genuinely support their claims; 2 industry-news findings (ocean/air-cargo market articles) passed grounding despite being about the market rather than Flexport — provenance is enforced, aboutness is not (known keyword-heuristic limit, logged for a future relevance pass).
- **Model verdict:** MODEL_FAST (`llama-3.1-8b-instant`) extraction is adequate — verbatim-faithful snippets, no invention; flaws are cosmetic (free-text `kind` enum drift, occasional claim/snippet pairing sloppiness). Left as-is; MODEL_SMART would cost ~4× tokens and has tighter free-tier rate limits (more 429s), for no observed recall gain.
- **Real-world cost:** `/healthz` after all runs: `spent_today_usd 0.12, calls_today 48` — $0.04/lead, entirely Tavily (4 source queries × $0.01); Groq free tier = $0 LLM cost. ~17% of Groq calls 429'd under burst; the client's stub-fallback absorbed every failure. Tech-signal false positive noted: prose mentions of "shopify"/"salesforce" in page HTML can register as tech hints.

## Fix A/B/C — Accuracy gaps from live hand-verification (post-audit 2)
Live reads of Flexport/Project44/Zocdoc/Redfin output surfaced a failure mode between
"no research" and "good research": leads with zero *usable* grounded findings could
still ship confident emails.
- **Fix A (claim=evidence breach):** `research_quality()` now treats the post-grounding
  finding count as a hard input — zero grounded findings caps quality at
  `QUALITY_FLOOR - 1` no matter how many pages/search hits exist, routing the lead to
  the honest fallback + `needs_review`. Redfin before (audit): 0 findings survived yet
  quality 64/"medium", and a personalized email shipped built on "Redfin's
  *hypothetical* B2B arm" speculation. Redfin after (live, 2026-07-07): 11 grounded
  findings (Crunchbase $85.2M IT spend, Trustpilot 2.2/5, "1% listing fee", live
  hiring), quality 99/100, email scored 93 — and when the same input produced zero
  findings on a Flexport re-run, quality capped at 39 → thin → the honest fallback,
  not a fabricated email.
- **Fix B (self-contradicting hypotheses):** `ANALYZE_SYSTEM` now forbids proposing a
  capability the findings show the company already has, and `analyze._drop_contradicted`
  backstops it (capability markers in evidence — "AI-powered/-driven/run by AI",
  "fully automated" — vs hypotheses proposing that same theme with absence framing).
  Verified live on Flexport: every generated hypothesis proposed AI automation against
  findings saturated with "AI-powered platform"; all were dropped and generation fell
  back honestly. Rich-brief-but-no-angle leads get distinct copy ("plenty of public
  detail, but nothing that gave me an angle") instead of the thin-research message.
- **Fix C (stale signals framed as fresh):** findings' dates now flow into the analyze
  prompt; hypotheses/emails whose dated evidence is all older than
  `LEADGENIUS_STALE_SIGNAL_DAYS` (365) get temporal framing stripped
  ("recently"→"previously", "just raised"→"raised", etc.) in `analyze._neutralize_stale`
  and at email/LinkedIn generation. Project44's 2021-funding case no longer reads as
  "recent."
- **Live-run hardening found two real crashes:** Groq returning a bare JSON array
  (`'list' object has no attribute 'get'` on Project44) and `"snippet": null` breaking
  a NOT NULL insert (Zocdoc) — all `complete_json` call sites now normalize shape and
  null fields. Extraction also retries once on `MODEL_SMART` when `MODEL_FAST` returns
  zero findings despite source material (observed 8B variance: identical Flexport input
  gave 14 findings in one run, 0 in another).
- **Known gap (logged, not fixed):** extraction can pull consumer/patient-narrative
  testimonial content as "findings" on healthcare-vertical sites (Zocdoc blog patient
  stories); none reached a final email, but source-targeting per page type needs a
  future pass. Related: grounding enforces provenance, not aboutness — market-news
  articles about the industry (not the company) can still pass.
- **Tests:** `test_thin_research.py` (+3: rich-but-zero-findings forces thin, one
  finding restores scoring, end-to-end honest fallback), `test_analysis_consistency.py`
  (9: contradiction drop/keep, stale neutralization incl. end-to-end email, no-angle
  copy), `test_llm_response_shapes.py` (8: bare-array/null-field normalization, non-dict
  fallbacks, smart-model retry, no-call-without-sources). Suite: 208 passing.

## Not yet built (documented in roadmap)
Scheduled auto-pull (cron), CRM integrations, AI SDR mode, credit top-up packs, Stripe customer portal (downgrades/cancellations). See `docs/04-roadmap.md`.

## Run it

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # unix

pytest                                              # 27 tests
uvicorn app.main:app --reload                       # http://127.0.0.1:8000
```

Offline (stub) mode is the default. To go live:

```bash
setx GROQ_API_KEY "gsk_..."              # free-tier LLM (or GEMINI_API_KEY / OPENROUTER_API_KEY)
setx ANTHROPIC_API_KEY "sk-ant-..."      # Claude generation (used only if no free-tier key is set)
setx LEADGENIUS_LLM_PROVIDER groq        # optional: force a provider; auto-picks groq > gemini > openrouter > anthropic
setx SEARCH_API_KEY "tvly-..."           # real web research (Tavily)
setx LEADGENIUS_FETCH_STUB 0             # enable live crawling
setx LEADGENIUS_SENDER_STUB 0            # live Instantly/Smartlead pushes (keys per workspace in Settings)
setx STRIPE_SECRET_KEY "sk_live_..."     # live Stripe checkout + webhook
setx STRIPE_WEBHOOK_SECRET "whsec_..."   # webhook signature verification
setx LEADGENIUS_BASE_URL "https://app.yourdomain.com"
```

For a public demo, leave `LEADGENIUS_SENDER_STUB` and Stripe unset — live sends and
charges from a demo are a liability.

Safety rails (on by default, tune via env):

```bash
setx LEADGENIUS_DAILY_BUDGET_USD 5.0     # global daily LLM+search spend kill-switch
setx LEADGENIUS_REQUEST_MAX_USD 0.10     # per-request spend ceiling
setx LEADGENIUS_DAILY_LLM_CALLS 1000     # daily LLM call cap (protects free tiers too)
setx LEADGENIUS_UPLOADS_PER_WINDOW 10    # uploads per IP+user per 10 min
setx LEADGENIUS_RESEARCH_PER_WINDOW 5    # research runs per IP+user per 10 min
setx LEADGENIUS_QUALITY_FLOOR 40         # below this research quality: honest generic fallback, needs_review
setx LEADGENIUS_APPROVAL_FLOOR 40        # assets scoring below this cannot be approved
setx LEADGENIUS_CRAWL_BUDGET_S 25        # total crawl time budget per lead
setx LEADGENIUS_CONTACT_URL "https://app.yourdomain.com/bot"   # shown in the crawler User-Agent
```

When the budget or call cap is hit, LLM calls degrade to deterministic stubs and web
search returns nothing — the app stays up, spend stops. `/healthz` reports spend,
call count, and whether the kill-switch has tripped. Trial workspaces are capped at
25 leads per list (`PLAN_LEAD_CAPS`).

The crawler honors robots.txt (including crawl-delay, capped at 5s), checks DNS
before spending a crawl, retries transient failures twice with exponential backoff,
skips non-HTML content, giant pages, and off-domain redirects, and identifies itself
with a contact URL. Research findings that can't be traced to crawled or searched
source text are dropped; leads whose research quality lands below the floor get an
honestly-generic sequence flagged for manual review instead of fabricated
personalization.

Research depth (Tier 3): web search fans out to four kind-tagged source queries
(news; hiring via LinkedIn/Indeed/Greenhouse/Lever; funding via
Crunchbase/Dealroom/TechCrunch; reviews via G2/Capterra/Trustpilot), each
budget-guarded. Search results carry publication dates; stale signals are
discounted in finding confidence and in the research-quality score, and dates show
next to findings in review. Tech-stack detection reads real signals (script tags,
asset domains, response headers) from raw page HTML, not just prose inference. Thin
leads get a "Dig deeper & regenerate" action (1 credit) that bypasses the crawl
cache, doubles the time budget, crawls seven extra paths, forces fresh search, and
regenerates. The review queue is framed as human-in-the-loop: the AI drafts, the
user approves.

Operational honesty (Tier 2): every researched lead carries a high/medium/low
research-confidence label shown in the review queue and list view; a lead that
fails mid-pipeline is marked `failed` with the exception reason and the rest of the
list continues; jobs stuck `running` longer than `LEADGENIUS_STALE_JOB_MINUTES`
(15) are requeued automatically and abandoned as failed after
`LEADGENIUS_MAX_JOB_ATTEMPTS` (3); failed leads are retried on the next research
run. Ingest refuses to treat free-mail domains (gmail, outlook, …) as company
domains and dedupes per person (email) rather than per company. While the sender
stub is on, export downloads are prefixed `PREVIEW_` and the exports page says
nothing is sent; deliverability (SPF/DKIM/DMARC) is explicitly the customer's
sending provider's job. Public trust pages: `/privacy`, `/terms`,
`/how-research-works`.
