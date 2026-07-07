import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("LEADGENIUS_DATA", str(ROOT / "data" / "live_verify"))

from app import config


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 2:
        print("usage: python scripts/verify_live.py <domain> [company name]")
        return 1
    domain = sys.argv[1].strip().lower()
    company = " ".join(sys.argv[2:]) or domain.split(".")[0].replace("-", " ").title()

    print("=" * 72)
    print(f"LIVE VERIFY — {company} ({domain})")
    print(f"provider={config.LLM_PROVIDER} llm_stub={config.USE_LLM_STUB} "
          f"fetch_stub={config.USE_FETCH_STUB}")
    print(f"model_fast={config.MODEL_FAST} model_smart={config.MODEL_SMART}")
    if config.USE_LLM_STUB or config.USE_FETCH_STUB:
        print("ABORT: stub mode active — need GROQ_API_KEY, SEARCH_API_KEY, "
              "LEADGENIUS_FETCH_STUB=0")
        return 1

    from app.db import core, queries
    from app.fetch import crawl
    from app.security import hash_password
    from app.services import analyze, budget, research, write

    core.init_db()
    stamp = int(time.time())
    user_id = queries.create_user(f"verify-{stamp}@local.test", "Verify",
                                  hash_password("verify-password"))
    ws_id = queries.create_workspace(f"Verify {stamp}", user_id, 100)
    profile_id = queries.create_offer_profile(
        ws_id, "Verify", "AI automation for lead follow-up and quoting",
        "B2B service businesses", "One client hit 16% replies", "consultative", "en", True,
    )
    list_id = queries.create_list(ws_id, f"verify-{domain}", "csv")
    lead_id = queries.insert_lead(list_id, {
        "company_name": company, "domain": domain, "contact_name": "Alex Doe",
        "contact_title": "COO", "email": f"alex@{domain}" if domain else "",
        "linkedin_url": "", "raw": {}, "dedupe_hash": f"verify:{domain}:{stamp}"[:16],
    })

    started = time.monotonic()
    brief_id = research.research_lead(lead_id)
    elapsed = time.monotonic() - started
    brief = queries.get_brief_by_lead(lead_id)
    findings = queries.findings_for_brief(brief_id) if brief_id else []

    crawl_result = crawl.crawl_domain(domain) if domain else {"pages": [], "reason": "no_domain"}
    pages = crawl_result["pages"]
    print(f"\nPAGES CRAWLED: {len(pages)}"
          + (f" (reason: {crawl_result['reason']})" if crawl_result["reason"] else ""))
    for p in pages:
        print(f"  [{p['path']}] {p['url']} — {len(p['text'])} chars extracted"
              + (f"; tech={p['tech_hints']}" if p.get("tech_hints") else ""))
        print(f"    page text preview: {p['text'][:200]!r}")

    cached_search = queries.get_cached_search(domain or company.lower(),
                                              config.SEARCH_CACHE_DAYS)
    results = json.loads(cached_search["results_json"]) if cached_search else []
    print(f"\nSEARCH HITS: {len(results)}")
    for r in results:
        print(f"  [{r['kind']}] {r.get('published_at') or 'undated'} — "
              f"{r['title'][:90]} — {r['url']}")

    print(f"\nFINDINGS KEPT AFTER GROUNDING: {len(findings)}")
    for f in findings:
        print(f"  ({f['kind']}, conf {f['confidence']}"
              + (f", {f['published_at'][:10]}" if f.get("published_at") else "") + ")")
        print(f"    CLAIM   : {f['claim']}")
        print(f"    SOURCE  : {f['source_url']}")
        print(f"    EVIDENCE: {f['snippet'][:220]!r}")

    print(f"\nQUALITY: {brief['quality']}/100 "
          f"({research.confidence_label(brief['quality'])} confidence)")
    thin = bool(brief["thin"])
    print(f"THIN: {thin}" + (f" — reason: {brief['thin_reason']}" if thin else ""))
    print(f"RESEARCH WALL-CLOCK: {elapsed:.1f}s")

    offer = queries.get_offer_profile(profile_id)
    analyze.analyze_lead(lead_id, offer, ws_id)
    hyps = queries.hypotheses_for_brief(brief_id) if brief_id else []
    if hyps:
        print(f"\nTOP HYPOTHESIS: [{hyps[0]['category']}] {hyps[0]['statement']}")
    assets = write.generate_for_lead(lead_id, offer)
    status = "needs_review" if thin else "ready"
    queries.set_lead_status(lead_id, status, brief["thin_reason"] if thin else "")
    print(f"LEAD STATUS: {status}")

    email1 = next((a for a in assets if a["kind"] == "email_1"), None)
    if email1:
        print(f"\nEMAIL 1 (score {email1['score']}/100, status {email1['status']}):")
        print(f"Subject: {email1['subject']}")
        print("-" * 40)
        print(email1["content"])
        print("-" * 40)

    spent, calls = budget.spent_today()
    print(f"\nBUDGET LEDGER: spent_today=${spent:.4f} calls_today={calls}")
    by_kind = core.query_all(
        "SELECT kind, COUNT(*) n, SUM(amount_usd) usd FROM spend_ledger "
        "WHERE day=date('now') GROUP BY kind"
    )
    for row in by_kind:
        print(f"  {row['kind']}: {row['n']} calls, ${row['usd']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
