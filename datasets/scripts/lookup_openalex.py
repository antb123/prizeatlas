#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Look up and apply exact ROR-to-OpenAlex affiliation crosswalks."""

from __future__ import annotations

import argparse
import email.utils
import json
import os
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

API_URL = "https://api.openalex.org/institutions"
USER_AGENT = "PrizeAtlas-openalex-lookup/1.0 (https://prizeatlas.org/)"
REPORT_VERSION = 1
REQUEST_INTERVAL = 0.1
REQUEST_TIMEOUT = 20

QID = re.compile(r"Q[1-9][0-9]*")
ROR_ID = re.compile(r"0[a-hj-km-np-tv-z0-9]{6}[0-9]{2}")
OPENALEX_ID = re.compile(r"I[0-9]+")

STATUSES = (
    "confirmed",
    "blocked_missing_name",
    "blocked_missing_qid",
    "blocked_missing_ror",
    "blocked_qid_name_conflict",
    "blocked_name_qid_conflict",
    "abstained_not_found",
    "unchanged",
)
LOOKED_UP_STATUSES = frozenset({"confirmed", "abstained_not_found"})


class OpenalexFailure(Exception):
    """A lookup or apply operation that cannot safely continue."""


@dataclass(frozen=True)
class AffiliationRow:
    award_record_id: str
    affiliation_name: str
    affiliation_wikidata_qid: str
    affiliate_ror: str
    institution_openalex_id: str


def log(message: str) -> None:
    print(message, file=sys.stderr)


def text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def read_env_file(path: Path) -> dict[str, str]:
    """Read KEY=VALUE lines from a .env file. Missing file returns {}."""
    if not path.exists():
        return {}
    settings: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, _, value = stripped.partition("=")
        if value:
            settings[key.strip()] = value.strip().strip("\"'")
    return settings


def resolve_api_key(env_path: Path) -> str:
    value = os.environ.get("OPENALEX_API", "").strip()
    if value:
        return value
    return read_env_file(env_path).get("OPENALEX_API", "").strip()


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


def request_url(ror: str) -> str:
    return f"{API_URL}/{urllib.parse.quote(f'https://ror.org/{ror}', safe='')}"


