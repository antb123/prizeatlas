# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import classify_affiliations


class ClassifyAffiliationsTests(unittest.TestCase):
    def test_classify_uses_first_matching_kind(self) -> None:
        self.assertEqual(classify_affiliations.classify(["university hospital", "university"]), "hospital")
        self.assertEqual(classify_affiliations.classify(["public university"]), "university")
        self.assertEqual(classify_affiliations.classify(["research institute"]), "institute")
        self.assertEqual(classify_affiliations.classify(["technology company"]), "company")
        self.assertEqual(classify_affiliations.classify(["government agency"]), "government")
        self.assertEqual(classify_affiliations.classify(["nonprofit organization"]), "other")

    def test_distinct_qids_reads_both_affiliation_stores(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "awards.sqlite3"
            with sqlite3.connect(database) as connection:
                connection.execute("CREATE TABLE awards (affiliation_wikidata_qid TEXT)")
                connection.execute("CREATE TABLE award_extra_affiliations (affiliation_wikidata_qid TEXT)")
                connection.executemany("INSERT INTO awards VALUES (?)", [("Q2",), ("Q1",), ("",), (None,)])
                connection.executemany("INSERT INTO award_extra_affiliations VALUES (?)", [("Q3",), ("Q1",), ("",)])

            self.assertEqual(classify_affiliations.distinct_qids(str(database)), ["Q1", "Q2", "Q3"])

    def test_add_kind_column_is_idempotent(self) -> None:
        with sqlite3.connect(":memory:") as connection:
            connection.execute("CREATE TABLE affiliations (affiliation_wikidata_qid TEXT PRIMARY KEY) STRICT")
            classify_affiliations.add_kind_column(connection)
            classify_affiliations.add_kind_column(connection)

            columns = {row[1]: row for row in connection.execute("PRAGMA table_info(affiliations)")}
            self.assertEqual(columns["kind"][2], "TEXT")
            self.assertEqual(columns["kind"][3], 1)
            self.assertEqual(columns["kind"][4], "''")


if __name__ == "__main__":
    unittest.main()
