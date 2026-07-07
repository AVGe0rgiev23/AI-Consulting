import json

from app import config
from app.db import core


def create_user(email, name, password_hash):
    return core.execute(
        "INSERT INTO users(email, name, password_hash) VALUES(?,?,?)",
        (email.lower().strip(), name, password_hash),
    )


def get_user_by_email(email):
    return core.query_one("SELECT * FROM users WHERE email=?", (email.lower().strip(),))


def get_user(user_id):
    return core.query_one("SELECT * FROM users WHERE id=?", (user_id,))


def create_workspace(name, owner_id, credits):
    ws_id = core.execute(
        "INSERT INTO workspaces(name, owner_id, credits_balance) VALUES(?,?,?)",
        (name, owner_id, credits),
    )
    core.execute(
        "INSERT INTO memberships(user_id, workspace_id, role) VALUES(?,?,'owner')",
        (owner_id, ws_id),
    )
    return ws_id


def get_workspace(ws_id):
    return core.query_one("SELECT * FROM workspaces WHERE id=?", (ws_id,))


def workspaces_for_user(user_id):
    return core.query_all(
        "SELECT w.* FROM workspaces w JOIN memberships m ON m.workspace_id=w.id "
        "WHERE m.user_id=? ORDER BY w.id",
        (user_id,),
    )


def is_member(user_id, ws_id):
    return core.query_one(
        "SELECT 1 FROM memberships WHERE user_id=? AND workspace_id=?", (user_id, ws_id)
    ) is not None


def membership_role(user_id, ws_id):
    row = core.query_one(
        "SELECT role FROM memberships WHERE user_id=? AND workspace_id=?", (user_id, ws_id)
    )
    return row["role"] if row else ""


def members_of_workspace(ws_id):
    return core.query_all(
        "SELECT u.id, u.email, u.name, m.role FROM users u "
        "JOIN memberships m ON m.user_id=u.id WHERE m.workspace_id=? ORDER BY u.id",
        (ws_id,),
    )


def add_membership(user_id, ws_id, role):
    core.execute(
        "INSERT INTO memberships(user_id, workspace_id, role) VALUES(?,?,?) "
        "ON CONFLICT(user_id, workspace_id) DO NOTHING",
        (user_id, ws_id, role),
    )


def update_membership_role(user_id, ws_id, role):
    core.execute(
        "UPDATE memberships SET role=? WHERE user_id=? AND workspace_id=?",
        (role, user_id, ws_id),
    )


def remove_membership(user_id, ws_id):
    core.execute(
        "DELETE FROM memberships WHERE user_id=? AND workspace_id=?", (user_id, ws_id)
    )


def create_invite(ws_id, email, role, token, invited_by):
    return core.execute(
        "INSERT INTO invites(workspace_id, email, role, token, invited_by) VALUES(?,?,?,?,?)",
        (ws_id, email.lower().strip(), role, token, invited_by),
    )


def get_invite(token, max_age_days=14):
    return core.query_one(
        "SELECT * FROM invites WHERE token=? AND "
        "julianday('now') - julianday(created_at) < ?",
        (token, max_age_days),
    )


def invites_for_workspace(ws_id):
    return core.query_all(
        "SELECT * FROM invites WHERE workspace_id=? ORDER BY id DESC", (ws_id,)
    )


def delete_invite(invite_id):
    core.execute("DELETE FROM invites WHERE id=?", (invite_id,))


def seat_count(ws_id):
    members = core.query_one(
        "SELECT COUNT(*) n FROM memberships WHERE workspace_id=?", (ws_id,)
    )["n"]
    pending = core.query_one(
        "SELECT COUNT(*) n FROM invites WHERE workspace_id=?", (ws_id,)
    )["n"]
    return members + pending


def create_offer_profile(ws_id, name, what_we_sell, icp, proof_point, voice, language, is_default):
    if is_default:
        core.execute("UPDATE offer_profiles SET is_default=0 WHERE workspace_id=?", (ws_id,))
    return core.execute(
        "INSERT INTO offer_profiles(workspace_id, name, what_we_sell, icp, proof_point, "
        "voice_preset, language, is_default) VALUES(?,?,?,?,?,?,?,?)",
        (ws_id, name, what_we_sell, icp, proof_point, voice, language, 1 if is_default else 0),
    )


