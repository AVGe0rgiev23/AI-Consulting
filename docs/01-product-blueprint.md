# LeadGenius — Product Blueprint

**One-liner:** LeadGenius turns a raw prospect list into deeply researched, human-quality cold outreach. It's the AI SDR that actually reads every prospect's website before writing a word.

---

## 1. Product Vision & Positioning

### The problem (in the buyer's words)
- "My SDRs spend 15 minutes researching each lead, or they skip research and send templates that get 0.5% replies."
- "AI writing tools produce obvious slop — 'I came across your amazing website' — and burn my domain reputation."
- "Clay is powerful but needs a full-time ops person. I just want good emails out."

### The wedge
Every competitor optimizes for **volume** (more sends, more mailboxes, more spintax). LeadGenius optimizes for **depth per lead**: real research → a business-specific hypothesis → a short, human email built around that hypothesis. The founding insight comes from a real campaign: a 5-step, hypothesis-driven sequence with soft-question CTAs produced a **16% reply rate** (45 replies / 278 leads). LeadGenius industrializes that pattern.

### Positioning statement
> For agencies and B2B teams who live or die by cold outreach, LeadGenius is the AI research-and-writing platform that produces outreach a prospect can't tell from a thoughtful human's — because the AI actually studied their business first. Unlike mass-personalization tools, it prioritizes one great hypothesis per lead over ten shallow merge fields.

### What LeadGenius deliberately is NOT (at MVP)
- Not a sending tool (no mailboxes, no deliverability liability) — it **exports to** Instantly, Smartlead, Lemlist, or CSV.
- Not a data provider (no contact database) — it **enriches what you bring**.
- Not a workflow builder — opinionated pipeline, not a canvas.

These three "nots" are what make the MVP buildable by one person and the product instantly differentiated.

---

## 2. Target Customers & Personas

| Persona | Who | Pain | Buying trigger | Plan fit |
|---|---|---|---|---|
| **Agency Operator** (primary) | Runs a lead-gen / AI / marketing agency, 1–15 people | Personalization is the bottleneck; VAs write bad first lines | Client campaign underperforming | Agency |
| **Founder-Seller** | B2B SaaS / dev-shop founder doing own outbound | No time to research; hates sounding like AI | Pipeline dried up | Starter → Pro |
| **Sales Team Lead** | 2–10 SDRs at a SaaS or services firm | SDR research time = $40/hr busywork | Rep productivity review | Pro → Enterprise |
| **Recruiter** | Agency recruiter doing BD + candidate outreach | Same message to 200 companies | Placement slump | Pro |
| **Consultant** | Solo consultant, high ACV | Needs 10 great emails, not 1,000 | New offer launch | Starter |

Secondary verticals (real estate, finance, logistics, healthcare, local services) are served by **industry research presets**, not separate products.

---

## 3. Full Feature List

### MVP (v1.0)
- **Import:** CSV/Excel upload; column auto-mapping; Apollo/Clay/LinkedIn-export presets; dedupe; validation report
- **Offer Profile:** workspace-level "what we sell, to whom, proof points, voice" — feeds every prompt
- **Research Engine:** per-lead crawl (home, about, services, pricing, blog, careers) + web search (news, reviews, hiring) → structured Research Brief with citations
- **Insight Engine:** 3–5 ranked pain/opportunity hypotheses per lead, each with evidence + confidence score
- **Outreach Generator:** cold email, subject variants, 5-step follow-up sequence (proven structure), LinkedIn connection note + DM, personalized opener snippets
- **Personalization Score:** 0–100 rubric (specificity, evidence-grounding, slop-phrase detection, length)
- **Review Queue:** approve / edit / regenerate per lead; bulk approve above score threshold
- **Export:** CSV, Instantly-ready CSV (custom variables), Smartlead CSV, copy-to-clipboard
- **Basics:** auth, workspaces, credits meter, usage page, dark mode

### v1.x (fast follows)
- Google Sheets two-way sync; templates & prompt library (editable); call scripts, voicemail scripts, meeting-prep notes; team seats & roles; activity log; Zapier/Make/webhooks; REST API
- Campaign performance loop: import reply data from Instantly/Smartlead → correlate hypothesis type × reply rate → auto-tune prompts

### v2+ (premium)
- HubSpot/Salesforce/Pipedrive native sync; audit-report generator (white-label PDF "AI opportunity audit" per prospect — agencies sell these); competitor analysis module; multilingual outreach (Danish/German/Spanish presets); lead scoring & intent signals; AI SDR agent (autonomous list → sequence → send via connected tool); voice AI; proposal generator; sales coaching on reply threads

---

## 4. User Journey (end to end)

