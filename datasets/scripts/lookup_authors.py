#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Preview or apply exact Wikidata-to-ORCID/OpenAlex author identifiers."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, parse, request

WIKIDATA_URL = "https://www.wikidata.org/w/api.php"
OPENALEX_URL = "https://api.openalex.org/authors/orcid:"
QID = re.compile(r"Q[1-9][0-9]*")
ORCID = re.compile(r"[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]")
OPENALEX = re.compile(r"A[1-9][0-9]*")
USER_AGENT = "PrizeAtlas-author-lookup/1.0 (https://prizeatlas.org/)"


class LookupFailure(Exception):
    pass


@dataclass(frozen=True)
class AwardRow:
    award_record_id: str
    laureate_wikidata_qid: str
    laureate_type: str
    orc_id: str
    author_openalex_id: str


def request_json(url: str) -> dict[str, Any]:
    http_request = request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with request.urlopen(http_request, timeout=20) as response:
            data = json.load(response)
    except error.HTTPError as response_error:
        if response_error.code == 404:
            return {}
        raise LookupFailure(f"HTTP {response_error.code} for {url}") from response_error
    except (error.URLError, TimeoutError, OSError, json.JSONDecodeError) as request_error:
        raise LookupFailure(f"request failed for {url}: {request_error}") from request_error
    if not isinstance(data, dict):
        raise LookupFailure(f"response is not an object for {url}")
    return data


def valid_orcid(value: str) -> bool:
    if not ORCID.fullmatch(value):
        return False
    digits = value.replace("-", "")
    total = 0
    for character in digits[:15]:
        total = (total + int(character)) * 2
    remainder = (12 - total % 11) % 11
    return digits[-1] == ("X" if remainder == 10 else str(remainder))


def effective_values(claims: Any, property_id: str) -> list[str]:
    if not isinstance(claims, dict) or not isinstance(claims.get(property_id), list):
        return []
    items = [claim for claim in claims[property_id] if isinstance(claim, dict) and claim.get("rank") != "deprecated"]
    preferred = [claim for claim in items if claim.get("rank") == "preferred"]
    values: set[str] = set()
    for claim in preferred or items:
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(value, str):
            values.add(value)
    return sorted(values)


def wikidata_claims(qid: str) -> tuple[dict[str, Any], str]:
    url = f"{WIKIDATA_URL}?{parse.urlencode({'action': 'wbgetentities', 'ids': qid, 'props': 'claims', 'format': 'json'})}"
    payload = request_json(url)
    entity = payload.get("entities", {}).get(qid)
    if not isinstance(entity, dict) or not isinstance(entity.get("claims"), dict):
        raise LookupFailure(f"Wikidata returned no claims for {qid}")
    return entity["claims"], url


def openalex_author(orcid: str) -> tuple[str | None, str]:
    url = f"{OPENALEX_URL}{parse.quote(orcid, safe='')}"
    payload = request_json(url)
    if not payload:
        return None, url
    identifier = payload.get("id")
    returned_orcid = payload.get("orcid")
    if not isinstance(identifier, str) or not identifier.startswith("https://openalex.org/"):
        raise LookupFailure(f"OpenAlex returned invalid author ID for ORCID {orcid}")
    compact_id = identifier.removeprefix("https://openalex.org/")
    if not OPENALEX.fullmatch(compact_id) or returned_orcid != f"https://orcid.org/{orcid}":
        return None, url
    return compact_id, url


def openalex_by_id(author_id: str) -> tuple[str | None, str]:
    url = f"https://api.openalex.org/authors/{author_id}"
    payload = request_json(url)
    identifier = payload.get("id")
    expected = f"https://openalex.org/{author_id}"
    return (author_id if identifier == expected else None), url


def read_rows(database: Path, record_ids: list[str] | None) -> list[AwardRow]:
    if not database.is_file():
        raise LookupFailure(f"database not found: {database}")
    with sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        stored = connection.execute("SELECT award_record_id, laureate_wikidata_qid, laureate_type, orc_id, author_openalex_id FROM awards ORDER BY rowid").fetchall()
    rows = [AwardRow(*(str(row[key] or "") for key in ("award_record_id", "laureate_wikidata_qid", "laureate_type", "orc_id", "author_openalex_id"))) for row in stored]
    by_id = {row.award_record_id: row for row in rows}
    if record_ids is not None:
        missing = [value for value in record_ids if value not in by_id]
        if missing:
            raise LookupFailure(f"unknown award_record_id(s): {', '.join(missing)}")
        return [by_id[value] for value in record_ids]
    return [row for row in rows if row.laureate_type == "Individual" and QID.fullmatch(row.laureate_wikidata_qid) and (not row.orc_id or not row.author_openalex_id)]


