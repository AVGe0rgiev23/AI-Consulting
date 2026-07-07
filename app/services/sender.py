from app import config
from app.db import queries

PROVIDERS = ["instantly", "smartlead"]
STEP_DELAY_DAYS = {1: 0, 2: 2, 3: 3, 4: 3, 5: 4}


class SenderError(Exception):
    pass


def api_key_for(ws, provider):
    settings = queries.get_settings(ws)
    return settings.get(f"{provider}_api_key", "").strip()


def connected_providers(ws):
    return [p for p in PROVIDERS if api_key_for(ws, p)]


def sequence_rows(list_id):
    rows = []
    for lead in queries.leads_for_list(list_id):
        if not lead["email"]:
            continue
        assets = queries.assets_for_lead(lead["id"])
        approved = [a for a in assets if a["status"] == "approved"]
        emails = {a["kind"]: a for a in approved if a["kind"].startswith("email_")}
        if not emails:
            continue
        variables = {}
        for step in range(1, 6):
            asset = emails.get(f"email_{step}")
            variables[f"email_{step}_subject"] = asset["subject"] if asset else ""
            variables[f"email_{step}_body"] = asset["content"] if asset else ""
        rows.append({"lead": lead, "variables": variables})
    return rows


def push_list(ws, list_id, provider, user_id=None):
    if provider not in PROVIDERS:
        raise SenderError(f"Unknown provider: {provider}")
    key = api_key_for(ws, provider)
    if not key:
        raise SenderError(
            f"No {provider.title()} API key configured. Add it in Settings first."
        )
    lst = queries.get_list(list_id)
    rows = sequence_rows(list_id)
    if not rows:
        raise SenderError("No approved emails to push yet. Approve leads in the review queue.")

    campaign_name = f"LeadGenius — {lst['name']}"
    if provider == "instantly":
        external_id = _push_instantly(key, campaign_name, rows)
    else:
        external_id = _push_smartlead(key, campaign_name, rows)

    push_id = queries.create_push(
        ws["id"], list_id, provider, campaign_name, str(external_id), len(rows)
    )
    queries.get_or_create_campaign(ws["id"], list_id, lst["name"], provider)
    for row in rows:
        queries.set_lead_status(row["lead"]["id"], "exported")
    queries.set_list_status(list_id, "exported")
    queries.log(ws["id"], user_id, "campaign_pushed", f"{lst['name']} → {provider}")
    return {"push_id": push_id, "external_id": str(external_id), "lead_count": len(rows)}


def _step_template(step):
    return {
        "subject": f"{{{{email_{step}_subject}}}}",
        "body": f"{{{{email_{step}_body}}}}",
    }


def _push_instantly(key, campaign_name, rows):
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    steps = []
    for step in range(1, 6):
        template = _step_template(step)
        steps.append(
            {
                "type": "email",
                "delay": STEP_DELAY_DAYS[step],
                "variants": [{"subject": template["subject"], "body": template["body"]}],
            }
        )
    campaign = _post(
        f"{config.INSTANTLY_API_BASE}/campaigns",
        headers,
        {
            "name": campaign_name,
            "campaign_schedule": {
                "schedules": [
                    {
                        "name": "Weekdays",
                        "timing": {"from": "09:00", "to": "17:00"},
                        "days": {"1": True, "2": True, "3": True, "4": True, "5": True},
                        "timezone": "Etc/GMT",
                    }
                ]
            },
            "sequences": [{"steps": steps}],
        },
    )
    campaign_id = campaign.get("id", "")
    for row in rows:
        lead = row["lead"]
        first_name = lead["contact_name"].split(" ")[0] if lead["contact_name"] else ""
        _post(
            f"{config.INSTANTLY_API_BASE}/leads",
            headers,
            {
                "campaign": campaign_id,
                "email": lead["email"],
                "first_name": first_name,
                "company_name": lead["company_name"],
                "website": lead["domain"],
                "custom_variables": row["variables"],
            },
        )
    return campaign_id


