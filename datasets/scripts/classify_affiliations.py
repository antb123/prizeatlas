#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""
Classify each affiliation in awards.sqlite3 as a university, hospital, institute, company or government body.

Reads Wikidata P31 (instance of) for every affiliation QID used by an award, resolves those P31 values to their
English labels, and maps the labels onto one `kind` per institution. datasets/affiliation_kinds.tsv overrides the
Wikidata answer by QID for the cases Wikidata states awkwardly.

Run from the datasets directory. Dry run by default; --apply writes affiliations.kind.
"""

import csv
import json
import sqlite3
import sys
import urllib.parse
import urllib.request
from pathlib import Path

DB_PATH = "awards.sqlite3"
OVERRIDES = Path("affiliation_kinds.tsv")
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
USER_AGENT = "PrizeAtlas-affiliation-classifier/1.0 (https://prizeatlas.org/)"
BATCH_SIZE = 50

# First rule that matches an instance-of label wins, so a university hospital is a hospital and not a university.
KIND_RULES = (
    ("hospital", ("hospital", "clinic", "medical center", "medical centre", "cancer center", "cancer centre")),
    ("university", ("university", "college", "higher education", "polytechnic", "école", "universität", "grande ecole")),
    ("institute", ("research institute", "institute", "laboratory", "academy", "learned society", "observatory", "research organization", "research center", "research centre")),
    ("company", ("business", "company", "enterprise", "corporation", "manufacturer")),
    ("government", ("government agency", "ministry", "government organization", "public authority", "armed forces", "legislature")),
)
KINDS = frozenset(kind for kind, _ in KIND_RULES) | {"other"}


def distinct_qids(db_path: str) -> list[str]:
    """Every affiliation QID an award points at, primary affiliation and additional ones alike."""
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT affiliation_wikidata_qid FROM awards WHERE affiliation_wikidata_qid != ''
            UNION
            SELECT DISTINCT affiliation_wikidata_qid FROM award_extra_affiliations WHERE affiliation_wikidata_qid != ''
            ORDER BY 1
            """
        ).fetchall()
    return [row[0] for row in rows]


def fetch(ids: list[str], props: str) -> dict:
    params = {"action": "wbgetentities", "ids": "|".join(ids), "props": props, "languages": "en", "format": "json"}
    request = urllib.request.Request(f"{WIKIDATA_API}?{urllib.parse.urlencode(params)}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8")).get("entities", {})


def fetch_all(ids: list[str], props: str) -> dict:
    entities: dict = {}
    for start in range(0, len(ids), BATCH_SIZE):
        batch = ids[start : start + BATCH_SIZE]
        print(f"fetch props={props} batch={start // BATCH_SIZE + 1}/{(len(ids) + BATCH_SIZE - 1) // BATCH_SIZE} ids={len(batch)}")
        entities.update(fetch(batch, props))
    return entities


def instance_of(entity: dict) -> list[str]:
    return [
        claim["mainsnak"]["datavalue"]["value"]["id"]
        for claim in entity.get("claims", {}).get("P31", [])
        if claim.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
    ]


def classify(labels: list[str]) -> str:
    text = [label.lower() for label in labels]
    for kind, patterns in KIND_RULES:
        if any(pattern in label for label in text for pattern in patterns):
            return kind
    return "other"


def read_overrides(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    overrides = {}
    for row in rows:
        kind = row["kind"].strip()
        if kind not in KINDS:
            raise SystemExit(f"override kind unknown qid={row['affiliation_wikidata_qid']} kind={kind!r}")
        overrides[row["affiliation_wikidata_qid"].strip()] = kind
    print(f"overrides file={path} rows={len(overrides)}")
    return overrides


def add_kind_column(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(affiliations)")}
    if "kind" not in columns:
        conn.execute("ALTER TABLE affiliations ADD COLUMN kind TEXT NOT NULL DEFAULT ''")
        print("schema affiliations.kind added")


def main() -> None:
    apply = "--apply" in sys.argv
    qids = distinct_qids(DB_PATH)
    print(f"affiliations qids={len(qids)} db={DB_PATH}")

    entities = fetch_all(qids, "claims")
    types_by_qid = {qid: instance_of(entities.get(qid, {})) for qid in qids}
    type_qids = sorted({type_qid for types in types_by_qid.values() for type_qid in types})
    labels_by_type = {
        qid: entity.get("labels", {}).get("en", {}).get("value", "")
        for qid, entity in fetch_all(type_qids, "labels").items()
    }

    overrides = read_overrides(OVERRIDES)
    kinds = {qid: overrides.get(qid) or classify([labels_by_type.get(t, "") for t in types]) for qid, types in types_by_qid.items()}

    counts = {kind: sum(1 for value in kinds.values() if value == kind) for kind in sorted(KINDS)}
    print("classified " + " ".join(f"{kind}={count}" for kind, count in counts.items()))

    if not apply:
        print("dry run (--apply to write). Sample:")
        for qid, kind in list(kinds.items())[:20]:
            print(f"  {qid} {kind}")
        return

    with sqlite3.connect(DB_PATH) as conn:
        add_kind_column(conn)
        conn.executemany(
            "INSERT INTO affiliations (affiliation_wikidata_qid, kind) VALUES (?, ?) "
            "ON CONFLICT(affiliation_wikidata_qid) DO UPDATE SET kind = excluded.kind",
            sorted(kinds.items()),
        )
    print(f"database updated rows={len(kinds)}")


if __name__ == "__main__":
    main()
