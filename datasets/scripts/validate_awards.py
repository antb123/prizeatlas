#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Check the award data against the invariants it is supposed to hold, and report what breaks them.

The awards table repeats an institution's facts on every row that names it. Berkeley appears 62 times, so its city,
coordinates and QID are typed 62 times, and nothing until now compared the copies. They have drifted: the campus was
recorded once as its own institution and once buried in a sub-name under the system office, splitting its rank 34/28.

Each check below is a defect found in the live data, not a hypothetical. Checks marked fatal are invariants — they
should read zero, and a non-zero count exits 1. The rest are backlogs: real work, counted so it stays visible, but
not a reason to fail a build.

Reports only. This script never writes to the database.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Check:
    name: str
    fatal: bool
    why: str
    sql: str


EXTRAS_TABLE = "award_extra_affiliations"

# Every affiliation check reads both stores as one relation: the flat awards columns at position 1, the extras table at 2+.
AFFILIATIONS = f"""
WITH affiliations AS (
    SELECT award_record_id, 1 AS position, affiliation_name, affiliation_sub_name, affiliation_city,
           affiliation_country, affiliation_coordinates, COALESCE(affiliation_wikidata_qid, '') AS affiliation_wikidata_qid
    FROM awards
    UNION ALL
    SELECT award_record_id, position, affiliation_name, affiliation_sub_name, affiliation_city,
           affiliation_country, affiliation_coordinates, affiliation_wikidata_qid
    FROM {EXTRAS_TABLE}
)
"""

# The loader creates the extras table. Until it has, substitute a relation of the same shape holding no rows — this
# script is read-only and must not create the table itself.
NO_EXTRAS = """(SELECT award_record_id, 2 AS position, affiliation_name, affiliation_sub_name, affiliation_city,
                       affiliation_country, affiliation_coordinates, affiliation_wikidata_qid FROM awards WHERE 0)"""