def get_offer_profile(profile_id):
    return core.query_one("SELECT * FROM offer_profiles WHERE id=?", (profile_id,))


def default_offer_profile(ws_id):
    return core.query_one(
        "SELECT * FROM offer_profiles WHERE workspace_id=? ORDER BY is_default DESC, id LIMIT 1",
        (ws_id,),
    )


def offer_profiles(ws_id):
    return core.query_all(
        "SELECT * FROM offer_profiles WHERE workspace_id=? ORDER BY id", (ws_id,)
    )


def create_list(ws_id, name, source):
    return core.execute(
        "INSERT INTO lead_lists(workspace_id, name, source) VALUES(?,?,?)",
        (ws_id, name, source),
    )


def get_list(list_id):
    return core.query_one("SELECT * FROM lead_lists WHERE id=?", (list_id,))


def lists_for_workspace(ws_id):
    return core.query_all(
        "SELECT * FROM lead_lists WHERE workspace_id=? AND source!='audit' ORDER BY id DESC",
        (ws_id,),
    )


def get_or_create_audit_list(ws_id):
    row = core.query_one(
        "SELECT * FROM lead_lists WHERE workspace_id=? AND source='audit' LIMIT 1", (ws_id,)
    )
    if row:
        return row["id"]
    return core.execute(
        "INSERT INTO lead_lists(workspace_id, name, source, status) "
        "VALUES(?,'Audits','audit','internal')",
        (ws_id,),
    )


def set_list_status(list_id, status):
    core.execute("UPDATE lead_lists SET status=? WHERE id=?", (status, list_id))


def set_list_counts(list_id, row_count, error_count):
    core.execute(
        "UPDATE lead_lists SET row_count=?, error_count=? WHERE id=?",
        (row_count, error_count, list_id),
    )


def insert_lead(list_id, lead):
    return core.execute(
        "INSERT INTO leads(list_id, company_name, domain, contact_name, contact_title, "
        "email, linkedin_url, raw_json, dedupe_hash) VALUES(?,?,?,?,?,?,?,?,?)",
        (
            list_id,
            lead["company_name"],
            lead["domain"],
            lead["contact_name"],
            lead["contact_title"],
            lead["email"],
            lead["linkedin_url"],
            json.dumps(lead["raw"]),
            lead["dedupe_hash"],
        ),
    )


def get_lead(lead_id):
    return core.query_one("SELECT * FROM leads WHERE id=?", (lead_id,))


def leads_for_list(list_id):
    return core.query_all(
        "SELECT * FROM leads WHERE list_id=? ORDER BY id", (list_id,)
    )


def existing_dedupe_hashes(list_id):
    rows = core.query_all("SELECT dedupe_hash FROM leads WHERE list_id=?", (list_id,))
    return {r["dedupe_hash"] for r in rows}


def set_lead_status(lead_id, status, reason=""):
    core.execute(
        "UPDATE leads SET status=?, status_reason=? WHERE id=?", (status, reason, lead_id)
    )


def create_job(ws_id, kind, payload):
    return core.execute(
        "INSERT INTO jobs(workspace_id, kind, payload_json) VALUES(?,?,?)",
        (ws_id, kind, json.dumps(payload)),
    )


def claim_next_job():
    conn = core.get_conn()
    _recover_stale_jobs(conn)
    row = conn.execute(
        "SELECT * FROM jobs WHERE status='queued' ORDER BY id LIMIT 1"
    ).fetchone()
    if not row:
        return None
    cur = conn.execute(
        "UPDATE jobs SET status='running', claimed_at=datetime('now'), attempts=attempts+1 "
        "WHERE id=? AND status='queued'",
        (row["id"],),
    )
    conn.commit()
    if cur.rowcount == 0:
        return None
    return dict(row)