```
DISCOVER            ACTIVATE (first 10 min)             HABIT (weekly)              EXPAND
LinkedIn post   →   Sign up (Google OAuth)          →   Monday: upload 200      →   Invites teammate
/ Upwork audit  →   "What do you sell?" (2-min      →   leads from Apollo       →   Connects Instantly
/ referral          Offer Profile wizard)           →   Research runs (~20 min) →   Upgrades for credits
                →   Upload 10 free leads            →   Reviews queue, bulk-    →   White-labels reports
                →   WATCH research happen live          approves 80%+ scores    →   Buys API access
                →   Read first 3 emails             →   Exports to Instantly
                →   "Whoa" moment: email cites          Thursday: imports reply
                    their prospect's actual             stats → sees which
                    pricing page                        hypotheses win
```

**The magic moment** (everything optimizes for this): within 10 minutes of signup, the user reads an email about a prospect *they know*, and it references something true and non-obvious about that business. That's when they believe.

---

## 5. Onboarding Flow (screen by screen)

1. **Sign up** — Google OAuth or email. No credit card. 25 free lead credits.
2. **Offer Profile wizard** (3 steps, ~2 min):
   - "What do you sell?" (free text + service-type picker)
   - "Who's it for + what result?" (ICP, one proof point with a number)
   - "Voice check" — pick 1 of 3 sample email tones (consultative / casual / direct); editable later
3. **First list** — drag-drop CSV or "try with 5 sample leads" (pre-loaded demo list for the empty-handed)
4. **Live research view** — progress per lead with streaming findings ("Found pricing page… detected Calendly… 3 open sales roles"). This screen *is* the marketing.
5. **First review** — side-by-side Research Brief + generated email. Coach marks: "This line cites their careers page."
6. **Export prompt** — "Send these from Instantly/Smartlead? Here's your ready file." + upgrade nudge at credit exhaustion.

Time-to-value target: **< 10 minutes**. Activation metric: user exports ≥ 1 approved email in first session.

---

## 6. Dashboard Design & Wireframes

### Information architecture
```
Sidebar:  Overview | Lead Lists | Review Queue | Campaigns | Templates & Prompts
          Analytics | Integrations | ──────── | Settings (team, billing, usage, API, logs)
Top bar:  Workspace switcher · Search · Credits meter · Notifications · Avatar
```

### Overview (home)
```
┌────────────────────────────────────────────────────────────────────┐
│  Good morning, Albert            ⚡ 1,240 credits   [ + New List ] │
├──────────────┬──────────────┬──────────────┬───────────────────────┤
│ Leads        │ Avg Person-  │ Est. time    │ Awaiting review       │
│ researched   │ alization    │ saved        │                       │
│ 1,847        │ 87 / 100     │ 61 hrs       │ 214 leads  [Review →] │
├──────────────┴──────────────┴──────────────┴───────────────────────┤
│ ACTIVE JOBS                                                        │
│ ▸ "SaaS CFOs — July"      ████████░░ 164/200 researched   ~12 min  │
│ ▸ "Dental DK — retarget"  ██████████ done ✓        [Open queue →]  │
├────────────────────────────────────────────────────────────────────┤
│ RECENT ACTIVITY                          HYPOTHESIS LEADERBOARD    │
│ · Maria approved 41 emails               1. Missed-call revenue    │
│ · Export → Instantly (198 rows)             18.2% reply            │
│ · List "Logistics DE" imported           2. Manual follow-up       │
│                                             11.4% reply            │
└────────────────────────────────────────────────────────────────────┘
```

### Review Queue (the core screen — where users live)
```
┌─ List: SaaS CFOs — July ──────────── Filter: score > 80 ▾  Bulk ▾ ─┐
│ ┌─ Lead 34/200 ────────────────┬─────────────────────────────────┐ │
│ │ RESEARCH BRIEF               │ EMAIL 1          Score: 91 🟢    │ │
│ │ Acme Logistics · 45 emp · DE │ Subject: Acme Logistics         │ │
│ │ ▸ Pricing: custom quotes     │ ┌─────────────────────────────┐ │ │
│ │   only (source: /pricing)    │ │ I was going to call about   │ │ │
│ │ ▸ Hiring 3 dispatchers       │ │ your dispatch team, but     │ │ │
│ │   (source: careers page)     │ │ figured I'd write first...  │ │ │
│ │ ▸ No online booking flow     │ │ [evidence-linked lines      │ │ │
│ │ HYPOTHESES                   │ │  highlighted on hover]      │ │ │
│ │ 1. Quote turnaround is       │ └─────────────────────────────┘ │ │
│ │    manual → slow (conf 82%)  │ Sequence: [1][2][3][4][5]       │ │
│ │ 2. Dispatch scaling pain     │ LinkedIn: [Connect] [DM]        │ │
│ │    (conf 74%)                │                                 │ │
│ │                              │ [✎ Edit] [↻ Regenerate] [✓ Approve]│
│ └──────────────────────────────┴─────────────────────────────────┘ │
│                 [← Prev]   ✓ Approve & Next (⏎)   [Skip →]         │
└────────────────────────────────────────────────────────────────────┘
```

