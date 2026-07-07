import io
import time

from fastapi.testclient import TestClient

from app.main import app
import app.db.queries as q

CSV = (
    "company,website,first_name,email\n"
    "Acme Logistics,acme-logistics.com,Sam,sam@acme-logistics.com\n"
)


def main():
    with TestClient(app) as c:
        c.post("/signup", data={"email": "pusher@agency.com", "name": "P",
                                "password": "password123"}, follow_redirects=False)
        c.post("/onboarding", data={"what_we_sell": "AI automation", "icp": "B2B",
                                    "proof_point": ""}, follow_redirects=False)
        user = q.get_user_by_email("pusher@agency.com")
        ws = q.workspaces_for_user(user["id"])[0]

        r = c.post("/settings", data={"brand_name": "", "accent": "", "report_title": "",
                                      "contact": "", "instantly_api_key": "smoke-key",
                                      "smartlead_api_key": ""}, follow_redirects=False)
        print("save api key:", r.status_code)

        c.post("/lists", data={"name": "Smoke Push"},
               files={"file": ("l.csv", io.BytesIO(CSV.encode()), "text/csv")},
               follow_redirects=False)
        lst = q.lists_for_workspace(ws["id"])[0]
        c.post(f"/lists/{lst['id']}/research", data={}, follow_redirects=False)
        for _ in range(60):
            if q.get_list(lst["id"])["status"] == "ready":
                break
            time.sleep(0.25)
        for lead in q.leads_for_list(lst["id"]):
            for a in q.assets_for_lead(lead["id"]):
                q.set_asset_status(a["id"], "approved")

        page = c.get("/exports")
        print("push button shown:", b"Push to Instantly" in page.content,
              "| connect link for smartlead:", b"Connect Smartlead" in page.content)

        r = c.post(f"/lists/{lst['id']}/push/instantly", follow_redirects=False)
        print("push:", r.status_code, "| location:", r.headers["location"])

        pushes = q.pushes_for_workspace(ws["id"])
        print("push recorded:", len(pushes) == 1 and pushes[0]["lead_count"] == 1)
        print("lead exported:", q.leads_for_list(lst["id"])[0]["status"] == "exported")

        page = c.get("/exports")
        print("history shown:", b"Recent pushes" in page.content)
    print("ALL GOOD")


if __name__ == "__main__":
    main()