def _recover_stale_jobs(conn):
    stale_days = config.STALE_JOB_MINUTES / (24 * 60)
    conn.execute(
        "UPDATE jobs SET status='failed', error='gave up after repeated attempts', "
        "finished_at=datetime('now') WHERE status='running' AND attempts>=? "
        "AND julianday('now') - julianday(claimed_at) > ?",
        (config.MAX_JOB_ATTEMPTS, stale_days),
    )
    conn.execute(
        "UPDATE jobs SET status='queued' WHERE status='running' "
        "AND julianday('now') - julianday(claimed_at) > ?",
        (stale_days,),
    )
    conn.commit()


def finish_job(job_id, status, error=""):
    core.execute(
        "UPDATE jobs SET status=?, error=?, finished_at=datetime('now') WHERE id=?",
        (status, error, job_id),
    )


def get_job(job_id):
    return core.query_one("SELECT * FROM jobs WHERE id=?", (job_id,))


def list_job_counts(list_id):
    return core.query_all(
        "SELECT status, COUNT(*) n FROM leads WHERE list_id=? GROUP BY status",
        (list_id,),
    )


def save_brief(lead_id, brief):
    brief_id = core.execute(
        "INSERT INTO research_briefs(lead_id, company_summary, industry, size_estimate, "
        "tech_stack_json, positioning, digest_md, thin, quality, thin_reason) "
        "VALUES(?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(lead_id) DO UPDATE SET company_summary=excluded.company_summary, "
        "industry=excluded.industry, size_estimate=excluded.size_estimate, "
        "tech_stack_json=excluded.tech_stack_json, positioning=excluded.positioning, "
        "digest_md=excluded.digest_md, thin=excluded.thin, quality=excluded.quality, "
        "thin_reason=excluded.thin_reason",
        (
            lead_id,
            brief["company_summary"],
            brief["industry"],
            brief["size_estimate"],
            json.dumps(brief["tech_stack"]),
            brief["positioning"],
            brief["digest_md"],
            1 if brief.get("thin") else 0,
            brief.get("quality", 0),
            brief.get("thin_reason", ""),
        ),
    )
    row = core.query_one("SELECT id FROM research_briefs WHERE lead_id=?", (lead_id,))
    return row["id"]


def get_brief_by_lead(lead_id):
    return core.query_one("SELECT * FROM research_briefs WHERE lead_id=?", (lead_id,))


def get_brief(brief_id):
    return core.query_one("SELECT * FROM research_briefs WHERE id=?", (brief_id,))


def briefs_by_lead_for_list(list_id):
    rows = core.query_all(
        "SELECT b.* FROM research_briefs b JOIN leads l ON l.id = b.lead_id "
        "WHERE l.list_id=?",
        (list_id,),
    )
    return {r["lead_id"]: r for r in rows}


def clear_findings(brief_id):
    core.execute("DELETE FROM findings WHERE brief_id=?", (brief_id,))
    core.execute("DELETE FROM hypotheses WHERE brief_id=?", (brief_id,))


def insert_finding(brief_id, f):
    return core.execute(
        "INSERT INTO findings(brief_id, kind, claim, source_url, snippet, confidence, "
        "published_at) VALUES(?,?,?,?,?,?,?)",
        (brief_id, f["kind"], f["claim"], f["source_url"], f["snippet"], f["confidence"],
         f.get("published_at", "")),
    )


def findings_for_brief(brief_id):
    return core.query_all(
        "SELECT * FROM findings WHERE brief_id=? ORDER BY confidence DESC", (brief_id,)
    )


def insert_hypothesis(brief_id, h):
    return core.execute(
        "INSERT INTO hypotheses(brief_id, rank, category, statement, evidence_json, confidence) "
        "VALUES(?,?,?,?,?,?)",
        (brief_id, h["rank"], h["category"], h["statement"],
         json.dumps(h["evidence"]), h["confidence"]),
    )


def hypotheses_for_brief(brief_id):
    return core.query_all(
        "SELECT * FROM hypotheses WHERE brief_id=? ORDER BY rank", (brief_id,)
    )


def get_hypothesis(hyp_id):
    return core.query_one("SELECT * FROM hypotheses WHERE id=?", (hyp_id,))


def clear_assets(lead_id):
    core.execute("DELETE FROM assets WHERE lead_id=?", (lead_id,))


