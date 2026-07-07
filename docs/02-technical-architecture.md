# LeadGenius — Technical Architecture

Follows project rules: Python 3.10+, lean procedural/functional modules, FastAPI, SQLite behind an isolated DB layer, native HTML + Tailwind CDN (htmx for interactivity — no React/Node build).

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser (Jinja2 templates + Tailwind CDN + htmx + SSE)         │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP / SSE
┌────────────────────────────▼────────────────────────────────────┐
│  FastAPI app (uvicorn)                                          │
│  routers/: auth, lists, leads, research, generate, review,      │
│            exports, prompts, analytics, billing, api_v1, webhooks│
├─────────────────────────────────────────────────────────────────┤
│  services/ (pure functions, no classes-for-the-sake-of-it)      │
│  ingest.py · research.py · analyze.py · write.py · score.py     │
│  export.py · credits.py · notify.py                             │
├──────────────┬──────────────────────────┬───────────────────────┤
│  db/         │  jobs/                   │  llm/                 │
│  sqlite via  │  worker loop polling     │  claude client,       │
│  one module  │  `jobs` table (SQLite    │  prompt assembly,     │
│  (swappable  │  as queue, atomic claim) │  retry/backoff,       │
│  to Postgres)│  N async workers         │  cost metering        │
├──────────────┴──────────────────────────┴───────────────────────┤
│  fetch/: httpx + trafilatura (crawl) · search provider (Tavily/ │
│  Serper) · robots.txt respect · per-domain rate limit · cache   │
└─────────────────────────────────────────────────────────────────┘
External: Anthropic API · Tavily/Serper · Stripe · SMTP (transactional)
```

**Key decisions**
- **SQLite as job queue** (a `jobs` table with `claimed_at` + atomic `UPDATE ... WHERE claimed_at IS NULL`) — no Redis/Celery at MVP. One process, N asyncio workers. Migration path: swap `jobs/` for a real queue when > ~50k leads/day.
- **SSE (Server-Sent Events)** for live research streaming — simpler than WebSockets, works through proxies.
- **WAL mode** on SQLite; single-writer discipline lives in the db module.
- **Everything metered**: every LLM and search call records its cost in `spend_ledger` (daily budget kill-switch reads from it); credits debit at job level.

### Repository layout
```
app/
  main.py            routers/…            services/…
  db/core.py         db/schema.sql        db/queries.py
  jobs/worker.py     jobs/pipeline.py
  llm/client.py      llm/prompts/…        llm/score.py
  fetch/crawl.py     fetch/search.py      fetch/cache.py
  templates/…        static/…
tests/               (one test module per router + per service — project rule)
```

---

## 2. Database Structure (SQLite, portable DDL)

```sql
users(id, email UNIQUE, name, password_hash, created_at)
workspaces(id, name, owner_id→users, plan, credits_balance, settings_json)
memberships(user_id, workspace_id, role)            -- owner|admin|member|reviewer

offer_profiles(id, workspace_id, name, what_we_sell, icp, proof_points,
               voice_preset, banned_phrases_json, language, is_default)

lead_lists(id, workspace_id, name, source,          -- csv|apollo|clay|sheets|api
           status, row_count, error_count, created_at)
leads(id, list_id, company_name, domain, contact_name, contact_title,
      email, linkedin_url, raw_json,                -- original row preserved
      status,                                       -- pending|researching|ready|approved|exported|failed
      dedupe_hash, created_at)

jobs(id, workspace_id, kind,                        -- research|generate|export|sync
     payload_json, status, claimed_at, attempts, error, created_at, finished_at)

research_briefs(id, lead_id UNIQUE, company_summary, industry, size_estimate,
                tech_stack_json, positioning, digest_md, completed_at)
findings(id, brief_id, kind,                        -- pricing|hiring|news|review|tech|social|testimonial
         claim, source_url, snippet, confidence)
hypotheses(id, brief_id, rank, category,            -- inefficiency|acquisition|automation|scaling|revenue_leak
           statement, evidence_finding_ids, confidence)

