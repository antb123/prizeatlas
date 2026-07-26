#!/usr/bin/env python3
"""Populate awards.high_school_subject with US high school curriculum subjects."""

import argparse
import sqlite3
import sys

SUBJECTS = (
    "Biology",
    "Physics",
    "Chemistry",
    "Math",
    "CS",
    "History",
    "Lit",
    "Arts",
    "Economics",
    "Earth Science",
)

KYOTO = {
    # Biology (Biological sciences & Life sciences)
    "kyoto_prize-000005": "Biology",
    "kyoto_prize-000017": "Biology",
    "kyoto_prize-000026": "Biology",
    "kyoto_prize-000041": "Biology",
    "kyoto_prize-000055": "Biology",
    "kyoto_prize-000067": "Biology",
    "kyoto_prize-000079": "Biology",
    "kyoto_prize-000080": "Biology",
    "kyoto_prize-000092": "Biology",
    "kyoto_prize-000104": "Biology",
    "kyoto_prize-000116": "Biology",
    "kyoto_prize-000128": "Biology",
    "kyoto_prize-000023": "Biology",
    "kyoto_prize-000035": "Biology",
    "kyoto_prize-000050": "Biology",
    "kyoto_prize-000064": "Biology",
    "kyoto_prize-000076": "Biology",
    "kyoto_prize-000089": "Biology",
    "kyoto_prize-000101": "Biology",
    "kyoto_prize-000113": "Biology",
    "kyoto_prize-000125": "Biology",
    # Math (Mathematical sciences)
    "kyoto_prize-000002": "Math",
    "kyoto_prize-000014": "Math",
    "kyoto_prize-000029": "Math",
    "kyoto_prize-000044": "Math",
    "kyoto_prize-000058": "Math",
    "kyoto_prize-000070": "Math",
    "kyoto_prize-000083": "Math",
    "kyoto_prize-000095": "Math",
    "kyoto_prize-000107": "Math",
    "kyoto_prize-000119": "Math",
    # Lit (Cognitive science)
    "kyoto_prize-000011": "Lit",
    # Earth and planetary sciences, astronomy and astrophysics split
    "kyoto_prize-000008": "Physics",
    "kyoto_prize-000020": "Earth Science",
    "kyoto_prize-000032": "Physics",
    "kyoto_prize-000047": "Earth Science",
    "kyoto_prize-000061": "Physics",
    "kyoto_prize-000073": "Earth Science",
    "kyoto_prize-000086": "Physics",
    "kyoto_prize-000098": "Physics",
    "kyoto_prize-000110": "Physics",
    "kyoto_prize-000122": "Earth Science",
}

BIO_KEYWORDS = ("Medic", "Bio", "Health", "Neuro", "Cell", "Genom", "Psychol", "Food", "Host Defense")
CS_KEYWORDS_1 = ("Information", "Comput", "Electro", "Communication", "Media")
EARTH_KEYWORDS = ("Environment", "Earth", "Global Change", "Resources, Energy", "Marine", "Sustainable")
CS_KEYWORDS_2 = ("Material", "Production", "Engineering", "Technolog", "Aerospace", "City Planning", "Complexity", "Devices")


def classify(record: dict[str, str]) -> str | None:
    prize_name = record.get("prize_name", "") or ""
    category = record.get("category", "") or ""

    if prize_name in ("Fields Medal", "Abel Prize"):
        return "Math"
    if prize_name == "Turing Award":
        return "CS"
    if prize_name == "Max Planck Medal":
        return "Physics"
    if prize_name in ("Canada Gairdner International Award", "Lasker Award"):
        return "Biology"

    if category in ("Physics", "Fundamental Physics"):
        return "Physics"
    if category == "Chemistry":
        return "Chemistry"
    if category in ("Mathematics", "Mathematical Sciences", "Applied Mathematics"):
        return "Math"
    if category in ("Medicine", "Life Sciences", "Biosciences", "Polyarthritis", "Life Science and Medicine", "Agriculture"):
        return "Biology"
    if category == "Literature":
        return "Lit"
    if category == "Peace":
        return "History"
    if category == "Economics":
        return "Economics"
    if category in ("Arts", "Arts and Philosophy"):
        return "Arts"
    if category == "Astronomy":
        return "Physics"
    if category == "Geosciences":
        return "Earth Science"

    category_lower = category.lower()

    if any(kw.lower() in category_lower for kw in BIO_KEYWORDS):
        return "Biology"
    if any(kw.lower() in category_lower for kw in CS_KEYWORDS_1):
        return "CS"
    if any(kw.lower() in category_lower for kw in EARTH_KEYWORDS):
        return "Earth Science"
    if any(kw.lower() in category_lower for kw in CS_KEYWORDS_2):
        return "CS"

    return None


def set_subjects(db_path: str, dry_run: bool = False) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check if high_school_subject column exists, add if missing
    cursor.execute("PRAGMA table_info(awards)")
    columns = [row["name"] for row in cursor.fetchall()]
    if "high_school_subject" not in columns:
        cursor.execute(
            "ALTER TABLE awards ADD COLUMN high_school_subject TEXT NOT NULL DEFAULT '' "
            "CHECK (high_school_subject IN ('', 'Biology', 'Physics', 'Chemistry', 'Math', "
            "'CS', 'History', 'Lit', 'Arts', 'Economics', 'Earth Science'))"
        )

    cursor.execute("SELECT award_record_id, prize_name, category, laureate_wikidata_qid, high_school_subject FROM awards")
    rows = cursor.fetchall()

    updates: list[tuple[str, str]] = []
    unclassified: list[sqlite3.Row] = []
    unchanged_count = 0

    for row in rows:
        rec_id = row["award_record_id"]
        current_val = row["high_school_subject"]

        if rec_id in KYOTO:
            target_val = KYOTO[rec_id]
        else:
            target_val = classify(dict(row))

        if target_val is None:
            unclassified.append(row)
            continue

        if current_val == target_val:
            unchanged_count += 1
        else:
            updates.append((target_val, rec_id))

    if unclassified:
        conn.rollback()
        for row in unclassified:
            print(
                f"award_subjects unclassified record_id={row['award_record_id']} "
                f"qid={row['laureate_wikidata_qid']} category={row['category']}",
                file=sys.stderr,
            )
        sys.exit(1)

    if not dry_run and updates:
        cursor.executemany("UPDATE awards SET high_school_subject = ? WHERE award_record_id = ?", updates)
        cursor.execute("PRAGMA integrity_check;")
        check = cursor.fetchone()[0]
        if check != "ok":
            conn.rollback()
            raise RuntimeError(f"PRAGMA integrity_check failed: {check}")
        conn.commit()

    set_count = len(updates)
    print(f"award_subjects set={set_count} unchanged={unchanged_count} dry_run={dry_run}")
    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate awards.high_school_subject")
    parser.add_argument("-d", "--database", default="awards.sqlite3", help="Path to awards.sqlite3")
    parser.add_argument("--dry-run", action="store_true", help="Do not write changes to database")
    args = parser.parse_args()

    set_subjects(args.database, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