def insert_asset(lead_id, a):
    return core.execute(
        "INSERT INTO assets(lead_id, kind, hypothesis_id, subject, content, score, "
        "score_breakdown_json, status, version) VALUES(?,?,?,?,?,?,?,?,?)",
        (lead_id, a["kind"], a.get("hypothesis_id"), a.get("subject", ""), a["content"],
         a["score"], json.dumps(a.get("breakdown", {})), a.get("status", "draft"),
         a.get("version", 1)),
    )


def assets_for_lead(lead_id):
    return core.query_all(
        "SELECT * FROM assets WHERE lead_id=? ORDER BY kind, id", (lead_id,)
    )


def get_asset(asset_id):
    return core.query_one("SELECT * FROM assets WHERE id=?", (asset_id,))


def update_asset(asset_id, content, subject, score, breakdown, status, version):
    core.execute(
        "UPDATE assets SET content=?, subject=?, score=?, score_breakdown_json=?, "
        "status=?, version=? WHERE id=?",
        (content, subject, score, json.dumps(breakdown), status, version, asset_id),
    )


def set_asset_status(asset_id, status):
    core.execute("UPDATE assets SET status=? WHERE id=?", (status, asset_id))


def record_credits(ws_id, delta, reason, job_id=None):
    ws = get_workspace(ws_id)
    new_balance = ws["credits_balance"] + delta
    core.execute("UPDATE workspaces SET credits_balance=? WHERE id=?", (new_balance, ws_id))
    core.execute(
        "INSERT INTO credits_ledger(workspace_id, delta, reason, job_id, balance_after) "
        "VALUES(?,?,?,?,?)",
        (ws_id, delta, reason, job_id, new_balance),
    )
    return new_balance


def ledger(ws_id, limit=50):
    return core.query_all(
        "SELECT * FROM credits_ledger WHERE workspace_id=? ORDER BY id DESC LIMIT ?",
        (ws_id, limit),
    )


def emit_event(list_id, phase, message="", lead_id=None, done=0, total=0):
    return core.execute(
        "INSERT INTO research_events(list_id, lead_id, phase, message, done, total) "
        "VALUES(?,?,?,?,?,?)",
        (list_id, lead_id, phase, message, done, total),
    )


def events_since(list_id, after_id):
    return core.query_all(
        "SELECT * FROM research_events WHERE list_id=? AND id>? ORDER BY id",
        (list_id, after_id),
    )


def latest_event(list_id):
    return core.query_one(
        "SELECT * FROM research_events WHERE list_id=? ORDER BY id DESC LIMIT 1",
        (list_id,),
    )


def clear_events(list_id):
    core.execute("DELETE FROM research_events WHERE list_id=?", (list_id,))


def get_settings(ws):
    try:
        return json.loads(ws["settings_json"]) if ws["settings_json"] else {}
    except (json.JSONDecodeError, KeyError, TypeError):
        return {}


def update_workspace_settings(ws_id, settings):
    core.execute(
        "UPDATE workspaces SET settings_json=? WHERE id=?", (json.dumps(settings), ws_id)
    )


def create_audit_report(ws_id, lead_id, company_name, domain, exec_summary, opportunities):
    return core.execute(
        "INSERT INTO audit_reports(workspace_id, lead_id, company_name, domain, exec_summary, "
        "opportunities_json) VALUES(?,?,?,?,?,?)",
        (ws_id, lead_id, company_name, domain, exec_summary, json.dumps(opportunities)),
    )


def get_audit_report(report_id):
    return core.query_one("SELECT * FROM audit_reports WHERE id=?", (report_id,))


def audit_reports_for_workspace(ws_id):
    return core.query_all(
        "SELECT * FROM audit_reports WHERE workspace_id=? ORDER BY id DESC", (ws_id,)
    )


def get_or_create_campaign(ws_id, list_id, name, exported_to=""):
    row = core.query_one(
        "SELECT * FROM campaigns WHERE list_id=? ORDER BY id LIMIT 1", (list_id,)
    )
    if row:
        return row["id"]
    return core.execute(
        "INSERT INTO campaigns(workspace_id, list_id, name, exported_to) VALUES(?,?,?,?)",
        (ws_id, list_id, name, exported_to),
    )


