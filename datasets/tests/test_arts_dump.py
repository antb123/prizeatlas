# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import dump_arts, load_arts


class NonScienceMoveTests(unittest.TestCase):
    def create_database(self, path: Path, extra_affiliation: bool = False) -> None:
        with sqlite3.connect(path) as connection:
            connection.executescript(
                """
                CREATE TABLE awards (
                    award_record_id TEXT PRIMARY KEY,
                    award_wikidata_qid TEXT NOT NULL,
                    prize_name TEXT NOT NULL,
                    high_school_subject TEXT NOT NULL
                ) STRICT;
                CREATE TABLE award_ranking (
                    award_wikidata_qid TEXT PRIMARY KEY,
                    prize_name TEXT NOT NULL UNIQUE,
                    score INTEGER NOT NULL UNIQUE,
                    blurb TEXT NOT NULL,
                    reasoning TEXT NOT NULL,
                    url TEXT NOT NULL DEFAULT '',
                    slug TEXT NOT NULL DEFAULT ''
                ) STRICT;
                CREATE UNIQUE INDEX award_ranking_slug_idx ON award_ranking(slug);
                CREATE TABLE affiliations (
                    affiliation_wikidata_qid TEXT PRIMARY KEY,
                    logo_url TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    application_url TEXT NOT NULL DEFAULT '',
                    kind TEXT NOT NULL DEFAULT ''
                ) STRICT;
                CREATE TABLE award_extra_affiliations (
                    award_record_id TEXT NOT NULL REFERENCES awards(award_record_id),
                    position INTEGER NOT NULL CHECK (position >= 2),
                    affiliation_name TEXT NOT NULL DEFAULT '',
                    affiliation_sub_name TEXT NOT NULL DEFAULT '',
                    affiliation_city TEXT NOT NULL DEFAULT '',
                    affiliation_country TEXT NOT NULL DEFAULT '',
                    affiliation_coordinates TEXT NOT NULL DEFAULT '',
                    affiliation_wikidata_qid TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (award_record_id, position)
                ) STRICT;
                """
            )
            connection.executemany(
                "INSERT INTO awards VALUES (?, ?, ?, ?)",
                [
                    ("history-1", "Qnobel", "Nobel Prize", "History"),
                    ("lit-1", "Qnobel", "Nobel Prize", "Lit"),
                    ("physics-1", "Qnobel", "Nobel Prize", "Physics"),
                    ("arts-1", "Qwolf", "Wolf Prize", "Arts"),
                    ("chemistry-1", "Qwolf", "Wolf Prize", "Chemistry"),
                    ("economics-1", "Qecon", "Economics Prize", "Economics"),
                    ("math-1", "Qmath", "Math Prize", "Math"),
                    ("cs-1", "Qcs", "CS Prize", "CS"),
                    ("biology-1", "Qbio", "Biology Prize", "Biology"),
                    ("earth-1", "Qearth", "Earth Prize", "Earth Science"),
                ],
            )
            connection.executemany(
                "INSERT INTO award_ranking VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    ("Qnobel", "Nobel Prize", 100, "Nobel", "Nobel", "https://example.org/nobel", "nobel"),
                    ("Qwolf", "Wolf Prize", 90, "Wolf", "Wolf", "https://example.org/wolf", "wolf"),
                    ("Qecon", "Economics Prize", 80, "Economics", "Economics", "https://example.org/economics", "economics"),
                    ("Qmath", "Math Prize", 70, "Math", "Math", "https://example.org/math", "math"),
                    ("Qcs", "CS Prize", 60, "CS", "CS", "https://example.org/cs", "cs"),
                    ("Qbio", "Biology Prize", 50, "Biology", "Biology", "https://example.org/biology", "biology"),
                    ("Qearth", "Earth Prize", 40, "Earth", "Earth", "https://example.org/earth", "earth"),
                ],
            )
            connection.execute("INSERT INTO affiliations VALUES ('Qinst', '', 'Kept profile', '', 'university')")
            if extra_affiliation:
                connection.execute(
                    "INSERT INTO award_extra_affiliations (award_record_id, position, affiliation_name) VALUES ('history-1', 2, 'Extra')"
                )

    def snapshot(self, database: Path) -> dict[str, list[tuple]]:
        with sqlite3.connect(database) as connection:
            tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
            return {table: connection.execute(f'SELECT * FROM "{table}" ORDER BY 1, 2').fetchall() for table in tables}

    def test_move_and_restore_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            database = directory / "awards.sqlite3"
            dump = directory / "non_science.json"
            self.create_database(database)
            before = self.snapshot(database)

            moved = dump_arts.dump_arts(database, dump)

            self.assertEqual((4, 1), (moved.awards, moved.rankings))
            self.assertTrue(moved.backup.exists())
            with sqlite3.connect(database) as connection:
                subjects = {row[0] for row in connection.execute("SELECT DISTINCT high_school_subject FROM awards")}
                ranking_qids = {row[0] for row in connection.execute("SELECT award_wikidata_qid FROM award_ranking")}
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            self.assertEqual({"Biology", "Physics", "Chemistry", "Math", "CS", "Earth Science"}, subjects)
            self.assertNotIn("Qecon", ranking_qids)
            self.assertEqual("ok", integrity)

            restored = load_arts.load_arts(database, dump)

            self.assertEqual((4, 1), (restored.awards, restored.rankings))
            self.assertTrue(restored.backup.exists())
            self.assertEqual(before, self.snapshot(database))
            with sqlite3.connect(database) as connection:
                self.assertEqual("ok", connection.execute("PRAGMA integrity_check").fetchone()[0])

    def test_existing_dump_does_not_change_database(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            database = directory / "awards.sqlite3"
            dump = directory / "non_science.json"
            self.create_database(database)
            dump.write_text("keep", encoding="utf-8")
            before = self.snapshot(database)

            with self.assertRaises(FileExistsError):
                dump_arts.dump_arts(database, dump)

            self.assertEqual("keep", dump.read_text(encoding="utf-8"))
            self.assertEqual(before, self.snapshot(database))
            self.assertEqual([], list(directory.glob("*.bak")))

    def test_extra_affiliation_blocks_move(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            database = directory / "awards.sqlite3"
            dump = directory / "non_science.json"
            self.create_database(database, extra_affiliation=True)
            before = self.snapshot(database)

            with self.assertRaisesRegex(dump_arts.DumpFailure, "extra affiliations"):
                dump_arts.dump_arts(database, dump)

            self.assertFalse(dump.exists())
            self.assertEqual(before, self.snapshot(database))
            self.assertEqual([], list(directory.glob("*.bak")))

    def test_second_load_does_not_overwrite_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            database = directory / "awards.sqlite3"
            dump = directory / "non_science.json"
            self.create_database(database)
            dump_arts.dump_arts(database, dump)
            load_arts.load_arts(database, dump)
            with sqlite3.connect(database) as connection:
                connection.execute("UPDATE awards SET prize_name = 'Newer value' WHERE award_record_id = 'history-1'")
            before = self.snapshot(database)
            backups = set(directory.glob("*.bak"))

            with self.assertRaisesRegex(load_arts.LoadFailure, "already exist"):
                load_arts.load_arts(database, dump)

            self.assertEqual(before, self.snapshot(database))
            self.assertEqual(backups, set(directory.glob("*.bak")))

    def test_bad_digest_fails_before_database_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            database = directory / "awards.sqlite3"
            dump = directory / "non_science.json"
            self.create_database(database)
            dump_arts.dump_arts(database, dump)
            before = self.snapshot(database)
            backups = set(directory.glob("*.bak"))
            payload = json.loads(dump.read_text(encoding="utf-8"))
            payload["sha256"] = "0" * 64
            dump.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(load_arts.LoadFailure, "digest mismatch"):
                load_arts.load_arts(database, dump)

            self.assertEqual(before, self.snapshot(database))
            self.assertEqual(backups, set(directory.glob("*.bak")))


if __name__ == "__main__":
    unittest.main()
