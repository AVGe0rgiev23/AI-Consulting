CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS workspaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    owner_id INTEGER NOT NULL REFERENCES users(id),
    plan TEXT NOT NULL DEFAULT 'trial',
    credits_balance INTEGER NOT NULL DEFAULT 0,
    settings_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS memberships (
    user_id INTEGER NOT NULL REFERENCES users(id),
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    role TEXT NOT NULL DEFAULT 'owner',
    PRIMARY KEY (user_id, workspace_id)
);

CREATE TABLE IF NOT EXISTS invites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    token TEXT UNIQUE NOT NULL,
    invited_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_invites_ws ON invites(workspace_id);

CREATE TABLE IF NOT EXISTS offer_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    name TEXT NOT NULL,
    what_we_sell TEXT NOT NULL DEFAULT '',
    icp TEXT NOT NULL DEFAULT '',
    proof_point TEXT NOT NULL DEFAULT '',
    voice_preset TEXT NOT NULL DEFAULT 'consultative',
    language TEXT NOT NULL DEFAULT 'en',
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lead_lists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    name TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'csv',
    status TEXT NOT NULL DEFAULT 'imported',
    row_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    list_id INTEGER NOT NULL REFERENCES lead_lists(id),
    company_name TEXT NOT NULL DEFAULT '',
    domain TEXT NOT NULL DEFAULT '',
    contact_name TEXT NOT NULL DEFAULT '',
    contact_title TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    linkedin_url TEXT NOT NULL DEFAULT '',
    raw_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',
    status_reason TEXT NOT NULL DEFAULT '',
    dedupe_hash TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_leads_list ON leads(list_id);
CREATE INDEX IF NOT EXISTS idx_leads_dedupe ON leads(dedupe_hash);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'queued',
    claimed_at TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_claim ON jobs(status, claimed_at);

CREATE TABLE IF NOT EXISTS research_briefs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER UNIQUE NOT NULL REFERENCES leads(id),
    company_summary TEXT NOT NULL DEFAULT '',
    industry TEXT NOT NULL DEFAULT '',
    size_estimate TEXT NOT NULL DEFAULT '',
    tech_stack_json TEXT NOT NULL DEFAULT '[]',
    positioning TEXT NOT NULL DEFAULT '',
    digest_md TEXT NOT NULL DEFAULT '',
    thin INTEGER NOT NULL DEFAULT 0,
    quality INTEGER NOT NULL DEFAULT 0,
    thin_reason TEXT NOT NULL DEFAULT '',
    completed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brief_id INTEGER NOT NULL REFERENCES research_briefs(id),
    kind TEXT NOT NULL DEFAULT 'other',
    claim TEXT NOT NULL,
    source_url TEXT NOT NULL DEFAULT '',
    snippet TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.5,
    published_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_findings_brief ON findings(brief_id);

CREATE TABLE IF NOT EXISTS hypotheses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brief_id INTEGER NOT NULL REFERENCES research_briefs(id),
    rank INTEGER NOT NULL DEFAULT 1,
    category TEXT NOT NULL DEFAULT 'inefficiency',
    statement TEXT NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '[]',
    confidence REAL NOT NULL DEFAULT 0.5
);
CREATE INDEX IF NOT EXISTS idx_hypotheses_brief ON hypotheses(brief_id);

CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL REFERENCES leads(id),
    kind TEXT NOT NULL,
    hypothesis_id INTEGER,
    subject TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    score INTEGER NOT NULL DEFAULT 0,
    score_breakdown_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'draft',
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_assets_lead ON assets(lead_id);

CREATE TABLE IF NOT EXISTS research_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    list_id INTEGER NOT NULL REFERENCES lead_lists(id),
    lead_id INTEGER,
    phase TEXT NOT NULL,
    message TEXT NOT NULL DEFAULT '',
    done INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_events_list ON research_events(list_id, id);

CREATE TABLE IF NOT EXISTS credits_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    delta INTEGER NOT NULL,
    reason TEXT NOT NULL,
    job_id INTEGER,
    balance_after INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ledger_ws ON credits_ledger(workspace_id);

CREATE TABLE IF NOT EXISTS exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    list_id INTEGER NOT NULL REFERENCES lead_lists(id),
    format TEXT NOT NULL,
    row_count INTEGER NOT NULL DEFAULT 0,
    file_path TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    list_id INTEGER NOT NULL REFERENCES lead_lists(id),
    name TEXT NOT NULL DEFAULT '',
    exported_to TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_campaigns_list ON campaigns(list_id);

CREATE TABLE IF NOT EXISTS campaign_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
    lead_id INTEGER REFERENCES leads(id),
    hypothesis_category TEXT NOT NULL DEFAULT '',
    sent INTEGER NOT NULL DEFAULT 0,
    opened INTEGER NOT NULL DEFAULT 0,
    replied INTEGER NOT NULL DEFAULT 0,
    meeting_booked INTEGER NOT NULL DEFAULT 0,
    imported_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(campaign_id, lead_id)
);
CREATE INDEX IF NOT EXISTS idx_stats_campaign ON campaign_stats(campaign_id);

CREATE TABLE IF NOT EXISTS audit_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    lead_id INTEGER REFERENCES leads(id),
    company_name TEXT NOT NULL DEFAULT '',
    domain TEXT NOT NULL DEFAULT '',
    exec_summary TEXT NOT NULL DEFAULT '',
    opportunities_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_audits_ws ON audit_reports(workspace_id);

CREATE TABLE IF NOT EXISTS domain_cache (
    domain TEXT PRIMARY KEY,
    pages_json TEXT NOT NULL DEFAULT '[]',
    fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS search_cache (
    cache_key TEXT PRIMARY KEY,
    results_json TEXT NOT NULL DEFAULT '[]',
    fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS spend_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT NOT NULL DEFAULT (date('now')),
    kind TEXT NOT NULL,
    amount_usd REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_spend_day ON spend_ledger(day);

CREATE TABLE IF NOT EXISTS integration_pushes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    list_id INTEGER NOT NULL REFERENCES lead_lists(id),
    provider TEXT NOT NULL,
    campaign_name TEXT NOT NULL DEFAULT '',
    external_id TEXT NOT NULL DEFAULT '',
    lead_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pushed',
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_pushes_ws ON integration_pushes(workspace_id);

CREATE TABLE IF NOT EXISTS prompt_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    slot TEXT NOT NULL,
    content TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(workspace_id, slot)
);
CREATE INDEX IF NOT EXISTS idx_prompts_ws ON prompt_templates(workspace_id);

CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    name TEXT NOT NULL DEFAULT '',
    hashed_key TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_used_at TEXT,
    revoked_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_api_keys_ws ON api_keys(workspace_id);

CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    user_id INTEGER,
    action TEXT NOT NULL,
    target TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