def campaigns_for_workspace(ws_id):
    return core.query_all(
        "SELECT * FROM campaigns WHERE workspace_id=? ORDER BY id DESC", (ws_id,)
    )


def lead_by_email_in_list(list_id, email):
    return core.query_one(
        "SELECT * FROM leads WHERE list_id=? AND lower(email)=?",
        (list_id, email.lower().strip()),
    )


def email1_category(lead_id):
    row = core.query_one(
        "SELECT h.category FROM assets a JOIN hypotheses h ON h.id=a.hypothesis_id "
        "WHERE a.lead_id=? AND a.kind='email_1' ORDER BY a.id DESC LIMIT 1",
        (lead_id,),
    )
    return row["category"] if row else ""


def upsert_campaign_stat(campaign_id, lead_id, category, sent, opened, replied, meeting):
    core.execute(
        "INSERT INTO campaign_stats(campaign_id, lead_id, hypothesis_category, sent, opened, "
        "replied, meeting_booked) VALUES(?,?,?,?,?,?,?) "
        "ON CONFLICT(campaign_id, lead_id) DO UPDATE SET hypothesis_category=excluded.hypothesis_category, "
        "sent=excluded.sent, opened=excluded.opened, replied=excluded.replied, "
        "meeting_booked=excluded.meeting_booked, imported_at=datetime('now')",
        (campaign_id, lead_id, category, sent, opened, replied, meeting),
    )


def hypothesis_leaderboard(ws_id):
    return core.query_all(
        "SELECT cs.hypothesis_category category, "
        "COUNT(*) leads, SUM(cs.sent) sent, SUM(cs.opened) opened, "
        "SUM(cs.replied) replied, SUM(cs.meeting_booked) meetings "
        "FROM campaign_stats cs JOIN campaigns c ON c.id=cs.campaign_id "
        "WHERE c.workspace_id=? AND cs.hypothesis_category != '' "
        "GROUP BY cs.hypothesis_category ORDER BY replied*1.0/MAX(SUM(cs.sent),1) DESC",
        (ws_id,),
    )


def workspace_funnel(ws_id):
    return core.query_one(
        "SELECT "
        "(SELECT COUNT(*) FROM leads l JOIN lead_lists ll ON ll.id=l.list_id "
        " WHERE ll.workspace_id=? AND ll.source!='audit') imported, "
        "(SELECT COUNT(*) FROM leads l JOIN lead_lists ll ON ll.id=l.list_id "
        " WHERE ll.workspace_id=? AND ll.source!='audit' "
        " AND l.status IN ('ready','approved','exported')) researched, "
        "(SELECT COUNT(*) FROM leads l JOIN lead_lists ll ON ll.id=l.list_id "
        " WHERE ll.workspace_id=? AND ll.source!='audit' "
        " AND l.status IN ('approved','exported')) approved, "
        "(SELECT COALESCE(SUM(cs.sent),0) FROM campaign_stats cs JOIN campaigns c "
        " ON c.id=cs.campaign_id WHERE c.workspace_id=?) sent, "
        "(SELECT COALESCE(SUM(cs.replied),0) FROM campaign_stats cs JOIN campaigns c "
        " ON c.id=cs.campaign_id WHERE c.workspace_id=?) replied, "
        "(SELECT COALESCE(SUM(cs.meeting_booked),0) FROM campaign_stats cs JOIN campaigns c "
        " ON c.id=cs.campaign_id WHERE c.workspace_id=?) meetings",
        (ws_id, ws_id, ws_id, ws_id, ws_id, ws_id),
    )


def record_export(ws_id, list_id, fmt, row_count, path):
    return core.execute(
        "INSERT INTO exports(workspace_id, list_id, format, row_count, file_path) "
        "VALUES(?,?,?,?,?)",
        (ws_id, list_id, fmt, row_count, path),
    )


def log(ws_id, user_id, action, target=""):
    core.execute(
        "INSERT INTO activity_log(workspace_id, user_id, action, target) VALUES(?,?,?,?)",
        (ws_id, user_id, action, target),
    )


def recent_activity(ws_id, limit=15):
    return core.query_all(
        "SELECT * FROM activity_log WHERE workspace_id=? ORDER BY id DESC LIMIT ?",
        (ws_id, limit),
    )


