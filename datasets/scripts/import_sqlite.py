#!/usr/bin/env python3
"""Import the canonical award CSVs into one SQLite database."""

from __future__ import annotations

import argparse
import csv
import os
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

CSV_COLUMNS = (
    "award_record_id",
    "year",
    "category",
    "prize",
    "motivation",
    "prize_share",
    "source_laureate_id",
    "laureate_type",
    "full_name",
    "birth_date",
    "birth_year",
    "birth_city",
    "birth_country",
    "birth_coordinates",
    "citizenship_countries",
    "sex",
    "affiliation_name",
    "affiliation_city",
    "affiliation_country",
    "affiliation_coordinates",
    "death_date",
    "death_city",
    "death_country",
    "field_language",
    "biographical_note",
    "remarks",
)

SQLITE_COLUMNS = (
    *CSV_COLUMNS[:4],
    "prize_name",
    "award_wikidata_qid",
    *CSV_COLUMNS[4:7],
    "laureate_wikidata_qid",
    *CSV_COLUMNS[7:],
)

AWARDS = {
    "abel_prize.csv": ("Abel Prize", "Q188184"),
    "breakthrough.csv": ("Breakthrough Prize", "Q17278140"),
    "crafoord.csv": ("Crafoord Prize", "Q583069"),
    "fields.csv": ("Fields Medal", "Q28835"),
    "gairdner_international_award.csv": ("Canada Gairdner International Award", "Q1031994"),
    "japan_prize.csv": ("Japan Prize", "Q908745"),
    "kyoto_prize.csv": ("Kyoto Prize", "Q658444"),
    "lasker_awards.csv": ("Lasker Award", "Q921415"),
    "max_planck_medal.csv": ("Max Planck Medal", "Q317038"),
    "nobel.csv": ("Nobel Prize", "Q7191"),
    "shaw_prize.csv": ("Shaw Prize", "Q584250"),
    "turing_award.csv": ("Turing Award", "Q185667"),
    "wolf_prize.csv": ("Wolf Prize", "Q739936"),
}

QID = re.compile(r"Q[1-9][0-9]*")


class ImportFailure(Exception):
    """Input data cannot be imported without violating the database contract."""


def create_schema(connection: sqlite3.Connection) -> None:
    definitions = ",\n                ".join(
        f'"{column}" TEXT{" PRIMARY KEY" if column == "award_record_id" else ""}'
        for column in SQLITE_COLUMNS
    )
    connection.executescript(
        f"""
        CREATE TABLE awards (
                {definitions}
        ) STRICT;

        CREATE INDEX awards_prize_category_year_idx
            ON awards (prize_name, category, year);
        CREATE INDEX awards_full_name_idx
            ON awards (full_name);
        CREATE INDEX awards_laureate_qid_idx
            ON awards (laureate_wikidata_qid)
            WHERE laureate_wikidata_qid <> '';
        """
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.reader(source)
        try:
            header = tuple(next(reader))
        except StopIteration as error:
            raise ImportFailure(f"{path.name}: empty file") from error

        if header != CSV_COLUMNS:
            raise ImportFailure(f"{path.name}: unexpected header")

        rows = []
        for line_number, values in enumerate(reader, start=2):
            if len(values) != len(CSV_COLUMNS):
                raise ImportFailure(f"{path.name}:{line_number}: expected {len(CSV_COLUMNS)} fields, found {len(values)}")
            rows.append(dict(zip(CSV_COLUMNS, values, strict=True)))
    return rows


def import_csv(
    connection: sqlite3.Connection,
    path: Path,
    prize_name: str,
    award_wikidata_qid: str,
    seen_ids: set[str],
) -> int:
    rows = read_csv(path)
    placeholders = ", ".join("?" for _ in SQLITE_COLUMNS)
    column_list = ", ".join(f'"{column}"' for column in SQLITE_COLUMNS)
    statement = f"INSERT INTO awards ({column_list}) VALUES ({placeholders})"

    for line_number, row in enumerate(rows, start=2):
        record_id = row["award_record_id"]
        if not record_id or not row["year"] or not row["prize"] or not row["full_name"]:
            raise ImportFailure(f"{path.name}:{line_number}: required identity field is blank")
        if not record_id.startswith(f"{path.stem}-"):
            raise ImportFailure(f"{path.name}:{line_number}: unexpected award_record_id {record_id!r}")
        if record_id in seen_ids:
            raise ImportFailure(f"{path.name}:{line_number}: duplicate award_record_id {record_id!r}")
        seen_ids.add(record_id)

        source_id = row["source_laureate_id"].strip()
        laureate_wikidata_qid = source_id if QID.fullmatch(source_id) else ""
        values = {
            **row,
            "prize_name": prize_name,
            "award_wikidata_qid": award_wikidata_qid,
            "laureate_wikidata_qid": laureate_wikidata_qid,
        }
        connection.execute(statement, tuple(values[column] for column in SQLITE_COLUMNS))

    return len(rows)


def build_database(input_dir: Path, output: Path) -> dict[str, int]:
    missing = [name for name in AWARDS if not (input_dir / name).is_file()]
    if missing:
        raise ImportFailure(f"missing input files: {', '.join(missing)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.NamedTemporaryFile(prefix=f".{output.name}.", suffix=".tmp", dir=output.parent, delete=False)
    temporary_path = Path(temporary.name)
    temporary.close()

    counts: dict[str, int] = {}
    try:
        connection = sqlite3.connect(temporary_path)
        try:
            connection.execute("PRAGMA journal_mode = DELETE")
            connection.execute("PRAGMA synchronous = FULL")
            create_schema(connection)
            seen_ids: set[str] = set()
            with connection:
                for filename, (prize_name, award_qid) in AWARDS.items():
                    counts[filename] = import_csv(connection, input_dir / filename, prize_name, award_qid, seen_ids)
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if integrity != ("ok",):
                raise ImportFailure(f"SQLite integrity check failed: {integrity!r}")
        finally:
            connection.close()
        os.replace(temporary_path, output)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise

    return counts


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    dataset_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=dataset_dir, help="directory containing the canonical CSV files")
    parser.add_argument("--output", type=Path, default=dataset_dir / "awards.sqlite3", help="SQLite database to replace atomically")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        counts = build_database(args.input_dir.resolve(), args.output.resolve())
    except (ImportFailure, OSError, sqlite3.Error) as error:
        print(f"import failed: {error}", file=sys.stderr)
        return 1

    for filename, count in counts.items():
        print(f"imported file={filename} rows={count}")
    print(f"database={args.output.resolve()} rows={sum(counts.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
