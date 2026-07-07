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
        c.post("/signup", data={"email": "prompter@agency.com", "name": "P",
                                "password": "password123"}, follow_redirects=False)
        c.post("/onboarding", data={"what_we_sell": "AI automation", "icp": "B2B",
                                    "proof_point": ""}, follow_redirects=False)
        user = q.get_user_by_email("prompter@agency.com")
        ws = q.workspaces_for_user(user["id"])[0]

        page = c.get("/prompts")
        print("prompts page:", page.status_code,
              "| slots shown:", b"Writing voice" in page.content
              and b"Email 5" in page.content)

        r = c.post("/prompts/email_step_2", data={"content": "SMOKE CUSTOM BUMP SPEC"},
                   follow_redirects=False)
        print("save override:", r.status_code)
        page = c.get("/prompts")
        print("customized badge:", b"Customized" in page.content)

        r = c.post("/lists", data={"name": "Smoke"}, files={"file": ("l.csv", io.BytesIO(CSV.encode()), "text/csv")},
                   follow_redirects=False)
        lst = q.lists_for_workspace(ws["id"])[0]
        c.post(f"/lists/{lst['id']}/research", data={}, follow_redirects=False)
        for _ in range(60):
            if q.get_list(lst["id"])["status"] == "ready":
                break
            time.sleep(0.25)
        lead = q.leads_for_list(lst["id"])[0]
        assets = q.assets_for_lead(lead["id"])
        print("assets generated after override:", len(assets) >= 7)

        api = c.get("/api/v1/prompts").json()
        custom = [p for p in api["prompts"] if p["customized"]]
        print("api customized:", [p["key"] for p in custom] == ["email_step_2"])

        c.post("/prompts/email_step_2/reset", follow_redirects=False)
        api = c.get("/api/v1/prompts").json()
        print("reset clears:", not any(p["customized"] for p in api["prompts"]))
    print("ALL GOOD")


if __name__ == "__main__":
    main()
