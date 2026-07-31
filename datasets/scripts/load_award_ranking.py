# SPDX-License-Identifier: GPL-2.0-or-later
"""Load the complete award prestige ranking into awards.sqlite3."""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

import tomllib

QID = re.compile(r"Q[1-9][0-9]*")
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
FIELDS = {"prize_name", "slug", "url", "score", "blurb", "reasoning"}
CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS award_ranking (
        "award_wikidata_qid" TEXT PRIMARY KEY,
        "prize_name"         TEXT NOT NULL UNIQUE,
        "slug"               TEXT NOT NULL UNIQUE,
        "url"                TEXT NOT NULL,
        "score"              INTEGER NOT NULL UNIQUE CHECK (score BETWEEN 0 AND 100),
        "blurb"              TEXT NOT NULL,
        "reasoning"          TEXT NOT NULL
) STRICT
"""


class LoadFailure(Exception):
    """The ranking cannot be loaded without violating its contract."""


@dataclass(frozen=True, slots=True)
class Award:
    qid: str
    prize_name: str
    slug: str
    url: str
    score: int
    blurb: str
    reasoning: str


def read_seed(path: Path) -> list[Award]:
    with path.open("rb") as source:
        document = tomllib.load(source)

    awards: list[Award] = []
    scores: dict[int, str] = {}
    slugs: dict[str, str] = {}
    for qid, values in document.items():
        if not QID.fullmatch(qid) or not isinstance(values, dict) or set(values) != FIELDS:
            raise LoadFailure(f"invalid seed block qid={qid}")
        if type(values["score"]) is not int or not 0 <= values["score"] <= 100:
            raise LoadFailure(f"invalid score qid={qid}")
        for field in ("prize_name", "blurb", "reasoning"):
            if not isinstance(values[field], str) or not values[field].strip():
                raise LoadFailure(f"invalid {field} qid={qid}")
        if not isinstance(values["url"], str) or not values["url"].startswith("https://"):
            raise LoadFailure(f"invalid url qid={qid}")
        if not isinstance(values["slug"], str) or not SLUG.fullmatch(values["slug"]):
            raise LoadFailure(f"invalid slug qid={qid}")
        if values["score"] in scores:
            raise LoadFailure(f"duplicate score={values['score']} qids={scores[values['score']]},{qid}")
        if values["slug"] in slugs:
            raise LoadFailure(f"duplicate slug={values['slug']} qids={slugs[values['slug']]},{qid}")
        scores[values["score"]] = qid
        slugs[values["slug"]] = qid
        awards.append(Award(qid=qid, **values))

    if not awards:
        raise LoadFailure("seed is empty")
    return awards


def validate_live_awards(connection: sqlite3.Connection, awards: list[Award]) -> None:
    live = dict(connection.execute("SELECT DISTINCT award_wikidata_qid, prize_name FROM awards"))
    seed = {award.qid: award.prize_name for award in awards}
    if live == seed:
        return

    missing = sorted(live.keys() - seed.keys())
    extra = sorted(seed.keys() - live.keys())
    mismatched = sorted(qid for qid in live.keys() & seed.keys() if live[qid] != seed[qid])
    details = []
    if missing:
        details.append(f"missing={','.join(missing)}")
    if extra:
        details.append(f"extra={','.join(extra)}")
    if mismatched:
        details.append(f"mismatched={','.join(mismatched)}")
    raise LoadFailure(f"seed does not match live awards {' '.join(details)}")


def load_ranking(database: Path, seed: Path, dry_run: bool = False) -> int:
    awards = read_seed(seed)
    with sqlite3.connect(database) as connection:
        validate_live_awards(connection, awards)
        if dry_run:
            return len(awards)

        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(CREATE_TABLE)
            columns = {row[1] for row in connection.execute("PRAGMA table_info(award_ranking)")}
            if "url" not in columns:
                connection.execute("ALTER TABLE award_ranking ADD COLUMN url TEXT NOT NULL DEFAULT ''")
            if "slug" not in columns:
                connection.execute("ALTER TABLE award_ranking ADD COLUMN slug TEXT NOT NULL DEFAULT ''")
            connection.execute("DELETE FROM award_ranking")
            connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS award_ranking_slug_idx ON award_ranking(slug)")
            connection.executemany(
                """
                INSERT INTO award_ranking
                    (award_wikidata_qid, prize_name, slug, url, score, blurb, reasoning)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (award.qid, award.prize_name, award.slug, award.url, award.score, award.blurb, award.reasoning)
                    for award in awards
                ],
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise

        if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise LoadFailure("SQLite integrity check failed")
    return len(awards)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    dataset_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=dataset_dir / "awards.sqlite3")
    parser.add_argument("--seed", type=Path, default=dataset_dir / "award_ranking.toml")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        count = load_ranking(args.database.resolve(), args.seed.resolve(), args.dry_run)
    except (LoadFailure, OSError, sqlite3.Error, tomllib.TOMLDecodeError) as error:
        print(f"award ranking load failed: {error}", file=sys.stderr)
        return 1

    print(f"award_ranking rows={count} dry_run={str(args.dry_run).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