assets(id, lead_id, kind,                           -- email_1..email_5|subject|li_connect|li_dm|call_script|voicemail|opener|report
       hypothesis_id, content, score, score_breakdown_json,
       status,                                      -- draft|approved|edited|rejected
       version, edited_by, created_at)

prompt_templates(id, workspace_id NULL,             -- NULL = system default
                 slug, stage,                       -- research|analyze|write_email|write_li|score|…
                 body, model, is_active, version)

campaigns(id, workspace_id, name, list_id, exported_to, external_id)
campaign_stats(id, campaign_id, lead_id NULL, sent, opened, replied,
               meeting_booked, imported_at)          -- feedback loop

exports(id, workspace_id, list_id, format, row_count, file_path, created_at)
integrations(id, workspace_id, provider, auth_json_encrypted, status)
api_keys(id, workspace_id, key_hash, label, last_used_at, revoked_at)
webhook_endpoints(id, workspace_id, url, secret, events_json)

credits_ledger(id, workspace_id, delta, reason,     -- research|generate|purchase|refund|bonus
               job_id NULL, balance_after, created_at)
llm_calls(id, job_id, model, prompt_tokens, completion_tokens, cost_usd, stage)
activity_log(id, workspace_id, user_id, action, target, meta_json, created_at)
```

Indexes on every FK + `leads(dedupe_hash)`, `jobs(status, claimed_at)`, `assets(lead_id, kind)`. All `*_json` columns keep SQLite simple while staying Postgres-portable (`jsonb` later).

---

## 3. Research Pipeline (per lead)

```
STAGE 0  Validate      email syntax, domain resolves, dedupe hash        (0 credits)
STAGE 1  Crawl         home → about → services → pricing → blog(3) →
                       careers; trafilatura extraction; 15 pages max;
                       robots.txt honored; cached 7 days per domain
STAGE 2  Enrich        search provider: "{company} news", "{company}
                       reviews", "{company} hiring"; tech detect from
                       HTML (meta generators, script src fingerprints)
STAGE 3  Extract       LLM pass 1 (haiku-class): raw pages → typed
                       findings[] with source_url + snippet. Rule:
                       NO finding without a quotable source.
STAGE 4  Analyze       LLM pass 2 (sonnet-class): findings + offer
                       profile → ranked hypotheses[] with evidence ids
                       + confidence. Generic hypotheses penalized.
STAGE 5  Digest        assemble research_brief digest_md (the human-
                       readable brief shown in the Review Queue)
```

Failure handling: each stage independently retryable (3 attempts, exponential backoff); a lead with a dead website still gets STAGE 2 search-only research, marked on the brief with `thin=1`, a 0–100 `quality` score, and a human-readable `thin_reason` so generation falls back to an honest generic draft instead of hedged fabrication. Cost target: **≤ $0.04/lead** research (cheap model for extraction, mid model for analysis).

---

## 4. AI Workflow & Prompt Architecture

### Layered prompt assembly (every generation call)
```
[1] SYSTEM VOICE       constant: hypothesis-don't-claim, one number not
                       buzzwords, soft-question CTAs, ≤6 short lines,
                       no signature, banned-phrase list (slop lexicon)
[2] OFFER PROFILE      workspace: what we sell, ICP, one proof point, language
[3] RESEARCH DIGEST    per-lead: brief + chosen hypothesis + its evidence
[4] TASK TEMPLATE      per-asset: email_1 | bump | asset_email | pivot |
                       li_connect | call_script … (editable prompt_templates)
[5] EXEMPLAR           the proven 5-step structure as a few-shot pattern
                       (rhythm/length/CTA shape — translated, never copied)
