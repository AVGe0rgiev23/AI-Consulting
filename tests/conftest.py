import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import config
from app.db import core, queries
from app.security import hash_password
from app.services import ratelimit


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    config.DB_PATH = tmp_path / "test.db"
    config.EXPORT_DIR = tmp_path / "exports"
    config.EXPORT_DIR.mkdir(exist_ok=True)
    config.USE_LLM_STUB = True
    config.USE_FETCH_STUB = True
    ratelimit.reset_for_tests()
    core.reset_for_tests(config.DB_PATH)
    yield


@pytest.fixture
def workspace():
    user_id = queries.create_user("t@example.com", "Test", hash_password("password123"))
    ws_id = queries.create_workspace("WS", user_id, 100)
    profile_id = queries.create_offer_profile(
        ws_id, "Default", "AI automation for lead follow-up",
        "B2B service businesses", "One client hit 16% replies", "consultative", "en", True
    )
    return {"user_id": user_id, "ws_id": ws_id, "profile_id": profile_id}


@pytest.fixture
def sample_list(workspace):
    list_id = queries.create_list(workspace["ws_id"], "Sample", "csv")
    for name, domain in [("Acme Logistics", "acme-logistics.com"), ("Beta Freight", "betafreight.io")]:
        queries.insert_lead(list_id, {
            "company_name": name, "domain": domain, "contact_name": "Sam Lee",
            "contact_title": "COO", "email": f"sam@{domain}", "linkedin_url": "",
            "raw": {}, "dedupe_hash": domain[:16],
        })
    queries.set_list_counts(list_id, 2, 0)
    return {"list_id": list_id, **workspace}


def make_client(email="u@example.com", plan=None):
    from fastapi.testclient import TestClient
    from app.main import app
    from app import security, config as cfg

    client = TestClient(app)
    user_id = queries.create_user(email, email.split("@")[0], hash_password("password123"))
    ws_id = queries.create_workspace(f"{email} WS", user_id, 100)
    queries.create_offer_profile(
        ws_id, "Default", "AI automation", "B2B", "", "consultative", "en", True
    )
    if plan:
        core.execute("UPDATE workspaces SET plan=? WHERE id=?", (plan, ws_id))
    client.cookies.set(cfg.SESSION_COOKIE, security.make_session(user_id))
    return client, {"user_id": user_id, "ws_id": ws_id}


def login_as(user_id):
    from fastapi.testclient import TestClient
    from app.main import app
    from app import security, config as cfg

    client = TestClient(app)
    client.cookies.set(cfg.SESSION_COOKIE, security.make_session(user_id))
    return client
