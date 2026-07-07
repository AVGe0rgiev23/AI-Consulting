from fastapi.testclient import TestClient

from app.main import app
import app.db.queries as q
from app.db import core


def main():
    with TestClient(app) as owner:
        owner.post("/signup", data={"email": "boss@agency.com", "name": "Boss",
                                    "password": "password123"}, follow_redirects=False)
        user = q.get_user_by_email("boss@agency.com")
        ws = q.workspaces_for_user(user["id"])[0]
        core.execute("UPDATE workspaces SET plan='agency' WHERE id=?", (ws["id"],))

        r = owner.post("/team/invite", data={"email": "sdr@agency.com", "role": "reviewer"},
                       follow_redirects=False)
        print("invite:", r.status_code)
        token = q.invites_for_workspace(ws["id"])[0]["token"]

        joiner = TestClient(app)
        page = joiner.get(f"/join/{token}")
        print("join page:", page.status_code, "| shows role:", b"reviewer" in page.content)
        r = joiner.post(f"/join/{token}", data={"name": "SDR", "password": "password123"},
                        follow_redirects=False)
        print("join accept:", r.status_code)

        sdr = q.get_user_by_email("sdr@agency.com")
        print("joined role:", q.membership_role(sdr["id"], ws["id"]))

        r = joiner.post("/lists", data={"name": "Blocked"}, follow_redirects=False)
        print("reviewer create-list blocked:", r.status_code == 403)
        r = joiner.get("/")
        print("reviewer dashboard ok:", r.status_code == 200)

        team_page = owner.get("/team")
        print("team page ok:", team_page.status_code == 200,
              "| seat line:", b"2 of 10 seats" in team_page.content)
    print("ALL GOOD")


if __name__ == "__main__":
    main()
