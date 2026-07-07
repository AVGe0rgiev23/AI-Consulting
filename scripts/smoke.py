from fastapi.testclient import TestClient

from app.main import app
import app.db.queries as q


def main():
    with TestClient(app) as c:
        print("health:", c.get("/healthz").json())
        r = c.post("/signup", data={"email": "smoke@x.com", "name": "Smoke",
                                    "password": "password123"}, follow_redirects=False)
        print("signup:", r.status_code)
        c.post("/onboarding", data={"what_we_sell": "AI lead follow-up", "icp": "agencies",
                                    "proof_point": "16% replies", "voice_preset": "consultative"},
               follow_redirects=False)
        csv = (b"Company,Domain,Email\n"
               b"Acme Logistics,acme-logistics.com,sam@acme-logistics.com\n"
               b"Beta Freight,betafreight.io,jo@betafreight.io\n")
        r = c.post("/lists", data={"name": "Smoke List"},
                   files={"file": ("l.csv", csv, "text/csv")}, follow_redirects=False)
        lid = int(r.headers["location"].split("/")[-1])
        print("list id:", lid)
        r = c.post(f"/lists/{lid}/research", data={}, follow_redirects=False)
        print("research redirect:", r.status_code, r.headers.get("location"))
        rv = c.get(f"/review/{lid}?i=0")
        print("review ok:", rv.status_code, "| brief:", b"Research brief" in rv.content,
              "| score shown:", b"/100" in rv.content)
        print("credits left:", c.get("/api/v1/usage").json()["credits_balance"])
        for lead in q.leads_for_list(lid):
            a1 = [a for a in q.assets_for_lead(lead["id"]) if a["kind"] == "email_1"][0]
            c.post(f"/assets/{a1['id']}/approve", data={"list_id": lid, "i": 0},
                   follow_redirects=False)
        ex = c.get(f"/lists/{lid}/export?format=instantly")
        print("export after approve:", ex.status_code, "| rows:", ex.text.count("\n") - 1)
        lead0 = q.leads_for_list(lid)[0]
        a1 = [a for a in q.assets_for_lead(lead0["id"]) if a["kind"] == "email_1"][0]
        print(f"--- EMAIL_1 (score {a1['score']}) ---")
        print("Subject:", a1["subject"])
        print(a1["content"])
    print("ALL GOOD")


if __name__ == "__main__":
    main()
