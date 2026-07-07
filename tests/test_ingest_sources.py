import io

from openpyxl import Workbook

from app.services import ingest

APOLLO_CSV = (
    b"First Name,Last Name,Title,Company,Email,Person Linkedin Url,Website\n"
    b"Sam,Lee,COO,Acme Logistics,sam@acme-logistics.com,"
    b"https://linkedin.com/in/samlee,https://www.acme-logistics.com\n"
)

CLAY_CSV = (
    b"full_name,job_title,company_name,company_domain,work_email,linkedin_profile\n"
    b"Jordan Kim,Head of Ops,Beta Freight,betafreight.io,jordan@betafreight.io,"
    b"https://linkedin.com/in/jordankim\n"
)


def _xlsx_bytes(header, data_rows):
    wb = Workbook()
    sheet = wb.active
    sheet.append(header)
    for row in data_rows:
        sheet.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_apollo_headers_auto_map():
    rows, errors = ingest.parse_csv(APOLLO_CSV)
    assert not errors
    lead = rows[0]
    assert lead["company_name"] == "Acme Logistics"
    assert lead["contact_name"] == "Sam Lee"
    assert lead["contact_title"] == "COO"
    assert lead["domain"] == "acme-logistics.com"
    assert lead["linkedin_url"] == "https://linkedin.com/in/samlee"


def test_clay_snake_case_headers_auto_map():
    rows, errors = ingest.parse_csv(CLAY_CSV)
    assert not errors
    lead = rows[0]
    assert lead["company_name"] == "Beta Freight"
    assert lead["contact_name"] == "Jordan Kim"
    assert lead["contact_title"] == "Head of Ops"
    assert lead["email"] == "jordan@betafreight.io"
    assert lead["domain"] == "betafreight.io"


def test_xlsx_parses_with_same_mapping():
    raw = _xlsx_bytes(
        ["Company", "Website", "First Name", "Email"],
        [["Acme Logistics", "acme-logistics.com", "Sam", "sam@acme-logistics.com"],
         ["", None, "", ""],
         ["Beta Freight", "betafreight.io", "Jordan", "jordan@betafreight.io"]],
    )
    rows, errors = ingest.parse_xlsx(raw)
    assert not errors
    assert len(rows) == 2
    assert rows[0]["company_name"] == "Acme Logistics"
    assert rows[0]["contact_name"] == "Sam"
    assert rows[1]["domain"] == "betafreight.io"


def test_xlsx_rejects_garbage():
    rows, errors = ingest.parse_xlsx(b"this is not a workbook")
    assert rows == [] and errors


def test_google_sheet_stub_returns_rows():
    url = "https://docs.google.com/spreadsheets/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ012345678901234/edit"
    rows, errors = ingest.parse_google_sheet(url)
    assert not errors
    assert len(rows) == len(ingest.SHEET_STUB_ROWS)
    assert rows[0]["company_name"] == "Acme Logistics"
    assert rows[0]["contact_name"] == "Sam Lee"


def test_google_sheet_accepts_bare_id_and_rejects_junk():
    rows, errors = ingest.parse_google_sheet("1aBcDeFgHiJkLmNoPqRsTuVwXyZ01234567890")
    assert rows and not errors
    rows, errors = ingest.parse_google_sheet("not a sheet")
    assert rows == [] and errors


def test_dedupe_identical_across_sources(sample_list):
    csv_rows, _ = ingest.parse_csv(APOLLO_CSV)
    xlsx_rows, _ = ingest.parse_xlsx(_xlsx_bytes(
        ["Company", "Website", "Email"],
        [["Acme Logistics", "https://www.acme-logistics.com", "sam@acme-logistics.com"]],
    ))
    assert csv_rows[0]["dedupe_hash"] == xlsx_rows[0]["dedupe_hash"]
    inserted, dupes = ingest.import_rows(sample_list["list_id"], csv_rows + xlsx_rows)
    assert dupes >= 1
