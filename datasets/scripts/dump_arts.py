#!/usr/bin/env python3
"""Dump and remove non-science awards from awards.sqlite3."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

FORMAT = "non-science-awards-v1"
SUBJECTS = ("History", "Arts", "Lit", "Economics")
TABLES = ("awards", "award_ranking")


class DumpFailure(Exception):
    """The non-science rows cannot be moved safely."""


@dataclass(frozen=True)
class MoveResult:
    awards: int
    rankings: int
    backup: Path


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def table_schema(connection: sqlite3.Connection, table: str) -> list[list[object]]:
    return [list(row) for row in connection.execute(f"PRAGMA table_info({quote_identifier(table)})")]


def table_rows(connection: sqlite3.Connection, table: str) -> list[list[object]]:
    schema = table_schema(connection, table)
    columns = [quote_identifier(str(row[1])) for row in schema]
    order = ", ".join(str(index) for index in range(1, len(columns) + 1))
    return [list(row) for row in connection.execute(f"SELECT {', '.join(columns)} FROM {quote_identifier(table)} ORDER BY {order}")]


def database_snapshot(connection: sqlite3.Connection) -> dict[str, object]:
    objects = [
        list(row)
        for row in connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        )
    ]
    tables = [row[1] for row in objects if row[0] == "table"]
    return {
        "objects": objects,
        "tables": {table: {"schema": table_schema(connection, table), "records": table_rows(connection, table)} for table in tables},
    }


def sync_file(path: Path) -> None:
    with path.open("rb") as source:
        os.fsync(source.fileno())


def sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def create_backup(locked: sqlite3.Connection, database: Path) -> Path:
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    backup = database.with_name(f"{database.name}.{stamp}.non-science.bak")
    descriptor = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
    os.close(descriptor)
    expected = database_snapshot(locked)
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as source, sqlite3.connect(backup) as destination:
        source.backup(destination)
    sync_file(backup)
    sync_directory(backup.parent)
    with sqlite3.connect(f"file:{backup}?mode=ro", uri=True) as verification:
        if verification.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise DumpFailure(f"backup integrity check failed: {backup}")
        if database_snapshot(verification) != expected:
            raise DumpFailure(f"backup does not match locked database: {backup}")
    return backup


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def add_digest(document: dict[str, object]) -> dict[str, object]:
    payload = dict(document)
    payload["sha256"] = hashlib.sha256(canonical_json(document)).hexdigest()
    return payload


def validate_written_dump(payload: object) -> None:
    if not isinstance(payload, dict):
        raise DumpFailure("written dump is not an object")
    digest = payload.get("sha256")
    document = {key: value for key, value in payload.items() if key != "sha256"}
    if not isinstance(digest, str) or digest != hashlib.sha256(canonical_json(document)).hexdigest():
        raise DumpFailure("written dump digest mismatch")
    if payload.get("format") != FORMAT or payload.get("subjects") != list(SUBJECTS):
        raise DumpFailure("written dump format mismatch")
    tables = payload.get("tables")
    if not isinstance(tables, dict) or set(tables) != set(TABLES):
        raise DumpFailure("written dump tables mismatch")
    for table in TABLES:
        entry = tables[table]
        if not isinstance(entry, dict) or entry.get("count") != len(entry.get("records", [])):
            raise DumpFailure(f"written dump count mismatch table={table}")


def placeholders(values: list[object] | tuple[object, ...]) -> str:
    return ", ".join("?" for _ in values)


def selected_rows(connection: sqlite3.Connection) -> tuple[list[list[object]], list[list[object]]]:
    award_schema = table_schema(connection, "awards")
    ranking_schema = table_schema(connection, "award_ranking")
    if not award_schema or not ranking_schema:
        raise DumpFailure("awards or award_ranking table not found")

    award_qids = {row[0] for row in connection.execute("SELECT DISTINCT award_wikidata_qid FROM awards WHERE award_wikidata_qid <> ''")}
    ranking_qids = {row[0] for row in connection.execute("SELECT award_wikidata_qid FROM award_ranking")}
    if award_qids != ranking_qids:
        raise DumpFailure("ranking rows do not match live awards")

    award_columns = [quote_identifier(str(row[1])) for row in award_schema]
    awards = [
        list(row)
        for row in connection.execute(
            f"SELECT {', '.join(award_columns)} FROM awards "
            f"WHERE high_school_subject IN ({placeholders(SUBJECTS)}) ORDER BY award_record_id",
            SUBJECTS,
        )
    ]
    if not awards:
        raise DumpFailure("no non-science awards found")
    id_index = next(index for index, row in enumerate(award_schema) if row[1] == "award_record_id")
    selected_ids = [row[id_index] for row in awards]
    extra_count = connection.execute(
        f"SELECT COUNT(*) FROM award_extra_affiliations WHERE award_record_id IN ({placeholders(selected_ids)})",
        selected_ids,
    ).fetchone()[0]
    if extra_count:
        raise DumpFailure(f"selected awards have extra affiliations count={extra_count}")

    removed_qids = [
        row[0]
        for row in connection.execute(
            f"SELECT award_wikidata_qid FROM awards GROUP BY award_wikidata_qid "
            f"HAVING SUM(high_school_subject NOT IN ({placeholders(SUBJECTS)})) = 0 "
            f"AND SUM(high_school_subject IN ({placeholders(SUBJECTS)})) > 0 "
            "ORDER BY award_wikidata_qid",
            (*SUBJECTS, *SUBJECTS),
        )
    ]
    ranking_columns = [quote_identifier(str(row[1])) for row in ranking_schema]
    rankings = [
        list(row)
        for row in connection.execute(
            f"SELECT {', '.join(ranking_columns)} FROM award_ranking "
            f"WHERE award_wikidata_qid IN ({placeholders(removed_qids)}) ORDER BY award_wikidata_qid",
            removed_qids,
        )
    ]
    if len(rankings) != len(removed_qids):
        raise DumpFailure("orphaned ranking selection mismatch")
    return awards, rankings


def build_payload(connection: sqlite3.Connection, awards: list[list[object]], rankings: list[list[object]]) -> dict[str, object]:
    return add_digest(
        {
            "format": FORMAT,
            "subjects": list(SUBJECTS),
            "tables": {
                "awards": {"schema": table_schema(connection, "awards"), "count": len(awards), "records": awards},
                "award_ranking": {
                    "schema": table_schema(connection, "award_ranking"),
                    "count": len(rankings),
                    "records": rankings,
                },
            },
        }
    )


def write_dump(destination, output: Path, payload: dict[str, object]) -> None:
    json.dump(payload, destination, ensure_ascii=False, indent=2)
    destination.write("\n")
    destination.flush()
    os.fsync(destination.fileno())
    sync_directory(output.parent)
    destination.seek(0)
    validate_written_dump(json.load(destination))


def dump_arts(database: Path, output: Path) -> MoveResult:
    destination = None
    connection = None
    verified = False
    try:
        destination = output.open("x+", encoding="utf-8")
        connection = sqlite3.connect(database)
        connection.execute("BEGIN IMMEDIATE")
        awards, rankings = selected_rows(connection)
        backup = create_backup(connection, database)
        payload = build_payload(connection, awards, rankings)
        write_dump(destination, output, payload)
        verified = True

        award_ids = [row[0] for row in awards]
        ranking_qids = [row[0] for row in rankings]
        retained_awards = [
            list(row)
            for row in connection.execute(
                f"SELECT * FROM awards WHERE high_school_subject NOT IN ({placeholders(SUBJECTS)}) ORDER BY award_record_id",
                SUBJECTS,
            )
        ]
        retained_rankings = [
            list(row)
            for row in connection.execute(
                f"SELECT * FROM award_ranking WHERE award_wikidata_qid NOT IN ({placeholders(ranking_qids)}) ORDER BY award_wikidata_qid",
                ranking_qids,
            )
        ]
        affiliations = table_rows(connection, "affiliations")

        deleted_awards = connection.executemany("DELETE FROM awards WHERE award_record_id = ?", ((value,) for value in award_ids)).rowcount
        deleted_rankings = connection.executemany(
            "DELETE FROM award_ranking WHERE award_wikidata_qid = ?", ((value,) for value in ranking_qids)
        ).rowcount
        if deleted_awards != len(awards) or deleted_rankings != len(rankings):
            raise DumpFailure("deleted row count does not match dump")
        if retained_awards != [list(row) for row in connection.execute("SELECT * FROM awards ORDER BY award_record_id")]:
            raise DumpFailure("retained awards changed during removal")
        if retained_rankings != [list(row) for row in connection.execute("SELECT * FROM award_ranking ORDER BY award_wikidata_qid")]:
            raise DumpFailure("retained rankings changed during removal")
        if affiliations != table_rows(connection, "affiliations"):
            raise DumpFailure("affiliations changed during removal")
        live_qids = {row[0] for row in connection.execute("SELECT DISTINCT award_wikidata_qid FROM awards WHERE award_wikidata_qid <> ''")}
        ranking_qids_live = {row[0] for row in connection.execute("SELECT award_wikidata_qid FROM award_ranking")}
        if live_qids != ranking_qids_live:
            raise DumpFailure("ranking rows do not match retained awards")
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise DumpFailure("database integrity check failed")
        connection.commit()
        return MoveResult(len(awards), len(rankings), backup)
    except Exception:
        if connection is not None:
            connection.rollback()
        if destination is not None:
            destination.close()
            if not verified:
                output.unlink(missing_ok=True)
        raise
    finally:
        if destination is not None and not destination.closed:
            destination.close()
        if connection is not None:
            connection.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    dataset_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=dataset_dir / "awards.sqlite3")
    parser.add_argument("--output", type=Path, default=dataset_dir / "non_science.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    database = args.database.resolve()
    output = args.output.resolve()
    try:
        result = dump_arts(database, output)
    except (DumpFailure, OSError, sqlite3.Error, json.JSONDecodeError) as error:
        print(f"non_science_dump failed database={database} output={output} error={error}", file=sys.stderr)
        return 1
    print(
        f"non_science_dump complete database={database} output={output} awards={result.awards} "
        f"rankings={result.rankings} backup={result.backup}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
