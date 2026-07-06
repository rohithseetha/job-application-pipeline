from db.models import Job
from fetcher.adzuna import _normalize
from fetcher.base import upsert_postings

RAW_ADZUNA_JOB = {
    "id": "93106885",
    "title": "AI & Automation Developer",
    "description": "We're ready to automate everything...",
    "company": {"display_name": "CR Plus"},
    "location": {"display_name": "Camellia, Sydney NSW"},
    "redirect_url": "https://www.adzuna.com.au/land/ad/93106885",
}


def test_normalize_maps_adzuna_fields_to_common_schema():
    posting = _normalize(RAW_ADZUNA_JOB)

    assert posting.id == "adzuna:93106885"
    assert posting.source == "adzuna"
    assert posting.title == "AI & Automation Developer"
    assert posting.company == "CR Plus"
    assert posting.location == "Camellia, Sydney NSW"
    assert posting.source_url == "https://www.adzuna.com.au/land/ad/93106885"


def test_normalize_falls_back_when_company_or_location_missing():
    raw = {**RAW_ADZUNA_JOB, "company": {}, "location": {}}
    posting = _normalize(raw)

    assert posting.company == "Unknown"
    assert posting.location is None


def test_upsert_postings_inserts_new_rows(db_session):
    posting = _normalize(RAW_ADZUNA_JOB)

    inserted = upsert_postings(db_session, [posting])
    db_session.commit()

    assert inserted == 1
    row = db_session.get(Job, "adzuna:93106885")
    assert row is not None
    assert row.status == "fetched"


def test_upsert_postings_skips_existing_rows(db_session):
    posting = _normalize(RAW_ADZUNA_JOB)
    upsert_postings(db_session, [posting])
    db_session.commit()

    inserted_again = upsert_postings(db_session, [posting])

    assert inserted_again == 0
