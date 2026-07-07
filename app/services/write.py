from app import config
from app.db import queries
from app.llm import client, prompt_library, prompts, score
from app.services import research

EMAIL_STEPS = [1, 2, 3, 4, 5]
SCORE_THRESHOLD = 70


def generate_for_lead(lead_id, offer, kinds=None):
    brief = queries.get_brief_by_lead(lead_id)
    if not brief:
        return []
    if _insufficient_research(brief):
        return _generate_generic(lead_id, offer, kinds)
    findings = queries.findings_for_brief(brief["id"])
    hyps = queries.hypotheses_for_brief(brief["id"])
    if not hyps:
        return _generate_generic(lead_id, offer, kinds, no_angle=True)
    for h in hyps:
        import json

        h["evidence"] = json.loads(h["evidence_json"])
    primary = hyps[0]
    secondary = hyps[1] if len(hyps) > 1 else hyps[0]
    company = brief["company_summary"][:60] or "the company"
    company_name = _company_name(lead_id)
    ws_id = offer.get("workspace_id")

    kinds = kinds or ["email", "linkedin"]
    queries.clear_assets(lead_id)
    created = []

    quality = brief.get("quality") or 100
    if "email" in kinds:
        for step in EMAIL_STEPS:
            hyp = secondary if step == 5 else primary
            created.append(
                _make_email(lead_id, company_name, offer, hyp, findings, step, ws_id, quality)
            )
    if "linkedin" in kinds:
        created.append(
            _make_linkedin(lead_id, company_name, offer, primary, findings, "li_connect", ws_id)
        )
        created.append(
            _make_linkedin(lead_id, company_name, offer, primary, findings, "li_dm", ws_id)
        )
    return created


def _company_name(lead_id):
    lead = queries.get_lead(lead_id)
    return lead["company_name"] or lead["domain"] or "your company"


def _insufficient_research(brief):
    if brief["thin"]:
        return True
    quality = brief.get("quality") or 0
    return 0 < quality < config.QUALITY_FLOOR


def _generate_generic(lead_id, offer, kinds=None, no_angle=False):
    company_name = _company_name(lead_id)
    kinds = kinds or ["email", "linkedin"]
    queries.clear_assets(lead_id)
    created = []
    if "email" in kinds:
        for step in EMAIL_STEPS:
            data = _generic_email(company_name, offer, step, no_angle)
            created.append(_save_generic(lead_id, f"email_{step}", data, is_email=True))
    if "linkedin" in kinds:
        for kind in ("li_connect", "li_dm"):
            data = _generic_linkedin(company_name, offer, kind)
            created.append(_save_generic(lead_id, kind, data, is_email=False))
    return created


def _save_generic(lead_id, kind, data, is_email):
    body = data["body"]
    total, breakdown = score.score_asset(body, [], is_email=is_email)
    breakdown["insufficient_research"] = True
    asset = {
        "kind": kind,
        "hypothesis_id": None,
        "subject": data.get("subject", ""),
        "content": body,
        "score": total,
        "breakdown": breakdown,
        "status": "flagged",
    }
    asset["id"] = queries.insert_asset(lead_id, asset)
    return asset


def _generic_email(company_name, offer, step, no_angle=False):
    sell = offer.get("what_we_sell", "our service")
    proof = offer.get("proof_point", "")
    if step == 1:
        if no_angle:
            body = (
                f"I did my homework on {company_name} — plenty of public detail, but "
                f"nothing that gave me an angle specific enough to be worth your time, "
                f"and I'd rather not force one.\n\nWhat I can say: we help teams like "
                f"yours with {sell}.\n\nWould it be worth a short note on whether "
                f"that's relevant to you?"
            )
        else:
            body = (
                f"I'll be honest — I couldn't find enough public detail about "
                f"{company_name} to write you something specific, and I'd rather not "
                f"invent it.\n\nWhat I can say: we help teams like yours with {sell}.\n\n"
                f"Would it be worth a short note on whether that's relevant to you?"
            )
        return {"subject": company_name, "body": body}
    if step == 2:
        return {"subject": "",
                "body": f"Is there someone else at {company_name} I should ask about this?"}
    if step == 3:
        return {
            "subject": f"A question about {company_name}",
            "body": (
                f"Happy to put together a concrete example for {company_name} — could "
                f"you point me at whoever handles your inbound leads today?"
            ),
        }
    if step == 4:
        return {"subject": "", "body": "Did my earlier note reach the right person?"}
    tail = f" {proof}" if proof else ""
    return {
        "subject": "",
        "body": (
            f"Different angle: the teams that respond to inbound leads fastest tend to "
            f"win the most of them.{tail}\n\nWould it help to see what that could look "
            f"like at {company_name}?"
        ),
    }


def _generic_linkedin(company_name, offer, kind):
    if kind == "li_connect":
        return {"body": f"Building something for teams like {company_name} — mind connecting?"}
    return {
        "body": (
            f"I couldn't find much public detail on {company_name}, so no pitch — "
            f"just curious how you handle inbound leads today.\n"
            f"Open to comparing notes?"
        ),
    }


