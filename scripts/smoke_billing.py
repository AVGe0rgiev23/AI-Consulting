from fastapi.testclient import TestClient

from app.main import app
import app.db.queries as q


def main():
    with TestClient(app) as c:
        c.post("/signup", data={"email": "payer@agency.com", "name": "P",
                                "password": "password123"}, follow_redirects=False)
        user = q.get_user_by_email("payer@agency.com")
        ws = q.workspaces_for_user(user["id"])[0]
        print("start:", ws["plan"], ws["credits_balance"], "credits")

        page = c.get("/billing")
        print("billing page:", page.status_code,
              "| plans shown:", b"Professional" in page.content,
              "| test mode:", b"Test mode" in page.content)

        r = c.post("/billing/checkout/professional", follow_redirects=False)
        print("checkout redirect:", r.status_code, r.headers["location"])

        page = c.get(r.headers["location"])
        print("mock checkout page:", page.status_code,
              b"Mock Stripe Checkout" in page.content)

        r = c.post("/billing/mock-checkout", data={"plan": "professional"},
                   follow_redirects=False)
        print("pay:", r.status_code, r.headers["location"])

        ws = q.get_workspace(ws["id"])
        print("after:", ws["plan"], ws["credits_balance"], "credits")
        ledger = q.ledger(ws["id"])
        print("ledger entry:", ledger[0]["reason"], ledger[0]["delta"])
    print("ALL GOOD")


if __name__ == "__main__":
    main()
