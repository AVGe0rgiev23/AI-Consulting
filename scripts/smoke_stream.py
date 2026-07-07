import json
import threading

from fastapi.testclient import TestClient

from app.main import app
import app.db.queries as q


def main():
    with TestClient(app) as c:
        c.post("/signup", data={"email": "s2@x.com", "name": "S2", "password": "password123"},
               follow_redirects=False)
        c.post("/onboarding", data={"what_we_sell": "AI lead follow-up", "icp": "agencies",
                                    "proof_point": "16% replies", "voice_preset": "consultative"},
               follow_redirects=False)
        csv = (b"Company,Domain,Email\n"
               b"Acme Logistics,acme-logistics.com,sam@acme-logistics.com\n"
               b"Beta Freight,betafreight.io,jo@betafreight.io\n")
        r = c.post("/lists", data={"name": "Stream List"},
                   files={"file": ("l.csv", csv, "text/csv")}, follow_redirects=False)
        lid = int(r.headers["location"].split("/")[-1])

        r = c.post(f"/lists/{lid}/research", data={}, follow_redirects=False)
        print("research redirect ->", r.headers.get("location"))
        page = c.get(f"/research/{lid}")
        print("live page ok:", page.status_code, "| has EventSource:", "EventSource" in page.text)

        received = []

        def consume():
            with c.stream("GET", f"/research/{lid}/stream") as resp:
                for line in resp.iter_lines():
                    if line and line.startswith("data: "):
                        ev = json.loads(line[6:])
                        received.append(ev)
                        print(f"  [{ev['phase']:<11}] {ev['done']}/{ev['total']}  {ev['message']}")
                        if ev["phase"] == "complete":
                            break

        t = threading.Thread(target=consume)
        t.start()
        t.join(timeout=30)

        phases = [e["phase"] for e in received]
        assert phases and phases[-1] == "complete", f"stream did not complete: {phases}"
        assert "found" in phases and "written" in phases
        print("STREAM OK — events:", len(received), "| final list status:",
              q.get_list(lid)["status"])
    print("ALL GOOD")


if __name__ == "__main__":
    main()
