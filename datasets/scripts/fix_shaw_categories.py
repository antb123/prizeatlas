#!/usr/bin/env python3
"""Give Shaw Prize records their category, and a prize share computed within it.

The Shaw Prize is three separate prizes awarded the same year: Astronomy, Life Science and Medicine, and Mathematical
Sciences. The category was never stored, only embedded in the citation as "Shaw Prize in Astronomy — ...", so every
laureate of a year was treated as one group. Seven laureates across the three prizes in 2023 each got a share of 1/7,
and Shrinivas Kulkarni, sole winner of Astronomy in 2024, got 1/4 instead of the whole prize.

This lifts the category out of the citation, drops the now-redundant prefix, and recomputes the share within the
category. Reports by default; pass --apply to back up the database and write.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PREFIX = re.compile(r"^Shaw Prize in (?P<category>[^—]+?)\s*—\s*(?P<citation>.+)$", re.DOTALL)
# The source writes these in sentence case; the site shows categories in title case, as the other prizes do.
CATEGORY_NAMES = {
    "astronomy": "Astronomy",
    "life science and medicine": "Life Science and Medicine",
    "mathematical sciences": "Mathematical Sciences",
}


class ShawFixError(Exception):
    """A Shaw record cannot be categorised without guessing."""


def plan(database: Path) -> list[tuple[str, str, str, str]]:
    """Every (record_id, category, citation, share) the fix would write."""
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT award_record_id, year, category, motivation, prize_share FROM awards "
            "WHERE prize_name LIKE 'Shaw%' ORDER BY award_record_id"
        ).fetchall()

    parsed: list[tuple[str, str, str, str]] = []
    groups: dict[tuple[str, str], int] = {}
    for row in rows:
        match = PREFIX.match(row["motivation"] or "")
        if not match:
            raise ShawFixError(f"citation has no category prefix record={row['award_record_id']}")
        key = match.group("category").strip().lower()
        if key not in CATEGORY_NAMES:
            raise ShawFixError(f"unknown Shaw category {key!r} record={row['award_record_id']}")
        category = CATEGORY_NAMES[key]
        groups[(row["year"], category)] = groups.get((row["year"], category), 0) + 1
        parsed.append((row["award_record_id"], row["year"], category, match.group("citation").strip()))

    return [
        (record_id, category, citation, f"1/{groups[(year, category)]}")
        for record_id, year, category, citation in parsed
    ]


def back_up(database: Path) -> Path:
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = database.with_name(f"{database.name}.{stamp}.shaw.bak")
    shutil.copyfile(database, backup)
    return backup


def apply_changes(database: Path, changes: list[tuple[str, str, str, str]]) -> int:
    connection = sqlite3.connect(database)
    try:
        with connection:
            for record_id, category, citation, share in changes:
                connection.execute(
                    "UPDATE awards SET category = ?, motivation = ?, prize_share = ? WHERE award_record_id = ?",
                    (category, citation, share, record_id),
                )
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ShawFixError(f"integrity check failed: {integrity}")
        return len(changes)
    finally:
        connection.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", type=Path, default=Path(__file__).resolve().parents[1] / "awards.sqlite3")
    parser.add_argument("--apply", action="store_true", help="back up the database and write")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        changes = plan(args.database)
        shares: dict[str, int] = {}
        categories: dict[str, int] = {}
        for _, category, _, share in changes:
            shares[share] = shares.get(share, 0) + 1
            categories[category] = categories.get(category, 0) + 1
        for category, count in sorted(categories.items()):
            print(f"shaw category='{category}' records={count}")
        for share, count in sorted(shares.items()):
            print(f"shaw share={share} records={count}")
        if not args.apply:
            print(f"shaw fix dry-run records={len(changes)}")
            return 0
        backup = back_up(args.database)
        written = apply_changes(args.database, changes)
    except (ShawFixError, sqlite3.Error, OSError) as error:
        print(f"shaw fix failed: {error}", file=sys.stderr)
        return 1
    print(f"shaw fix complete records={written} backup={backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
