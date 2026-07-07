from app.db import queries

DEFAULTS = {
    "brand_name": "LeadGenius",
    "accent": "#b07a1e",
    "report_title": "AI Opportunity Audit",
    "contact": "",
}


def branding(ws):
    settings = queries.get_settings(ws)
    brand = dict(DEFAULTS)
    brand["brand_name"] = ws["name"] or DEFAULTS["brand_name"]
    for key in DEFAULTS:
        value = settings.get(key)
        if value:
            brand[key] = value
    return brand
