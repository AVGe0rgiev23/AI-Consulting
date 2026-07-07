import pytest

from app.services import credits


def test_charge_reduces_balance(workspace):
    ws = workspace["ws_id"]
    start = credits.balance(ws)
    credits.charge(ws, 5, "research")
    assert credits.balance(ws) == start - 5


def test_charge_beyond_balance_raises(workspace):
    ws = workspace["ws_id"]
    with pytest.raises(credits.InsufficientCredits):
        credits.charge(ws, 9999, "research")


def test_grant_adds_and_logs_ledger(workspace):
    ws = workspace["ws_id"]
    credits.grant(ws, 10, "bonus")
    from app.db import queries
    entries = queries.ledger(ws)
    assert entries[0]["delta"] == 10