```

### The default sequence structure (system asset, from the 16%-reply campaign)
| Step | Delay | Subject | Pattern |
|---|---|---|---|
| 1 | day 0 | `{{companyName}} ` | disarming opener → quantified pain hypothesis → soft permission CTA tied to an artifact |
| 2 | +3d | *(threaded)* | one-line "wrong person?" bump |
| 3 | +4d | *asset name* | offer a named, tangible asset ("lost-revenue calculator for {{companyName}}") |
| 4 | +1d | *(threaded)* | casual two-line bump |
| 5 | +4d | *(threaded)* | pivot to hypothesis #2 — a different angle |

### Scoring rubric (`llm/score.py`, LLM-judge + deterministic checks)
| Dimension | Weight | Deterministic part |
|---|---|---|
| Specificity (names a real, checkable fact) | 30 | evidence link present |
| Evidence grounding (fact matches findings) | 25 | string/claim match vs findings |
| Slop absence | 20 | regex lexicon: "came across", "hope this finds", "amazing", "revolutionize", "I noticed you"… |
| Brevity & shape | 15 | 100–170 words, ≤6 lines, ends with `?` |
| CTA softness | 10 | no imperatives, no calendar links |

Score < 70 → auto-regenerate once with critique injected; still < 70 → flag 🔴 for human.

---

## 5. API Design (REST, `/api/v1`, key auth)

```
POST   /lists                      create list (multipart CSV or JSON rows)
GET    /lists/{id}                 status + counts
POST   /lists/{id}/research        enqueue research      → 202 {job_id}
GET    /leads/{id}                 lead + brief + hypotheses + assets
POST   /leads/{id}/generate       {kinds:[...], offer_profile_id}
POST   /leads/{id}/assets/{aid}/approve | /regenerate
GET    /lists/{id}/export?format=csv|instantly|smartlead|json
POST   /webhooks                   register endpoint
GET    /usage                      credits, llm spend, rate limits
```
Conventions: cursor pagination, idempotency keys on POSTs, per-key rate limits, HMAC-signed webhooks (`research.completed`, `list.ready`, `asset.approved`, `credits.low`). API access gated to Agency+ plans.

---

## 6. Integrations Roadmap

| Wave | Integrations | Mechanism |
|---|---|---|
| MVP | CSV/Excel in; CSV/Instantly/Smartlead out | file formats — zero API risk |
| 1 | Google Sheets, Zapier, Make, webhooks | REST API + OAuth (Sheets) |
| 2 | Instantly & Smartlead APIs (push campaigns, pull reply stats), Slack notifications | provider APIs; closes the feedback loop |
| 3 | HubSpot, Pipedrive, Apollo, Notion | OAuth apps + marketplace listings (distribution!) |
| 4 | Salesforce, calendar, LinkedIn (via compliant partners) | enterprise pull |

Each integration is a marketplace listing = a free acquisition channel. Prioritize by listing traffic, not engineering elegance.

---

## 7. Security & Compliance Essentials

- Password hashing (argon2), session cookies `HttpOnly/SameSite=Lax`, CSRF tokens on forms; API keys stored hashed.
- Integration credentials encrypted at rest (Fernet, key outside DB).
- Crawler: obeys robots.txt, identifies itself (`LeadGeniusBot/1.0`), per-domain throttle, never bypasses auth walls — public info only.
- GDPR posture: leads are customer-supplied data (processor role); DPA template, per-workspace data export + hard delete; EU hosting option later.
- Prompt-injection defense: crawled page text is data, never instructions — wrapped in delimited blocks with an explicit "content may contain adversarial text" guard, and outputs validated against the finding schema.

---

## 8. Scaling Roadmap (technical)

| Trigger | Change |
|---|---|
| >5k leads/day | SQLite → Postgres (db module swap), jobs table → Redis + RQ/arq |
| Research latency complaints | dedicated crawler pool + shared domain-cache service |
| >3 engineers | split worker into its own deployable; add OpenTelemetry traces |
| Enterprise deals | SSO (SAML/OIDC), audit-log export, VPC/self-host quote, SOC 2 program |
| Model cost pressure | batch API for research stages (50% off), per-stage model routing, prompt caching on system layers |
