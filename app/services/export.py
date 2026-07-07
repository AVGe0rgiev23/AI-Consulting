import csv
import io

from app.db import queries

FORMATS = ["csv", "instantly", "smartlead"]


def build_export(list_id, fmt):
    leads = queries.leads_for_list(list_id)
    rows = []
    for lead in leads:
        assets = queries.assets_for_lead(lead["id"])
        approved = [a for a in assets if a["status"] == "approved"]
        emails = {a["kind"]: a for a in approved if a["kind"].startswith("email_")}
        if not emails:
            continue
        rows.append(_row_for(lead, emails, fmt))
    return _render(rows, fmt)


def _row_for(lead, emails, fmt):
    first = emails.get("email_1")
    base = {
        "company_name": lead["company_name"],
        "domain": lead["domain"],
        "email": lead["email"],
        "contact_name": lead["contact_name"],
    }
    if fmt == "instantly":
        base.update(
            {
                "subject": first["subject"] if first else "",
                "body": first["content"] if first else "",
                "step2": emails.get("email_2", {}).get("content", ""),
                "step3": emails.get("email_3", {}).get("content", ""),
                "step4": emails.get("email_4", {}).get("content", ""),
                "step5": emails.get("email_5", {}).get("content", ""),
            }
        )
    elif fmt == "smartlead":
        base.update(
            {
                "email_subject": first["subject"] if first else "",
                "email_body": first["content"] if first else "",
            }
        )
    else:
        for kind, a in sorted(emails.items()):
            base[kind + "_subject"] = a["subject"]
            base[kind + "_body"] = a["content"]
    return base


def _render(rows, fmt):
    if not rows:
        return "", 0
    fieldnames = list(rows[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return buf.getvalue(), len(rows)


def save_export(ws_id, list_id, fmt):
    from app import config

    content, count = build_export(list_id, fmt)
    if count == 0:
        return None, 0
    path = config.EXPORT_DIR / f"list{list_id}_{fmt}.csv"
    path.write_text(content, encoding="utf-8")
    queries.record_export(ws_id, list_id, fmt, count, str(path))
    return str(path), count
