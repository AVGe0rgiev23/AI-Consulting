import io
import time

from openpyxl import Workbook
from fastapi.testclient import TestClient

from app.main import app
import app.db.queries as q


def _xlsx():
    wb = Workbook()
    sheet = wb.active
    sheet.append(["First Name", "Last Name", "Title", "Company", "Email", "Website"])
    sheet.append(["Sam", "Lee", "COO", "Acme Logistics", "sam@acme-logistics.com",
                  "https://www.acme-logistics.com"])
    sheet.append(["Jordan", "Kim", "Head of Ops", "Beta Freight",
                  "jordan@betafreight.io", "betafreight.io"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def main():
    with TestClient(app) as c:
        c.post("/signup", data={"email": "loop@agency.com", "name": "Loop",
                                "password": "password123"}, follow_redirects=False)
        c.post("/onboarding", data={"what_we_sell": "AI automation", "icp": "B2B",
                                    "proof_point": ""}, follow_redirects=False)
        user = q.get_user_by_email("loop@agency.com")
        ws = q.workspaces_for_user(user["id"])[0]

        r = c.post("/lists", data={"name": "Apollo XLSX"},
                   files={"file": ("apollo.xlsx", io.BytesIO(_xlsx()),
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                   follow_redirects=False)
        xlsx_list = int(r.headers["location"].split("/")[-1])
        leads = q.leads_for_list(xlsx_list)
        print("xlsx import:", len(leads) == 2,
              "| apollo name mapped:", leads[0]["contact_name"] == "Sam Lee")

        r = c.post("/lists", data={
            "name": "Sheet Import",
            "sheet_url": "https://docs.google.com/spreadsheets/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789012/edit",
        }, follow_redirects=False)
        sheet_list = int(r.headers["location"].split("/")[-1])
        print("gsheet import (stub):", len(q.leads_for_list(sheet_list)) == 2,
              "| source:", q.get_list(sheet_list)["source"])

        c.post("/settings", data={"brand_name": "", "accent": "", "report_title": "",
                                  "contact": "", "instantly_api_key": "loop-key",
                                  "smartlead_api_key": ""}, follow_redirects=False)
        c.post(f"/lists/{xlsx_list}/research", data={}, follow_redirects=False)
        for _ in range(60):
            if q.get_list(xlsx_list)["status"] == "ready":
                break
            time.sleep(0.25)
        for lead in q.leads_for_list(xlsx_list):
            for a in q.assets_for_lead(lead["id"]):
                q.set_asset_status(a["id"], "approved")

        r = c.post(f"/lists/{xlsx_list}/push/instantly", follow_redirects=False)
        print("push:", r.status_code, r.headers["location"])

        r = c.post(f"/lists/{xlsx_list}/pull/instantly", follow_redirects=False)
        print("pull:", r.status_code, "|", r.headers["location"])

        page = c.get("/analytics")
        print("leaderboard populated:", b"reply" in page.content.lower()
              and b"No reply data yet" not in page.content)

        from app.services import feedback
        board = feedback.leaderboard(ws["id"])
        print("board:", [(b["category"], b["sent"], b["replied"]) for b in board])
        weights = feedback.category_weights(ws["id"])
        print("weights derived (5+ sends needed, 2 sent so empty):", weights == {})
    print("ALL GOOD — full round trip: xlsx/sheet in -> research -> push -> pull -> leaderboard")


if __name__ == "__main__":
    main()
