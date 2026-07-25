from __future__ import annotations

import contextlib
import csv
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import enrich

# The database is the source of truth; no importer defines these any more. Held here as a test
# fixture only, mirroring the live `awards` table.
CSV_COLUMNS = (
    "award_record_id", "year", "category", "prize", "motivation", "prize_share", "source_laureate_id",
    "laureate_type", "full_name", "birth_date", "birth_year", "birth_city", "birth_country",
    "birth_coordinates", "citizenship_countries", "sex", "affiliation_name", "affiliation_city",
    "affiliation_country", "affiliation_coordinates", "death_date", "death_city", "death_country",
    "field_language", "biographical_note", "remarks",
)

AWARDS_COLUMNS = (
    "award_record_id", "year", "category", "prize", "prize_name", "award_wikidata_qid", "motivation",
    "prize_share", "source_laureate_id", "laureate_wikidata_qid", "laureate_type", "full_name",
    "birth_date", "birth_year", "birth_city", "birth_country", "birth_coordinates",
    "citizenship_countries", "sex", "affiliation_name", "affiliation_city", "affiliation_country",
    "affiliation_coordinates", "death_date", "death_city", "death_country", "field_language",
    "biographical_note", "remarks",
)


def create_schema(connection: sqlite3.Connection) -> None:
    definitions = ", ".join(
        f'"{column}" TEXT{" PRIMARY KEY" if column == "award_record_id" else ""}'
        for column in AWARDS_COLUMNS
    )
    connection.execute(f"CREATE TABLE awards ({definitions}) STRICT")


