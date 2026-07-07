from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def main():
    with TestClient(app) as c:
        c.post("/signup", data={"email": "au@x.com", "name": "Audit Agency",
                                "password": "password123"}, follow_redirects=False)
        c.post("/onboarding", data={"what_we_sell": "AI automation systems", "icp": "logistics firms",
                                    "proof_point": "cut quote time 60%", "voice_preset": "consultative"},
               follow_redirects=False)
        c.post("/settings", data={"brand_name": "Northstar Growth", "accent": "#0a7d55",
                                  "report_title": "AI Opportunity Audit",
                                  "contact": "hello@northstar.io · northstar.io"},
               follow_redirects=False)
        r = c.post("/audit", data={"company_name": "Acme Logistics", "domain": "acme-logistics.com"},
                   follow_redirects=False)
        rid = int(r.headers["location"].split("/")[-1])
        page = c.get(f"/audit/{rid}")
        out = Path("D:/SaaS/data_audit_preview.html")
        out.write_text(page.text, encoding="utf-8")
        print("status:", page.status_code, "| bytes:", len(page.text))
        print("branded:", "Northstar Growth" in page.text, "| accent:", "#0a7d55" in page.text)
        print("opportunities:", page.text.count("class=\"opp\""))
        data = c.get(f"/api/v1/audits/{rid}").json()
        print("exec summary:", data["report"]["exec_summary"])
        for o in data["opportunities"]:
            ev = len(o.get("evidence", []))
            print(f"  - {o['title']} [{o['category']}] evidence={ev}")
        print("preview written:", out)
    print("ALL GOOD")


if __name__ == "__main__":
    main()
