from app import deps
from app.db import queries


def test_role_rank_ordering():
    assert deps.ROLE_RANK["owner"] > deps.ROLE_RANK["admin"]
    assert deps.ROLE_RANK["admin"] > deps.ROLE_RANK["member"]
    assert deps.ROLE_RANK["member"] > deps.ROLE_RANK["reviewer"]


def test_membership_helpers(workspace):
    ws_id = workspace["ws_id"]
    assert queries.membership_role(workspace["user_id"], ws_id) == "owner"
    other = queries.create_user("m@x.com", "M", "hash")
    queries.add_membership(other, ws_id, "reviewer")
    assert queries.membership_role(other, ws_id) == "reviewer"
    queries.update_membership_role(other, ws_id, "admin")
    assert queries.membership_role(other, ws_id) == "admin"
    queries.remove_membership(other, ws_id)
    assert queries.membership_role(other, ws_id) == ""


def test_seat_count_includes_pending_invites(workspace):
    ws_id = workspace["ws_id"]
    assert queries.seat_count(ws_id) == 1
    queries.create_invite(ws_id, "new@x.com", "member", "tok123", workspace["user_id"])
    assert queries.seat_count(ws_id) == 2


def test_invite_lookup_and_expiry(workspace):
    ws_id = workspace["ws_id"]
    queries.create_invite(ws_id, "new@x.com", "member", "tokabc", workspace["user_id"])
    assert queries.get_invite("tokabc")["email"] == "new@x.com"
    assert queries.get_invite("wrong") is None
    from app.db import core
    core.execute("UPDATE invites SET created_at=datetime('now','-20 days') WHERE token='tokabc'")
    assert queries.get_invite("tokabc") is None