def research(qid: str) -> dict[str, Any]:
    claims, wikidata_url = wikidata_claims(qid)
    orcids = [value for value in effective_values(claims, "P496") if valid_orcid(value)]
    author_ids = [value for value in effective_values(claims, "P10283") if OPENALEX.fullmatch(value)]
    updates: dict[str, str] = {}
    sources = {"wikidata": wikidata_url}
    if len(orcids) == 1:
        updates["orc_id"] = orcids[0]
        author_id, openalex_url = openalex_author(orcids[0])
        sources["openalex"] = openalex_url
        if author_id:
            updates["author_openalex_id"] = author_id
    if len(author_ids) == 1:
        direct = author_ids[0]
        resolved, direct_url = openalex_by_id(direct)
        sources["openalex_p10283"] = direct_url
        if resolved is None:
            return {"updates": updates, "sources": sources, "reason": "Wikidata P10283 did not resolve to its exact OpenAlex author"}
        if "author_openalex_id" in updates and updates["author_openalex_id"] != direct:
            updates.pop("author_openalex_id")
            return {"updates": updates, "sources": sources, "reason": "Wikidata P10283 conflicts with ORCID OpenAlex lookup"}
        updates.setdefault("author_openalex_id", direct)
    if not updates:
        return {"updates": {}, "sources": sources, "reason": "no single verified Wikidata identifier"}
    return {"updates": updates, "sources": sources, "reason": "exact Wikidata claim verified"}


def apply_updates(database: Path, results: list[dict[str, Any]]) -> None:
    with sqlite3.connect(database) as connection:
        for result in results:
            updates = result["updates"]
            if not updates:
                continue
            assignments = ", ".join(f"{field} = ?" for field in updates)
            values = list(updates.values()) + [result["award_record_id"], result["laureate_wikidata_qid"]]
            conditions = " AND ".join(f"{field} = ''" for field in updates)
            changed = connection.execute(f"UPDATE awards SET {assignments} WHERE award_record_id = ? AND laureate_wikidata_qid = ? AND {conditions}", values).rowcount
            if changed != 1:
                raise LookupFailure(f"guarded update failed for {result['award_record_id']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--record-id", action="append")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if bool(args.record_id) == args.all:
        parser.error("provide repeatable --record-id or --all")
    if args.record_id and len(set(args.record_id)) != len(args.record_id):
        parser.error("duplicate --record-id")
    try:
        rows = read_rows(args.db, args.record_id)
        findings: dict[str, dict[str, Any]] = {}
        results = []
        for row in rows:
            if row.laureate_type != "Individual" or not QID.fullmatch(row.laureate_wikidata_qid):
                result = {
                    "award_record_id": row.award_record_id,
                    "laureate_wikidata_qid": row.laureate_wikidata_qid,
                    "status": "abstained_identity",
                    "updates": {},
                    "reason": "not an individual with a valid Wikidata QID",
                }
            else:
                finding = findings.get(row.laureate_wikidata_qid)
                if finding is None:
                    finding = research(row.laureate_wikidata_qid)
                    findings[row.laureate_wikidata_qid] = finding
                updates = {field: value for field, value in finding["updates"].items() if not getattr(row, field)}
                result = {
                    "award_record_id": row.award_record_id,
                    "laureate_wikidata_qid": row.laureate_wikidata_qid,
                    "status": "confirmed" if updates else "unchanged",
                    "updates": updates,
                    "reason": finding["reason"],
                    "sources": finding["sources"],
                }
            results.append(result)
        if args.apply:
            apply_updates(args.db, results)
        print(json.dumps({"version": 1, "results": results}, indent=2, sort_keys=True))
        return 0
    except LookupFailure as error:
        print(f"author lookup: outcome=failed reason={error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
