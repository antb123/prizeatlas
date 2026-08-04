#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Report stored ORCIDs whose public owner is inconsistent with award rows.

This command never writes the database.  A matching name is only a review lead;
an owner mismatch is strong evidence for removal, not for assigning a replacement.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sqlite3
import time
import unicodedata
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

ORCID_URL = "https://pub.orcid.org/v3.0/{}/person"
USER_AGENT = "PrizeAtlas-orcid-owner-audit/1.0 (https://prizeatlas.org/)"
TITLE_WORDS = {"dr", "sir", "dame", "prof", "jr", "sr", "ii", "iii"}


def normalized_words(value: str) -> list[str]:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return [word for word in re.findall(r"[a-z]+", value) if word not in TITLE_WORDS]


def owner_name(orcid: str) -> tuple[str, str, str | None]:
    request = urllib.request.Request(ORCID_URL.format(orcid), headers={"Accept": "application/vnd.orcid+json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        return "error", "", f"HTTP {error.code}"
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        return "error", "", str(error)
    name = payload.get("name") if isinstance(payload, dict) else None
    if not isinstance(name, dict):
        return "empty", "", None
    given_field = name.get("given-names")
    family_field = name.get("family-name")
    given = given_field.get("value") if isinstance(given_field, dict) else None
    family = family_field.get("value") if isinstance(family_field, dict) else None
    if not isinstance(given, str) and not isinstance(family, str):
        return "empty", "", None
    return "owner", f"{given or ''} {family or ''}".strip(), None


def classify(laureate: str, owner: str) -> str:
    person = normalized_words(laureate)
    profile = normalized_words(owner)
    if not person or not profile:
        return "unverifiable_empty_owner"
    # A different surname, or different fully spelled first name, proves conflict.
    if person[-1] != profile[-1]:
        return "wrong_owner"
    first_person, first_profile = person[0], profile[0]
    if len(first_person) > 1 and len(first_profile) > 1 and first_person != first_profile:
        return "wrong_owner"
    return "review_required"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    if not args.db.is_file() or args.workers < 1:
        parser.error("database must exist and --workers must be positive")
    with sqlite3.connect(f"{args.db.resolve().as_uri()}?mode=ro", uri=True) as connection:
        rows = connection.execute(
            "SELECT award_record_id, full_name, laureate_wikidata_qid, orc_id FROM awards "
            "WHERE laureate_type = 'Individual' AND orc_id <> '' ORDER BY award_record_id"
        ).fetchall()
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for record_id, name, qid, orcid in rows:
        grouped[orcid].append({"award_record_id": record_id, "full_name": name, "laureate_wikidata_qid": qid})
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        fetched = dict(zip(grouped, pool.map(owner_name, grouped)))
    results = []
    for orcid, awards in grouped.items():
        outcome, owner, error = fetched[orcid]
        statuses = {classify(row["full_name"], owner) if outcome == "owner" else ("fetch_error" if outcome == "error" else "unverifiable_empty_owner") for row in awards}
        results.append({"orc_id": orcid, "owner": owner, "error": error, "status": next(iter(statuses)) if len(statuses) == 1 else "mixed_award_status", "awards": awards})
    report = {"version": 1, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "results": results}
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    counts: dict[str, int] = defaultdict(int)
    for result in results:
        counts[result["status"]] += 1
    print(json.dumps({"distinct_orcids": len(results), "status_counts": dict(sorted(counts.items())), "output": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
