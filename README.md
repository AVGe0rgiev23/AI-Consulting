# LeadGenius

AI lead enrichment & personalized outreach platform. Turns a raw prospect list into deeply researched, human-quality cold outreach — the AI SDR that reads every prospect's website before writing a word.

## Status

MVP is **built and tested** (179 passing tests): full research→outreach pipeline, live SSE research-streaming view, a reply-data feedback loop that tunes hypothesis ranking, a white-label AI-audit report generator, and team seats with role-based permissions and invite links. Production safety rails are in: robots.txt-respecting crawler with retries and time budgets, daily spend kill-switch with per-request ceilings, per-IP rate limits, evidence-grounding validation that drops unverifiable findings, and a thin-research gate that refuses to fabricate personalization. The product surfaces uncertainty honestly: per-lead research confidence (high/medium/low), per-lead failure states with reasons, crash-resumable background jobs, preview-labeled exports while sending is stubbed, and public /privacy, /terms, and /how-research-works pages. Research quality is deep as well as honest: multi-source search (LinkedIn/job boards, Crunchbase/funding, G2/Capterra reviews, news) with recency-weighted signals, tech-stack detection from real HTML/header signals, and a "dig deeper & regenerate" action for thin leads. Runs fully offline with deterministic stubs; set a free-tier LLM key (`GROQ_API_KEY`, `GEMINI_API_KEY`, or `OPENROUTER_API_KEY`) + `SEARCH_API_KEY` for live generation and web research — `ANTHROPIC_API_KEY` also works and is used only when no free-tier key is set. See [docs/06 — Build Phases](docs/06-build-phases.md) for the phase map and run guide.

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m pytest        # 27 tests
.venv/Scripts/uvicorn app.main:app --reload
```

## Blueprint

| Doc | Covers |
|---|---|
| [01 — Product Blueprint](docs/01-product-blueprint.md) | Vision, positioning, personas, feature list, user journey, onboarding, dashboard wireframes, UX, landing page copy, differentiation |
| [02 — Technical Architecture](docs/02-technical-architecture.md) | System design (FastAPI + SQLite + htmx), database schema, research pipeline, AI workflow & prompt architecture, scoring, API design, integrations, security |
| [03 — Pricing & Competition](docs/03-pricing-and-competition.md) | Pricing tiers, monetization mechanics, competitive landscape, defensibility |
| [04 — Roadmap](docs/04-roadmap.md) | 12-week MVP plan, quarterly scaling roadmap, future expansion |
| [05 — Go-to-Market](docs/05-go-to-market.md) | Brand, GTM plan, marketing channels, sales strategy, LinkedIn content, agency & Upwork positioning |
| [06 — Build Phases](docs/06-build-phases.md) | What each phase ships in code, test map, and how to run it |

## Stack (per CLAUDE.md)

Python 3.10+ · FastAPI · SQLite (isolated db layer) · Jinja2 + Tailwind CDN + htmx · Anthropic API
