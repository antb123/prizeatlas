from __future__ import annotations

import csv
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import import_sqlite


class SQLiteImportTests(unittest.TestCase):
    def write_inputs(self, directory: Path) -> None:
        for index, name in enumerate(import_sqlite.AWARDS, start=1):
            row = {column: "" for column in import_sqlite.CSV_COLUMNS}
            row.update(
                {
                    "award_record_id": f"{Path(name).stem}-000001",
                    "year": "2000",
                    "prize": f"Source prize {index}",
                    "source_laureate_id": "Q42" if name == "abel_prize.csv" else f"official-{index}",
                    "laureate_type": "Individual",
                    "full_name": f"Recipient {index}",
                }
            )
            with (directory / name).open("w", newline="") as target:
                writer = csv.DictWriter(target, fieldnames=import_sqlite.CSV_COLUMNS)
                writer.writeheader()
                writer.writerow(row)

    def test_import_preserves_source_values_and_adds_normalized_identifiers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            output = directory / "awards.sqlite3"
            self.write_inputs(directory)

            counts = import_sqlite.build_database(directory, output)

            self.assertEqual(len(import_sqlite.AWARDS), sum(counts.values()))
            with sqlite3.connect(output) as connection:
                row = connection.execute(
                    """
                    SELECT prize, prize_name, category, award_wikidata_qid,
                           source_laureate_id, laureate_wikidata_qid
                    FROM awards
                    WHERE award_record_id = 'abel_prize-000001'
                    """
                ).fetchone()
                columns = [item[1] for item in connection.execute("PRAGMA table_info(awards)")]

            self.assertEqual(import_sqlite.SQLITE_COLUMNS, tuple(columns))
            self.assertEqual(("Source prize 1", "Abel Prize", "", "Q188184", "Q42", "Q42"), row)

    def test_failed_import_does_not_replace_existing_database(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            output = directory / "awards.sqlite3"
            output.write_bytes(b"existing database")
            self.write_inputs(directory)
            (directory / "nobel.csv").write_text("wrong,header\n")

            with self.assertRaisesRegex(import_sqlite.ImportFailure, "unexpected header"):
                import_sqlite.build_database(directory, output)

            self.assertEqual(b"existing database", output.read_bytes())


if __name__ == "__main__":
    unittest.main()
