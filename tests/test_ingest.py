from app.services import ingest
from app.db import queries


def test_parse_csv_maps_columns_and_derives_domain():
    raw = b"Company,Website,Email,Job Title\nAcme,https://www.acme.com/x,jo@acme.com,CEO\n"
    rows, errors = ingest.parse_csv(raw)
    assert errors == []
    assert rows[0]["company_name"] == "Acme"
    assert rows[0]["domain"] == "acme.com"
    assert rows[0]["contact_title"] == "CEO"


def test_parse_csv_derives_domain_from_email_when_missing():
    raw = b"Company,Email\nAcme,jo@acme.io\n"
    rows, _ = ingest.parse_csv(raw)
    assert rows[0]["domain"] == "acme.io"


def test_parse_csv_flags_empty_rows():
    raw = b"Company,Email\n,\nReal,jo@real.com\n"
    rows, errors = ingest.parse_csv(raw)
    assert len(rows) == 1
    assert len(errors) == 1


def test_import_rows_dedupes(workspace):
    list_id = queries.create_list(workspace["ws_id"], "L", "csv")
    raw = b"Company,Domain\nAcme,acme.com\nAcme Again,acme.com\nBeta,beta.com\n"
    rows, _ = ingest.parse_csv(raw)
    inserted, dupes = ingest.import_rows(list_id, rows)
    assert inserted == 2
    assert dupes == 1
