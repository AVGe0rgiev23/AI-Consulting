import csv
import io

from app.db import queries

_TRUE = {"1", "true", "yes", "y", "replied", "sent", "opened", "booked"}
_FIELDS = {
    "email": ["email", "email address", "lead email"],
    "sent": ["sent", "emails sent", "delivered"],
    "opened": ["opened", "open", "opens"],
    "replied": ["replied", "reply", "replies", "responded"],
    "meeting_booked": ["meeting", "meeting booked", "booked", "meetings"],
}


def parse_stats_csv(raw_bytes):
    text = raw_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return []
    lookup = _header_lookup(reader.fieldnames)
    if "email" not in lookup:
        return []
    rows = []
    for raw in reader:
        email = (raw.get(lookup["email"]) or "").strip()
        if not email:
            continue
        rows.append(
            {
                "email": email,
                "sent": _int(raw, lookup.get("sent")),
                "opened": _int(raw, lookup.get("opened")),
                "replied": _int(raw, lookup.get("replied")),
                "meeting_booked": _int(raw, lookup.get("meeting_booked")),
            }
        )
    return rows


def _header_lookup(fieldnames):
    lookup = {}
    for field in fieldnames:
        key = field.strip().lower()
        for target, aliases in _FIELDS.items():
            if key == target or key in aliases:
                lookup[target] = field
                break
    return lookup


def _int(raw, col):
    if not col:
        return 0
    value = (raw.get(col) or "").strip().lower()
    if value in _TRUE:
        return 1
    try:
        return 1 if int(float(value)) > 0 else 0
    except ValueError:
        return 0


def import_stats(ws_id, list_id, rows):
    lst = queries.get_list(list_id)
    campaign_id = queries.get_or_create_campaign(ws_id, list_id, lst["name"] if lst else "Campaign")
    matched = 0
    unmatched = 0
    for row in rows:
        lead = queries.lead_by_email_in_list(list_id, row["email"])
        if not lead:
            unmatched += 1
            continue
        category = queries.email1_category(lead["id"])
        sent = max(row["sent"], 1) if (row["opened"] or row["replied"]) else row["sent"]
        queries.upsert_campaign_stat(
            campaign_id, lead["id"], category, sent, row["opened"],
            row["replied"], row["meeting_booked"],
        )
        matched += 1
    return {"campaign_id": campaign_id, "matched": matched, "unmatched": unmatched}


def leaderboard(ws_id):
    rows = queries.hypothesis_leaderboard(ws_id)
    out = []
    for r in rows:
        sent = r["sent"] or 0
        replied = r["replied"] or 0
        out.append(
            {
                "category": r["category"],
                "leads": r["leads"],
                "sent": sent,
                "replied": replied,
                "meetings": r["meetings"] or 0,
                "reply_rate": round(replied / sent * 100, 1) if sent else 0.0,
            }
        )
    return out


def category_weights(ws_id):
    board = leaderboard(ws_id)
    weights = {}
    for row in board:
        if row["sent"] < 5:
            continue
        rate = row["reply_rate"] / 100
        weights[row["category"]] = round(min(rate * 2.0, 0.6), 3)
    return weights


def funnel(ws_id):
    f = queries.workspace_funnel(ws_id)
    sent = f["sent"] or 0
    replied = f["replied"] or 0
    return {
        "imported": f["imported"] or 0,
        "researched": f["researched"] or 0,
        "approved": f["approved"] or 0,
        "sent": sent,
        "replied": replied,
        "meetings": f["meetings"] or 0,
        "reply_rate": round(replied / sent * 100, 1) if sent else 0.0,
    }
