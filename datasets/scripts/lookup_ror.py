#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Look up and apply exact Wikidata-to-ROR affiliation crosswalks."""

from __future__ import annotations

import argparse
import email.utils
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API_URL = "https://api.ror.org/v2/organizations"
USER_AGENT = "PrizeAtlas-ror-lookup/1.0 (https://prizeatlas.org/)"
REPORT_VERSION = 1
REQUEST_INTERVAL = 0.16
REQUEST_TIMEOUT = 20
QID = re.compile(r"Q[1-9][0-9]*")
ROR_ID = re.compile(r"0[a-hj-km-np-tv-z0-9]{6}[0-9]{2}")
STATUSES = (
    "confirmed",
    "blocked_missing_name",
    "blocked_missing_qid",
    "blocked_qid_name_conflict",
    "blocked_name_qid_conflict",
    "blocked_withdrawn",
    "abstained_not_found",
    "abstained_ambiguous",
    "unchanged",
)
API_STATUSES = frozenset({
    "confirmed",
    "blocked_withdrawn",
    "abstained_not_found",
    "abstained_ambiguous",
})


class RorFailure(Exception):
    """A lookup or apply operation that cannot safely continue."""


@dataclass(frozen=True)
class AffiliationRow:
    award_record_id: str
    affiliation_name: str
    affiliation_city: str
    affiliation_country: str
    affiliation_wikidata_qid: str
    affiliate_ror: str


def log(message: str) -> None:
    print(message, file=sys.stderr)


def text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def read_inputs(database: Path, record_ids: list[str] | None) -> tuple[list[AffiliationRow], set[str], set[str]]:
    if not database.is_file():
        raise RorFailure(f"database not found: {database}")

    connection = sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("BEGIN")
        award_rows = connection.execute(
            """
            SELECT award_record_id, affiliation_name, affiliation_city, affiliation_country,
                   affiliation_wikidata_qid, affiliate_ror
            FROM awards
            ORDER BY rowid
            """
        ).fetchall()
        relation = connection.execute(
            """
            SELECT affiliation_name, COALESCE(affiliation_wikidata_qid, '') AS affiliation_wikidata_qid
            FROM awards
            UNION ALL
            SELECT affiliation_name, affiliation_wikidata_qid
            FROM award_extra_affiliations
            """
        ).fetchall()
    finally:
        connection.close()

    rows = [
        AffiliationRow(
            award_record_id=text(row["award_record_id"]),
            affiliation_name=text(row["affiliation_name"]),
            affiliation_city=text(row["affiliation_city"]),
            affiliation_country=text(row["affiliation_country"]),
            affiliation_wikidata_qid=text(row["affiliation_wikidata_qid"]),
            affiliate_ror=text(row["affiliate_ror"]),
        )
        for row in award_rows
    ]
    if record_ids is None:
        selected = [row for row in rows if row.affiliation_name.strip() and not row.affiliate_ror]
    else:
        rows_by_id = {row.award_record_id: row for row in rows}
        missing = [record_id for record_id in record_ids if record_id not in rows_by_id]
        if missing:
            raise RorFailure(f"record selection failed: unknown award_record_id(s): {', '.join(missing)}")
        selected = [rows_by_id[record_id] for record_id in record_ids]

    qid_to_names: dict[str, set[str]] = defaultdict(set)
    name_to_qids: dict[str, set[str]] = defaultdict(set)
    for stored in relation:
        name = text(stored["affiliation_name"])
        qid = text(stored["affiliation_wikidata_qid"])
        if name.strip() and qid.strip():
            qid_to_names[qid].add(name)
            name_to_qids[name].add(qid)

    qid_name_conflicts = {qid for qid, names in qid_to_names.items() if len(names) > 1}
    name_qid_conflicts = {name for name, qids in name_to_qids.items() if len(qids) > 1}
    return selected, qid_name_conflicts, name_qid_conflicts


def retry_after_seconds(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        retry_at = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)
    return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())


