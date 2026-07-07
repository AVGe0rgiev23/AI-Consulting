from app.db import queries


class InsufficientCredits(Exception):
    pass


def balance(ws_id):
    ws = queries.get_workspace(ws_id)
    return ws["credits_balance"] if ws else 0


def ensure(ws_id, amount):
    if balance(ws_id) < amount:
        raise InsufficientCredits(f"Need {amount} credits, have {balance(ws_id)}.")


def charge(ws_id, amount, reason, job_id=None):
    ensure(ws_id, amount)
    return queries.record_credits(ws_id, -amount, reason, job_id)


def grant(ws_id, amount, reason):
    return queries.record_credits(ws_id, amount, reason)
