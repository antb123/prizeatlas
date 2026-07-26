# /// script
# requires-python = ">=3.12"
# ///
"""Build the standalone awards data explorer from awards.sqlite3.

Reads the awards and award_ranking tables plus the population.json snapshot,
folds every laureate into one identity (Wikidata QID; rows without a QID stay
unmerged), scores each win as the prize family's prestige score / 100, and
writes a single self-contained index.html with all data baked in. Run from the
datasets directory:

    uv run explorer/build.py
"""

from __future__ import annotations

import datetime
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATABASE = SCRIPT_DIR.parent / "awards.sqlite3"
YEAR_PREFIX = re.compile(r"(\d{4})")


class BuildFailure(Exception):
    """The explorer cannot be built from the current database."""


def read_rows() -> tuple[list[tuple[str, int]], list[tuple[str, ...]]]:
    if not DATABASE.is_file():
        raise BuildFailure(f"database is missing: {DATABASE}")
    with closing(sqlite3.connect(DATABASE.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        families = connection.execute("SELECT prize_name, score FROM award_ranking ORDER BY score DESC").fetchall()
        rows = connection.execute(
            """
            SELECT award_record_id, year, category, prize_name,
                   laureate_wikidata_qid, laureate_type, full_name,
                   birth_country, death_country, affiliation_country, citizenship_countries,
                   birth_date, birth_year
            FROM awards
            """
        ).fetchall()
    return families, rows


def load_population(country_names: list[str]) -> list[int | None]:
    """Population per country name, None where the snapshot has no figure."""
    snapshot = json.loads((SCRIPT_DIR / "population.json").read_text(encoding="utf-8"))
    figures = snapshot["population"]
    return [figures.get(name) for name in country_names]


def main() -> int:
    families, rows = read_rows()
    family_index = {name: index for index, (name, _) in enumerate(families)}

    people: dict[str, dict] = {}
    countries: dict[str, int] = {}

    def country_index(name: str) -> int:
        if name not in countries:
            countries[name] = len(countries)
        return countries[name]

    for record_id, year, category, prize_name, qid, laureate_type, full_name, birth, death, affiliation, citizenship, birth_date, birth_year in rows:
        match = YEAR_PREFIX.match(year)
        if not match:
            raise BuildFailure(f"invalid year record_id={record_id}")
        if prize_name not in family_index:
            raise BuildFailure(f"prize missing from award_ranking record_id={record_id}")
        key = qid or f"row:{record_id}"
        person = people.setdefault(
            key,
            {"n": full_name, "o": 1 if laureate_type == "Organization" else 0, "a": [], "bc": None, "dc": None, "ac": set(), "cc": set(), "by": None},
        )
        person["a"].append([int(match.group(1)), family_index[prize_name], category or ""])
        if person["by"] is None:
            birth_match = YEAR_PREFIX.match(birth_date or "") or YEAR_PREFIX.match(birth_year or "")
            if birth_match:
                person["by"] = int(birth_match.group(1))
        if birth and person["bc"] is None:
            person["bc"] = country_index(birth)
        if death and person["dc"] is None:
            person["dc"] = country_index(death)
        for name in (affiliation or "").split(";"):
            if name.strip():
                person["ac"].add(country_index(name.strip()))
        for name in (citizenship or "").split(";"):
            if name.strip():
                person["cc"].add(country_index(name.strip()))

    ranked = []
    for person in people.values():
        person["a"].sort()
        points = round(sum(families[family][1] / 100 for _, family, _ in person["a"]), 2)
        ranked.append({
            "n": person["n"], "o": person["o"], "c": len(person["a"]), "p": points, "a": person["a"],
            "bc": person["bc"], "dc": person["dc"], "ac": sorted(person["ac"]), "cc": sorted(person["cc"]), "by": person["by"],
        })
    ranked.sort(key=lambda person: (-person["p"], -person["c"], person["n"]))

    payload = {
        "families": [{"name": name, "score": score} for name, score in families],
        "countries": list(countries),
        "population": load_population(list(countries)),
        "people": ranked,
    }
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")

    template = (SCRIPT_DIR / "template.html").read_text(encoding="utf-8")
    if "__DATA__" not in template or "__GENERATED__" not in template:
        raise BuildFailure("template is missing a placeholder")
    stamp = datetime.datetime.fromtimestamp(DATABASE.stat().st_mtime, tz=datetime.UTC).date().isoformat()   # data date, not build date: rebuilds stay byte-identical
    html = template.replace("__DATA__", blob).replace("__GENERATED__", stamp)
    output = SCRIPT_DIR / "index.html"
    output.write_text(html, encoding="utf-8")

    awards = sum(person["c"] for person in ranked)
    print(
        f"explorer build complete people={len(ranked)} awards={awards} "
        f"families={len(families)} bytes={output.stat().st_size} output={output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
