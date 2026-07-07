import re

from app import config


def score_asset(content, findings, is_email=True):
    text = content.strip()
    lower = text.lower()
    words = re.findall(r"\b[\w']+\b", text)
    word_count = len(words)

    slop_hits = [p for p in config.BANNED_PHRASES if p in lower]
    slop = 20 if not slop_hits else max(0, 20 - 7 * len(slop_hits))

    grounded = _grounding(lower, findings)
    evidence = 25 if grounded else 6
    specificity = 30 if (grounded or _has_specific_token(text)) else 10

    if is_email:
        line_count = len([l for l in text.splitlines() if l.strip()])
        good_len = 100 <= word_count <= 170
        good_lines = line_count <= 6
        ends_soft = text.rstrip().endswith("?")
        brevity = 15 if (good_len and good_lines) else (8 if good_lines else 3)
        cta = 10 if (ends_soft and not _has_imperative_cta(lower)) else 3
    else:
        brevity = 15 if word_count <= 90 else 8
        cta = 10 if text.rstrip().endswith("?") else 5

    total = slop + evidence + specificity + brevity + cta
    breakdown = {
        "specificity": specificity,
        "evidence": evidence,
        "slop": slop,
        "brevity": brevity,
        "cta": cta,
        "slop_hits": slop_hits,
        "word_count": word_count,
    }
    return min(100, total), breakdown


def _grounding(lower, findings):
    for f in findings:
        for token in _keywords(f["claim"]):
            if token in lower:
                return True
    return False


def _keywords(claim):
    return [w for w in re.findall(r"\b[\w']+\b", claim.lower()) if len(w) > 5]


def _has_specific_token(text):
    return bool(re.search(r"\d", text)) or bool(re.search(r"[A-Z][a-z]+ [A-Z][a-z]+", text))


def _has_imperative_cta(lower):
    triggers = ["book a call", "schedule a", "click here", "buy now", "sign up now", "calendly"]
    return any(t in lower for t in triggers)


def critique(breakdown):
    notes = []
    if breakdown["slop_hits"]:
        notes.append("Remove these phrases: " + ", ".join(breakdown["slop_hits"]) + ".")
    if breakdown["evidence"] < 25:
        notes.append("Reference a specific fact from the research, not a generic claim.")
    if breakdown["brevity"] < 15:
        notes.append("Cut it to under six short lines and 100-170 words.")
    if breakdown["cta"] < 10:
        notes.append("End on a soft permission question, no imperatives or links.")
    return " ".join(notes)
