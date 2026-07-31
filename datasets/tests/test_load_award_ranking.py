# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import load_award_ranking


class AwardRankingTests(unittest.TestCase):
    def create_database(self, path: Path) -> None:
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE awards (award_wikidata_qid TEXT, prize_name TEXT) STRICT")
            connection.executemany(
                "INSERT INTO awards VALUES (?, ?)",
                [("Q1", "First Prize"), ("Q2", "Second Prize")],
            )

    def write_seed(self, path: Path, first_score: int = 90, second_score: int = 80, include_second: bool = True) -> None:
        second = f"""
[Q2]
prize_name = "Second Prize"
slug = "second-prize"
url = "https://example.com/second"
score = {second_score}
blurb = "Second blurb."
reasoning = "Second reasoning."
""" if include_second else ""
        path.write_text(
            f"""
[Q1]
prize_name = "First Prize"
slug = "first-prize"
url = "https://example.com/first"
score = {first_score}
blurb = "First blurb."
reasoning = "First reasoning."
{second}
"""
        )

    def test_load_replaces_rows_and_allows_score_swaps(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            database = directory / "awards.sqlite3"
            seed = directory / "award_ranking.toml"
            self.create_database(database)
            self.write_seed(seed)

            self.assertEqual(2, load_award_ranking.load_ranking(database, seed))
            self.write_seed(seed, first_score=80, second_score=90)
            self.assertEqual(2, load_award_ranking.load_ranking(database, seed))

            with sqlite3.connect(database) as connection:
                rows = connection.execute(
                    "SELECT award_wikidata_qid, score, slug, url FROM award_ranking ORDER BY award_wikidata_qid"
                ).fetchall()
                awards = connection.execute("SELECT COUNT(*) FROM awards").fetchone()
            self.assertEqual(
                [
                    ("Q1", 80, "first-prize", "https://example.com/first"),
                    ("Q2", 90, "second-prize", "https://example.com/second"),
                ],
                rows,
            )
            self.assertEqual((2,), awards)

    def test_incomplete_seed_does_not_create_table(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            database = directory / "awards.sqlite3"
            seed = directory / "award_ranking.toml"
            self.create_database(database)
            self.write_seed(seed, include_second=False)

            with self.assertRaisesRegex(load_award_ranking.LoadFailure, "missing=Q2"):
                load_award_ranking.load_ranking(database, seed)

            with sqlite3.connect(database) as connection:
                table = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'award_ranking'"
                ).fetchone()
            self.assertIsNone(table)

    def test_failed_insert_rolls_back_deleted_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            database = directory / "awards.sqlite3"
            seed = directory / "award_ranking.toml"
            self.create_database(database)
            self.write_seed(seed)
            with sqlite3.connect(database) as connection:
                connection.execute(
                    """
                    CREATE TABLE award_ranking (
                        award_wikidata_qid TEXT PRIMARY KEY,
                        prize_name TEXT,
                        score INTEGER,
                        blurb TEXT,
                        reasoning TEXT,
                        required TEXT NOT NULL
                    ) STRICT
                    """
                )
                connection.execute(
                    "INSERT INTO award_ranking VALUES ('old', 'Old', 1, 'Old', 'Old', 'kept')"
                )

            with self.assertRaises(sqlite3.IntegrityError):
                load_award_ranking.load_ranking(database, seed)

            with sqlite3.connect(database) as connection:
                rows = connection.execute("SELECT award_wikidata_qid FROM award_ranking").fetchall()
            self.assertEqual([("old",)], rows)

    def test_existing_table_migrates_slug_and_enforces_uniqueness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            database = directory / "awards.sqlite3"
            seed = directory / "award_ranking.toml"
            self.create_database(database)
            self.write_seed(seed)
            with sqlite3.connect(database) as connection:
                connection.execute(
                    """
                    CREATE TABLE award_ranking (
                        award_wikidata_qid TEXT PRIMARY KEY,
                        prize_name TEXT NOT NULL UNIQUE,
                        url TEXT NOT NULL,
                        score INTEGER NOT NULL UNIQUE,
                        blurb TEXT NOT NULL,
                        reasoning TEXT NOT NULL
                    ) STRICT
                    """
                )
                connection.executemany(
                    "INSERT INTO award_ranking VALUES (?, ?, ?, ?, ?, ?)",
                    [
                        ("old-1", "Old One", "https://example.com/one", 1, "Old", "Old"),
                        ("old-2", "Old Two", "https://example.com/two", 2, "Old", "Old"),
                    ],
                )

            self.assertEqual(2, load_award_ranking.load_ranking(database, seed))

            with sqlite3.connect(database) as connection:
                columns = {row[1] for row in connection.execute("PRAGMA table_info(award_ranking)")}
                indexes = {row[1] for row in connection.execute("PRAGMA index_list(award_ranking)")}
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO award_ranking
                            (award_wikidata_qid, prize_name, slug, url, score, blurb, reasoning)
                        VALUES ('Q3', 'Third Prize', 'first-prize', 'https://example.com/third', 70, 'Third', 'Third')
                        """
                    )
            self.assertIn("slug", columns)
            self.assertIn("award_ranking_slug_idx", indexes)

    def test_invalid_and_duplicate_slugs_fail_before_writing(self) -> None:
        for replacement, message in (
            ('slug = "First Prize"', "invalid slug"),
            ('slug = "first-prize"', "duplicate slug"),
        ):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                database = directory / "awards.sqlite3"
                seed = directory / "award_ranking.toml"
                self.create_database(database)
                self.write_seed(seed)
                text = seed.read_text()
                if "duplicate" in message:
                    text = text.replace('slug = "second-prize"', replacement)
                else:
                    text = text.replace('slug = "first-prize"', replacement)
                seed.write_text(text)

                with self.assertRaisesRegex(load_award_ranking.LoadFailure, message):
                    load_award_ranking.load_ranking(database, seed)

                with sqlite3.connect(database) as connection:
                    table = connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'award_ranking'"
                    ).fetchone()
                self.assertIsNone(table)

    def test_failed_migration_rolls_back_schema_and_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            database = directory / "awards.sqlite3"
            seed = directory / "award_ranking.toml"
            self.create_database(database)
            self.write_seed(seed)
            with sqlite3.connect(database) as connection:
                connection.execute(
                    """
                    CREATE TABLE award_ranking (
                        award_wikidata_qid TEXT PRIMARY KEY,
                        prize_name TEXT,
                        score INTEGER,
                        blurb TEXT,
                        reasoning TEXT,
                        required TEXT NOT NULL
                    ) STRICT
                    """
                )
                connection.execute("INSERT INTO award_ranking VALUES ('old', 'Old', 1, 'Old', 'Old', 'kept')")

            with self.assertRaises(sqlite3.IntegrityError):
                load_award_ranking.load_ranking(database, seed)

            with sqlite3.connect(database) as connection:
                columns = {row[1] for row in connection.execute("PRAGMA table_info(award_ranking)")}
                rows = connection.execute("SELECT award_wikidata_qid FROM award_ranking").fetchall()
                index = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'award_ranking_slug_idx'"
                ).fetchone()
            self.assertNotIn("slug", columns)
            self.assertEqual([("old",)], rows)
            self.assertIsNone(index)

    def test_dry_run_does_not_create_table(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            database = directory / "awards.sqlite3"
            seed = directory / "award_ranking.toml"
            self.create_database(database)
            self.write_seed(seed)

            self.assertEqual(2, load_award_ranking.load_ranking(database, seed, dry_run=True))

            with sqlite3.connect(database) as connection:
                table = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'award_ranking'"
                ).fetchone()
            self.assertIsNone(table)


if __name__ == "__main__":
    unittest.main()
