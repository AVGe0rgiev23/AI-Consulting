from app.db import queries
from app.jobs import pipeline
from app.services import analyze, feedback


def _prepare_and_approve(sample_list):
    pipeline.process_list_now(sample_list["ws_id"], sample_list["list_id"], sample_list["profile_id"])
    for lead in queries.leads_for_list(sample_list["list_id"]):
        for a in queries.assets_for_lead(lead["id"]):
            queries.set_asset_status(a["id"], "approved")
        queries.set_lead_status(lead["id"], "approved")


def test_parse_stats_csv_maps_columns_and_booleans():
    raw = b"Email,Sent,Opened,Replied,Meeting\nsam@acme.com,1,yes,true,0\njo@b.io,1,0,no,1\n"
    rows = feedback.parse_stats_csv(raw)
    assert rows[0]["email"] == "sam@acme.com"
    assert rows[0]["replied"] == 1
    assert rows[1]["replied"] == 0
    assert rows[1]["meeting_booked"] == 1


def test_parse_requires_email_column():
    assert feedback.parse_stats_csv(b"Foo,Bar\n1,2\n") == []


def test_import_matches_leads_and_records_category(sample_list):
    _prepare_and_approve(sample_list)
    raw = (b"email,sent,replied\n"
           b"sam@acme-logistics.com,1,1\n"
           b"sam@betafreight.io,1,0\n"
           b"nobody@ghost.com,1,1\n")
    rows = feedback.parse_stats_csv(raw)
    result = feedback.import_stats(sample_list["ws_id"], sample_list["list_id"], rows)
    assert result["matched"] == 2
    assert result["unmatched"] == 1
    board = feedback.leaderboard(sample_list["ws_id"])
    assert board
    assert board[0]["category"]
    assert board[0]["sent"] == 2
    assert board[0]["replied"] == 1
    assert board[0]["reply_rate"] == 50.0


def test_leaderboard_orders_by_reply_rate_and_weights_threshold(sample_list):
    _prepare_and_approve(sample_list)
    leads = queries.leads_for_list(sample_list["list_id"])
    campaign_id = queries.get_or_create_campaign(sample_list["ws_id"], sample_list["list_id"], "C")
    queries.upsert_campaign_stat(campaign_id, leads[0]["id"], "revenue_leak", 8, 5, 4, 1)
    queries.upsert_campaign_stat(campaign_id, leads[1]["id"], "scaling", 3, 3, 3, 0)

    board = feedback.leaderboard(sample_list["ws_id"])
    cats = [r["category"] for r in board]
    assert cats.index("scaling") < cats.index("revenue_leak")

    weights = feedback.category_weights(sample_list["ws_id"])
    assert "revenue_leak" in weights
    assert "scaling" not in weights


def test_reweight_promotes_proven_category(sample_list):
    leads = queries.leads_for_list(sample_list["list_id"])
    campaign_id = queries.get_or_create_campaign(sample_list["ws_id"], sample_list["list_id"], "C")
    queries.upsert_campaign_stat(campaign_id, leads[0]["id"], "scaling", 10, 8, 6, 2)

    hyps = [
        {"rank": 1, "category": "inefficiency", "statement": "x", "evidence": [], "confidence": 0.8},
        {"rank": 2, "category": "scaling", "statement": "y", "evidence": [], "confidence": 0.6},
    ]
    ranked = analyze._reweight(hyps, sample_list["ws_id"])
    assert ranked[0]["category"] == "scaling"
    assert ranked[0]["rank"] == 1


def test_funnel_counts_after_import(sample_list):
    _prepare_and_approve(sample_list)
    raw = b"email,sent,replied\nsam@acme-logistics.com,1,1\nsam@betafreight.io,1,0\n"
    feedback.import_stats(sample_list["ws_id"], sample_list["list_id"],
                          feedback.parse_stats_csv(raw))
    f = feedback.funnel(sample_list["ws_id"])
    assert f["researched"] == 2
    assert f["approved"] == 2
    assert f["sent"] == 2
    assert f["replied"] == 1
    assert f["reply_rate"] == 50.0
