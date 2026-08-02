# /// script
# requires-python = ">=3.12"
# ///
# SPDX-License-Identifier: GPL-2.0-or-later
"""Fetch the Spanish and French Wikidata labels used by the website catalogue.

This is an explicit authoring command.  The website builder reads the committed
``website/i18n/labels.toml`` snapshot and never makes this request itself.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from pathlib import Path
from typing import Any

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
LANGUAGES = ("es", "fr")
QID = re.compile(r"Q[1-9][0-9]*")
MAX_BATCH_SIZE = 50
DEFAULT_TIMEOUT = 20.0
USER_AGENT = "PrizeAtlas-label-snapshot/1.0 (https://prizeatlas.org/)"


class LabelFetchFailure(Exception):
    """The label snapshot cannot safely be updated."""


def log(message: str) -> None:
    print(message, file=sys.stderr)


def batches(values: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def read_affiliation_qids(database: Path) -> list[str]:
    """Return the exact QID union from primary and additional affiliations."""
    if not database.is_file():
        raise LabelFetchFailure(f"database not found: {database}")

    uri = f"{database.resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        rows = connection.execute(
            """
            SELECT affiliation_wikidata_qid FROM awards
            WHERE affiliation_wikidata_qid <> ''
            UNION
            SELECT affiliation_wikidata_qid FROM award_extra_affiliations
            WHERE affiliation_wikidata_qid <> ''
            ORDER BY affiliation_wikidata_qid
            """
        ).fetchall()
    except sqlite3.Error as error:
        raise LabelFetchFailure(f"could not read affiliation QIDs: {error}") from error
    finally:
        connection.close()

    qids = [row[0] for row in rows]
    if not all(isinstance(qid, str) and QID.fullmatch(qid) for qid in qids):
        raise LabelFetchFailure("database contains an invalid affiliation Wikidata QID")
    return qids


def request_entities(qids: list[str], timeout: float) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {
            "action": "wbgetentities",
            "format": "json",
            "formatversion": "2",
            "ids": "|".join(qids),
            "languages": "|".join(LANGUAGES),
            "props": "labels",
        }
    )
    request = urllib.request.Request(f"{WIKIDATA_API}?{query}", headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        raise LabelFetchFailure(f"Wikidata request failed with HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise LabelFetchFailure("Wikidata request failed") from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise LabelFetchFailure("Wikidata returned invalid JSON") from error

    if not isinstance(payload, dict) or not isinstance(payload.get("entities"), dict):
        raise LabelFetchFailure("Wikidata returned an invalid entity response")
    return payload["entities"]


def validate_entity(qid: str, entity: Any) -> dict[str, Any]:
    if not isinstance(entity, dict):
        raise LabelFetchFailure(f"Wikidata returned an invalid entity qid={qid}")
    entity_qid = entity.get("id")
    redirects = entity.get("redirects")
    if entity_qid == qid and redirects is None:
        return entity
    if (
        not isinstance(entity_qid, str)
        or not QID.fullmatch(entity_qid)
        or not isinstance(redirects, dict)
        or redirects.get("from") != qid
        or redirects.get("to") != entity_qid
    ):
        raise LabelFetchFailure(f"Wikidata returned an invalid entity qid={qid}")
    return entity


def entity_labels(qid: str, entity: dict[str, Any]) -> dict[str, str]:
    if entity.get("missing") is not None:
        return {}
    labels = entity.get("labels")
    if not isinstance(labels, dict):
        raise LabelFetchFailure(f"Wikidata returned invalid labels for {qid}")

    translated: dict[str, str] = {}
    for language in LANGUAGES:
        entry = labels.get(language)
        if entry is None:
            continue
        if not isinstance(entry, dict) or entry.get("language") != language or not isinstance(entry.get("value"), str):
            raise LabelFetchFailure(f"Wikidata returned invalid {language} label for {qid}")
        value = entry["value"].strip()
        if value:
            translated[language] = value
    return translated


def fetch_batch(qids: list[str], timeout: float) -> dict[str, dict[str, str]]:
    """Fetch and validate one bounded group of exact QIDs without label fallback."""
    if not qids or len(qids) > MAX_BATCH_SIZE or not all(QID.fullmatch(qid) for qid in qids):
        raise LabelFetchFailure("invalid Wikidata label batch")

    requested = set(qids)
    entities: dict[str, Any] = {}
    for response_qid, entity in request_entities(qids, timeout).items():
        if not isinstance(response_qid, str):
            raise LabelFetchFailure("Wikidata returned an invalid entity")
        qid = response_qid
        if qid not in requested or qid in entities:
            raise LabelFetchFailure("Wikidata returned unexpected entities")
        entities[qid] = validate_entity(qid, entity)
    if set(entities) != requested:
        raise LabelFetchFailure("Wikidata response omitted requested QIDs")
    return {qid: entity_labels(qid, entities[qid]) for qid in qids}


def toml_string(value: str) -> str:
    """Encode one TOML basic string using JSON's compatible string syntax."""
    return json.dumps(value, ensure_ascii=False)


def render_labels(labels_by_qid: dict[str, dict[str, str]]) -> str:
    lines = ["# Generated by scripts/fetch_wikidata_labels.py; do not edit by hand.", "", "[labels]"]
    for qid in sorted(labels_by_qid):
        labels = labels_by_qid[qid]
        fields = ", ".join(f"{language} = {toml_string(labels[language])}" for language in LANGUAGES if language in labels)
        if fields:
            lines.append(f"{qid} = {{ {fields} }}")
    return "\n".join(lines) + "\n"


def atomic_write(destination: Path, content: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent, text=True)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def build_snapshot(database: Path, destination: Path, batch_size: int = MAX_BATCH_SIZE, timeout: float = DEFAULT_TIMEOUT) -> tuple[int, int]:
    """Fetch every required QID and atomically update *destination* on success."""
    if not 1 <= batch_size <= MAX_BATCH_SIZE:
        raise LabelFetchFailure(f"batch size must be between 1 and {MAX_BATCH_SIZE}")
    if timeout <= 0:
        raise LabelFetchFailure("timeout must be positive")

    labels_by_qid: dict[str, dict[str, str]] = {}
    for qids in batches(read_affiliation_qids(database), batch_size):
        labels_by_qid.update(fetch_batch(qids, timeout))

    missing = sorted(qid for qid, labels in labels_by_qid.items() if not labels)
    if missing:
        log(f"wikidata labels: missing_qids={','.join(missing)}")
    atomic_write(destination, render_labels(labels_by_qid))
    return len(labels_by_qid) - len(missing), len(missing)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    dataset_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=dataset_dir / "awards.sqlite3", help="read-only awards database")
    parser.add_argument("--output", type=Path, default=dataset_dir / "website" / "i18n" / "labels.toml", help="label snapshot to replace after validation")
    parser.add_argument("--batch-size", type=int, default=MAX_BATCH_SIZE, help=f"QIDs per Wikidata request (1-{MAX_BATCH_SIZE})")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="per-request timeout in seconds")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        resolved, missing = build_snapshot(args.database.resolve(), args.output.resolve(), args.batch_size, args.timeout)
    except (LabelFetchFailure, OSError) as error:
        log(f"wikidata label fetch failed: {error}")
        return 1
    print(f"resolved={resolved} missing={missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
