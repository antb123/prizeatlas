#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Restore a non-science award dump into awards.sqlite3."""

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


class LoadFailure(Exception):
    """The non-science dump cannot be restored safely."""


@dataclass(frozen=True)
class TableDump:
    schema: tuple[tuple[object, ...], ...]
    records: tuple[tuple[object, ...], ...]

    @property
    def columns(self) -> tuple[str, ...]:
        return tuple(str(row[1]) for row in self.schema)

    @property
    def primary_key(self) -> str:
        keys = [str(row[1]) for row in self.schema if row[5]]
        if len(keys) != 1:
            raise LoadFailure("dump table must have one primary key")
        return keys[0]


@dataclass(frozen=True)
class DumpData:
    awards: TableDump
    rankings: TableDump


@dataclass(frozen=True)
class LoadResult:
    awards: int
    rankings: int
    backup: Path


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def valid_schema(raw_schema: object, table: str) -> tuple[tuple[object, ...], ...]:
    if not isinstance(raw_schema, list) or not raw_schema:
        raise LoadFailure(f"invalid schema table={table}")
    schema: list[tuple[object, ...]] = []
    names: set[str] = set()
    for position, raw_row in enumerate(raw_schema):
        if not isinstance(raw_row, list) or len(raw_row) != 6:
            raise LoadFailure(f"invalid schema row table={table}")
        cid, name, declared_type, not_null, default, primary_key = raw_row
        if (
            type(cid) is not int
            or cid != position
            or not isinstance(name, str)
            or not name
            or not isinstance(declared_type, str)
            or type(not_null) is not int
            or not_null not in (0, 1)
            or (default is not None and not isinstance(default, str))
            or type(primary_key) is not int
            or primary_key not in (0, 1)
            or name in names
        ):
            raise LoadFailure(f"invalid schema value table={table}")
        names.add(name)
        schema.append(tuple(raw_row))
    return tuple(schema)


def valid_value(value: object, schema_row: tuple[object, ...]) -> bool:
    declared_type = str(schema_row[2]).upper()
    required = bool(schema_row[3]) or bool(schema_row[5])
    if value is None:
        return not required
    if declared_type == "TEXT":
        return isinstance(value, str)
    if declared_type == "INTEGER":
        return type(value) is int
    return False


def valid_table(raw_table: object, table: str) -> TableDump:
    if not isinstance(raw_table, dict) or set(raw_table) != {"schema", "count", "records"}:
        raise LoadFailure(f"invalid table payload table={table}")
    schema = valid_schema(raw_table["schema"], table)
    raw_records = raw_table["records"]
    if type(raw_table["count"]) is not int or not isinstance(raw_records, list) or raw_table["count"] != len(raw_records):
        raise LoadFailure(f"record count mismatch table={table}")
    records: list[tuple[object, ...]] = []
    for number, raw_record in enumerate(raw_records, start=1):
        if not isinstance(raw_record, list) or len(raw_record) != len(schema):
            raise LoadFailure(f"record width mismatch table={table} record={number}")
        if not all(valid_value(value, schema_row) for value, schema_row in zip(raw_record, schema, strict=True)):
            raise LoadFailure(f"record type mismatch table={table} record={number}")
        records.append(tuple(raw_record))

    result = TableDump(schema, tuple(records))
    key_index = result.columns.index(result.primary_key)
    keys = [row[key_index] for row in result.records]
    if any(not key for key in keys) or len(keys) != len(set(keys)):
        raise LoadFailure(f"invalid or duplicate primary key table={table}")
    return result


def read_dump(path: Path) -> DumpData:
    with path.open(encoding="utf-8") as source:
        payload = json.load(source)
    if not isinstance(payload, dict) or set(payload) != {"format", "subjects", "tables", "sha256"}:
        raise LoadFailure(f"{path} is not an {FORMAT} dump")
    if payload["format"] != FORMAT or payload["subjects"] != list(SUBJECTS):
        raise LoadFailure(f"{path} is not an {FORMAT} dump")
    digest = payload["sha256"]
    document = {key: value for key, value in payload.items() if key != "sha256"}
    if not isinstance(digest, str) or digest != hashlib.sha256(canonical_json(document)).hexdigest():
        raise LoadFailure("dump digest mismatch")
    raw_tables = payload["tables"]
    if not isinstance(raw_tables, dict) or set(raw_tables) != set(TABLES):
        raise LoadFailure("dump tables mismatch")
    awards = valid_table(raw_tables["awards"], "awards")
    rankings = valid_table(raw_tables["award_ranking"], "award_ranking")
    if not awards.records:
        raise LoadFailure("dump contains no awards")
    if "award_record_id" not in awards.columns or "high_school_subject" not in awards.columns:
        raise LoadFailure("awards dump is missing required columns")
    subject_index = awards.columns.index("high_school_subject")
    if any(row[subject_index] not in SUBJECTS for row in awards.records):
        raise LoadFailure("dump contains a retained subject")
    if rankings.primary_key != "award_wikidata_qid":
        raise LoadFailure("award_ranking dump has the wrong primary key")
    return DumpData(awards, rankings)


def table_schema(connection: sqlite3.Connection, table: str) -> tuple[tuple[object, ...], ...]:
    return tuple(tuple(row) for row in connection.execute(f"PRAGMA table_info({quote_identifier(table)})"))