def read_inputs(
    database: Path,
    record_ids: list[str] | None,
) -> tuple[list[AffiliationRow], set[str], set[str]]:
    if not database.is_file():
        raise OpenalexFailure(f"database not found: {database}")

    connection = sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("BEGIN")
        award_rows = connection.execute(
            """
            SELECT award_record_id, affiliation_name,
                   COALESCE(affiliation_wikidata_qid, '') AS affiliation_wikidata_qid,
                   affiliate_ror, institution_openalex_id
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
            affiliation_wikidata_qid=text(row["affiliation_wikidata_qid"]),
            affiliate_ror=text(row["affiliate_ror"]),
            institution_openalex_id=text(row["institution_openalex_id"]),
        )
        for row in award_rows
    ]
    if record_ids is None:
        selected = [
            row
            for row in rows
            if row.affiliate_ror.strip() and not row.institution_openalex_id.strip()
        ]
    else:
        rows_by_id = {row.award_record_id: row for row in rows}
        missing = [record_id for record_id in record_ids if record_id not in rows_by_id]
        if missing:
            raise OpenalexFailure(
                f"record selection failed: unknown award_record_id(s): {', '.join(missing)}"
            )
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


def query_openalex(ror: str, api_key: str) -> tuple[int, dict[str, Any] | None]:
    params: dict[str, str] = {"select": "id,display_name,ror"}
    if api_key:
        params["api_key"] = api_key
    request = urllib.request.Request(
        f"{request_url(ror)}?{urllib.parse.urlencode(params)}",
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return 404, None
            if error.code != 429:
                raise OpenalexFailure(
                    f"OpenAlex API returned HTTP {error.code} for {ror}"
                ) from error
            delay = retry_after_seconds(error.headers.get("Retry-After"))
            if attempt or delay is None:
                raise OpenalexFailure(
                    f"OpenAlex API returned HTTP 429 for {ror} without a usable retry"
                ) from error
            log(f"openalex lookup: ror={ror} outcome=rate_limited retry_after={delay:g}s")
            time.sleep(delay)
            continue
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise OpenalexFailure(
                f"OpenAlex API request failed for {ror}: {error}"
            ) from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise OpenalexFailure(
                f"OpenAlex API returned invalid JSON for {ror}"
            ) from error
    raise AssertionError("unreachable")


def parse_record(payload: Any, requested_ror: str) -> tuple[str, str, str, str] | WrongRor:
    """Return Confirmed fields, WrongRor fields, or raise OpenalexFailure on malformed shape."""
    if not isinstance(payload, dict):
        raise OpenalexFailure(f"OpenAlex response is not an object for ror={requested_ror}")
    id_field = payload.get("id")
    display_name = payload.get("display_name")
    ror_field = payload.get("ror")
    if not isinstance(id_field, str) or not isinstance(display_name, str) or not isinstance(ror_field, str):
        raise OpenalexFailure(
            f"OpenAlex response fields are not all strings for ror={requested_ror}"
        )
    expected_ror = f"https://ror.org/{requested_ror}"
    if ror_field != expected_ror:
        return WrongRor(id_field, display_name, ror_field)
    if not id_field.startswith("https://openalex.org/"):
        raise OpenalexFailure(
            f"OpenAlex response id is not a https://openalex.org/ URL: {id_field!r}"
        )
    compact_id = id_field.removeprefix("https://openalex.org/")
    if not OPENALEX_ID.fullmatch(compact_id):
        raise OpenalexFailure(
            f"OpenAlex response contains an invalid compact ID: {compact_id!r}"
        )
    return (compact_id, display_name, ror_field, id_field)


class WrongRor:
    def __init__(self, id_field: Any, display_name: Any, ror_field: Any) -> None:
        self.id_field = id_field
        self.display_name = display_name
        self.ror_field = ror_field


def _sanitized_record(id_field: Any, display_name: Any, ror_field: Any) -> dict[str, Any] | None:
    if not isinstance(id_field, str) or not isinstance(display_name, str) or not isinstance(ror_field, str):
        return None
    return {"id": id_field, "display_name": display_name, "ror": ror_field}


def classify(ror: str, status_code: int, payload: dict[str, Any] | None) -> tuple[str, str, dict[str, Any] | None]:
    if status_code == 404:
        return "abstained_not_found", f"OpenAlex returned HTTP 404 for ROR {ror}", None
    assert payload is not None
    parsed = parse_record(payload, ror)
    if isinstance(parsed, WrongRor):
        record = _sanitized_record(parsed.id_field, parsed.display_name, parsed.ror_field)
        return (
            "abstained_not_found",
            f"OpenAlex returned a well-formed record whose ror field {parsed.ror_field!r} does not match https://ror.org/{ror}",
            record,
        )
    compact_id, display_name, ror_url, id_url = parsed
    return (
        "confirmed",
        f"OpenAlex returned institution {compact_id} echoing ROR {ror}",
        {
            "id": id_url,
            "display_name": display_name,
            "ror": ror_url,
            "compact_openalex_id": compact_id,
        },
    )


def base_result(row: AffiliationRow, status: str, reason: str, updates: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "award_record_id": row.award_record_id,
        "affiliation_name": row.affiliation_name,
        "affiliation_wikidata_qid": row.affiliation_wikidata_qid,
        "affiliate_ror": row.affiliate_ror,
        "institution_openalex_id": row.institution_openalex_id,
        "status": status,
        "reason": reason,
        "updates": updates or {},
    }


def blocked_result(
    row: AffiliationRow,
    qid_name_conflicts: set[str],
    name_qid_conflicts: set[str],
) -> dict[str, Any] | None:
    """Return a blocked/unchanged result, or None if the row is eligible for lookup."""
    if not row.affiliation_name.strip():
        return base_result(row, "blocked_missing_name", "affiliation_name is blank")
    if not QID.fullmatch(row.affiliation_wikidata_qid):
        reason = (
            "affiliation_wikidata_qid is blank"
            if not row.affiliation_wikidata_qid.strip()
            else "affiliation_wikidata_qid is malformed"
        )
        return base_result(row, "blocked_missing_qid", reason)
    if row.affiliation_wikidata_qid in qid_name_conflicts:
        return base_result(row, "blocked_qid_name_conflict", "Wikidata QID occurs under multiple stored parent names")
    if row.affiliation_name in name_qid_conflicts:
        return base_result(row, "blocked_name_qid_conflict", "stored parent name occurs with multiple Wikidata QIDs")
    if not ROR_ID.fullmatch(row.affiliate_ror):
        reason = (
            "affiliate_ror is blank"
            if not row.affiliate_ror.strip()
            else "affiliate_ror is malformed"
        )
        return base_result(row, "blocked_missing_ror", reason)
    if row.institution_openalex_id.strip():
        return base_result(row, "unchanged", "institution_openalex_id is already populated")
    return None


def research(
    rows: list[AffiliationRow],
    qid_name_conflicts: set[str],
    name_qid_conflicts: set[str],
    api_key: str,
) -> list[dict[str, Any]]:
    outcomes: dict[str, tuple[str, str, dict[str, Any] | None]] = {}
    for row in rows:
        if blocked_result(row, qid_name_conflicts, name_qid_conflicts) is not None:
            continue
        if row.affiliate_ror in outcomes:
            continue
        outcomes[row.affiliate_ror] = (None, None, None)

    for index, ror in enumerate(outcomes):
        if index:
            time.sleep(REQUEST_INTERVAL)
        log(f"openalex lookup: ror={ror} operation=query")
        status_code, payload = query_openalex(ror, api_key)
        outcomes[ror] = classify(ror, status_code, payload)
        log(f"openalex lookup: ror={ror} outcome={outcomes[ror][0]}")

    results: list[dict[str, Any]] = []
    for row in rows:
        blocker = blocked_result(row, qid_name_conflicts, name_qid_conflicts)
        if blocker is not None:
            results.append(blocker)
            log(f"openalex record: award_record_id={row.award_record_id} outcome={blocker['status']}")
            continue

        status, reason, record = outcomes[row.affiliate_ror]
        updates: dict[str, str] = {}
        if status == "confirmed" and record is not None:
            updates = {"institution_openalex_id": record["compact_openalex_id"]}
        result = base_result(row, status, reason, updates)
        result["request_url"] = request_url(row.affiliate_ror)
        result["openalex_record"] = record
        results.append(result)
        log(f"openalex record: award_record_id={row.award_record_id} outcome={status}")
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
        raise OpenalexFailure(f"invalid report {context} keys")


def _validate_record_fields(record: dict[str, Any]) -> None:
    for field in ("id", "display_name", "ror", "compact_openalex_id"):
        if not isinstance(record.get(field), str) or not record[field]:
            raise OpenalexFailure(f"invalid confirmed report record field: {field}")


def _validate_confirmed(value: dict[str, Any], record: dict[str, Any]) -> None:
    if (
        value["affiliate_ror"] == ""
        or value["institution_openalex_id"]
        or not value["affiliation_name"].strip()
        or not QID.fullmatch(value["affiliation_wikidata_qid"])
        or not OPENALEX_ID.fullmatch(value["updates"]["institution_openalex_id"])
        or value["updates"] != {"institution_openalex_id": record["compact_openalex_id"]}
        or record["ror"] != f"https://ror.org/{value['affiliate_ror']}"
    ):
        raise OpenalexFailure("invalid confirmed report result")


def _validate_other(value: dict[str, Any], status: str) -> None:
    if value["updates"]:
        raise OpenalexFailure("nonconfirmed report result contains updates")
    if status == "abstained_not_found" and value["institution_openalex_id"]:
        raise OpenalexFailure("invalid not-found report result")


def validate_result(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OpenalexFailure("invalid report result")
    status = value.get("status")
    if status not in STATUSES:
        raise OpenalexFailure(f"invalid report result status: {status!r}")
    expected = {
        "award_record_id",
        "affiliation_name",
        "affiliation_wikidata_qid",
        "affiliate_ror",
        "institution_openalex_id",
        "status",
        "reason",
        "updates",
    }
    if status in LOOKED_UP_STATUSES:
        expected |= {"request_url", "openalex_record"}
    require_keys(value, expected, "result")

    for field in (
        "award_record_id",
        "affiliation_name",
        "affiliation_wikidata_qid",
        "affiliate_ror",
        "institution_openalex_id",
        "reason",
    ):
        if not isinstance(value[field], str):
            raise OpenalexFailure(f"invalid report result field: {field}")
    if not value["award_record_id"] or not value["reason"]:
        raise OpenalexFailure("invalid report result identity or reason")
    if not isinstance(value["updates"], dict):
        raise OpenalexFailure("invalid report updates")

    if status in LOOKED_UP_STATUSES:
        if not isinstance(value["request_url"], str) or not value["request_url"]:
            raise OpenalexFailure("invalid report request_url")
        record = value["openalex_record"]
        if record is not None and not isinstance(record, dict):
            raise OpenalexFailure("invalid report openalex_record")
    else:
        record = None

    if status == "confirmed":
        if record is None:
            raise OpenalexFailure("confirmed report result is missing openalex_record")
        _validate_record_fields(record)
        _validate_confirmed(value, record)
    else:
        _validate_other(value, status)
    return value


def validate_report(payload: Any, database: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise OpenalexFailure("report must be a JSON object")
    require_keys(payload, {"report_version", "mode", "database", "processed", "status_totals", "results"}, "top-level")
    if payload["report_version"] != REPORT_VERSION:
        raise OpenalexFailure(f"unsupported report version: {payload['report_version']!r}")
    if payload["mode"] != "preview":
        raise OpenalexFailure("apply requires a preview report")
    if payload["database"] != database:
        raise OpenalexFailure("report database does not match --db")
    if not isinstance(payload["results"], list):
        raise OpenalexFailure("invalid report results")

    results = [validate_result(result) for result in payload["results"]]
    record_ids = [result["award_record_id"] for result in results]
    if len(record_ids) != len(set(record_ids)):
        raise OpenalexFailure("report contains duplicate award_record_id values")
    if payload["processed"] != len(results):
        raise OpenalexFailure("report processed count does not match its results")
    if payload["status_totals"] != status_totals(results):
        raise OpenalexFailure("report status totals do not match its results")
    return results


def load_report(path: Path, database: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        with path.open(encoding="utf-8") as source:
            payload = json.load(source)
    except OSError as error:
        raise OpenalexFailure(f"cannot read report {path}: {error}") from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise OpenalexFailure(f"report is not valid JSON: {path}") from error
    return payload, validate_report(payload, database)


def apply_updates(database: Path, results: list[dict[str, Any]]) -> int:
    if not database.is_file():
        raise OpenalexFailure(f"database not found: {database}")

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
                SET institution_openalex_id = ?
                WHERE award_record_id = ?
                  AND affiliation_name = ?
                  AND COALESCE(affiliation_wikidata_qid, '') = ?
                  AND affiliate_ror = ?
                  AND institution_openalex_id = ''
                """,
                (
                    result["updates"]["institution_openalex_id"],
                    result["award_record_id"],
                    result["affiliation_name"],
                    result["affiliation_wikidata_qid"],
                    result["affiliate_ror"],
                ),
            )
            if cursor.rowcount != 1:
                raise OpenalexFailure(
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
    operation.add_argument("--all", action="store_true", help="research every actionable position-1 affiliation")
    operation.add_argument("--apply", type=Path, metavar="REPORT.json", help="apply one reviewed preview report without network access")
    args = parser.parse_args(argv)
    if args.record_id and len(args.record_id) != len(set(args.record_id)):
        parser.error("duplicate --record-id values are not allowed")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    database = Path(args.db)
    env_path = database.parent / ".env"

    try:
        if args.apply:
            log(
                f"openalex apply: database={args.db} operation=start "
                "prerequisite=create timestamped .openalex.bak backup before continuing"
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
            log(f"openalex apply: database={args.db} outcome=applied affected_rows={affected}")
        else:
            api_key = resolve_api_key(env_path)
            rows, qid_name_conflicts, name_qid_conflicts = read_inputs(
                database,
                args.record_id if args.record_id else None,
            )
            log(
                f"openalex preview: database={args.db} selected_rows={len(rows)} "
                f"operation=start api_key={'set' if api_key else 'unset'}"
            )
            results = research(rows, qid_name_conflicts, name_qid_conflicts, api_key)
            report = preview_report(args.db, results)
            log(f"openalex preview: database={args.db} outcome=complete processed={len(results)}")
    except (OpenalexFailure, OSError, sqlite3.Error) as error:
        log(f"openalex operation: database={args.db} outcome=failed error={error}")
        return 1

    json.dump(report, sys.stdout, ensure_ascii=False, indent=2, allow_nan=False)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