class EnrichJsonTests(unittest.TestCase):
    def create_database(self, path: Path, record_id: str, **values: str) -> None:
        with sqlite3.connect(path) as connection:
            create_schema(connection)
            columns = ("award_record_id", *values)
            placeholders = ", ".join("?" for _ in columns)
            connection.execute(
                f"INSERT INTO awards ({', '.join(columns)}) VALUES ({placeholders})",
                (record_id, *values.values()),
            )

    def test_known_qid_ignores_official_source_identifier(self) -> None:
        row = {"full_name": "Example", "source_laureate_id": "official-123"}

        self.assertEqual("", enrich.known_qid(row, {}))
        self.assertEqual("Q42", enrich.known_qid(row, {"Example": "Q42"}))

    def test_dry_run_returns_sqlite_ready_json_without_writing_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "abel_prize.csv"
            row = {column: "" for column in CSV_COLUMNS}
            row.update({
                "award_record_id": "abel_prize-000001",
                "year": "2000",
                "prize": "Abel Prize",
                "full_name": "Example Person",
            })
            with path.open("w", newline="") as target:
                writer = csv.DictWriter(target, fieldnames=CSV_COLUMNS)
                writer.writeheader()
                writer.writerow(row)
            original = path.read_bytes()

            def fill(candidate: dict, qid: str, entity: dict, verdict: str, delay: float) -> None:
                candidate["source_laureate_id"] = qid
                candidate["laureate_type"] = "Individual"
                candidate["birth_date"] = "1900-01-02"

            output = io.StringIO()
            with (
                patch.object(enrich, "resolve_award_qids", return_value={"Q188184"}),
                patch.object(enrich, "resolve", return_value=("Q42", {"labels": {"en": {"value": "Example Person"}}}, "individual", "award match")),
                patch.object(enrich, "fill_row", side_effect=fill),
                contextlib.redirect_stdout(output),
            ):
                result = enrich.main([str(path), "--dry-run"])

            payload = json.loads(output.getvalue())
            self.assertEqual(0, result)
            self.assertEqual(original, path.read_bytes())
            self.assertEqual("awards.sqlite3", payload["target"])
            self.assertEqual(1, payload["processed"])
            self.assertEqual(
                {
                    "laureate_wikidata_qid": "Q42",
                    "laureate_type": "Individual",
                    "birth_date": "1900-01-02",
                },
                payload["results"][0]["updates"],
            )
            self.assertNotIn("source_laureate_id", payload["results"][0]["updates"])

    def test_db_mode_reads_and_applies_report_without_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "awards.sqlite3"
            self.create_database(
                database,
                "abel_prize-000001",
                prize="Abel Prize",
                award_wikidata_qid="Q188184",
                source_laureate_id="official-123",
                full_name="Example Person",
            )

            def fill(candidate: dict, qid: str, entity: dict, verdict: str, delay: float) -> None:
                candidate["source_laureate_id"] = qid
                candidate["laureate_type"] = "Individual"
                candidate["birth_date"] = "1900-01-02"

            output = io.StringIO()
            with (
                patch.object(enrich, "resolve", return_value=("Q42", {"labels": {"en": {"value": "Example Person"}}}, "individual", "award match")),
                patch.object(enrich, "fill_row", side_effect=fill),
                contextlib.redirect_stdout(output),
            ):
                result = enrich.main(["--db", str(database), "--record-id", "abel_prize-000001"])

            with sqlite3.connect(database) as connection:
                stored = connection.execute(
                    """
                    SELECT laureate_wikidata_qid, source_laureate_id, laureate_type, birth_date
                    FROM awards
                    WHERE award_record_id = 'abel_prize-000001'
                    """
                ).fetchone()

            payload = json.loads(output.getvalue())
            self.assertEqual(0, result)
            self.assertEqual(str(database), payload["input_db"])
            self.assertNotIn("input_csv", payload)
            self.assertEqual(("Q42", "official-123", "Individual", "1900-01-02"), stored)
            self.assertEqual({"status": "applied", "rows": 1}, payload["database_apply"])

    def test_db_mode_requires_explicit_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "awards.sqlite3"
            self.create_database(database, "abel_prize-000001")

            with (
                patch.object(enrich, "read_database_rows") as read_database_rows,
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit) as raised,
            ):
                enrich.main(["--db", str(database)])

            self.assertEqual(2, raised.exception.code)
            read_database_rows.assert_not_called()

    def test_db_mode_selects_exact_record_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "awards.sqlite3"
            self.create_database(
                database,
                "abel_prize-000001",
                prize="Abel Prize",
                award_wikidata_qid="Q188184",
                full_name="First Person",
            )
            with sqlite3.connect(database) as connection:
                connection.execute(
                    """
                    INSERT INTO awards (award_record_id, prize, award_wikidata_qid, full_name)
                    VALUES ('abel_prize-000002', 'Abel Prize', 'Q188184', 'Second Person')
                    """
                )

            def fill(candidate: dict, qid: str, entity: dict, verdict: str, delay: float) -> None:
                candidate["laureate_type"] = "Individual"

            output = io.StringIO()
            with (
                patch.object(enrich, "resolve", return_value=("Q42", {"labels": {"en": {"value": "Second Person"}}}, "individual", "award match")),
                patch.object(enrich, "fill_row", side_effect=fill),
                contextlib.redirect_stdout(output),
            ):
                result = enrich.main(["--db", str(database), "--record-id", "abel_prize-000002"])

            with sqlite3.connect(database) as connection:
                stored = connection.execute(
                    "SELECT award_record_id, laureate_wikidata_qid FROM awards ORDER BY award_record_id"
                ).fetchall()

            payload = json.loads(output.getvalue())
            self.assertEqual(0, result)
            self.assertEqual(["abel_prize-000002"], [item["award_record_id"] for item in payload["results"]])
            self.assertEqual([("abel_prize-000001", None), ("abel_prize-000002", "Q42")], stored)

    def test_db_mode_rejects_missing_record_id_before_research(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "awards.sqlite3"
            self.create_database(database, "abel_prize-000001")

            with patch.object(enrich, "resolve") as resolve:
                result = enrich.main(["--db", str(database), "--record-id", "abel_prize-999999"])

            self.assertEqual(1, result)
            resolve.assert_not_called()

    def test_db_mode_selects_target_range(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "awards.sqlite3"
            self.create_database(
                database,
                "abel_prize-000001",
                prize="Abel Prize",
                award_wikidata_qid="Q188184",
                full_name="First Person",
            )
            with sqlite3.connect(database) as connection:
                connection.execute(
                    """
                    INSERT INTO awards (award_record_id, prize, award_wikidata_qid, full_name)
                    VALUES ('abel_prize-000002', 'Abel Prize', 'Q188184', 'Second Person')
                    """
                )

            def fill(candidate: dict, qid: str, entity: dict, verdict: str, delay: float) -> None:
                candidate["laureate_type"] = "Individual"

            output = io.StringIO()
            with (
                patch.object(enrich, "resolve", return_value=("Q42", {"labels": {"en": {"value": "Second Person"}}}, "individual", "award match")),
                patch.object(enrich, "fill_row", side_effect=fill),
                contextlib.redirect_stdout(output),
            ):
                result = enrich.main(["--db", str(database), "--offset", "1", "--limit", "1"])

            payload = json.loads(output.getvalue())
            self.assertEqual(0, result)
            self.assertEqual(["abel_prize-000002"], [item["award_record_id"] for item in payload["results"]])

    def test_database_updates_preserve_existing_values_and_ignore_disallowed_or_blank_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "awards.sqlite3"
            self.create_database(database, "abel_prize-000001", laureate_type="Organization")

            applied = enrich.apply_database_updates(str(database), [{
                "award_record_id": "abel_prize-000001",
                "updates": {
                    "laureate_wikidata_qid": "Q42",
                    "laureate_type": "Individual",
                    "birth_date": " ",
                    "source_laureate_id": "Q42",
                },
            }])

            with sqlite3.connect(database) as connection:
                stored = connection.execute(
                    """
                    SELECT laureate_wikidata_qid, source_laureate_id, laureate_type, birth_date
                    FROM awards
                    WHERE award_record_id = 'abel_prize-000001'
                    """
                ).fetchone()

            self.assertEqual(1, applied)
            self.assertEqual(("Q42", None, "Organization", None), stored)

    def test_database_updates_roll_back_when_any_record_id_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "awards.sqlite3"
            self.create_database(database, "abel_prize-000001")

            with self.assertRaisesRegex(enrich.DatabaseUpdateError, "award_record_id not found"):
                enrich.apply_database_updates(str(database), [
                    {
                        "award_record_id": "abel_prize-000001",
                        "updates": {"laureate_wikidata_qid": "Q42"},
                    },
                    {
                        "award_record_id": "abel_prize-999999",
                        "updates": {},
                    },
                ])

            with sqlite3.connect(database) as connection:
                stored = connection.execute(
                    "SELECT laureate_wikidata_qid FROM awards WHERE award_record_id = 'abel_prize-000001'"
                ).fetchone()

            self.assertEqual((None,), stored)

    def test_database_updates_roll_back_on_sql_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "awards.sqlite3"
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "CREATE TABLE awards (award_record_id TEXT PRIMARY KEY, laureate_wikidata_qid TEXT)"
                )
                connection.executemany(
                    "INSERT INTO awards VALUES (?, '')",
                    [("abel_prize-000001",), ("abel_prize-000002",)],
                )

            with self.assertRaisesRegex(sqlite3.OperationalError, "no such column"):
                enrich.apply_database_updates(str(database), [
                    {
                        "award_record_id": "abel_prize-000001",
                        "updates": {"laureate_wikidata_qid": "Q42"},
                    },
                    {
                        "award_record_id": "abel_prize-000002",
                        "updates": {"birth_date": "1900-01-02"},
                    },
                ])

            with sqlite3.connect(database) as connection:
                stored = connection.execute(
                    "SELECT laureate_wikidata_qid FROM awards WHERE award_record_id = 'abel_prize-000001'"
                ).fetchone()

            self.assertEqual(("",), stored)


if __name__ == "__main__":
    unittest.main()