def create_push(ws_id, list_id, provider, campaign_name, external_id, lead_count):
    return core.execute(
        "INSERT INTO integration_pushes(workspace_id, list_id, provider, campaign_name, "
        "external_id, lead_count) VALUES(?,?,?,?,?,?)",
        (ws_id, list_id, provider, campaign_name, external_id, lead_count),
    )


def pushes_for_workspace(ws_id, limit=20):
    return core.query_all(
        "SELECT p.*, ll.name list_name FROM integration_pushes p "
        "JOIN lead_lists ll ON ll.id=p.list_id "
        "WHERE p.workspace_id=? ORDER BY p.id DESC LIMIT ?",
        (ws_id, limit),
    )


def latest_push_for_list(list_id, provider):
    return core.query_one(
        "SELECT * FROM integration_pushes WHERE list_id=? AND provider=? "
        "ORDER BY id DESC LIMIT 1",
        (list_id, provider),
    )


def prompt_overrides(ws_id):
    rows = core.query_all(
        "SELECT slot, content FROM prompt_templates WHERE workspace_id=?", (ws_id,)
    )
    return {r["slot"]: r["content"] for r in rows}


def get_prompt_override(ws_id, slot):
    row = core.query_one(
        "SELECT content FROM prompt_templates WHERE workspace_id=? AND slot=?",
        (ws_id, slot),
    )
    return row["content"] if row else None


def upsert_prompt_override(ws_id, slot, content):
    core.execute(
        "INSERT INTO prompt_templates(workspace_id, slot, content) VALUES(?,?,?) "
        "ON CONFLICT(workspace_id, slot) DO UPDATE SET content=excluded.content, "
        "updated_at=datetime('now')",
        (ws_id, slot, content),
    )


def delete_prompt_override(ws_id, slot):
    core.execute(
        "DELETE FROM prompt_templates WHERE workspace_id=? AND slot=?", (ws_id, slot)
    )


def get_cached_domain(domain, max_age_days):
    return core.query_one(
        "SELECT * FROM domain_cache WHERE domain=? AND "
        "julianday('now') - julianday(fetched_at) < ?",
        (domain, max_age_days),
    )


def set_cached_domain(domain, pages_json):
    core.execute(
        "INSERT INTO domain_cache(domain, pages_json, fetched_at) VALUES(?,?,datetime('now')) "
        "ON CONFLICT(domain) DO UPDATE SET pages_json=excluded.pages_json, "
        "fetched_at=datetime('now')",
        (domain, pages_json),
    )


def create_api_key(ws_id, name, hashed_key):
    return core.execute(
        "INSERT INTO api_keys(workspace_id, name, hashed_key) VALUES(?,?,?)",
        (ws_id, name, hashed_key),
    )


def api_keys_for_workspace(ws_id):
    return core.query_all(
        "SELECT id, name, created_at, last_used_at, revoked_at FROM api_keys "
        "WHERE workspace_id=? ORDER BY id DESC",
        (ws_id,),
    )


def get_api_key_by_hash(hashed_key):
    return core.query_one("SELECT * FROM api_keys WHERE hashed_key=?", (hashed_key,))


def touch_api_key(key_id):
    core.execute(
        "UPDATE api_keys SET last_used_at=datetime('now') WHERE id=?", (key_id,)
    )


def revoke_api_key(key_id, ws_id):
    core.execute(
        "UPDATE api_keys SET revoked_at=datetime('now') "
        "WHERE id=? AND workspace_id=? AND revoked_at IS NULL",
        (key_id, ws_id),
    )


def get_cached_search(cache_key, max_age_days):
    return core.query_one(
        "SELECT * FROM search_cache WHERE cache_key=? AND "
        "julianday('now') - julianday(fetched_at) < ?",
        (cache_key, max_age_days),
    )


def set_cached_search(cache_key, results_json):
    core.execute(
        "INSERT INTO search_cache(cache_key, results_json, fetched_at) "
        "VALUES(?,?,datetime('now')) "
        "ON CONFLICT(cache_key) DO UPDATE SET results_json=excluded.results_json, "
        "fetched_at=datetime('now')",
        (cache_key, results_json),
    )
