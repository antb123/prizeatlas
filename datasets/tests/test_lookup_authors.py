# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts import lookup_authors as lookup


def claims(*, orcid: str | None = None, openalex: str | None = None) -> dict:
    values = {}
    for property_id, value in (("P496", orcid), ("P10283", openalex)):
        if value:
            values[property_id] = [{"rank": "normal", "mainsnak": {"datavalue": {"value": value}}}]
    return values


class LookupAuthorsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.database = Path(self.tmp.name) / "awards.sqlite3"
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                "CREATE TABLE awards (award_record_id TEXT PRIMARY KEY, laureate_wikidata_qid TEXT, "
                "laureate_type TEXT, orc_id TEXT NOT NULL DEFAULT '', "
                "author_openalex_id TEXT NOT NULL DEFAULT '') STRICT"
            )
            connection.execute("INSERT INTO awards VALUES ('r1', 'Q1', 'Individual', '', '')")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_main(self, arguments: list[str]) -> dict:
        output = __import__('io').StringIO()
        with redirect_stdout(output):
            self.assertEqual(0, lookup.main(["--db", str(self.database), *arguments]))
        return json.loads(output.getvalue())

    def test_checksum(self) -> None:
        self.assertTrue(lookup.valid_orcid("0000-0002-1825-0097"))
        self.assertFalse(lookup.valid_orcid("0000-0002-1825-0098"))

    def test_exact_claim_preview(self) -> None:
        with patch.object(lookup, "wikidata_claims", return_value=(claims(orcid="0000-0002-1825-0097"), "wikidata")), patch.object(
            lookup, "openalex_author", return_value=("A1", "openalex")
        ):
            result = self.run_main(["--record-id", "r1"])["results"][0]
        self.assertEqual({"orc_id": "0000-0002-1825-0097", "author_openalex_id": "A1"}, result["updates"])

    def test_missing_claim_abstains(self) -> None:
        with patch.object(lookup, "wikidata_claims", return_value=(claims(), "wikidata")):
            result = self.run_main(["--record-id", "r1"])["results"][0]
        self.assertEqual("unchanged", result["status"])
        self.assertEqual({}, result["updates"])

    def test_direct_openalex_claim_is_checked(self) -> None:
        with patch.object(lookup, "wikidata_claims", return_value=(claims(openalex="A1"), "wikidata")), patch.object(
            lookup, "openalex_by_id", return_value=("A1", "openalex")
        ):
            result = self.run_main(["--record-id", "r1"])["results"][0]
        self.assertEqual({"author_openalex_id": "A1"}, result["updates"])

    def test_apply_is_blank_only(self) -> None:
        with patch.object(lookup, "wikidata_claims", return_value=(claims(orcid="0000-0002-1825-0097"), "wikidata")), patch.object(
            lookup, "openalex_author", return_value=("A1", "openalex")
        ):
            self.run_main(["--record-id", "r1", "--apply"])
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(("0000-0002-1825-0097", "A1"), connection.execute("SELECT orc_id, author_openalex_id FROM awards WHERE award_record_id = 'r1'").fetchone())


if __name__ == "__main__":
    unittest.main()