def _make_email(lead_id, company_name, offer, hyp, findings, step, ws_id, quality=100):
    def stub():
        return _stub_email(company_name, offer, hyp, findings, step)

    voice = prompt_library.resolve(ws_id, "voice")
    spec = prompt_library.resolve(ws_id, f"email_step_{step}")
    user_prompt = prompts.email_user(company_name, offer, hyp, findings, step, spec)
    if quality < 70:
        user_prompt += (
            "\n\nResearch quality is limited. Only reference the evidence provided above, "
            "verbatim. Do not extrapolate or invent any detail about the prospect."
        )
    data = client.complete_json(
        config.MODEL_SMART,
        voice,
        user_prompt,
        stub,
    )
    if not isinstance(data, dict):
        data = stub()
    subject = data.get("subject", "") if step in (1, 3) else ""
    if step == 1:
        subject = company_name
    body = data.get("body", "").strip()
    body = _run_score_and_maybe_fix(
        company_name, offer, hyp, findings, step, subject, body, voice, spec, is_email=True
    )
    if research.stale_evidence_only(findings, hyp.get("evidence", [])):
        subject = research.strip_temporal_framing(subject)
        body = research.strip_temporal_framing(body)
    total, breakdown = score.score_asset(body, findings, is_email=True)
    asset = {
        "kind": f"email_{step}",
        "hypothesis_id": hyp["id"],
        "subject": subject,
        "content": body,
        "score": total,
        "breakdown": breakdown,
        "status": "flagged" if total < SCORE_THRESHOLD else "draft",
    }
    asset_id = queries.insert_asset(lead_id, asset)
    asset["id"] = asset_id
    return asset


def _make_linkedin(lead_id, company_name, offer, hyp, findings, kind, ws_id):
    def stub():
        if kind == "li_connect":
            return {"body": f"Saw {company_name} is scaling ops. Building something adjacent — "
                            f"mind connecting?"}
        return {"body": f"Noticed {company_name} is hiring on the ops side.\n"
                        f"I'd guess quoting turnaround is getting tighter as you grow.\n"
                        f"Put together a quick example for you — want me to send it over?"}

    data = client.complete_json(
        config.MODEL_FAST,
        prompt_library.resolve(ws_id, "voice"),
        prompts.linkedin_user(company_name, offer, hyp, kind,
                              prompt_library.resolve(ws_id, kind)),
        stub,
    )
    if not isinstance(data, dict):
        data = stub()
    body = data.get("body", "").strip()
    if research.stale_evidence_only(findings, hyp.get("evidence", [])):
        body = research.strip_temporal_framing(body)
    total, breakdown = score.score_asset(body, findings, is_email=False)
    asset = {
        "kind": kind,
        "hypothesis_id": hyp["id"],
        "content": body,
        "score": total,
        "breakdown": breakdown,
        "status": "draft",
    }
    asset_id = queries.insert_asset(lead_id, asset)
    asset["id"] = asset_id
    return asset


def _run_score_and_maybe_fix(company_name, offer, hyp, findings, step, subject, body,
                             voice, spec, is_email):
    total, breakdown = score.score_asset(body, findings, is_email=is_email)
    if total >= SCORE_THRESHOLD or config.USE_LLM_STUB:
        return body
    note = score.critique(breakdown)
    fixed = client.complete_json(
        config.MODEL_SMART,
        voice,
        prompts.email_user(company_name, offer, hyp, findings, step, spec)
        + f"\n\nYour previous draft scored low. Fix it: {note}",
        lambda: {"subject": subject, "body": body},
    )
    if not isinstance(fixed, dict):
        return body
    return fixed.get("body", body).strip()


def _stub_email(company_name, offer, hyp, findings, step):
    proof = offer.get("proof_point", "")
    if step == 1:
        body = (
            f"I was going to call about your operations team, but figured I'd write first.\n\n"
            f"{hyp['statement']} I'd guess that's quietly costing you a few deals a week.\n\n"
            f"I put together a short example of what a faster path could look like for "
            f"{company_name}. Mind if I send it over?"
        )
        return {"subject": company_name, "body": body}
    if step == 2:
        return {"subject": "", "body": f"Is there someone else at {company_name} I should send this to?"}
    if step == 3:
        return {
            "subject": f"Quote-turnaround calculator for {company_name}",
            "body": (
                f"I built a quick calculator that estimates what slow quote turnaround costs "
                f"{company_name} each month.\n\nWant me to send it over?"
            ),
        }
    if step == 4:
        return {"subject": "", "body": "Had a bit of time to write today.\n\nDid you get a chance "
                                       "to see my note above?"}
    tail = f" {proof}" if proof else ""
    return {
        "subject": "",
        "body": (
            f"Different angle: the teams that respond to inbound quotes fastest tend to win "
            f"the most of them.{tail}\n\nWould it help to see how {company_name} could shave "
            f"hours off that? Happy to show you."
        ),
    }