CHECKS = (
    Check(
        "invalid-affiliation-kind", True,
        "affiliation kind outside the university, institute, hospital, company, government, other or blank vocabulary",
        """
        SELECT affiliation_wikidata_qid, kind
        FROM affiliations
        WHERE kind NOT IN ('', 'university', 'institute', 'hospital', 'company', 'government', 'other')
        ORDER BY affiliation_wikidata_qid
        """,
    ),
    Check(
        "institution-facts-disagree", True,
        "one institution recorded with two different cities, coordinates or QIDs",
        AFFILIATIONS + """
        SELECT affiliation_name,
               GROUP_CONCAT(DISTINCT affiliation_city),
               GROUP_CONCAT(DISTINCT affiliation_coordinates),
               GROUP_CONCAT(DISTINCT affiliation_wikidata_qid)
        FROM affiliations WHERE affiliation_name <> ''
        GROUP BY affiliation_name
        HAVING COUNT(DISTINCT affiliation_city) > 1
            OR COUNT(DISTINCT affiliation_coordinates) > 1
            OR COUNT(DISTINCT affiliation_wikidata_qid) > 1
        ORDER BY 1
        """,
    ),
    Check(
        "laureate-two-names", True,
        "one laureate QID carrying two names — website/build.py:950 refuses to build on this",
        """
        SELECT laureate_wikidata_qid, GROUP_CONCAT(DISTINCT full_name), COUNT(*)
        FROM awards WHERE COALESCE(laureate_wikidata_qid, '') <> ''
        GROUP BY laureate_wikidata_qid HAVING COUNT(DISTINCT full_name) > 1
        """,
    ),
    Check(
        "coords-shared-across-cities", True,
        "one coordinate claimed by rows in different cities — one of them is in the wrong place",
        AFFILIATIONS + """
        SELECT affiliation_coordinates,
               GROUP_CONCAT(DISTINCT affiliation_city),
               GROUP_CONCAT(DISTINCT affiliation_name)
        FROM affiliations WHERE affiliation_coordinates <> '' AND affiliation_city <> ''
        GROUP BY affiliation_coordinates HAVING COUNT(DISTINCT affiliation_city) > 1
        ORDER BY COUNT(DISTINCT affiliation_city) DESC
        """,
    ),
    Check(
        "umbrella-qid", False,
        "one QID spread over several institutions — the QID names a parent body, not the place on the row",
        AFFILIATIONS + """
        SELECT affiliation_wikidata_qid, COUNT(DISTINCT affiliation_name),
               GROUP_CONCAT(DISTINCT affiliation_name)
        FROM affiliations WHERE affiliation_wikidata_qid <> ''
        GROUP BY affiliation_wikidata_qid HAVING COUNT(DISTINCT affiliation_name) > 1
        ORDER BY COUNT(DISTINCT affiliation_name) DESC
        """,
    ),
    Check(
        "sub-name-is-the-institution", False,
        "sub-name holds the real institution while the name holds a parent — nothing ranks the sub-name",
        AFFILIATIONS + """
        SELECT affiliation_name, affiliation_sub_name, COUNT(*)
        FROM affiliations
        WHERE affiliation_sub_name <> ''
          AND (affiliation_sub_name LIKE affiliation_name || '%' OR affiliation_sub_name LIKE '%' || affiliation_name || '%')
        GROUP BY 1, 2 ORDER BY 3 DESC
        """,
    ),
    Check(
        "city-with-state-suffix", False,
        "city written 'City, ST' against the bare-city house style",
        AFFILIATIONS + """
        SELECT affiliation_city, COUNT(*) FROM affiliations
        WHERE affiliation_city GLOB '*, [A-Z][A-Z]' GROUP BY 1 ORDER BY 2 DESC
        """,
    ),
    Check(
        "affiliation-without-qid", False,
        "affiliation with no QID — cannot be linked, logoed, or placed on the map",
        AFFILIATIONS + """
        SELECT affiliation_name, affiliation_city, affiliation_country, COUNT(*)
        FROM affiliations WHERE affiliation_name <> '' AND affiliation_wikidata_qid = ''
        GROUP BY 1, 2, 3 ORDER BY 4 DESC, 1
        """,
    ),
    Check(
        "missing-place", False,
        "affiliation with no city or no country",
        AFFILIATIONS + """
        SELECT affiliation_name, affiliation_city, affiliation_country, COUNT(*)
        FROM affiliations WHERE affiliation_name <> '' AND (affiliation_city = '' OR affiliation_country = '')
        GROUP BY 1, 2, 3 ORDER BY 4 DESC, 1
        """,
    ),
)


def has_extras(connection: sqlite3.Connection) -> bool:
    return connection.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (EXTRAS_TABLE,)).fetchone() is not None


def run(database: Path, check: Check) -> list[tuple]:
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        if has_extras(connection):
            return connection.execute(check.sql).fetchall()
        return connection.execute(check.sql.replace(EXTRAS_TABLE, NO_EXTRAS)).fetchall()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", type=Path, default=Path(__file__).resolve().parents[1] / "awards.sqlite3")
    parser.add_argument("--check", action="append", metavar="NAME", help="run only these checks; repeatable")
    parser.add_argument("--detail", type=int, default=0, metavar="N", help="print up to N offending rows per check")
    parser.add_argument("--list", action="store_true", help="print the check names and exit")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.list:
        for check in CHECKS:
            print(f"validate {check.name} fatal={str(check.fatal).lower()} — {check.why}")
        return 0

    selected = [c for c in CHECKS if not args.check or c.name in args.check]
    if unknown := set(args.check or ()) - {c.name for c in CHECKS}:
        print(f"validate failed: unknown check {sorted(unknown)}", file=sys.stderr)
        return 1

    failures = 0
    try:
        for check in selected:
            rows = run(args.database, check)
            kind = "FAIL" if check.fatal and rows else "backlog" if rows else "ok"
            failures += bool(check.fatal and rows)
            # Every check groups, so this counts distinct offenders, not award rows. One group can cover many rows.
            print(f"validate {check.name} groups={len(rows):4d} {kind} — {check.why}")
            for row in rows[: args.detail]:
                print(f"  {check.name} | " + " | ".join("" if value is None else str(value) for value in row))
    except sqlite3.Error as error:
        print(f"validate failed: {error}", file=sys.stderr)
        return 1

    print(f"validate complete checks={len(selected)} fatal_failing={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