Keyboard-first: `⏎` approve+next, `E` edit, `R` regenerate, `1–5` switch sequence step. A reviewer should clear 200 leads in 30 minutes.

### Other key screens
- **Lead Lists:** table of lists with status pipeline (Imported → Researching → Ready → Reviewed → Exported), row counts, error counts.
- **Analytics:** funnel (imported → researched → approved → exported → replies), score distribution, hypothesis leaderboard, credits burn, time-saved estimate, cost per meeting.
- **Templates & Prompts:** the prompt library exposed as editable cards (sequence structures, tones, industry presets) with "restore default".

---

## 7. UX Recommendations

1. **Streaming beats spinners.** Research is slow (10–30 s/lead). Show live findings as they arrive; never a dead progress bar.
2. **Evidence on hover.** Every personalized line links to its source (URL + quoted snippet). This is the trust feature — no competitor does it.
3. **Score as traffic light**, not vanity number: 🟢 ≥80 ship it, 🟡 60–79 skim it, 🔴 <60 regenerate. Bulk-approve respects the threshold.
4. **Opinionated defaults, escape hatches later.** Non-technical users get the proven 5-step structure out of the box; prompt editing lives behind "Advanced".
5. **Empty states sell.** Every empty screen shows a filled example + one CTA.
6. **Slop guard visible.** When the generator kills a banned phrase ("Hope you're doing well"), show it crossed out in an audit trail — users love seeing the tool refuse to be cringe.
7. Dark mode default (the audience lives in dark-mode tools); Tailwind via CDN; zero-build frontend; sub-100 ms page loads.

---

## 8. SaaS Page Layouts & Landing Page Copy

### Site map
`/` landing · `/pricing` · `/how-it-works` (the live-research demo, ungated) · `/agencies` (white-label pitch) · `/vs/clay`, `/vs/instantly` (comparison SEO) · `/blog` · `/login`

### Landing page (section by section, copy included)

**Hero**
> **Cold outreach that sounds like you actually did the homework.**
> LeadGenius researches every prospect's website, news, and hiring activity — then writes short, specific emails around one real business problem. No templates. No "I came across your amazing website."
> [Research 25 leads free] · [Watch a live research run — 90 sec]
> *No credit card. Works with Instantly, Smartlead, Apollo, and Clay exports.*

**Problem strip**
> Your prospects get 30 cold emails a day. 29 are templates with a `{{first_name}}` bolted on. Reply rates prove it: the average cold campaign gets under 2% replies. The one email that references *their actual pricing page problem* is the one that gets answered.

**How it works (3 steps, animated)**
> 1. **Upload your list.** CSV, Apollo, Clay, LinkedIn export — we validate and dedupe.
> 2. **AI researches every company.** Website, pricing, blog, careers, news, reviews. You watch it happen.
> 3. **Review and export.** Human-quality sequences, scored for specificity, ready for your sending tool.

**Proof section**
> Built on a sequence structure that produced **45 replies from 278 leads (16.2%)** in a real campaign — 8× the industry average. That structure ships as the default.

**Evidence feature spotlight**
> **Every line has a receipt.** Hover any sentence to see the exact page it came from. If we can't cite it, we don't write it.

**Objection block**
> *"AI emails sound like AI."* Ours are graded by a slop detector trained on the phrases that get emails deleted — and rejected until they pass. Average approved email: 120 words, one observation, one idea, one soft question.

**CTA footer**
> **Your next 25 sales meetings are hiding in a CSV you already have.** [Start free]

Tone rules for all copy: specific numbers over adjectives, hypothesis voice, no exclamation marks, no "revolutionize/supercharge/unleash".

---

## 9. Competitive Differentiation (summary)

| Axis | Clay | Instantly/Smartlead | Lavender/Twain | Copy.ai GTM | **LeadGenius** |
|---|---|---|---|---|---|
| Depth of research | Waterfall data fields | None | None (coaching) | Shallow | **Full-site + web, cited** |
| Output quality | DIY prompts | Spintax templates | Per-email coaching | Generic | **Scored, slop-guarded, proven structure** |
| Skill required | High (ops person) | Medium | Low | Medium | **Low** |
| Sends email | No | Yes | No | No | No (exports) — v2 via integrations |
| Insight, not data | ✗ | ✗ | ✗ | ✗ | **✓ ranked pain hypotheses w/ evidence** |

The moat compounds: reply-data feedback (which hypotheses get replies, per industry) becomes proprietary training signal no copycat has.
