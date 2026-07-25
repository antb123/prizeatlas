#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pycountry==24.6.1"]
# ///
"""Fix defects in the awards table rather than working around them at render time.

Three kinds of defect, all of them visible on the site today:

  entities   sixteen affiliation names hold raw HTML entities, so "King&#8217;s College London" renders as that
             literal string rather than an apostrophe.
  spacing    sixty-nine citations end " ." and four contain a double space.
  countries  birth and death countries name the state of the day, "Prussia (Germany)". The site should say where
             the place is now, so the modern name replaces it.

Reports by default and changes nothing. Pass --apply to back up the database and write.
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

TEXT_COLUMNS = ("full_name", "motivation", "affiliation_name", "biographical_note", "category", "prize", "remarks")
COUNTRY_COLUMNS = ("birth_country", "death_country")
DOUBLE_SPACE = re.compile(r"  +")
SPACE_BEFORE_PUNCTUATION = re.compile(r"\s+([.,;:])")

# Countries with no parenthetical modern equivalent, mapped to the country holding that territory today.
COUNTRY_ALIASES = {
    "USA": "United States",
    "the Netherlands": "Netherlands",
    "Czechia": "Czech Republic",
    "People's Republic of China": "China",
    "Russian Federation": "Russia",
    "USSR": "Russia",
    "Soviet Union": "Russia",
    "Soviet Union; Russia": "Russia",
    "Russian Empire": "Russia",
    "Prussia": "Germany",
    "Scotland": "United Kingdom",
    "England": "United Kingdom",
    "Wales": "United Kingdom",
    "Northern Ireland": "United Kingdom",
    "Republic of Macedonia": "North Macedonia",
    # Enrichment matched a city to the polity that held it long ago rather than to a country: London to the Roman
    # Empire, Berlin to the Margraviate of Brandenburg, Frankfurt to Francia, Moscow to the Duchy of Moscow.
    "Roman Empire": "United Kingdom",
    "Margraviate of Brandenburg": "Germany",
    "Francia": "Germany",
    "Duchy of Moscow": "Russia",
    "Tashkent Khanate": "Uzbekistan",
    "Kievan Rus'": "Ukraine",
    # Territories and renames.
    "Belgian Congo": "Democratic Republic of the Congo",
    "French protectorate of Tunisia": "Tunisia",
    "Guadeloupe Island": "France",
    "Trinidad": "Trinidad and Tobago",
    # Found by --validate rather than by eye, all in death_country.
    "East Germany": "Germany",
    "Czechoslovakia": "Czech Republic",
    "Union of Soviet Socialist Republics": "Russia",
    "Kingdom of Judah": "Israel",
    # ISO spellings.
    "The Bahamas": "Bahamas",
    "East Timor": "Timor-Leste",
    "Turkey": "Türkiye",
}
# A vanished empire spans several modern countries, so where one is recorded the city decides, not the empire.
# Enrichment reintroduces these from Wikidata P17, which answers with the polity of the day.
POLITY_NAMES = frozenset(
    {"Roman Empire", "Russian Empire", "Duchy of Moscow", "Margraviate of Brandenburg", "Francia", "Kievan Rus'",
     "Tashkent Khanate", "Austria-Hungary", "Austrian Empire", "Prussia", "Czechoslovakia", "Soviet Union", "USSR"}
)
HISTORICAL_BY_CITY = {
    "London": "United Kingdom",
    "Berlin": "Germany",
    "Frankfurt": "Germany",
    "Moscow": "Russia",
    "Odesa": "Ukraine",
    "Odessa": "Ukraine",
    "Kyiv": "Ukraine",
    "Tashkent": "Uzbekistan",
}
# Names we keep even though ISO 3166 lists them differently. "Russian Federation" is the ISO name; "Russia" is what
# English readers expect and pycountry carries no common_name for it.
DISPLAY_EXCEPTIONS = frozenset({"Russia", "Democratic Republic of the Congo"})
# Individual records whose columns hold the wrong thing entirely.
RECORD_FIXES = {
    # The sex landed in birth_country and the country in birth_city.
    "lasker_awards-000225": {"birth_country": "United States", "birth_city": ""},
}
# States that no longer exist. A parenthetical naming one glosses the outer name rather than modernising it, as in
# "Belarus (USSR)", so the outer name is the modern one there.
HISTORICAL_STATES = frozenset(
    {"USSR", "Soviet Union", "Russian Empire", "Prussia", "Austria-Hungary", "Austrian Empire", "Czechoslovakia"}
)


class CleanFailure(Exception):
    """The table cannot be cleaned without guessing."""


def clean_text(value: str) -> str:
    if not value:
        return value
    unescaped = html.unescape(value)
    collapsed = DOUBLE_SPACE.sub(" ", unescaped)
    return SPACE_BEFORE_PUNCTUATION.sub(r"\1", collapsed).strip()


def modern_country(value: str, city: str = "") -> str:
    """The country holding this birthplace today, using the city to disambiguate a multi-country empire."""
    name = clean_text(value)
    if name.endswith(")") and "(" in name:
        opening = name.rindex("(")
        inner = name[opening + 1 : -1].strip()
        name = name[:opening].strip() if inner in HISTORICAL_STATES else inner
    if name in POLITY_NAMES and (from_city := HISTORICAL_BY_CITY.get(clean_text(city))):
        return from_city
    return COUNTRY_ALIASES.get(name, name)


def plan(database: Path) -> list[tuple[str, str, str, str]]:
    """Every (record, column, old, new) the clean would write."""
    columns = ", ".join(("award_record_id", *TEXT_COLUMNS, *COUNTRY_COLUMNS, "birth_city"))
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(f"SELECT {columns} FROM awards").fetchall()

    changes: list[tuple[str, str, str, str]] = []
    for row in rows:
        for column in TEXT_COLUMNS:
            old = row[column] or ""
            if (new := clean_text(old)) != old:
                changes.append((row["award_record_id"], column, old, new))
        for column in COUNTRY_COLUMNS:
            old = row[column] or ""
            city = row["birth_city"] if column == "birth_country" else ""
            if (new := modern_country(old, city)) != old:
                changes.append((row["award_record_id"], column, old, new))
        for column, new in RECORD_FIXES.get(row["award_record_id"], {}).items():
            if (old := row[column] or "") != new:
                changes.append((row["award_record_id"], column, old, new))
    return changes


def validate(database: Path) -> int:
    """Check every stored country against ISO 3166-1.

    pycountry decides what is a real country today; the mapping above decides what we call it. A value it cannot
    resolve is either a historical polity the enrichment mistook for a country, or a defect.
    """
    import pycountry

    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        rows = connection.execute(
            "SELECT DISTINCT birth_country FROM awards WHERE birth_country <> '' "
            "UNION SELECT DISTINCT death_country FROM awards WHERE death_country <> ''"
        ).fetchall()

    unknown = []
    for (name,) in rows:
        if name in DISPLAY_EXCEPTIONS:
            continue
        try:
            pycountry.countries.lookup(name)
        except LookupError:
            unknown.append(name)
    for name in sorted(unknown):
        print(f"clean country-unknown '{name}'", file=sys.stderr)
    print(f"clean validate countries={len(rows)} unknown={len(unknown)}")
    return 1 if unknown else 0


def back_up(database: Path) -> Path:
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = database.with_name(f"{database.name}.{stamp}.clean.bak")
    shutil.copyfile(database, backup)
    return backup


def apply_changes(database: Path, changes: list[tuple[str, str, str, str]]) -> int:
    connection = sqlite3.connect(database)
    try:
        with connection:
            for record_id, column, _, new in changes:
                connection.execute(f"UPDATE awards SET {column} = ? WHERE award_record_id = ?", (new, record_id))
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise CleanFailure(f"integrity check failed: {integrity}")
        return len(changes)
    finally:
        connection.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", type=Path, default=Path(__file__).resolve().parents[1] / "awards.sqlite3")
    parser.add_argument("--apply", action="store_true", help="back up the database and write the cleaned values")
    parser.add_argument("--limit", type=int, default=25, help="how many example changes to print")
    parser.add_argument("--validate", action="store_true", help="check every country against ISO 3166 and exit")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.validate:
            return validate(args.database)
        changes = plan(args.database)
        by_column: dict[str, int] = {}
        for _, column, _, _ in changes:
            by_column[column] = by_column.get(column, 0) + 1
        for record_id, column, old, new in changes[: args.limit]:
            print(f"clean {column} record={record_id} '{old}' -> '{new}'")
        for column, count in sorted(by_column.items()):
            print(f"clean column={column} changes={count}")
        if not args.apply:
            print(f"clean dry-run changes={len(changes)}")
            return 0
        backup = back_up(args.database)
        written = apply_changes(args.database, changes)
    except (CleanFailure, sqlite3.Error, OSError) as error:
        print(f"clean failed: {error}", file=sys.stderr)
        return 1
    print(f"clean complete changes={written} backup={backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
