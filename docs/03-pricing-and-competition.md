# LeadGenius — Pricing, Monetization & Competitive Analysis

---

## 1. Pricing Strategy

### Principles
- **Price the outcome unit, not the tokens.** The unit is a *fully researched + written lead* ("lead credit"). One credit = research brief + full asset bundle for one lead. Regenerations are free (quality is our promise); re-research of the same domain within 7 days is free (cache).
- **Anchor against labor, not software.** An SDR spends ~15 min/lead researching + writing = ~$10 of labor. We charge $0.15–0.40/lead. The pitch writes itself.
- **Margin check:** COGS ≈ $0.06–0.09/lead (LLM + search + infra) → 70–85% gross margin at listed prices.

### Tiers

| | **Free Trial** | **Starter** | **Professional** | **Agency** | **Enterprise** |
|---|---|---|---|---|---|
| Price | $0 | **$49/mo** | **$149/mo** | **$399/mo** | custom, $1k+/mo |
| Lead credits /mo | 25 (once) | 250 | 1,000 | 4,000 | custom |
| Effective $/lead | — | $0.20 | $0.15 | $0.10 | negotiated |
| Seats | 1 | 1 | 3 | 10 | unlimited |
| Offer profiles | 1 | 1 | 3 | unlimited | unlimited |
| Outputs | emails + sequence | + LinkedIn, openers | + call scripts, meeting prep, Sheets sync | + audit reports (white-label), API, webhooks | + SSO, DPA, priority models, CSM |
| Analytics | basic | basic | full + feedback loop | full + client-level rollups | + exportable audit logs |
| Support | community | email | priority email | priority + onboarding call | dedicated |

Add-ons: extra credits $0.25 → $0.12/lead (volume steps) · white-label report branding $99/mo (below Agency) · premium research depth (competitor scan, deeper crawl) 2× credits per lead.

Annual: 2 months free. Overage: soft-block with one-click top-up (never silently bill).

### Why these numbers
- $49 clears the "serious tool" bar while staying impulse-purchasable for founders.
- $149 ≈ Clay's entry tier but with zero learning curve — the comparison page target.
- $399 Agency is the profit engine: agencies bill clients $1–3k/mo per campaign; $399 is a rounding error, and white-label audit reports let them *resell our output directly*.
- Enterprise exists on the pricing page from day 1 for anchoring, even before it's sellable.

### Monetization mechanics beyond subscriptions
1. **Credits ledger** (built into schema) enables promos, referral bonuses (50 credits per referral), and win-back grants at near-zero cost.
2. **White-label audit reports** — agencies pay us so *they* can charge $500–2,000 per "AI opportunity audit". We become COGS in their product. Stickiest revenue in the plan.
3. **API metering** — per-credit pricing for platforms embedding research (v2).
4. **Marketplace rev-share** later: prompt-pack and industry-preset marketplace (creators sell presets, we take 20%).

---

## 2. Competitive Analysis

### The landscape (four clusters)

**A. Data/enrichment platforms — Clay, Apollo, ZoomInfo**
Clay ($134–800/mo) is the giant: waterfall enrichment + AI columns ("Claygent"). Strengths: data breadth, ops-community cult. Weaknesses: steep learning curve (agencies exist *just* to operate Clay), pricing anxiety (credit burn), output quality depends entirely on the user's prompt skill. **Our angle:** "Clay gives you 150 data fields. We give you the email. No ops hire required." We also *import Clay exports* — complement first, replace later.

**B. Sending platforms — Instantly, Smartlead, Lemlist**
Own the mailbox/deliverability layer; personalization is spintax + merge fields. They are our **export targets and distribution channel**, not enemies. Risk: they build "AI personalization" in (Instantly already has basic AI). Defense: depth + evidence + feedback loop is a different product DNA than a sending tool bolt-on; stay the best "brain" for every "arm".

**C. AI email writers — Lavender, Twain, Lyne.ai, Smartwriter, Copy.ai GTM**
First-line generators and coaching tools. Most produce exactly the shallow flattery we ban ("Loved your recent post!"). Lyne/Smartwriter validated demand then stagnated on quality. **Our angle:** research depth + hypothesis + evidence citations + scoring — a pipeline, not a writing assistant.

**D. AI SDR agents — 11x, Artisan, AiSDR, Unify**
$1.5k–5k/mo autonomous "digital workers." Well-funded, enterprise-aimed, and earning a reputation for confidently sending slop at scale. **Our angle:** human-in-the-loop quality at 1/10 the price; we earn the right to add autonomy (v2 AI SDR mode) after the quality loop proves itself. When the AI-SDR backlash articles circulate, we're the "quality-first" counter-position.

### Positioning map
```
                 High research depth
                        │
            (empty!) ★ LeadGenius        Clay (DIY depth)
                        │
 Human-quality ─────────┼───────────── Volume/automation
 output                 │
        Lavender/Twain  │   11x/Artisan · Instantly AI
                        │
                 Shallow/no research
```
The top-left quadrant — deep research **and** finished human-quality output, low skill required — is genuinely unoccupied.

### Defensibility (in order of realism)
1. **Reply-data flywheel:** campaign stats imported from sending tools → we learn which hypothesis categories get replies per industry → prompts auto-tune. Data no one else has in this shape.
2. **Slop lexicon + scoring rubric** continuously updated from edits users make (every human edit is a training label).
3. **Proven-structure library:** licensed/curated sequence structures with real performance numbers, starting with the founder's own 16% campaign.
4. Switching costs: offer profiles, edited prompt libraries, historical briefs.

### Honest risks
- Frontier models make "good enough" personalization a commodity → counter: the moat is research pipeline + evidence + feedback loop, not the prose.
- Clay ships a "one-click email" mode → counter: their DNA and pricing are ops-platform; we win non-technical buyers and agencies on simplicity.
- Cold email regulatory/deliverability tightening → counter: we don't send; quality-first positioning *benefits* from crackdowns on volume spam.