def table_rows(connection: sqlite3.Connection, table: str) -> tuple[tuple[object, ...], ...]:
    schema = table_schema(connection, table)
    columns = [quote_identifier(str(row[1])) for row in schema]
    order = ", ".join(str(index) for index in range(1, len(columns) + 1))
    return tuple(connection.execute(f"SELECT {', '.join(columns)} FROM {quote_identifier(table)} ORDER BY {order}"))


def database_snapshot(connection: sqlite3.Connection) -> dict[str, object]:
    objects = tuple(
        tuple(row)
        for row in connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        )
    )
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
            raise LoadFailure(f"backup integrity check failed: {backup}")
        if database_snapshot(verification) != expected:
            raise LoadFailure(f"backup does not match locked database: {backup}")
    return backup


def placeholders(values: tuple[object, ...]) -> str:
    return ", ".join("?" for _ in values)


def primary_keys(table: TableDump) -> tuple[object, ...]:
    index = table.columns.index(table.primary_key)
    return tuple(row[index] for row in table.records)


def select_dumped_rows(connection: sqlite3.Connection, table: TableDump, table_name: str) -> tuple[tuple[object, ...], ...]:
    keys = primary_keys(table)
    columns = ", ".join(quote_identifier(column) for column in table.columns)
    key = quote_identifier(table.primary_key)
    return tuple(
        connection.execute(
            f"SELECT {columns} FROM {quote_identifier(table_name)} WHERE {key} IN ({placeholders(keys)}) ORDER BY {key}",
            keys,
        )
    )


def insert_rows(connection: sqlite3.Connection, table: TableDump, table_name: str) -> None:
    columns = ", ".join(quote_identifier(column) for column in table.columns)
    statement = f"INSERT INTO {quote_identifier(table_name)} ({columns}) VALUES ({placeholders(tuple(table.columns))})"
    connection.executemany(statement, table.records)


def load_arts(database: Path, source: Path) -> LoadResult:
    dump = read_dump(source)
    connection = sqlite3.connect(database)
    try:
        connection.execute("BEGIN IMMEDIATE")
        if table_schema(connection, "awards") != dump.awards.schema or table_schema(connection, "award_ranking") != dump.rankings.schema:
            raise LoadFailure("dump schemas do not match the database")

        award_ids = primary_keys(dump.awards)
        ranking_qids = primary_keys(dump.rankings)
        award_conflicts = connection.execute(
            f"SELECT COUNT(*) FROM awards WHERE award_record_id IN ({placeholders(award_ids)})", award_ids
        ).fetchone()[0]
        ranking_conflicts = connection.execute(
            f"SELECT COUNT(*) FROM award_ranking WHERE award_wikidata_qid IN ({placeholders(ranking_qids)})", ranking_qids
        ).fetchone()[0]
        extra_conflicts = connection.execute(
            f"SELECT COUNT(*) FROM award_extra_affiliations WHERE award_record_id IN ({placeholders(award_ids)})", award_ids
        ).fetchone()[0]
        conflicts = award_conflicts + ranking_conflicts + extra_conflicts
        if conflicts:
            raise LoadFailure(f"dumped primary keys already exist count={conflicts}; nothing loaded")

        live_qids = {row[0] for row in connection.execute("SELECT DISTINCT award_wikidata_qid FROM awards WHERE award_wikidata_qid <> ''")}
        live_ranking_qids = {row[0] for row in connection.execute("SELECT award_wikidata_qid FROM award_ranking")}
        if live_qids != live_ranking_qids:
            raise LoadFailure("ranking rows do not match live awards before restore")

        backup = create_backup(connection, database)
        insert_rows(connection, dump.awards, "awards")
        insert_rows(connection, dump.rankings, "award_ranking")
        if select_dumped_rows(connection, dump.awards, "awards") != dump.awards.records:
            raise LoadFailure("restored awards do not match dump")
        if select_dumped_rows(connection, dump.rankings, "award_ranking") != dump.rankings.records:
            raise LoadFailure("restored rankings do not match dump")
        restored_qids = {row[0] for row in connection.execute("SELECT DISTINCT award_wikidata_qid FROM awards WHERE award_wikidata_qid <> ''")}
        restored_ranking_qids = {row[0] for row in connection.execute("SELECT award_wikidata_qid FROM award_ranking")}
        if restored_qids != restored_ranking_qids:
            raise LoadFailure("ranking rows do not match restored awards")
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise LoadFailure("database integrity check failed")
        connection.commit()
        return LoadResult(len(dump.awards.records), len(dump.rankings.records), backup)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    dataset_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=dataset_dir / "awards.sqlite3")
    parser.add_argument("--input", type=Path, default=dataset_dir / "non_science.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    database = args.database.resolve()
    source = args.input.resolve()
    try:
        result = load_arts(database, source)
    except (LoadFailure, OSError, sqlite3.Error, json.JSONDecodeError) as error:
        print(f"non_science_load failed database={database} input={source} error={error}", file=sys.stderr)
        return 1
    print(
        f"non_science_load complete database={database} input={source} awards={result.awards} "
        f"rankings={result.rankings} backup={result.backup}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
