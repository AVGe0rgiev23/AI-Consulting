from app.db import queries
from app.llm import prompts

SLOT_DEFS = [
    ("voice", "Writing voice", "Voice & writing",
     "System rules every generated email and LinkedIn message must follow."),
    ("research", "Research extraction", "Research & analysis",
     "How factual findings are extracted from crawled pages and search results."),
    ("analysis", "Business analysis", "Research & analysis",
     "How pain points and opportunities are inferred from the findings."),
    ("email_step_1", "Email 1 — opener", "Email sequence",
     "Spec for the first email: hypothesis, artifact offer, soft permission question."),
    ("email_step_2", "Email 2 — redirect bump", "Email sequence",
     "Spec for the one-line 'someone else I should send this to?' follow-up."),
    ("email_step_3", "Email 3 — named asset", "Email sequence",
     "Spec for the email offering a specific asset built for the prospect."),
    ("email_step_4", "Email 4 — polite bump", "Email sequence",
     "Spec for the casual two-line reminder."),
    ("email_step_5", "Email 5 — angle pivot", "Email sequence",
     "Spec for the final email that pivots to the second-best hypothesis."),
    ("li_connect", "LinkedIn connection note", "LinkedIn",
     "Spec for the sub-300-character connection request."),
    ("li_dm", "LinkedIn DM", "LinkedIn",
     "Spec for the short direct message after connecting."),
    ("audit", "Audit report voice", "Audit reports",
     "Voice and grounding rules for the client-facing opportunity audit."),
]

GROUP_ORDER = ["Voice & writing", "Research & analysis", "Email sequence", "LinkedIn",
               "Audit reports"]


def defaults():
    base = {
        "voice": prompts.SYSTEM_VOICE,
        "research": prompts.EXTRACT_SYSTEM,
        "analysis": prompts.ANALYZE_SYSTEM,
        "audit": prompts.AUDIT_SYSTEM,
        "li_connect": prompts.LINKEDIN_SPECS["li_connect"],
        "li_dm": prompts.LINKEDIN_SPECS["li_dm"],
    }
    for step, spec in prompts.EMAIL_STEP_SPECS.items():
        base[f"email_step_{step}"] = spec
    return base


def slots():
    base = defaults()
    return [
        {"key": key, "label": label, "group": group, "description": description,
         "default": base[key]}
        for key, label, group, description in SLOT_DEFS
    ]


def slot_keys():
    return {key for key, _, _, _ in SLOT_DEFS}


def overrides(ws_id):
    known = slot_keys()
    return {k: v for k, v in queries.prompt_overrides(ws_id).items() if k in known}


def resolve(ws_id, key):
    base = defaults()
    if key not in base:
        raise ValueError(f"unknown prompt slot: {key}")
    if not ws_id:
        return base[key]
    override = queries.get_prompt_override(ws_id, key)
    return override if override else base[key]


def set_override(ws_id, key, content):
    base = defaults()
    if key not in base:
        raise ValueError(f"unknown prompt slot: {key}")
    content = (content or "").strip()
    if not content or content == base[key]:
        queries.delete_prompt_override(ws_id, key)
        return False
    queries.upsert_prompt_override(ws_id, key, content)
    return True


def clear_override(ws_id, key):
    if key not in slot_keys():
        raise ValueError(f"unknown prompt slot: {key}")
    queries.delete_prompt_override(ws_id, key)
