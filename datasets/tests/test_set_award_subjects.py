import sqlite3
import unittest
from pathlib import Path

from scripts.set_award_subjects import classify, set_subjects


def create_test_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test_awards.sqlite3"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE awards (
            award_record_id TEXT PRIMARY KEY,
            prize_name TEXT,
            category TEXT,
            laureate_wikidata_qid TEXT,
            high_school_subject TEXT NOT NULL DEFAULT '' CHECK (high_school_subject IN (
                '', 'Biology', 'Physics', 'Chemistry', 'Math', 'CS',
                'History', 'Lit', 'Arts', 'Economics', 'Earth Science'
            ))
        )
        """
    )
    cursor.executemany(
        "INSERT INTO awards (award_record_id, prize_name, category, laureate_wikidata_qid) VALUES (?, ?, ?, ?)",
        [
            ("abel_prize-000001", "Abel Prize", "", "Q1"),
            ("turing_award-000001", "Turing Award", "", "Q2"),
            ("japan_prize-000001", "Japan Prize", "Healthcare and Medical Technology", "Q3"),
            ("kyoto_prize-000002", "Kyoto Prize", "Basic Sciences", "Q4"),
        ],
    )
    conn.commit()
    conn.close()
    return db_path


class TestSetAwardSubjects(unittest.TestCase):
    def test_classify_ladder(self):
        self.assertEqual(classify({"prize_name": "Fields Medal", "category": ""}), "Math")
        self.assertEqual(classify({"prize_name": "Turing Award", "category": ""}), "Computer Science")
        self.assertEqual(classify({"prize_name": "Japan Prize", "category": "Healthcare and Medical Technology"}), "Biology")
        self.assertIsNone(classify({"prize_name": "Japan Prize", "category": "Unknown Subject XYZ"}))

    def test_set_subjects_success_and_idempotency(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = create_test_db(Path(tmp_dir))

            # Dry run test
            set_subjects(str(db_path), dry_run=True)
            conn = sqlite3.connect(db_path)
            rows = conn.execute("SELECT high_school_subject FROM awards").fetchall()
            self.assertTrue(all(r[0] == "" for r in rows))
            conn.close()

            # Actual run
            set_subjects(str(db_path), dry_run=False)
            conn = sqlite3.connect(db_path)
            res = dict(conn.execute("SELECT award_record_id, high_school_subject FROM awards").fetchall())
            conn.close()

            self.assertEqual(res["abel_prize-000001"], "Math")
            self.assertEqual(res["turing_award-000001"], "Computer Science")
            self.assertEqual(res["japan_prize-000001"], "Biology")  # Medical keyword beats CS
            self.assertEqual(res["kyoto_prize-000002"], "Math")  # Kyoto override

            # Second run is no-op
            set_subjects(str(db_path), dry_run=False)

    def test_unclassifiable_record_raises(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_unclassifiable.sqlite3"
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE awards (
                    award_record_id TEXT PRIMARY KEY,
                    prize_name TEXT,
                    category TEXT,
                    laureate_wikidata_qid TEXT,
                    high_school_subject TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute("INSERT INTO awards VALUES ('unknown-001', 'Mysterious Award', 'Bizarre Category', 'Q99', '')")
            conn.commit()
            conn.close()

            with self.assertRaises(SystemExit):
                set_subjects(str(db_path), dry_run=False)


if __name__ == "__main__":
    unittest.main()
