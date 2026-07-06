"""Fetcher for Adzuna's official job search API.

Docs: https://developer.adzuna.com/docs/search
Register for app_id/app_key at https://developer.adzuna.com/signup
"""

from __future__ import annotations

import argparse
import os

import httpx
from dotenv import load_dotenv

from common.schema import NormalizedPosting
from db.session import get_session
from fetcher.base import upsert_postings

load_dotenv()

SOURCE = "adzuna"
BASE_URL = "https://api.adzuna.com/v1/api/jobs"


def _normalize(raw: dict) -> NormalizedPosting:
    location = raw.get("location", {}).get("display_name")
    company = raw.get("company", {}).get("display_name", "Unknown")
    return NormalizedPosting(
        id=f"{SOURCE}:{raw['id']}",
        source=SOURCE,
        title=raw["title"],
        company=company,
        location=location,
        description=raw.get("description", ""),
        source_url=raw["redirect_url"],
    )


def fetch_postings(
    what: str,
    where: str = "",
    country: str | None = None,
    pages: int = 1,
    results_per_page: int = 20,
) -> list[NormalizedPosting]:
    """Fetch job postings from Adzuna and normalize them.

    Raises RuntimeError if ADZUNA_APP_ID / ADZUNA_APP_KEY are not configured.
    """
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    country = country or os.getenv("ADZUNA_COUNTRY", "au")

    if not app_id or not app_key:
        raise RuntimeError(
            "ADZUNA_APP_ID and ADZUNA_APP_KEY must be set (see .env.example). "
            "Register at https://developer.adzuna.com/signup"
        )

    postings: list[NormalizedPosting] = []
    with httpx.Client(timeout=30.0) as client:
        for page in range(1, pages + 1):
            response = client.get(
                f"{BASE_URL}/{country}/search/{page}",
                params={
                    "app_id": app_id,
                    "app_key": app_key,
                    "what": what,
                    "where": where,
                    "results_per_page": results_per_page,
                    "content-type": "application/json",
                },
            )
            response.raise_for_status()
            results = response.json().get("results", [])
            if not results:
                break
            postings.extend(_normalize(raw) for raw in results)
    return postings


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch job postings from Adzuna")
    parser.add_argument("--what", required=True, help="Keywords, e.g. 'python developer'")
    parser.add_argument("--where", default="", help="Location, e.g. 'Sydney'")
    parser.add_argument("--pages", type=int, default=1)
    args = parser.parse_args()

    postings = fetch_postings(what=args.what, where=args.where, pages=args.pages)
    with get_session() as session:
        inserted = upsert_postings(session, postings)

    print(f"Fetched {len(postings)} postings, inserted {inserted} new rows.")


if __name__ == "__main__":
    main()
