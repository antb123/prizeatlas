"""Load the reviewed second-and-later affiliations into awards.sqlite3.

The six flat `awards.affiliation_*` columns are position 1; this table is positions 2+, so the two stores are disjoint
and nothing is recorded twice. The TSV is the source of truth: every run replaces the table's contents from it.
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

COLUMNS = ("affiliation_name", "affiliation_sub_name", "affiliation_city", "affiliation_country", "affiliation_coordinates", "affiliation_wikidata_qid")
INSERT = f"INSERT INTO award_extra_affiliations (award_record_id, position, {', '.join(COLUMNS)}) VALUES ({', '.join(['?'] * (2 + len(COLUMNS)))})"
CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS award_extra_affiliations (
    award_record_id          TEXT    NOT NULL REFERENCES awards(award_record_id),
    position                 INTEGER NOT NULL CHECK (position >= 2),
    affiliation_name         TEXT    NOT NULL DEFAULT '',
    affiliation_sub_name     TEXT    NOT NULL DEFAULT '',
    affiliation_city         TEXT    NOT NULL DEFAULT '',
    affiliation_country      TEXT    NOT NULL DEFAULT '',
    affiliation_coordinates  TEXT    NOT NULL DEFAULT '',
    affiliation_wikidata_qid TEXT    NOT NULL DEFAULT '',
    PRIMARY KEY (award_record_id, position)
) STRICT
"""


class LoadFailure(Exception):
    """The reviewed affiliations cannot be loaded without violating their contract."""


def read_tsv(path: Path) -> list[tuple]:
    """Rows as (award_record_id, position, *COLUMNS). Position counts from 2 per award, in file order."""
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source, delimiter="\t")
        if missing := {"award_record_id", *COLUMNS} - set(reader.fieldnames or ()):
            raise LoadFailure(f"tsv missing columns {sorted(missing)}")
        rows: list[tuple] = []
        positions: dict[str, int] = {}
        for line, row in enumerate(reader, start=2):
            record_id = (row["award_record_id"] or "").strip()
            if not record_id:
                raise LoadFailure(f"blank award_record_id at line {line}")
            positions[record_id] = positions.get(record_id, 1) + 1
            rows.append((record_id, positions[record_id], *((row[column] or "").strip() for column in COLUMNS)))
    if not rows:
        raise LoadFailure(f"{path} has no rows")
    return rows


def require_awards(database: Path, rows: list[tuple]) -> None:
    """Fail before the backup, not mid-transaction, when the TSV names an award that does not exist."""
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        live = {record_id for record_id, in connection.execute("SELECT award_record_id FROM awards")}
    unknown = sorted({record_id for record_id, *_ in rows if record_id not in live})
    for record_id in unknown:
        print(f"extra_affiliations unknown award_record_id={record_id}", file=sys.stderr)
    if unknown:
        raise LoadFailure(f"{len(unknown)} award_record_id values are not in awards")


def back_up(database: Path) -> Path:
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = database.with_name(f"{database.name}.{stamp}.extras.bak")
    shutil.copyfile(database, backup)
    return backup


def write(database: Path, rows: list[tuple]) -> int:
    """Replace the table's contents with rows; return how many rows the previous load left behind."""
    connection = sqlite3.connect(database)
    try:
        with connection:
            connection.execute(CREATE_TABLE)
            replaced = connection.execute("DELETE FROM award_extra_affiliations").rowcount
            connection.executemany(INSERT, rows)
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise LoadFailure(f"integrity check failed: {integrity}")
        return replaced
    finally:
        connection.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    dataset_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", type=Path, default=dataset_dir / "awards.sqlite3")
    parser.add_argument("--tsv", type=Path, default=dataset_dir / "award_extra_affiliations.tsv", help="reviewed affiliations, one row per position")
    parser.add_argument("--dry-run", action="store_true", help="report what would be written and exit without writing")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    database, tsv = args.database.resolve(), args.tsv.resolve()
    try:
        rows = read_tsv(tsv)
        print(f"extra_affiliations read tsv={tsv} rows={len(rows)} awards={len({record_id for record_id, *_ in rows})}")
        require_awards(database, rows)
        if args.dry_run:
            print(f"extra_affiliations dry-run database={database} rows={len(rows)} written=0 — rerun without --dry-run to load")
            return 0
        backup = back_up(database)
        print(f"extra_affiliations backup database={database} backup={backup}")
        replaced = write(database, rows)
    except (LoadFailure, OSError, sqlite3.Error, csv.Error) as error:
        print(f"extra_affiliations load failed: {error}", file=sys.stderr)
        return 1

    print(f"extra_affiliations loaded table=award_extra_affiliations rows={len(rows)} replaced={replaced}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
