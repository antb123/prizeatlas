from __future__ import annotations

import contextlib
import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import enrich
from scripts import import_sqlite


class EnrichJsonTests(unittest.TestCase):
    def test_known_qid_ignores_official_source_identifier(self) -> None:
        row = {"full_name": "Example", "source_laureate_id": "official-123"}

        self.assertEqual("", enrich.known_qid(row, {}))
        self.assertEqual("Q42", enrich.known_qid(row, {"Example": "Q42"}))

    def test_dry_run_returns_sqlite_ready_json_without_writing_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "abel_prize.csv"
            row = {column: "" for column in import_sqlite.CSV_COLUMNS}
            row.update({
                "award_record_id": "abel_prize-000001",
                "year": "2000",
                "prize": "Abel Prize",
                "full_name": "Example Person",
            })
            with path.open("w", newline="") as target:
                writer = csv.DictWriter(target, fieldnames=import_sqlite.CSV_COLUMNS)
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


if __name__ == "__main__":
    unittest.main()