def _push_smartlead(key, campaign_name, rows):
    base = config.SMARTLEAD_API_BASE
    campaign = _post(f"{base}/campaigns/create?api_key={key}", {}, {"name": campaign_name})
    campaign_id = campaign.get("id", "")
    sequences = []
    for step in range(1, 6):
        template = _step_template(step)
        sequences.append(
            {
                "seq_number": step,
                "seq_delay_details": {"delay_in_days": STEP_DELAY_DAYS[step]},
                "subject": template["subject"] if step in (1, 3) else "",
                "email_body": template["body"],
            }
        )
    _post(
        f"{base}/campaigns/{campaign_id}/sequences?api_key={key}",
        {},
        {"sequences": sequences},
    )
    lead_list = []
    for row in rows:
        lead = row["lead"]
        first_name = lead["contact_name"].split(" ")[0] if lead["contact_name"] else ""
        lead_list.append(
            {
                "email": lead["email"],
                "first_name": first_name,
                "company_name": lead["company_name"],
                "website": lead["domain"],
                "custom_fields": row["variables"],
            }
        )
    _post(f"{base}/campaigns/{campaign_id}/leads?api_key={key}", {}, {"lead_list": lead_list})
    return campaign_id


def pull_stats(ws, list_id, provider, user_id=None):
    if provider not in PROVIDERS:
        raise SenderError(f"Unknown provider: {provider}")
    key = api_key_for(ws, provider)
    if not key:
        raise SenderError(
            f"No {provider.title()} API key configured. Add it in Settings first."
        )
    push = queries.latest_push_for_list(list_id, provider)
    if not push:
        raise SenderError("This list was never pushed to that provider.")
    lst = queries.get_list(list_id)

    if config.USE_SENDER_STUB:
        rows = _stub_stats(list_id)
    elif provider == "instantly":
        rows = _pull_instantly(key, push["external_id"])
    else:
        rows = _pull_smartlead(key, push["external_id"])

    from app.services import feedback

    result = feedback.import_stats(ws["id"], list_id, rows)
    queries.log(ws["id"], user_id, "stats_pulled", f"{lst['name']} ← {provider}")
    return {**result, "pulled": len(rows), "provider": provider}


def _stub_stats(list_id):
    leads = [l for l in queries.leads_for_list(list_id) if l["email"]]
    leads.sort(key=lambda l: l["email"])
    rows = []
    for i, lead in enumerate(leads):
        rows.append(
            {
                "email": lead["email"],
                "sent": 1,
                "opened": 1 if i % 2 == 0 else 0,
                "replied": 1 if i == 0 else 0,
                "meeting_booked": 0,
            }
        )
    return rows


def _pull_instantly(key, campaign_id):
    headers = {"Authorization": f"Bearer {key}"}
    data = _get(
        f"{config.INSTANTLY_API_BASE}/leads?campaign={campaign_id}&limit=100", headers
    )
    rows = []
    for item in data.get("items", data.get("leads", [])):
        email = (item.get("email") or "").strip()
        if not email:
            continue
        rows.append(
            {
                "email": email,
                "sent": 1,
                "opened": 1 if (item.get("email_open_count") or 0) > 0 else 0,
                "replied": 1 if (item.get("email_reply_count") or 0) > 0 else 0,
                "meeting_booked": 1 if item.get("interest_status") == "meeting_booked" else 0,
            }
        )
    return rows


def _pull_smartlead(key, campaign_id):
    base = config.SMARTLEAD_API_BASE
    data = _get(f"{base}/campaigns/{campaign_id}/statistics?api_key={key}", {})
    rows = []
    for item in data.get("data", []):
        email = (item.get("lead_email") or item.get("email") or "").strip()
        if not email:
            continue
        rows.append(
            {
                "email": email,
                "sent": 1 if (item.get("sent_count") or 0) > 0 else 0,
                "opened": 1 if (item.get("open_count") or 0) > 0 else 0,
                "replied": 1 if (item.get("reply_count") or 0) > 0 else 0,
                "meeting_booked": 1 if item.get("is_interested") else 0,
            }
        )
    return rows


def _get(url, headers):
    if config.USE_SENDER_STUB:
        return {}
    import httpx

    try:
        resp = httpx.get(url, headers=headers, timeout=30)
    except httpx.HTTPError as e:
        raise SenderError(f"Request to {url.split('?')[0]} failed: {e}") from e
    if resp.status_code >= 400:
        raise SenderError(
            f"{url.split('?')[0]} returned {resp.status_code}: {resp.text[:200]}"
        )
    try:
        return resp.json()
    except ValueError:
        return {}


def _post(url, headers, payload):
    if config.USE_SENDER_STUB:
        return {"id": f"stub-{len(url) % 1000}", "ok": True}
    import httpx

    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=30)
    except httpx.HTTPError as e:
        raise SenderError(f"Request to {url.split('?')[0]} failed: {e}") from e
    if resp.status_code >= 400:
        raise SenderError(
            f"{url.split('?')[0]} returned {resp.status_code}: {resp.text[:200]}"
        )
    try:
        return resp.json()
    except ValueError:
        return {}