def query_ror(qid: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({"query": f'"{qid}"'})
    request = urllib.request.Request(
        f"{API_URL}?{query}&all_status",
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as error:
            if error.code != 429:
                raise RorFailure(f"ROR API returned HTTP {error.code} for {qid}") from error
            delay = retry_after_seconds(error.headers.get("Retry-After"))
            if attempt or delay is None:
                raise RorFailure(f"ROR API returned HTTP 429 for {qid} without a usable retry") from error
            log(f"ror lookup: qid={qid} outcome=rate_limited retry_after={delay:g}s")
            time.sleep(delay)
            continue
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise RorFailure(f"ROR API request failed for {qid}: {error}") from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise RorFailure(f"ROR API returned invalid JSON for {qid}") from error

        if not isinstance(payload, dict):
            raise RorFailure(f"ROR API returned a non-object response for {qid}")
        return payload
    raise AssertionError("unreachable")


def parse_locations(compact_id: str, locations: Any) -> list[dict[str, str]]:
    if not isinstance(locations, list):
        raise RorFailure(f"ROR response contains invalid locations for {compact_id}")
    summaries: list[dict[str, str]] = []
    for location in locations:
        details = location.get("geonames_details") if isinstance(location, dict) else None
        if not isinstance(details, dict):
            raise RorFailure(f"ROR response contains an invalid location entry for {compact_id}")
        summary: dict[str, str] = {}
        for output_field, source_field in (
            ("city", "name"),
            ("country", "country_name"),
            ("country_code", "country_code"),
        ):
            value = details.get(source_field)
            if value is not None and not isinstance(value, str):
                raise RorFailure(f"ROR response contains invalid location details for {compact_id}")
            summary[output_field] = value or ""
        summaries.append(summary)
    return summaries


def parse_match(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise RorFailure("ROR response contains a non-object item")

    source_url = item.get("id")
    if not isinstance(source_url, str) or not source_url.startswith("https://ror.org/"):
        raise RorFailure("ROR response contains an invalid organization ID URL")
    compact_id = source_url.removeprefix("https://ror.org/")
    if not ROR_ID.fullmatch(compact_id):
        raise RorFailure(f"ROR response contains an invalid compact organization ID: {compact_id!r}")

    status = item.get("status")
    if status not in {"active", "inactive", "withdrawn"}:
        raise RorFailure(f"ROR response contains an invalid record status for {compact_id}")

    names = item.get("names")
    if not isinstance(names, list):
        raise RorFailure(f"ROR response contains invalid names for {compact_id}")
    display_names: list[str] = []
    for name in names:
        if not isinstance(name, dict) or not isinstance(name.get("types"), list) or not isinstance(name.get("value"), str):
            raise RorFailure(f"ROR response contains an invalid name entry for {compact_id}")
        if not all(isinstance(name_type, str) for name_type in name["types"]):
            raise RorFailure(f"ROR response contains invalid name types for {compact_id}")
        if "ror_display" in name["types"]:
            display_names.append(name["value"])
    if len(display_names) != 1 or not display_names[0]:
        raise RorFailure(f"ROR response does not contain exactly one display name for {compact_id}")

    external_ids = item.get("external_ids")
    if not isinstance(external_ids, list):
        raise RorFailure(f"ROR response contains invalid external IDs for {compact_id}")
    wikidata_ids: list[str] = []
    for external_id in external_ids:
        if (
            not isinstance(external_id, dict)
            or not isinstance(external_id.get("type"), str)
            or not isinstance(external_id.get("all"), list)
            or not all(isinstance(value, str) for value in external_id["all"])
        ):
            raise RorFailure(f"ROR response contains an invalid external ID entry for {compact_id}")
        if external_id["type"] == "wikidata":
            wikidata_ids.extend(external_id["all"])

    return {
        "source_url": source_url,
        "ror_id": compact_id,
        "ror_display_name": display_names[0],
        "ror_status": status,
        "wikidata_external_ids": wikidata_ids,
        "ror_locations": parse_locations(compact_id, item.get("locations")),
    }


def classify_response(qid: str, payload: dict[str, Any]) -> tuple[str, str, list[dict[str, Any]]]:
    items = payload.get("items")
    count = payload.get("number_of_results")
    if not isinstance(items, list) or not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise RorFailure(f"ROR API returned an invalid result page for {qid}")
    if count != len(items):
        raise RorFailure(f"ROR API returned an incomplete result page for {qid}: reported {count}, returned {len(items)}")

    parsed = [parse_match(item) for item in items]
    matches = [match for match in parsed if qid in match["wikidata_external_ids"]]
    if not matches:
        return "abstained_not_found", f"no ROR record contains exact Wikidata ID {qid}", parsed
    if len(matches) > 1:
        return "abstained_ambiguous", f"{len(matches)} ROR records contain exact Wikidata ID {qid}", parsed

    match = matches[0]
    if match["ror_status"] == "withdrawn":
        return "blocked_withdrawn", f"exact ROR record {match['ror_id']} is withdrawn", parsed
    return "confirmed", f"one {match['ror_status']} ROR record contains exact Wikidata ID {qid}", parsed


def base_result(row: AffiliationRow, status: str, reason: str, updates: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "award_record_id": row.award_record_id,
        "affiliation_name": row.affiliation_name,
        "affiliation_city": row.affiliation_city,
        "affiliation_country": row.affiliation_country,
        "affiliation_wikidata_qid": row.affiliation_wikidata_qid,
        "affiliate_ror": row.affiliate_ror,
        "status": status,
        "reason": reason,
        "updates": updates or {},
    }


def blocked_result(row: AffiliationRow, qid_name_conflicts: set[str], name_qid_conflicts: set[str]) -> dict[str, Any] | None:
    if row.affiliate_ror:
        return base_result(row, "unchanged", "affiliate_ror is already populated")
    if not row.affiliation_name.strip():
        return base_result(row, "blocked_missing_name", "affiliation_name is blank")
    if not QID.fullmatch(row.affiliation_wikidata_qid):
        reason = "affiliation_wikidata_qid is blank" if not row.affiliation_wikidata_qid.strip() else "affiliation_wikidata_qid is malformed"
        return base_result(row, "blocked_missing_qid", reason)
    if row.affiliation_wikidata_qid in qid_name_conflicts:
        return base_result(row, "blocked_qid_name_conflict", "Wikidata QID occurs under multiple stored parent names")
    if row.affiliation_name in name_qid_conflicts:
        return base_result(row, "blocked_name_qid_conflict", "stored parent name occurs with multiple Wikidata QIDs")
    return None


def research(
    rows: list[AffiliationRow],
    qid_name_conflicts: set[str],
    name_qid_conflicts: set[str],
) -> list[dict[str, Any]]:
    outcomes: dict[str, tuple[str, str, list[dict[str, Any]]]] = {}
    eligible_qids: dict[str, None] = {}
    for row in rows:
        if blocked_result(row, qid_name_conflicts, name_qid_conflicts) is None:
            eligible_qids.setdefault(row.affiliation_wikidata_qid, None)

    for index, qid in enumerate(eligible_qids):
        if index:
            time.sleep(REQUEST_INTERVAL)
        log(f"ror lookup: qid={qid} operation=query")
        outcomes[qid] = classify_response(qid, query_ror(qid))
        log(f"ror lookup: qid={qid} outcome={outcomes[qid][0]}")

    results: list[dict[str, Any]] = []
    for row in rows:
        if result := blocked_result(row, qid_name_conflicts, name_qid_conflicts):
            results.append(result)
            log(f"ror record: award_record_id={row.award_record_id} outcome={result['status']}")
            continue

        status, reason, records = outcomes[row.affiliation_wikidata_qid]
        exact_records = [record for record in records if row.affiliation_wikidata_qid in record["wikidata_external_ids"]]
        updates = {"affiliate_ror": exact_records[0]["ror_id"]} if status == "confirmed" else {}
        result = base_result(row, status, reason, updates)
        result["source_url"] = API_URL
        result["ror_records"] = records
        results.append(result)
        log(f"ror record: award_record_id={row.award_record_id} outcome={status}")
    return results


def status_totals(results: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(result["status"] for result in results)
    return {status: counts[status] for status in STATUSES}


def preview_report(database: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "report_version": REPORT_VERSION,
        "mode": "preview",
        "database": database,
        "processed": len(results),
        "status_totals": status_totals(results),
        "results": results,
    }


def require_keys(value: dict[str, Any], expected: set[str], context: str) -> None:
    if set(value) != expected:
        raise RorFailure(f"invalid report {context} keys")


def validate_match(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RorFailure("invalid report ROR match")
    require_keys(
        value,
        {"source_url", "ror_id", "ror_display_name", "ror_status", "wikidata_external_ids", "ror_locations"},
        "ROR match",
    )
    compact_id = value["ror_id"]
    if not isinstance(compact_id, str) or not ROR_ID.fullmatch(compact_id):
        raise RorFailure("invalid report ROR ID")
    if value["source_url"] != f"https://ror.org/{compact_id}":
        raise RorFailure("invalid report ROR source URL")
    if not isinstance(value["ror_display_name"], str) or not value["ror_display_name"]:
        raise RorFailure("invalid report ROR display name")
    if value["ror_status"] not in {"active", "inactive", "withdrawn"}:
        raise RorFailure("invalid report ROR status")
    if not isinstance(value["wikidata_external_ids"], list) or not all(
        isinstance(qid, str) for qid in value["wikidata_external_ids"]
    ):
        raise RorFailure("invalid report Wikidata external IDs")
    if not isinstance(value["ror_locations"], list):
        raise RorFailure("invalid report ROR locations")
    for location in value["ror_locations"]:
        if (
            not isinstance(location, dict)
            or set(location) != {"city", "country", "country_code"}
            or not all(isinstance(field, str) for field in location.values())
        ):
            raise RorFailure("invalid report ROR location")
    return value


def validate_result(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RorFailure("invalid report result")
    status = value.get("status")
    if status not in STATUSES:
        raise RorFailure(f"invalid report result status: {status!r}")

    expected = {
        "award_record_id",
        "affiliation_name",
        "affiliation_city",
        "affiliation_country",
        "affiliation_wikidata_qid",
        "affiliate_ror",
        "status",
        "reason",
        "updates",
    }
    if status in API_STATUSES:
        expected |= {"source_url", "ror_records"}
    require_keys(value, expected, "result")

    for field in (
        "award_record_id",
        "affiliation_name",
        "affiliation_city",
        "affiliation_country",
        "affiliation_wikidata_qid",
        "affiliate_ror",
        "reason",
    ):
        if not isinstance(value[field], str):
            raise RorFailure(f"invalid report result field: {field}")
    if not value["award_record_id"] or not value["reason"]:
        raise RorFailure("invalid report result identity or reason")
    if not isinstance(value["updates"], dict):
        raise RorFailure("invalid report updates")

    records: list[dict[str, Any]] = []
    if status in API_STATUSES:
        if value["source_url"] != API_URL or not isinstance(value["ror_records"], list):
            raise RorFailure("invalid report API source")
        records = [validate_match(record) for record in value["ror_records"]]
    matches = [
        record
        for record in records
        if value["affiliation_wikidata_qid"] in record["wikidata_external_ids"]
    ]

    if status == "confirmed":
        if (
            value["affiliate_ror"]
            or not value["affiliation_name"].strip()
            or not QID.fullmatch(value["affiliation_wikidata_qid"])
            or len(matches) != 1
            or matches[0]["ror_status"] not in {"active", "inactive"}
            or value["affiliation_wikidata_qid"] not in matches[0]["wikidata_external_ids"]
            or value["updates"] != {"affiliate_ror": matches[0]["ror_id"]}
        ):
            raise RorFailure("invalid confirmed report result")
    elif value["updates"]:
        raise RorFailure("nonconfirmed report result contains updates")
    elif status == "blocked_withdrawn" and (
        len(matches) != 1
        or matches[0]["ror_status"] != "withdrawn"
        or value["affiliation_wikidata_qid"] not in matches[0]["wikidata_external_ids"]
    ):
        raise RorFailure("invalid withdrawn report result")
    elif status == "abstained_not_found" and matches:
        raise RorFailure("invalid not-found report result")
    elif status == "abstained_ambiguous" and (
        len(matches) < 2
        or any(value["affiliation_wikidata_qid"] not in match["wikidata_external_ids"] for match in matches)
    ):
        raise RorFailure("invalid ambiguous report result")

    return value


def validate_report(payload: Any, database: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise RorFailure("report must be a JSON object")
    require_keys(payload, {"report_version", "mode", "database", "processed", "status_totals", "results"}, "top-level")
    if payload["report_version"] != REPORT_VERSION:
        raise RorFailure(f"unsupported report version: {payload['report_version']!r}")
    if payload["mode"] != "preview":
        raise RorFailure("apply requires a preview report")
    if payload["database"] != database:
        raise RorFailure("report database does not match --db")
    if not isinstance(payload["results"], list):
        raise RorFailure("invalid report results")

    results = [validate_result(result) for result in payload["results"]]
    record_ids = [result["award_record_id"] for result in results]
    if len(record_ids) != len(set(record_ids)):
        raise RorFailure("report contains duplicate award_record_id values")
    if payload["processed"] != len(results):
        raise RorFailure("report processed count does not match its results")
    if payload["status_totals"] != status_totals(results):
        raise RorFailure("report status totals do not match its results")
    return results


def load_report(path: Path, database: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        with path.open(encoding="utf-8") as source:
            payload = json.load(source)
    except OSError as error:
        raise RorFailure(f"cannot read report {path}: {error}") from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise RorFailure(f"report is not valid JSON: {path}") from error
    return payload, validate_report(payload, database)


def apply_updates(database: Path, results: list[dict[str, Any]]) -> int:
    if not database.is_file():
        raise RorFailure(f"database not found: {database}")

    connection = sqlite3.connect(database)
    try:
        connection.execute("BEGIN")
        affected = 0
        for result in results:
            if result["status"] != "confirmed":
                continue
            cursor = connection.execute(
                """
                UPDATE awards
                SET affiliate_ror = ?
                WHERE award_record_id = ?
                  AND affiliation_name = ?
                  AND affiliation_wikidata_qid = ?
                  AND affiliate_ror = ''
                """,
                (
                    result["updates"]["affiliate_ror"],
                    result["award_record_id"],
                    result["affiliation_name"],
                    result["affiliation_wikidata_qid"],
                ),
            )
            if cursor.rowcount != 1:
                raise RorFailure(
                    f"database drift for award_record_id={result['award_record_id']}: expected one blank matching row, affected {cursor.rowcount}"
                )
            affected += 1
        connection.commit()
        return affected
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="SQLite awards database")
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--record-id", action="append", help="research this exact award_record_id (repeatable)")
    operation.add_argument("--all", action="store_true", help="research every named position-1 affiliation with a blank ROR ID")
    operation.add_argument("--apply", type=Path, metavar="REPORT.json", help="apply one reviewed preview report without network access")
    args = parser.parse_args(argv)
    if args.record_id and len(args.record_id) != len(set(args.record_id)):
        parser.error("duplicate --record-id values are not allowed")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    database = Path(args.db)

    try:
        if args.apply:
            log(
                f"ror apply: database={args.db} operation=start "
                "prerequisite=create timestamped .ror.bak backup before continuing"
            )
            payload, results = load_report(args.apply, args.db)
            affected = apply_updates(database, results)
            report = {
                "report_version": REPORT_VERSION,
                "mode": "apply",
                "database": args.db,
                "source_report": str(args.apply),
                "processed": len(results),
                "status_totals": payload["status_totals"],
                "results": results,
                "database_apply": {"outcome": "applied", "affected_rows": affected},
            }
            log(f"ror apply: database={args.db} outcome=applied affected_rows={affected}")
        else:
            rows, qid_name_conflicts, name_qid_conflicts = read_inputs(
                database,
                args.record_id if args.record_id else None,
            )
            log(f"ror preview: database={args.db} selected_rows={len(rows)} operation=start")
            results = research(rows, qid_name_conflicts, name_qid_conflicts)
            report = preview_report(args.db, results)
            log(f"ror preview: database={args.db} outcome=complete processed={len(results)}")
    except (RorFailure, OSError, sqlite3.Error) as error:
        log(f"ror operation: database={args.db} outcome=failed error={error}")
        return 1

    json.dump(report, sys.stdout, ensure_ascii=False, indent=2, allow_nan=False)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
