from fastapi.testclient import TestClient

from app.main import app
import app.db.queries as q
from app.jobs import worker
from app.services import feedback


def main():
    with TestClient(app) as c:
        c.post("/signup", data={"email": "fb@x.com", "name": "FB", "password": "password123"},
               follow_redirects=False)
        c.post("/onboarding", data={"what_we_sell": "AI lead follow-up", "icp": "agencies",
                                    "proof_point": "16% replies", "voice_preset": "consultative"},
               follow_redirects=False)
        csv = (b"Company,Domain,Email\n"
               b"Acme Logistics,acme-logistics.com,sam@acme-logistics.com\n"
               b"Beta Freight,betafreight.io,jo@betafreight.io\n")
        r = c.post("/lists", data={"name": "FB List"},
                   files={"file": ("l.csv", csv, "text/csv")}, follow_redirects=False)
        lid = int(r.headers["location"].split("/")[-1])
        c.post(f"/lists/{lid}/research", data={}, follow_redirects=False)
        worker.run_pending_sync()

        for lead in q.leads_for_list(lid):
            a1 = [a for a in q.assets_for_lead(lead["id"]) if a["kind"] == "email_1"][0]
            c.post(f"/assets/{a1['id']}/approve", data={"list_id": lid, "i": 0},
                   follow_redirects=False)
        c.get(f"/lists/{lid}/export?format=instantly")

        stats = (b"email,sent,opened,replied,meeting\n"
                 b"sam@acme-logistics.com,1,1,1,1\n"
                 b"jo@betafreight.io,1,1,0,0\n")
        r = c.post(f"/lists/{lid}/import-stats",
                   files={"file": ("s.csv", stats, "text/csv")}, follow_redirects=False)
        print("import-stats:", r.status_code)

        api = c.get("/api/v1/leaderboard").json()
        print("funnel:", api["funnel"])
        print("leaderboard:")
        for row in api["leaderboard"]:
            print(f"  {row['category']:<14} sent {row['sent']} replied {row['replied']} "
                  f"rate {row['reply_rate']}%")

        weights = feedback.category_weights(ctx_ws(c))
        print("tuning weights (fed back into ranking):", weights)
    print("ALL GOOD")


def ctx_ws(c):
    user = q.get_user_by_email("fb@x.com")
    return q.workspaces_for_user(user["id"])[0]["id"]


if __name__ == "__main__":
    main()
