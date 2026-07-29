# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "jinja2==3.1.6",
# ]
# ///
"""Build the static awards website from awards.sqlite3."""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import math
import posixpath
import re
import shutil
import sqlite3
import sys
import tempfile
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, quote_plus, urlsplit, urlunsplit
from xml.sax.saxutils import escape as xml_escape

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

SCRIPT_DIR = Path(__file__).resolve().parent
DATASET_DIR = SCRIPT_DIR.parent
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
YEAR_PREFIX = re.compile(r"([0-9]{4})")
WIKIDATA_QID = re.compile(r"Q[1-9][0-9]*")
SITEMAP_URL_LIMIT = 50_000
SITEMAP_BYTE_LIMIT = 52_428_800
TEMPLATES = (
    "base.html",
    "index.html",
    "awards.html",
    "prize.html",
    "winners.html",
    "category.html",
    "year.html",
    "winner.html",
    "person.html",
    "people.html",
    "_view_tabs.html",
    "countries.html",
    "country.html",
    "affiliation_countries.html",
    "affiliation_country.html",
    "affiliations.html",
    "affiliation.html",
    "universities.html",
    "university_countries.html",
    "subjects.html",
    "subject.html",
    "subject_affiliations.html",
    "subject_recent.html",
    "explorer.html",
    "nearby.html",
    "map.html",
    "about.html",
    "404.html",
)
AWARDS_ROUTE = "/awards/"
PEOPLE_ROUTE = "/people/"
PEOPLE_PER_PAGE = 200
HOMEPAGE_ROWS = 8
COUNTRIES_ROUTE = "/countries/"
COUNTRY_AFFILIATIONS_ROUTE = "/countries/affiliations/"
COUNTRY_AFFILIATIONS_SEGMENT = "affiliations"
COUNTRY_VIEWS = (
    ("Born", COUNTRIES_ROUTE),
    ("Awarded", "/countries/awarded/"),
    ("Died", "/countries/died/"),
)
RESERVED_COUNTRY_SEGMENTS = frozenset({COUNTRY_AFFILIATIONS_SEGMENT, "awarded", "died"})
AFFILIATIONS_ROUTE = "/affiliations/"
AFFILIATION_SLUG_MAX = 80
UNIVERSITIES_ROUTE = "/universities/"
UNIVERSITY_COUNTRIES_ROUTE = "/universities/countries/"
# The one affiliations.kind that names a degree-granting university or college; institutes, laboratories, hospitals,
# companies and government bodies are ranked under Institutions instead.
UNIVERSITY_KIND = "university"
UNIVERSITY_ROWS = 40
COUNTRY_UNIVERSITY_ROWS = 10
SUBJECTS_ROUTE = "/subjects/"
EXPLORER_ROUTE = "/explorer/"
NEARBY_ROUTE = "/nearby/"
MAP_ROUTE = "/map/"
ABOUT_ROUTE = "/about/"
SUBJECTS = (
    "Biology", "Physics", "Chemistry", "Math", "CS",
    "History", "Lit", "Arts", "Economics", "Earth Science",
)
POPULATION_FILE = SCRIPT_DIR / "population.json"
AFFILIATION_ROWS = 40
# Recorded in the affiliation column but not an institution.
AFFILIATION_BLOCKLIST = frozenset({"Freelance"})
PRIZE_PAGE_YEARS = 30
SUBJECT_RECENT_YEARS = 3
# The prize page shows recent years only. Its complete index of recipients lives one segment below.
WINNERS_SEGMENT = "winners"
DESCRIPTION_LIMIT = 160
# Prizes whose "category" is a topic chosen afresh each year rather than a standing division. Routing those by
# category yields a page per award; they browse by year instead.
YEAR_ROUTED_PRIZES = frozenset({"japan-prize"})
FACT_FIELDS = (
    ("Type", "laureate_type"),
    ("Born", "birth_date"),
    ("Birth year", "birth_year"),
    ("Birth city", "birth_city"),
    ("Birth country", "birth_country"),
    ("Citizenship", "citizenship_countries"),
    ("Died", "death_date"),
    ("Death city", "death_city"),
    ("Death country", "death_country"),
)
AWARD_COLUMNS = (
    "award_record_id",
    "year",
    "category",
    "prize",
    "prize_name",
    "award_wikidata_qid",
    "motivation",
    "prize_share",
    "laureate_wikidata_qid",
    "laureate_type",
    "full_name",
    "birth_date",
    "birth_year",
    "birth_city",
    "birth_country",
    "birth_coordinates",
    "citizenship_countries",
    "sex",
    "affiliation_name",
    "affiliation_sub_name",
    "affiliation_wikidata_qid",
    "affiliation_city",
    "affiliation_country",
    "affiliation_coordinates",
    "death_date",
    "death_city",
    "death_country",
    "biographical_note",
    "high_school_subject",
)


class BuildFailure(Exception):
    """The website cannot be built without violating its contract."""


@dataclass(frozen=True, slots=True)
class Ranking:
    qid: str
    prize_name: str
    slug: str
    url: str
    score: int
    blurb: str
    reasoning: str
    logo: str = ""


@dataclass(frozen=True, slots=True)
class AwardRecord:
    award_record_id: str
    year: str
    category: str
    prize: str
    prize_name: str
    award_wikidata_qid: str
    motivation: str
    prize_share: str
    laureate_wikidata_qid: str
    laureate_type: str
    full_name: str
    birth_date: str
    birth_year: str
    birth_city: str
    birth_country: str
    birth_coordinates: str
    citizenship_countries: str
    sex: str
    affiliation_name: str
    affiliation_sub_name: str
    affiliation_wikidata_qid: str
    affiliation_city: str
    affiliation_country: str
    affiliation_coordinates: str
    death_date: str
    death_city: str
    death_country: str
    biographical_note: str
    high_school_subject: str
    affiliations: tuple[AwardAffiliation, ...] = ()


@dataclass(frozen=True, slots=True)
class AwardAffiliation:
    """One recorded affiliation of one award. `position` orders rows; it does not rank them."""
    position: int
    name: str
    sub_name: str
    city: str
    country: str
    coordinates: str
    wikidata_qid: str


@dataclass(frozen=True, slots=True)
class AwardLink:
    """An award as it appears under one institution, carrying the affiliation row that placed it there."""
    record: AwardRecord
    affiliation: AwardAffiliation
    route: str


@dataclass(frozen=True, slots=True)
class AffiliationProfile:
    qid: str
    logo_url: str
    description: str
    application_url: str
    kind: str

    @property
    def wikidata_url(self) -> str:
        return f"https://www.wikidata.org/wiki/{self.qid}"


@dataclass(frozen=True, slots=True)
class Affiliation:
    """An institution and the constituent units recorded under it. `count` is laureates, not awards, so it is the
    size of the union of the units' members and is never their sum."""
    name: str
    slug: str
    route: str
    count: int
    units: tuple[tuple[str, int], ...]
    awards: tuple[AwardLink, ...]
    subjects: tuple[tuple[str, str], ...]
    profile: AffiliationProfile | None


@dataclass(frozen=True, slots=True)
class Breadcrumb:
    label: str
    route: str | None


@dataclass(frozen=True, slots=True)
class PageJob:
    template: str
    route: str
    title: str
    description: str
    breadcrumbs: tuple[Breadcrumb, ...]
    context: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Laureate:
    qid: str
    name: str
    route: str
    awards: tuple[tuple[AwardRecord, str], ...]
    subjects: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class Place:
    name: str
    slug: str
    route: str
    people: tuple[Laureate, ...]


@dataclass(frozen=True, slots=True)
class RankedAffiliation:
    """An institution ranked inside one country or one subject. `count` is laureates within that slice, never the
    institution's worldwide total, so the rows of a page can be compared with each other."""
    affiliation: Affiliation
    count: int
    place: str


@dataclass(frozen=True, slots=True)
class AffiliationCountry:
    name: str
    slug: str
    route: str
    members: tuple[RankedAffiliation, ...]
    laureates: int
    cities: int


@dataclass(frozen=True, slots=True)
class Subject:
    name: str
    route: str
    affiliations_route: str
    recent_route: str
    award_count: int
    people: tuple[Laureate, ...]
    affiliations: tuple[RankedAffiliation, ...] = ()


@dataclass(frozen=True, slots=True)
class RecentSubjectAwards:
    start_year: int
    end_year: int
    recipient_count: int
    prize_count: int
    groups: tuple[tuple[str, tuple[tuple[str, tuple[tuple[AwardRecord, str], ...]], ...]], ...]


@dataclass(frozen=True, slots=True)
class PrizeLayout:
    """Every route one prize owns, allocated before any of its pages are built."""
    ranking: Ranking
    route: str
    records: list[AwardRecord]
    routed_categories: bool
    category_slugs: dict[str, str]
    year_routes: dict[tuple[str | None, str], str]
    year_records: dict[tuple[str | None, str], list[AwardRecord]]
    record_routes: dict[str, str]


@dataclass(frozen=True, slots=True)
class SitePlan:
    jobs: tuple[PageJob, ...]
    prize_count: int
    category_count: int
    year_count: int
    winner_count: int
    recipient_count: int
    person_count: int
    country_count: int
    subject_count: int
    year_span: str


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", errors="ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    if not slug:
        raise BuildFailure("derived slug is empty")
    return slug


def affiliation_slug(name: str) -> str:
    base = slugify(name)
    if len(base) <= AFFILIATION_SLUG_MAX:
        return base
    digest = hashlib.sha1(name.encode()).hexdigest()[:8]
    return f"{base[: AFFILIATION_SLUG_MAX - 9].rstrip('-')}-{digest}"


def normalize_base_url(value: str) -> str:
    parsed = urlsplit(value)
    allowed_scheme = parsed.scheme == "https" or (parsed.scheme == "http" and parsed.hostname == "localhost")
    if (
        not allowed_scheme
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise BuildFailure("base URL must be credential-free HTTPS without query or fragment")
    path = parsed.path.rstrip("/") + "/"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def validate_official_url(value: str) -> None:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise BuildFailure("invalid official URL")


def public_url(base_url: str, route: str) -> str:
    return base_url + route.lstrip("/")


def read_env(path: Path) -> dict[str, str]:
    """Read KEY=VALUE lines from a .env file. A missing file is not an error — every setting it holds is optional."""
    if not path.exists():
        return {}
    settings = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, separator, value = stripped.partition("=")
        if separator:
            settings[key.strip()] = value.strip().strip("\"'")
    return settings


def correction_mailto(email: str, page_url: str, record_id: str = "") -> str:
    """Prefilled mailto: for a data correction. Empty when no address is configured, which hides the link entirely."""
    if not email:
        return ""
    subject = f"Correction: {record_id or page_url}"
    record_line = f"Record: {record_id}\n" if record_id else ""
    body = f"Page: {page_url}\n{record_line}\nWhat is wrong:\n\n\nWhere it can be checked:\n\n"
    return f"mailto:{quote(email)}?subject={quote(subject)}&body={quote(body)}"


def wikipedia_search_url(name: str) -> str:
    return f"https://en.wikipedia.org/w/index.php?search={quote_plus(name)}"


def relative_route(source_route: str, target_route: str) -> str:
    source = source_route.strip("/") or "."
    target = target_route.strip("/") or "."
    relative = posixpath.relpath(target, source)
    return "./" if relative == "." else relative + "/"


def relative_file(source_route: str, target: str) -> str:
    source = source_route.strip("/") or "."
    return posixpath.relpath(target, source)


def _text(value: object) -> str:
    return "" if value is None else str(value)


def _nonblank(value: str) -> bool:
    return bool(value.strip())


def _year_prefix(value: str, record_id: str) -> int:
    match = YEAR_PREFIX.match(value)
    if not match:
        raise BuildFailure(f"invalid year record_id={record_id}")
    return int(match.group(1))


def load_population(country_names: list[str], population_file: Path = POPULATION_FILE) -> list[int | None]:
    """Return population figures aligned positionally with country_names."""
    snapshot = json.loads(population_file.read_text(encoding="utf-8"))
    figures = snapshot["population"]
    return [figures.get(name) for name in country_names]


def explorer_payload(
    rankings: list[Ranking],
    records: list[AwardRecord],
    routes_by_laureate: dict[str, str],
    population_file: Path = POPULATION_FILE,
) -> dict[str, Any]:
    family_index = {ranking.prize_name: index for index, ranking in enumerate(rankings)}
    people: dict[str, dict[str, Any]] = {}
    countries: dict[str, int] = {}
    subjects: dict[str, int] = {}

    def country_index(name: str) -> int:
        if name not in countries:
            countries[name] = len(countries)
        return countries[name]

    def subject_index(name: str) -> int:
        if name not in subjects:
            subjects[name] = len(subjects)
        return subjects[name]

    for record in records:
        year = _year_prefix(record.year, record.award_record_id)
        if record.prize_name not in family_index:
            raise BuildFailure(f"prize missing from award_ranking record_id={record.award_record_id}")
        key = record.laureate_wikidata_qid or f"row:{record.award_record_id}"
        person = people.setdefault(
            key,
            {
                "n": record.full_name,
                "o": 1 if record.laureate_type == "Organization" else 0,
                "r": relative_route(EXPLORER_ROUTE, routes_by_laureate[record.laureate_wikidata_qid])
                if record.laureate_wikidata_qid
                else "",
                "a": [],
                "bc": None,
                "dc": None,
                "ac": set(),
                "cc": set(),
                "by": None,
            },
        )
        person["a"].append([year, family_index[record.prize_name], record.category or "", subject_index(record.high_school_subject)])
        if person["by"] is None:
            birth_match = YEAR_PREFIX.match(record.birth_date or "") or YEAR_PREFIX.match(record.birth_year or "")
            if birth_match:
                person["by"] = int(birth_match.group(1))
        if record.birth_country and person["bc"] is None:
            person["bc"] = country_index(record.birth_country)
        if record.death_country and person["dc"] is None:
            person["dc"] = country_index(record.death_country)
        for affiliation in record.affiliations:
            if _nonblank(affiliation.country):
                person["ac"].add(country_index(affiliation.country.strip()))
        for name in record.citizenship_countries.split(";"):
            if name.strip():
                person["cc"].add(country_index(name.strip()))

    ranked: list[dict[str, Any]] = []
    for person in people.values():
        person["a"].sort()
        points = round(sum(rankings[family].score / 100 for _, family, _, _ in person["a"]), 2)
        ranked.append(
            {
                "n": person["n"],
                "o": person["o"],
                "r": person["r"],
                "c": len(person["a"]),
                "p": points,
                "a": person["a"],
                "bc": person["bc"],
                "dc": person["dc"],
                "ac": sorted(person["ac"]),
                "cc": sorted(person["cc"]),
                "by": person["by"],
            }
        )
    ranked.sort(key=lambda person: (-person["p"], -person["c"], person["n"]))

    country_names = list(countries)
    return {
        "families": [{"name": ranking.prize_name, "score": ranking.score} for ranking in rankings],
        "countries": country_names,
        "subjects": list(subjects),
        "population": load_population(country_names, population_file),
        "people": ranked,
    }


def explorer_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def parse_map_points(value: str, record_id: str, field: str, multiple: bool) -> tuple[tuple[float, float], ...]:
    segments = value.split(";") if multiple else [value]
    if not multiple and ";" in value:
        raise BuildFailure(f"invalid coordinate record_id={record_id} field={field}")

    points: list[tuple[float, float]] = []
    for segment in segments:
        parts = segment.strip().split(",")
        if len(parts) != 2:
            raise BuildFailure(f"invalid coordinate record_id={record_id} field={field}")
        try:
            longitude, latitude = (float(part.strip()) for part in parts)
        except ValueError as error:
            raise BuildFailure(f"invalid coordinate record_id={record_id} field={field}") from error
        if (
            not math.isfinite(longitude)
            or not math.isfinite(latitude)
            or not -180 <= longitude <= 180
            or not -90 <= latitude <= 90
        ):
            raise BuildFailure(f"invalid coordinate record_id={record_id} field={field}")
        points.append((longitude, latitude))
    return tuple(points)


def _map_display_label(kind: str, label: tuple[str, ...]) -> str:
    if kind == "birth":
        city, country = label
        return city or country or "Unnamed birthplace"
    name, city, country = label
    return name or city or country or "Unnamed institution"


def map_payload(records: list[AwardRecord]) -> dict[str, list[dict[str, object]]]:
    labels: dict[str, dict[tuple[float, float], Counter[tuple[str, ...]]]] = {
        "birth": {},
        "affiliation": {},
    }
    subjects: dict[str, dict[tuple[float, float], Counter[str]]] = {"birth": {}, "affiliation": {}}
    decades: dict[str, dict[tuple[float, float], Counter[str]]] = {"birth": {}, "affiliation": {}}
    subject_decades: dict[str, dict[tuple[float, float], Counter[tuple[str, str]]]] = {
        "birth": {},
        "affiliation": {},
    }

    def add(kind: str, point: tuple[float, float], label: tuple[str, ...], subject: str, decade: str) -> None:
        labels[kind].setdefault(point, Counter())[label] += 1
        subjects[kind].setdefault(point, Counter())[subject] += 1
        decades[kind].setdefault(point, Counter())[decade] += 1
        subject_decades[kind].setdefault(point, Counter())[(subject, decade)] += 1

    for record in records:
        subject = record.high_school_subject
        decade = f"{_year_prefix(record.year, record.award_record_id) // 10 * 10}s"
        if _nonblank(record.birth_coordinates):
            point = parse_map_points(
                record.birth_coordinates,
                record.award_record_id,
                "birth_coordinates",
                multiple=False,
            )[0]
            add("birth", point, (record.birth_city.strip(), record.birth_country.strip()), subject, decade)

        for affiliation in record.affiliations:
            if not _nonblank(affiliation.coordinates):
                continue
            point = parse_map_points(
                affiliation.coordinates,
                record.award_record_id,
                "affiliation_coordinates",
                multiple=False,
            )[0]
            label = (affiliation.name.strip(), affiliation.city.strip(), affiliation.country.strip())
            add("affiliation", point, label, subject, decade)

    result: dict[str, list[dict[str, object]]] = {"birth": [], "affiliation": []}
    for kind, points in labels.items():
        for point, point_labels in sorted(points.items()):
            ordered_labels = sorted(point_labels.items(), key=lambda item: (-item[1], item[0]))
            primary = ordered_labels[0][0]
            marker: dict[str, object] = {
                "lng": point[0],
                "lat": point[1],
                "count": sum(point_labels.values()),
                "title": _map_display_label(kind, primary),
                "extra_labels": len(point_labels) - 1,
                "subjects": dict(sorted(subjects[kind][point].items())),
                "decades": dict(sorted(decades[kind][point].items())),
                "subject_decades": {
                    subject_name: dict(sorted(
                        (decade_name, count)
                        for (bucket_subject, decade_name), count in subject_decades[kind][point].items()
                        if bucket_subject == subject_name
                    ))
                    for subject_name in sorted(subjects[kind][point])
                },
            }
            if kind == "birth":
                marker["city"], marker["country"] = primary
            else:
                marker["name"], marker["city"], marker["country"] = primary
            result[kind].append(marker)
    return result


def map_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")


def nearby_payload(
    records: list[AwardRecord],
    routes_by_laureate: dict[str, str],
    affiliations: Iterable[Affiliation] = (),
) -> dict[str, Any]:
    """Return every recorded coordinate grouped into places and their laureates."""
    people: dict[str, str] = {}
    routed_people: set[str] = set()
    places: dict[tuple[str, tuple[float, float]], dict[str, Any]] = {}
    affiliations_by_slug = {affiliation.slug: affiliation for affiliation in affiliations}

    def add(
        kind: str,
        point: tuple[float, float],
        name: str,
        where: str,
        record: AwardRecord,
        affiliation: Affiliation | None = None,
    ) -> None:
        key = record.laureate_wikidata_qid or f"row:{record.award_record_id}"
        people[key] = min(people.get(key, record.full_name), record.full_name)
        if record.laureate_wikidata_qid:
            routed_people.add(key)
        place = places.setdefault(
            (kind, point),
            {"names": Counter(), "where": {}, "people": set(), "affiliations": {}},
        )
        place["names"][name] += 1
        place["where"].setdefault(name, Counter())[where] += 1
        place["people"].add(key)
        if affiliation is not None:
            place["affiliations"][name] = affiliation

    for record in records:
        if _nonblank(record.birth_coordinates):
            point = parse_map_points(record.birth_coordinates, record.award_record_id, "birth_coordinates", multiple=False)[0]
            city = record.birth_city.strip()
            country = record.birth_country.strip()
            add("b", point, city or country or "Unnamed birthplace", country if city else "", record)

        for affiliation in record.affiliations:
            if not _nonblank(affiliation.coordinates):
                continue
            point = parse_map_points(affiliation.coordinates, record.award_record_id, "affiliation_coordinates", multiple=False)[0]
            city = affiliation.city.strip()
            country = affiliation.country.strip()
            name = affiliation.name.strip()
            where_parts = [part for part in (city, country) if part]
            if not name:
                name = where_parts.pop(0) if where_parts else "Unnamed institution"
            matched_affiliation = affiliations_by_slug.get(affiliation_slug(name)) if affiliation.name.strip() else None
            add("a", point, name, ", ".join(where_parts), record, matched_affiliation)

    ordered_people = sorted(people, key=lambda key: (people[key], key))
    person_index = {key: index for index, key in enumerate(ordered_people)}
    result_places: list[dict[str, Any]] = []
    for (kind, point), place in sorted(places.items()):
        headline = min(place["names"].items(), key=lambda item: (-item[1], item[0]))[0]
        where = min(place["where"][headline].items(), key=lambda item: (-item[1], item[0]))[0]
        affiliation = place["affiliations"].get(headline)
        result_places.append(
            {
                "k": kind,
                "g": [point[0], point[1]],
                "n": headline,
                "w": where,
                "x": len(place["names"]) - 1,
                "p": [person_index[key] for key in sorted(place["people"], key=lambda key: (people[key], key))],
                "r": relative_route(NEARBY_ROUTE, affiliation.route) if affiliation else "",
                "c": affiliation.count if affiliation else 0,
            }
        )
    return {
        "people": [
            [people[key], relative_route(NEARBY_ROUTE, routes_by_laureate[key]) if key in routed_people else ""]
            for key in ordered_people
        ],
        "places": result_places,
    }


def _descending_records(records: Iterable[AwardRecord]) -> list[AwardRecord]:
    ordered = sorted(records, key=lambda record: record.award_record_id)
    ordered.sort(key=lambda record: record.year, reverse=True)
    ordered.sort(key=lambda record: _year_prefix(record.year, record.award_record_id), reverse=True)
    return ordered


def _category_slugs(categories: set[str]) -> dict[str, str]:
    grouped: dict[str, list[str]] = {}
    for category in categories:
        grouped.setdefault(slugify(category), []).append(category)
    result: dict[str, str] = {}
    for base, values in grouped.items():
        for number, category in enumerate(sorted(values), start=1):
            result[category] = base if number == 1 else f"{base}-{number}"
    return result


def _read_affiliation(row: sqlite3.Row, position: int) -> AwardAffiliation:
    """Read one affiliation from either store — both spell the six columns the same way."""
    return AwardAffiliation(
        position=position,
        name=_text(row["affiliation_name"]),
        sub_name=_text(row["affiliation_sub_name"]),
        city=_text(row["affiliation_city"]),
        country=_text(row["affiliation_country"]),
        coordinates=_text(row["affiliation_coordinates"]),
        wikidata_qid=_text(row["affiliation_wikidata_qid"]),
    )


def read_database(database: Path) -> tuple[list[Ranking], list[AffiliationProfile], list[AwardRecord]]:
    if not database.is_file():
        raise BuildFailure("database is missing")
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN")
        ranking_rows = connection.execute(
            """
            SELECT award_wikidata_qid, prize_name, slug, url, score, blurb, reasoning
            FROM award_ranking
            ORDER BY score DESC
            """
        ).fetchall()
        profile_rows = connection.execute(
            "SELECT affiliation_wikidata_qid, logo_url, description, application_url, kind "
            "FROM affiliations ORDER BY affiliation_wikidata_qid"
        ).fetchall()
        award_rows = connection.execute(f"SELECT {', '.join(AWARD_COLUMNS)} FROM awards").fetchall()
        # Positions 2+ live in their own table, which a database predating this feature simply does not have.
        extra_rows: list[sqlite3.Row] = []
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'award_extra_affiliations'").fetchone():
            extra_rows = connection.execute(
                """
                SELECT award_record_id, position, affiliation_name, affiliation_sub_name, affiliation_wikidata_qid,
                       affiliation_city, affiliation_country, affiliation_coordinates
                FROM award_extra_affiliations
                ORDER BY award_record_id, position
                """
            ).fetchall()
        connection.commit()

    rankings = [
        Ranking(
            qid=_text(row["award_wikidata_qid"]),
            prize_name=_text(row["prize_name"]),
            slug=_text(row["slug"]),
            url=_text(row["url"]),
            score=row["score"],
            blurb=_text(row["blurb"]),
            reasoning=_text(row["reasoning"]),
            logo={
                "nobel-prize": "static/logos/nobel-prize.png",
                "fields-medal": "static/logos/fields-medal.jpg",
                "turing-award": "static/logos/turing-award.jpg",
                "max-planck-medal": "static/logos/max-planck-medal.png",
                "abel-prize": "static/logos/abel-prize.ico",
                "lasker-award": "static/logos/lasker-award.svg",
                "canada-gairdner-international-award": "static/logos/canada-gairdner-international-award.ico",
                "wolf-prize": "static/logos/wolf-prize.png",
                "kyoto-prize": "static/logos/kyoto-prize.png",
                "crafoord-prize": "static/logos/crafoord-prize.svg",
                "shaw-prize": "static/logos/shaw-prize.ico",
                "japan-prize": "static/logos/japan-prize.png",
                "breakthrough-prize": "static/logos/breakthrough-prize.png",
                "sveriges-riksbank-prize-in-economic-sciences": "static/logos/sveriges-riksbank-prize-in-economic-sciences.png",
            }.get(_text(row["slug"]), ""),
        )
        for row in ranking_rows
    ]
    profiles = [
        AffiliationProfile(
            qid=_text(row["affiliation_wikidata_qid"]),
            logo_url=_text(row["logo_url"]),
            description=_text(row["description"]),
            application_url=_text(row["application_url"]),
            kind=_text(row["kind"]),
        )
        for row in profile_rows
    ]
    extras: dict[str, list[AwardAffiliation]] = {}
    for row in extra_rows:
        extras.setdefault(_text(row["award_record_id"]), []).append(_read_affiliation(row, row["position"]))

    records: list[AwardRecord] = []
    for row in award_rows:
        # The flat columns are position 1 and the table is positions 2+; a wholly blank flat set records no affiliation.
        first = _read_affiliation(row, 1)
        rest = extras.get(_text(row["award_record_id"]), ())
        recorded = any(_nonblank(value) for value in (first.name, first.sub_name, first.city, first.country, first.coordinates, first.wikidata_qid))
        records.append(
            AwardRecord(
                *(_text(row[column]) for column in AWARD_COLUMNS),
                affiliations=(first, *rest) if recorded else tuple(rest),
            )
        )
    return rankings, profiles, records


def _page(
    template: str,
    route: str,
    title: str,
    description: str,
    breadcrumbs: Iterable[Breadcrumb],
    **context: Any,
) -> PageJob:
    return PageJob(template, route, title, description, tuple(breadcrumbs), context)


def _clamp(text: str, limit: int = DESCRIPTION_LIMIT) -> str:
    """Collapse whitespace and cut on a word boundary, so a description reads as a sentence in a result list."""
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _winner_description(record: AwardRecord, award_label: str) -> str:
    """Name, prize, motivation, then where they were.

    The unit is dropped before anything is clamped. A long one — "Department of Economics and School of Public
    Policy" — costs 78 of 160 characters and would eat the motivation, which is the reason the prize was won and
    outranks knowing which building they sat in.
    """
    lead = f"{record.full_name} won the {award_label} in {record.year}."
    motivation = record.motivation if _nonblank(record.motivation) else ""
    affiliation = next((item for item in record.affiliations if _nonblank(item.name)), None)
    if affiliation is None:
        return _clamp(f"{lead} {motivation}")

    places = [affiliation.name]
    if _nonblank(affiliation.sub_name):
        places.insert(0, f"{affiliation.sub_name}, {affiliation.name}")
    for place in places:
        candidate = " ".join(f"{lead} {motivation} At the time: {place}.".split())
        if len(candidate) <= DESCRIPTION_LIMIT:
            return candidate
    return _clamp(candidate)


def _names(values: list[str], limit: int = 3) -> str:
    if len(values) > limit:
        return f"{', '.join(values[:limit])} and {len(values) - limit} more"
    if len(values) > 1:
        return f"{', '.join(values[:-1])} and {values[-1]}"
    return values[0] if values else ""


def _year_span(years: list[str]) -> str:
    prefixes = sorted({year[:4] for year in years if year})
    if not prefixes:
        return ""
    return prefixes[0] if prefixes[0] == prefixes[-1] else f"{prefixes[0]}-{prefixes[-1]}"


def _affiliation_schema(affiliation: AwardAffiliation) -> dict[str, Any]:
    payload: dict[str, Any] = {"@type": "Organization", "name": affiliation.name}
    # schema.org's department is an Organization, not a string. The parent stays the resolvable entity.
    if _nonblank(affiliation.sub_name):
        payload["department"] = {"@type": "Organization", "name": affiliation.sub_name}
    return payload


def _laureate_schema(record: AwardRecord, url: str) -> dict[str, Any]:
    """schema.org markup for one recipient, carrying only the fields the record actually holds."""
    payload: dict[str, Any] = {
        "@type": "Organization" if record.laureate_type == "Organization" else "Person",
        "name": record.full_name,
        "url": url,
    }
    if _nonblank(record.laureate_wikidata_qid):
        payload["sameAs"] = f"https://www.wikidata.org/wiki/{record.laureate_wikidata_qid}"
    if _nonblank(record.birth_date):
        payload["birthDate"] = record.birth_date
    if birth_place := ", ".join(value for value in (record.birth_city, record.birth_country) if _nonblank(value)):
        payload["birthPlace"] = {"@type": "Place", "name": birth_place}
    if _nonblank(record.death_date):
        payload["deathDate"] = record.death_date
    named = [affiliation for affiliation in record.affiliations if _nonblank(affiliation.name)]
    if len(named) == 1:
        payload["affiliation"] = _affiliation_schema(named[0])
    elif named:
        payload["affiliation"] = [_affiliation_schema(affiliation) for affiliation in named]
    return payload


def _structured_data(base_url: str, job: PageJob) -> str:
    graph: list[dict[str, Any]] = []
    if job.breadcrumbs:
        graph.append(
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": position,
                        "name": crumb.label,
                        **({"item": public_url(base_url, crumb.route)} if crumb.route else {}),
                    }
                    for position, crumb in enumerate(job.breadcrumbs, start=1)
                ],
            }
        )
    if schema := job.context.get("schema"):
        graph.append(schema)
    if not graph:
        return ""
    # Escaping "<" keeps a "</script>" inside any field from closing the block early; it stays valid JSON.
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False).replace("<", "\\u003c")


def _by_motivation(pairs: Iterable[tuple[AwardRecord, str]]) -> tuple[tuple[str, tuple[tuple[AwardRecord, str], ...]], ...]:
    """Collapse recipients who share one citation into a single group.

    A shared prize carries one motivation for every recipient. Printing it under each name repeats the same sentence
    two or three times per year. Groups keep the order in which their first recipient appeared.
    """
    groups: dict[str, list[tuple[AwardRecord, str]]] = {}
    for record, route in pairs:
        groups.setdefault(record.motivation, []).append((record, route))
    return tuple((motivation, tuple(members)) for motivation, members in groups.items())


def _named_affiliations(record: AwardRecord) -> tuple[AwardAffiliation, ...]:
    """The affiliation rows that name an institution the rankings should count."""
    return tuple(item for item in record.affiliations if _nonblank(item.name) and item.name not in AFFILIATION_BLOCKLIST)


def _born_countries(person: Laureate) -> Iterable[str]:
    return next(((record.birth_country.strip(),) for record, _ in person.awards if _nonblank(record.birth_country)), ())


def _awarded_countries(person: Laureate) -> Iterable[str]:
    return {affiliation.country.strip() for record, _ in person.awards for affiliation in record.affiliations if _nonblank(affiliation.country)}


def _died_countries(person: Laureate) -> Iterable[str]:
    return next(((record.death_country.strip(),) for record, _ in person.awards if _nonblank(record.death_country)), ())


MEMBERS = {
    "Born": _born_countries,
    "Awarded": _awarded_countries,
    "Died": _died_countries,
}


def plan_country_places(
    people: list[Laureate],
    route: str,
    countries_for: Callable[[Laureate], Iterable[str]],
) -> list[Place]:
    """Rank countries by distinct laureates under one country-membership rule."""
    by_country: dict[str, list[Laureate]] = {}
    for person in people:
        for country in countries_for(person):
            by_country.setdefault(country, []).append(person)

    countries: list[Place] = []
    slugs: dict[str, str] = {}
    for name, members in by_country.items():
        slug = slugify(name)
        if slug in slugs:
            raise BuildFailure(f"duplicate country slug slug={slug} name={name!r} other={slugs[slug]!r}")
        if slug in RESERVED_COUNTRY_SEGMENTS:
            raise BuildFailure(f"country slug collides with a reserved route slug={slug} name={name!r}")
        slugs[slug] = name
        countries.append(
            Place(
                name,
                slug,
                f"{route}{slug}/",
                tuple(sorted(members, key=lambda person: _surname_key(person.name))),
            )
        )
    countries.sort(key=lambda place: (-len(place.people), place.name))
    return countries


def plan_affiliations(
    records: list[AwardRecord],
    record_routes: dict[str, str],
    profiles_by_qid: dict[str, AffiliationProfile],
) -> list[Affiliation]:
    """Rank affiliations by laureate, never by award record.

    Affiliations are keyed on (institution, unit) so that a school ranks under its parent while still being shown.
    Someone recorded under both Harvard Medical School and Harvard University appears in two units and once in
    Harvard's own count, which is why a parent's count is a union and not a sum.
    """
    laureates_by_name: dict[str, set[str]] = {}
    units_by_name: dict[str, dict[str, set[str]]] = {}
    awards_by_name: dict[str, list[AwardLink]] = {}
    for record in records:
        for affiliation in _named_affiliations(record):
            awards_by_name.setdefault(affiliation.name, []).append(AwardLink(record, affiliation, record_routes[record.award_record_id]))
            if _nonblank(record.laureate_wikidata_qid):
                laureates_by_name.setdefault(affiliation.name, set()).add(record.laureate_wikidata_qid)
                if affiliation.sub_name:
                    units_by_name.setdefault(affiliation.name, {}).setdefault(affiliation.sub_name, set()).add(record.laureate_wikidata_qid)

    names_by_slug: dict[str, list[str]] = {}
    for name in set(awards_by_name) | set(laureates_by_name):
        names_by_slug.setdefault(affiliation_slug(name), []).append(name)

    affiliations: list[Affiliation] = []
    for slug, names in names_by_slug.items():
        display = max(names, key=lambda name: (len(awards_by_name.get(name, ())), name))
        laureates: set[str] = set()
        units: dict[str, set[str]] = {}
        awards: list[AwardLink] = []
        for name in names:
            laureates.update(laureates_by_name.get(name, ()))
            for unit, members in units_by_name.get(name, {}).items():
                units.setdefault(unit, set()).update(members)
            awards.extend(awards_by_name.get(name, ()))
        awards.sort(
            key=lambda link: (_year_prefix(link.record.year, link.record.award_record_id), link.record.award_record_id),
            reverse=True,
        )
        subject_counts: dict[str, int] = {}
        for link in awards:
            subject_counts[link.record.high_school_subject] = subject_counts.get(link.record.high_school_subject, 0) + 1
        subjects = tuple(
            (subject, f"{SUBJECTS_ROUTE}{slugify(subject)}/")
            for subject in sorted(subject_counts, key=lambda subject: (-subject_counts[subject], subject))
        )
        qids = {link.affiliation.wikidata_qid for link in awards if _nonblank(link.affiliation.wikidata_qid)}
        matched_profiles = [profiles_by_qid[qid] for qid in qids if qid in profiles_by_qid]
        if matched_profiles and len(qids) != 1:
            raise BuildFailure(f"conflicting affiliation metadata route={AFFILIATIONS_ROUTE}{slug}/ qids={','.join(sorted(qids))}")
        affiliations.append(
            Affiliation(
                display,
                slug,
                f"{AFFILIATIONS_ROUTE}{slug}/",
                len(laureates),
                _ranked(units),
                tuple(awards),
                subjects,
                matched_profiles[0] if matched_profiles else None,
            )
        )
    affiliations.sort(key=lambda affiliation: (-affiliation.count, affiliation.name))
    return affiliations


def plan_affiliation_countries(affiliations: list[Affiliation]) -> list[AffiliationCountry]:
    """Group institutions under the countries their awards were recorded in.

    Every count here is scoped to the country. An institution recorded in two countries contributes only the laureates
    recorded there to each page, so the rows of one page can be compared with each other and the country's own laureate
    total is the union of its rows rather than their sum.
    """
    members_by_country: dict[str, list[RankedAffiliation]] = {}
    laureates_by_country: dict[str, set[str]] = {}
    cities_by_country: dict[str, set[str]] = {}
    slugs: dict[str, str] = {}
    for affiliation in affiliations:
        laureates: dict[str, set[str]] = {}
        cities: dict[str, list[str]] = {}
        for link in affiliation.awards:
            if not _nonblank(link.affiliation.country):
                continue
            name = link.affiliation.country.strip()
            laureates.setdefault(name, set()).add(link.record.laureate_wikidata_qid)
            if _nonblank(link.affiliation.city):
                cities.setdefault(name, []).append(link.affiliation.city.strip())
        for name, qids in laureates.items():
            slug = slugify(name)
            if slugs.setdefault(slug, name) != name:
                raise BuildFailure(f"duplicate affiliation country slug slug={slug} name={name!r} other={slugs[slug]!r}")
            city = _commonest(cities.get(name, ()))
            members_by_country.setdefault(name, []).append(RankedAffiliation(affiliation, len(qids), city))
            laureates_by_country.setdefault(name, set()).update(qids)
            if city:
                cities_by_country.setdefault(name, set()).add(city)

    countries = [
        AffiliationCountry(
            name,
            slugify(name),
            f"{COUNTRY_AFFILIATIONS_ROUTE}{slugify(name)}/",
            tuple(sorted(members, key=lambda row: (-row.count, row.affiliation.name))),
            len(laureates_by_country[name]),
            len(cities_by_country.get(name, ())),
        )
        for name, members in members_by_country.items()
    ]
    countries.sort(key=lambda country: (-len(country.members), country.name))
    return countries


def plan_subject_affiliations(affiliations: list[Affiliation]) -> dict[str, tuple[RankedAffiliation, ...]]:
    """Rank institutions per subject, counting laureates within the subject rather than across the institution."""
    members: dict[str, list[RankedAffiliation]] = {}
    for affiliation in affiliations:
        laureates: dict[str, set[str]] = {}
        cities: dict[str, list[str]] = {}
        for link in affiliation.awards:
            laureates.setdefault(link.record.high_school_subject, set()).add(link.record.laureate_wikidata_qid)
            if _nonblank(link.affiliation.city) or _nonblank(link.affiliation.country):
                cities.setdefault(link.record.high_school_subject, []).append(_place_label(link.affiliation))
        for subject, qids in laureates.items():
            members.setdefault(subject, []).append(RankedAffiliation(affiliation, len(qids), _commonest(cities.get(subject, ()))))
    return {
        subject: tuple(sorted(rows, key=lambda row: (-row.count, row.affiliation.name)))
        for subject, rows in members.items()
    }


def _place_label(affiliation: AwardAffiliation) -> str:
    """City and country as a reader sees them, dropping whichever half is missing."""
    city, country = affiliation.city.strip(), affiliation.country.strip()
    return ", ".join(part for part in (city, country) if part)


def _commonest(values: Iterable[str]) -> str:
    counts = Counter(values)
    return max(counts, key=lambda value: (counts[value], value)) if counts else ""


def _ranked(units: dict[str, set[str]]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(((unit, len(members)) for unit, members in units.items()), key=lambda row: (-row[1], row[0])))


def _surname_key(name: str) -> tuple[str, str]:
    """Order people by the last word of their name, then the whole name."""
    slug = slugify(name)
    return (slug.rsplit("-", 1)[-1], slug)


def person_routes(records: list[AwardRecord]) -> dict[str, str]:
    """Map each laureate QID to its page route.

    The QID is the identity: one person holds one route no matter how many awards they won. Records without a QID get
    no person page — they cannot be merged with confidence, and a wrong merge is worse than a missing page.
    """
    names: dict[str, str] = {}
    for record in records:
        if not _nonblank(record.laureate_wikidata_qid):
            continue
        previous = names.setdefault(record.laureate_wikidata_qid, record.full_name)
        if previous != record.full_name:
            raise BuildFailure(f"laureate recorded under two names qid={record.laureate_wikidata_qid} names={previous!r} {record.full_name!r}")

    routes: dict[str, str] = {}
    owners: dict[str, str] = {}
    for qid, name in names.items():
        slug = slugify(name)
        if slug in owners:
            raise BuildFailure(f"duplicate person slug slug={slug} qid={qid} other_qid={owners[slug]}")
        owners[slug] = qid
        routes[qid] = f"{PEOPLE_ROUTE}{slug}/"
    return routes


def plan_people(
    records: list[AwardRecord],
    routes: dict[str, str],
    record_routes: dict[str, str],
    subject_order: dict[str, int],
) -> list[Laureate]:
    grouped: dict[str, list[AwardRecord]] = {}
    for record in records:
        if _nonblank(record.laureate_wikidata_qid):
            grouped.setdefault(record.laureate_wikidata_qid, []).append(record)

    people = [
        Laureate(
            qid,
            awards[0].full_name,
            routes[qid],
            tuple(
                (record, record_routes[record.award_record_id])
                for record in sorted(awards, key=lambda record: (_year_prefix(record.year, record.award_record_id), record.award_record_id))
            ),
            tuple(
                (subject, f"{SUBJECTS_ROUTE}{slugify(subject)}/")
                for subject in sorted(
                    {record.high_school_subject for record in awards if _nonblank(record.high_school_subject)},
                    key=subject_order.__getitem__,
                )
            ),
        )
        for qid, awards in grouped.items()
    ]
    people.sort(key=lambda person: _surname_key(person.name))
    return people


def plan_subjects(people: list[Laureate], subject_counts: dict[str, int], affiliations: list[Affiliation]) -> list[Subject]:
    by_subject = plan_subject_affiliations(affiliations)
    subjects: list[Subject] = []
    for name in sorted(subject_counts, key=lambda subject: (-subject_counts[subject], subject)):
        members: list[Laureate] = []
        for person in people:
            awards = tuple((record, route) for record, route in person.awards if record.high_school_subject == name)
            if awards:
                members.append(Laureate(person.qid, person.name, person.route, awards, person.subjects))
        members.sort(key=lambda person: (-len(person.awards), _surname_key(person.name)))
        route = f"{SUBJECTS_ROUTE}{slugify(name)}/"
        subjects.append(
            Subject(
                name,
                route,
                f"{route}{COUNTRY_AFFILIATIONS_SEGMENT}/",
                f"{route}recent/",
                subject_counts[name],
                tuple(members),
                by_subject.get(name, ()),
            )
        )
    return subjects


def plan_recent_subject_awards(records: Iterable[AwardRecord], record_routes: dict[str, str]) -> RecentSubjectAwards:
    subject_records = list(records)
    latest_year = max(_year_prefix(record.year, record.award_record_id) for record in subject_records)
    earliest_year = latest_year - SUBJECT_RECENT_YEARS + 1
    recent_records = [
        record
        for record in subject_records
        if earliest_year <= _year_prefix(record.year, record.award_record_id) <= latest_year
    ]
    recent_records.sort(key=lambda record: (record.prize_name, record.full_name, record.award_record_id))
    recent_records.sort(key=lambda record: (_year_prefix(record.year, record.award_record_id), record.year), reverse=True)
    by_year: dict[str, dict[str, list[tuple[AwardRecord, str]]]] = {}
    for record in recent_records:
        by_year.setdefault(record.year, {}).setdefault(record.prize_name, []).append(
            (record, record_routes[record.award_record_id])
        )
    groups = tuple(
        (year, tuple((prize_name, tuple(recipients)) for prize_name, recipients in prizes.items()))
        for year, prizes in by_year.items()
    )
    return RecentSubjectAwards(earliest_year, latest_year, len(recent_records), sum(len(prizes) for _, prizes in groups), groups)


def index_rankings(rankings: list[Ranking]) -> dict[str, Ranking]:
    ranking_by_qid: dict[str, Ranking] = {}
    slugs: set[str] = set()
    scores: set[int] = set()
    for ranking in rankings:
        if ranking.qid in ranking_by_qid:
            raise BuildFailure(f"duplicate ranking qid={ranking.qid}")
        if not SLUG.fullmatch(ranking.slug):
            raise BuildFailure(f"invalid prize slug qid={ranking.qid}")
        if ranking.slug in slugs:
            raise BuildFailure("duplicate prize slug")
        if (
            type(ranking.score) is not int
            or not 0 <= ranking.score <= 100
            or ranking.score in scores
            or not all(_nonblank(value) for value in (ranking.prize_name, ranking.blurb, ranking.reasoning))
        ):
            raise BuildFailure(f"invalid ranking qid={ranking.qid}")
        validate_official_url(ranking.url)
        ranking_by_qid[ranking.qid] = ranking
        slugs.add(ranking.slug)
        scores.add(ranking.score)
    return ranking_by_qid


def index_records(records: list[AwardRecord]) -> dict[str, list[AwardRecord]]:
    live_names: dict[str, str] = {}
    records_by_qid: dict[str, list[AwardRecord]] = {}
    seen_record_ids: set[str] = set()
    for record in records:
        if not record.award_record_id or record.award_record_id in seen_record_ids:
            raise BuildFailure("missing or duplicate award record ID")
        seen_record_ids.add(record.award_record_id)
        if not _nonblank(record.full_name):
            raise BuildFailure(f"missing winner name record_id={record.award_record_id}")
        if not _nonblank(record.high_school_subject):
            raise BuildFailure(f"missing subject record_id={record.award_record_id}")
        if record.high_school_subject not in SUBJECTS:
            raise BuildFailure(f"invalid subject record_id={record.award_record_id}")
        _year_prefix(record.year, record.award_record_id)
        previous_name = live_names.setdefault(record.award_wikidata_qid, record.prize_name)
        if previous_name != record.prize_name:
            raise BuildFailure(f"inconsistent prize name qid={record.award_wikidata_qid}")
        records_by_qid.setdefault(record.award_wikidata_qid, []).append(record)
    return records_by_qid


def index_profiles(profiles: Iterable[AffiliationProfile]) -> dict[str, AffiliationProfile]:
    profiles_by_qid: dict[str, AffiliationProfile] = {}
    for profile in profiles:
        if not WIKIDATA_QID.fullmatch(profile.qid):
            raise BuildFailure(f"invalid affiliation QID qid={profile.qid}")
        if profile.qid in profiles_by_qid:
            raise BuildFailure(f"duplicate affiliation profile qid={profile.qid}")
        profiles_by_qid[profile.qid] = profile
    return profiles_by_qid


def layout_prize(ranking: Ranking, prize_records: list[AwardRecord]) -> PrizeLayout:
    route = f"/{ranking.slug}/"
    categories = {record.category for record in prize_records if _nonblank(record.category)}
    routed_categories = len(categories) > 1 and ranking.slug not in YEAR_ROUTED_PRIZES
    category_slugs = _category_slugs(categories) if routed_categories else {}
    if routed_categories and any(not _nonblank(record.category) for record in prize_records):
        raise BuildFailure(f"blank routed category qid={ranking.qid}")

    parent_records: dict[str | None, list[AwardRecord]] = {}
    for record in prize_records:
        parent_records.setdefault(record.category if routed_categories else None, []).append(record)

    year_routes: dict[tuple[str | None, str], str] = {}
    year_records: dict[tuple[str | None, str], list[AwardRecord]] = {}
    for category, parent_group in parent_records.items():
        labels: dict[str, str] = {}
        parent_route = route
        if category is not None:
            parent_route += f"{category_slugs[category]}/"
        for record in parent_group:
            year_slug = slugify(record.year)
            previous = labels.setdefault(year_slug, record.year)
            if previous != record.year:
                raise BuildFailure(f"duplicate year slug qid={ranking.qid}")
            key = (category, record.year)
            year_routes[key] = parent_route + f"{year_slug}/"
            year_records.setdefault(key, []).append(record)

    record_routes: dict[str, str] = {}
    for key, grouped_records in year_records.items():
        winner_slugs: dict[str, str] = {}
        for record in grouped_records:
            winner_slug = slugify(record.full_name)
            if winner_slug in winner_slugs:
                raise BuildFailure(f"duplicate winner slug record_id={record.award_record_id}")
            winner_slugs[winner_slug] = record.award_record_id
            record_routes[record.award_record_id] = year_routes[key] + f"{winner_slug}/"

    return PrizeLayout(
        ranking,
        route,
        prize_records,
        routed_categories,
        category_slugs,
        year_routes,
        year_records,
        record_routes,
    )


def _year_groups(
    group: list[AwardRecord],
    record_routes: dict[str, str],
) -> tuple[tuple[str, tuple[tuple[AwardRecord, str], ...]], ...]:
    result: list[tuple[str, tuple[tuple[AwardRecord, str], ...]]] = []
    for record in group:
        if result and result[-1][0] == record.year:
            prior = result[-1][1] + ((record, record_routes[record.award_record_id]),)
            result[-1] = (record.year, prior)
        else:
            result.append((record.year, ((record, record_routes[record.award_record_id]),)))
    return tuple(result)


def plan_category_pages(layout: PrizeLayout) -> list[PageJob]:
    if not layout.routed_categories:
        return []

    jobs: list[PageJob] = []
    for category in sorted(layout.category_slugs):
        category_route = layout.route + f"{layout.category_slugs[category]}/"
        category_years = [
            (
                year,
                layout.year_routes[(category, year)],
                _year_prefix(year, grouped[0].award_record_id),
                _by_motivation(
                    (record, layout.record_routes[record.award_record_id])
                    for record in sorted(grouped, key=lambda item: item.award_record_id)
                ),
            )
            for (record_category, year), grouped in layout.year_records.items()
            if record_category == category
        ]
        category_years.sort(key=lambda item: item[0], reverse=True)
        category_years.sort(key=lambda item: item[2], reverse=True)
        title = f"{layout.ranking.prize_name} for {category}: Winners by Year"
        category_records = [record for record in layout.records if record.category == category]
        category_span = _year_span([record.year for record in category_records])
        jobs.append(
            _page(
                "category.html",
                category_route,
                title,
                _clamp(
                    f"All {len(category_records)} {layout.ranking.prize_name} laureates in {category}, {category_span}, "
                    f"with the citation for each award year."
                ),
                (
                    Breadcrumb("Home", "/"),
                    Breadcrumb(layout.ranking.prize_name, layout.route),
                    Breadcrumb(category, None),
                ),
                prize=layout.ranking,
                category=category,
                years=tuple(category_years),
            )
        )
    return jobs


def plan_prize_page(layout: PrizeLayout) -> PageJob:
    category_links = (
        tuple(
            (category, layout.route + f"{layout.category_slugs[category]}/")
            for category in sorted(layout.category_slugs)
        )
        if layout.routed_categories
        else ()
    )
    direct_years: list[tuple[str, str, int]] = []
    if not layout.routed_categories:
        direct_years = [
            (year, route, _year_prefix(year, layout.year_records[(None, year)][0].award_record_id))
            for (category, year), route in layout.year_routes.items()
            if category is None
        ]
        direct_years.sort(key=lambda item: item[0], reverse=True)
        direct_years.sort(key=lambda item: item[2], reverse=True)

    ordered_records = _descending_records(layout.records)
    recent_prefixes = {
        _year_prefix(record.year, record.award_record_id)
        for record in ordered_records
    }
    recent_prefixes = set(sorted(recent_prefixes, reverse=True)[:PRIZE_PAGE_YEARS])
    recent = [record for record in ordered_records if _year_prefix(record.year, record.award_record_id) in recent_prefixes]

    prize_title = f"{layout.ranking.prize_name}: Winners by Year"
    prize_span = _year_span([record.year for record in layout.records])
    return _page(
        "prize.html",
        layout.route,
        prize_title,
        _clamp(f"All {len(layout.records)} {layout.ranking.prize_name} laureates, {prize_span}. {layout.ranking.blurb}"),
        (Breadcrumb("Home", "/"), Breadcrumb(layout.ranking.prize_name, None)),
        prize=layout.ranking,
        routed_categories=layout.routed_categories,
        category_links=category_links,
        year_links=tuple(direct_years),
        recent_groups=_year_groups(recent, layout.record_routes),
        recent_years=PRIZE_PAGE_YEARS,
        winners_route=layout.route + f"{WINNERS_SEGMENT}/",
    )


def plan_winners_page(layout: PrizeLayout) -> PageJob:
    """List every recipient of one prize, including prizes without standing categories."""
    ascending = sorted(
        layout.records,
        key=lambda record: (_year_prefix(record.year, record.award_record_id), record.year, record.award_record_id),
    )
    prize_span = _year_span([record.year for record in layout.records])
    return _page(
        "winners.html",
        layout.route + f"{WINNERS_SEGMENT}/",
        f"{layout.ranking.prize_name}: every winner",
        _clamp(
            f"All {len(layout.records)} {layout.ranking.prize_name} recipients, {prize_span}, "
            "in one list with a link to every award."
        ),
        (
            Breadcrumb("Home", "/"),
            Breadcrumb(layout.ranking.prize_name, layout.route),
            Breadcrumb("Every winner", None),
        ),
        prize=layout.ranking,
        prize_route=layout.route,
        routed_categories=layout.routed_categories,
        winners=tuple((record, layout.record_routes[record.award_record_id]) for record in ascending),
        span=prize_span,
    )


def _year_neighbours(
    layout: PrizeLayout,
) -> dict[tuple[str | None, str], tuple[tuple[str, str] | None, tuple[str, str] | None]]:
    """Link adjacent award years within one category so a year page is never a dead end."""
    neighbours: dict[tuple[str | None, str], tuple[tuple[str, str] | None, tuple[str, str] | None]] = {}
    years_by_category: dict[str | None, list[tuple[int, str, str]]] = {}
    for (category_key, year), route in layout.year_routes.items():
        prefix = _year_prefix(year, layout.year_records[(category_key, year)][0].award_record_id)
        years_by_category.setdefault(category_key, []).append((prefix, year, route))
    for category_key, entries in years_by_category.items():
        entries.sort()
        for index, (_, year, _route) in enumerate(entries):
            earlier = entries[index - 1] if index else None
            later = entries[index + 1] if index + 1 < len(entries) else None
            neighbours[(category_key, year)] = (
                (earlier[1], earlier[2]) if earlier else None,
                (later[1], later[2]) if later else None,
            )
    return neighbours


def plan_year_pages(
    layout: PrizeLayout,
    base_url: str,
    routes_by_laureate: dict[str, str],
) -> list[PageJob]:
    neighbours = _year_neighbours(layout)
    jobs: list[PageJob] = []
    for (routed_category, year), grouped_records in layout.year_records.items():
        route = layout.year_routes[(routed_category, year)]
        # A year-routed prize can award several topics in one year, so name the category in the heading only when
        # the year has exactly one; otherwise each recipient group carries its own.
        year_categories = {record.category for record in grouped_records if _nonblank(record.category)}
        display_category = next(iter(year_categories)) if len(year_categories) == 1 else ""
        ordered_group = sorted(grouped_records, key=lambda record: record.award_record_id)
        roll_call = _names([record.full_name for record in ordered_group])
        # The award leads, then the recipients: a long recipient name must not push the year page's description
        # into looking identical to the winner page's, which leads with the name.
        if display_category:
            title = f"{layout.ranking.prize_name} for {display_category} {year}: Winners"
            description = _clamp(f"{layout.ranking.prize_name} for {display_category}, {year}: awarded to {roll_call}.")
        else:
            title = f"{layout.ranking.prize_name} {year}: Winners"
            description = _clamp(f"{layout.ranking.prize_name}, {year}: awarded to {roll_call}.")
        crumbs = [Breadcrumb("Home", "/"), Breadcrumb(layout.ranking.prize_name, layout.route)]
        if routed_category is not None:
            crumbs.append(Breadcrumb(routed_category, layout.route + f"{layout.category_slugs[routed_category]}/"))
        crumbs.append(Breadcrumb(year, None))
        jobs.append(
            _page(
                "year.html",
                route,
                title,
                description,
                crumbs,
                prize=layout.ranking,
                category=display_category,
                show_group_categories=len(year_categories) > 1,
                year=year,
                winners=_by_motivation((record, layout.record_routes[record.award_record_id]) for record in ordered_group),
                earlier_year=neighbours[(routed_category, year)][0],
                later_year=neighbours[(routed_category, year)][1],
            )
        )

        for record in ordered_group:
            # Name first: people search for the person, not the prize, and the name survives SERP truncation.
            award_label = (
                f"{layout.ranking.prize_name} for {record.category}"
                if _nonblank(record.category)
                else layout.ranking.prize_name
            )
            winner_title = f"{record.full_name} — {award_label}, {record.year}"
            winner_description = _winner_description(record, award_label)
            winner_crumbs = [
                Breadcrumb("Home", "/"),
                Breadcrumb(layout.ranking.prize_name, layout.route),
            ]
            if routed_category is not None:
                winner_crumbs.append(
                    Breadcrumb(routed_category, layout.route + f"{layout.category_slugs[routed_category]}/")
                )
            winner_crumbs.extend((Breadcrumb(record.year, route), Breadcrumb(record.full_name, None)))
            facts = tuple(
                (label, getattr(record, attribute))
                for label, attribute in FACT_FIELDS
                if _nonblank(getattr(record, attribute))
            )
            jobs.append(
                _page(
                    "winner.html",
                    layout.record_routes[record.award_record_id],
                    winner_title,
                    winner_description,
                    winner_crumbs,
                    prize=layout.ranking,
                    record=record,
                    facts=facts,
                    co_laureates=tuple(
                        (other, layout.record_routes[other.award_record_id])
                        for other in ordered_group
                        if other.award_record_id != record.award_record_id
                    ),
                    person_route=routes_by_laureate.get(record.laureate_wikidata_qid, ""),
                    affiliation_routes=tuple(
                        f"{AFFILIATIONS_ROUTE}{affiliation_slug(affiliation.name)}/"
                        if _nonblank(affiliation.name) and affiliation.name not in AFFILIATION_BLOCKLIST
                        else ""
                        for affiliation in record.affiliations
                    ),
                    schema={
                        **_laureate_schema(record, public_url(base_url, layout.record_routes[record.award_record_id])),
                        "award": f"{award_label}, {record.year}",
                    },
                    wikipedia_url=wikipedia_search_url(record.full_name),
                )
            )
    return jobs


def plan_person_pages(people: list[Laureate], base_url: str) -> list[PageJob]:
    jobs: list[PageJob] = []
    for person in people:
        prizes = list(dict.fromkeys(record.prize_name for record, _ in person.awards))
        span = _year_span([record.year for record, _ in person.awards])
        latest = person.awards[-1][0]
        birth_date = next((record.birth_date for record, _ in person.awards if _nonblank(record.birth_date)), "")
        recorded_birth_year = next((record.birth_year for record, _ in person.awards if _nonblank(record.birth_year)), "")
        birth_year = birth_date[:4] if len(birth_date) >= 4 else recorded_birth_year
        birth_country = next((record.birth_country for record, _ in person.awards if _nonblank(record.birth_country)), "")
        death_date = next((record.death_date for record, _ in person.awards if _nonblank(record.death_date)), "")
        lifespan = f"{birth_year}–{death_date[:4]}" if birth_year and len(death_date) >= 4 else ""
        jobs.append(
            _page(
                "person.html",
                person.route,
                f"{person.name}: awards and recognition",
                _clamp(
                    f"{person.name} won {len(person.awards)} recorded {'award' if len(person.awards) == 1 else 'awards'} "
                    f"({span}): {_names(prizes, limit=4)}."
                ),
                (Breadcrumb("Home", "/"), Breadcrumb("People", PEOPLE_ROUTE), Breadcrumb(person.name, None)),
                person=person,
                birth_year=birth_year,
                birth_country=birth_country,
                sex=next((record.sex[:1] for record, _ in person.awards if _nonblank(record.sex)), ""),
                lifespan=lifespan,
                schema={
                    **_laureate_schema(latest, public_url(base_url, person.route)),
                    "award": [f"{record.prize_name}, {record.year}" for record, _ in person.awards],
                },
            )
        )
    return jobs


def plan_subject_pages(
    subjects: list[Subject],
    records: list[AwardRecord],
    record_routes: dict[str, str],
) -> list[PageJob]:
    jobs = [
        _page(
            "subjects.html",
            SUBJECTS_ROUTE,
            "Awards by subject",
            "Browse awards and laureates by high school subject.",
            (Breadcrumb("Home", "/"), Breadcrumb("Subjects", None)),
            subjects=tuple(subjects),
            leader=subjects[0].award_count if subjects else 0,
        )
    ]
    for subject in subjects:
        recent = plan_recent_subject_awards(
            (record for record in records if record.high_school_subject == subject.name),
            record_routes,
        )
        jobs.append(
            _page(
                "subject.html",
                subject.route,
                f"{subject.name} awards and laureates",
                _clamp(
                    f"{subject.award_count} recorded {'award' if subject.award_count == 1 else 'awards'} in "
                    f"{subject.name}, received by {len(subject.people)} "
                    f"{'laureate' if len(subject.people) == 1 else 'laureates'}."
                ),
                (Breadcrumb("Home", "/"), Breadcrumb("Subjects", SUBJECTS_ROUTE), Breadcrumb(subject.name, None)),
                subject=subject,
            )
        )
        jobs.append(
            _page(
                "subject_affiliations.html",
                subject.affiliations_route,
                f"Where {subject.name} laureates worked",
                _clamp(
                    f"{len(subject.affiliations)} recorded "
                    f"{'institution' if len(subject.affiliations) == 1 else 'institutions'} behind "
                    f"{subject.award_count} {subject.name} {'award' if subject.award_count == 1 else 'awards'}, "
                    f"ranked by laureates."
                ),
                (
                    Breadcrumb("Home", "/"),
                    Breadcrumb("Subjects", SUBJECTS_ROUTE),
                    Breadcrumb(subject.name, subject.route),
                    Breadcrumb("Institutions", None),
                ),
                subject=subject,
                leader=subject.affiliations[0].count if subject.affiliations else 0,
            )
        )
        jobs.append(
            _page(
                "subject_recent.html",
                subject.recent_route,
                f"Recent {subject.name} prizes and recipients",
                _clamp(
                    f"{recent.recipient_count} recipients from {recent.prize_count} {subject.name} prize "
                    f"{'edition' if recent.prize_count == 1 else 'editions'}, {recent.start_year}-{recent.end_year}."
                ),
                (
                    Breadcrumb("Home", "/"),
                    Breadcrumb("Subjects", SUBJECTS_ROUTE),
                    Breadcrumb(subject.name, subject.route),
                    Breadcrumb("Recent", None),
                ),
                subject=subject,
                recent_groups=recent.groups,
                recent_recipient_count=recent.recipient_count,
                recent_prize_count=recent.prize_count,
                recent_start_year=recent.start_year,
                recent_end_year=recent.end_year,
            )
        )
    return jobs


def plan_country_pages(country_places: dict[str, list[Place]]) -> list[PageJob]:
    jobs: list[PageJob] = []
    for label, route in COUNTRY_VIEWS:
        places = country_places[label]
        covered = len({person.qid for place in places for person in place.people})
        if label == "Born":
            title = "Where laureates were born"
            description = (
                f"The birthplaces of {covered:,} laureates across {len(places)} countries, ranked. "
                "Birthplace only, not where the work was done."
            )
            blurb = "Every laureate counted once, by the country that holds their birthplace today."
            caveat = (
                "This is where laureates were <strong>born</strong>, not where they did the work. Many moved "
                "countries to study or research, so a country's place here reflects both who it produced and who it lost."
            )
            detail_title = "Laureates born in {name}"
            detail_description = (
                "{count} award-winning {laureates} born in {name}, with every prize each of them won."
            )
            detail_blurb = "{count} {laureates} on record were born here."
        elif label == "Awarded":
            title = "Where laureates were awarded"
            description = (
                f"The award-time institution countries of {covered:,} laureates across {len(places)} countries, ranked. "
                "Laureates may appear under more than one country."
            )
            blurb = f"{covered:,} laureates recorded at award-time institutions across {len(places)} countries."
            caveat = (
                "A laureate is counted once in every country where an institution was recorded for them. "
                "Because some laureates were affiliated with institutions in more than one country, the country column does not sum to the laureate total."
            )
            detail_title = "Laureates awarded in {name}"
            detail_description = (
                "{count} award-winning {laureates} recorded at institutions in {name}, with every prize each of them won."
            )
            detail_blurb = "{count} {laureates} on record were affiliated with institutions here when their awards were made."
        else:
            title = "Where laureates died"
            description = (
                f"The recorded death countries of {covered:,} laureates across {len(places)} countries, ranked. "
                "Living laureates and records without a death country are excluded."
            )
            blurb = f"{covered:,} laureates with a recorded country of death across {len(places)} countries."
            caveat = (
                "Living laureates appear nowhere in this view. A country of death may reflect retirement, travel, or exile, "
                "so it is often incidental and is the weakest of these country signals."
            )
            detail_title = "Laureates who died in {name}"
            detail_description = (
                "{count} award-winning {laureates} with a recorded country of death of {name}, with every prize each of them won."
            )
            detail_blurb = "{count} {laureates} on record died here."

        index_breadcrumbs = (
            (Breadcrumb("Home", "/"), Breadcrumb("Countries", None))
            if label == "Born"
            else (Breadcrumb("Home", "/"), Breadcrumb("Countries", COUNTRIES_ROUTE), Breadcrumb(label, None))
        )
        jobs.append(
            _page(
                "countries.html",
                route,
                title,
                _clamp(description),
                index_breadcrumbs,
                countries=tuple(places),
                leader=len(places[0].people) if places else 0,
                tab=label,
                eyebrow=f"{label} in",
                blurb=blurb,
                caveat=caveat,
                plain_counts=label == "Died",
            )
        )
        for place in places:
            count = len(place.people)
            laureates = "laureate" if count == 1 else "laureates"
            detail_breadcrumbs = (
                (Breadcrumb("Home", "/"), Breadcrumb("Countries", COUNTRIES_ROUTE), Breadcrumb(place.name, None))
                if label == "Born"
                else (
                    Breadcrumb("Home", "/"),
                    Breadcrumb("Countries", COUNTRIES_ROUTE),
                    Breadcrumb(label, route),
                    Breadcrumb(place.name, None),
                )
            )
            jobs.append(
                _page(
                    "country.html",
                    place.route,
                    detail_title.format(name=place.name),
                    _clamp(detail_description.format(count=count, laureates=laureates, name=place.name)),
                    detail_breadcrumbs,
                    place=place,
                    tab=label,
                    eyebrow=f"{label} in",
                    blurb=detail_blurb.format(count=count, laureates=laureates),
                    view_route=route,
                )
            )
    return jobs


def plan_affiliation_country_pages(
    affiliation_countries: list[AffiliationCountry],
    records: list[AwardRecord],
) -> list[PageJob]:
    recorded_affiliation_countries = sum(
        1
        for record in records
        if any(_nonblank(affiliation.country) for affiliation in record.affiliations)
    )
    jobs = [
        _page(
            "affiliation_countries.html",
            COUNTRY_AFFILIATIONS_ROUTE,
            "Countries by recorded institutions",
            _clamp(
                f"{len(affiliation_countries)} countries ranked by distinct institutions recorded for "
                f"{recorded_affiliation_countries:,} of {len(records):,} awards."
            ),
            (Breadcrumb("Home", "/"), Breadcrumb("Countries", COUNTRIES_ROUTE), Breadcrumb("Institutions", None)),
            countries=tuple(affiliation_countries),
            leader=len(affiliation_countries[0].members) if affiliation_countries else 0,
            recorded=recorded_affiliation_countries,
            total=len(records),
        )
    ]
    for place in affiliation_countries:
        jobs.append(
            _page(
                "affiliation_country.html",
                place.route,
                f"Where {place.name}'s laureates worked",
                _clamp(
                    f"{len(place.members)} recorded "
                    f"{'institution' if len(place.members) == 1 else 'institutions'} in {place.name}, "
                    f"ranked by laureates, with the city of each."
                ),
                (
                    Breadcrumb("Home", "/"),
                    Breadcrumb("Countries", COUNTRIES_ROUTE),
                    Breadcrumb("Institutions", COUNTRY_AFFILIATIONS_ROUTE),
                    Breadcrumb(place.name, None),
                ),
                place=place,
                leader=place.members[0].count if place.members else 0,
            )
        )
    return jobs


def plan_affiliation_pages(affiliations: list[Affiliation], records: list[AwardRecord]) -> list[PageJob]:
    recorded_affiliations = sum(
        1
        for record in records
        if any(_nonblank(affiliation.name) for affiliation in record.affiliations)
    )
    jobs = [
        _page(
            "affiliations.html",
            AFFILIATIONS_ROUTE,
            "Institutions with the most laureates",
            _clamp(
                f"The universities, institutes, and laboratories most often recorded against these awards, ranked by "
                f"laureate. Recorded for {recorded_affiliations:,} of {len(records):,} awards."
            ),
            (Breadcrumb("Home", "/"), Breadcrumb("Institutions", None)),
            affiliations=tuple(affiliations[:AFFILIATION_ROWS]),
            leader=affiliations[0].count if affiliations else 0,
            recorded=recorded_affiliations,
            total=len(records),
        )
    ]
    for affiliation in affiliations:
        span = _year_span([link.record.year for link in affiliation.awards])
        award_count = len(affiliation.awards)
        jobs.append(
            _page(
                "affiliation.html",
                affiliation.route,
                f"{affiliation.name}: laureate awards",
                _clamp(
                    f"{affiliation.name} records {award_count} "
                    f"{'award' if award_count == 1 else 'awards'} ({span}) across {affiliation.count} "
                    f"{'laureate' if affiliation.count == 1 else 'laureates'}."
                ),
                (
                    Breadcrumb("Home", "/"),
                    Breadcrumb("Institutions", AFFILIATIONS_ROUTE),
                    Breadcrumb(affiliation.name, None),
                ),
                affiliation=affiliation,
                wikipedia_url=wikipedia_search_url(affiliation.name),
            )
        )
    return jobs


def plan_university_pages(affiliations: list[Affiliation]) -> list[PageJob]:
    """Rank universities and colleges alone, overall and by country.

    Membership is the institution's recorded `kind`, never its name: ETH Zurich and Karolinska Institutet are
    universities, the Institute for Advanced Study and a university's own medical centre are not. An institution
    with no recorded kind is left out rather than guessed at.
    """
    universities = [
        affiliation for affiliation in affiliations if affiliation.profile and affiliation.profile.kind == UNIVERSITY_KIND
    ]
    countries = plan_affiliation_countries(universities)
    laureates = len({
        link.record.laureate_wikidata_qid
        for affiliation in universities
        for link in affiliation.awards
        if _nonblank(link.record.laureate_wikidata_qid)
    })
    return [
        _page(
            "universities.html",
            UNIVERSITIES_ROUTE,
            "Universities with the most award-winning laureates",
            _clamp(
                f"The {len(universities):,} universities and colleges recorded against these awards, ranked by the "
                f"laureates affiliated with them at the time of the award."
            ),
            (Breadcrumb("Home", "/"), Breadcrumb("Institutions", AFFILIATIONS_ROUTE), Breadcrumb("Universities", None)),
            universities=tuple(universities[:UNIVERSITY_ROWS]),
            leader=universities[0].count if universities else 0,
            total=len(universities),
            laureates=laureates,
        ),
        _page(
            "university_countries.html",
            UNIVERSITY_COUNTRIES_ROUTE,
            "Universities with the most award-winning laureates, by country",
            _clamp(
                f"{len(universities):,} universities and colleges in {len(countries)} countries, ranked within each "
                f"country by the laureates recorded there."
            ),
            (
                Breadcrumb("Home", "/"),
                Breadcrumb("Institutions", AFFILIATIONS_ROUTE),
                Breadcrumb("Universities", UNIVERSITIES_ROUTE),
                Breadcrumb("By country", None),
            ),
            countries=tuple(countries),
            rows=COUNTRY_UNIVERSITY_ROWS,
            total=len(universities),
        ),
    ]


def plan_home_page(
    rankings: list[Ranking],
    records: list[AwardRecord],
    people: list[Laureate],
    prize_routes: dict[str, str],
    ranking_by_qid: dict[str, Ranking],
    record_routes: dict[str, str],
) -> PageJob:
    """Plan the homepage last because it reports on laureates and routes from the whole site."""
    year_prefixes = [_year_prefix(record.year, record.award_record_id) for record in records]
    latest_year = max(year_prefixes)
    # At most two per prize, so the list shows the breadth of a season rather than one prize's whole cohort.
    recent: list[AwardRecord] = []
    seen_per_prize: dict[str, int] = {}
    for record in sorted(
        (record for record in records if _year_prefix(record.year, record.award_record_id) >= latest_year - 1),
        key=lambda record: (
            -_year_prefix(record.year, record.award_record_id),
            -ranking_by_qid[record.award_wikidata_qid].score,
            record.full_name,
        ),
    ):
        if seen_per_prize.get(record.award_wikidata_qid, 0) >= 2:
            continue
        seen_per_prize[record.award_wikidata_qid] = seen_per_prize.get(record.award_wikidata_qid, 0) + 1
        recent.append(record)
    decorated = sorted(
        (person for person in people if len(person.awards) > 1),
        key=lambda person: (-len(person.awards), _surname_key(person.name)),
    )
    return _page(
        "index.html",
        "/",
        "Prestigious Awards and Winners",
        _clamp(
            f"{len(people):,} laureates and {len(records):,} awards across {len(rankings)} international prizes, "
            f"{min(year_prefixes)}-{latest_year}. Ranked, cross-referenced, and browsable by person."
        ),
        (),
        prizes=tuple((ranking, prize_routes[ranking.qid]) for ranking in rankings),
        totals=(
            (f"{len(people):,}", "laureates"),
            (f"{len(records):,}", "awards"),
            (f"{len(rankings)}", "prizes"),
            (f"{min(year_prefixes)}-{latest_year}", "years"),
            (f"{len({record.birth_country for record in records if _nonblank(record.birth_country)})}", "countries"),
        ),
        recent=tuple(
            (record, record_routes[record.award_record_id], ranking_by_qid[record.award_wikidata_qid])
            for record in recent[:HOMEPAGE_ROWS]
        ),
        decorated=tuple(decorated[:HOMEPAGE_ROWS]),
    )


def plan_awards_page(rankings: list[Ranking], prize_routes: dict[str, str]) -> PageJob:
    return _page(
        "awards.html",
        AWARDS_ROUTE,
        "Awards",
        f"Browse {len(rankings)} international awards and their recipients.",
        (),
        prizes=tuple((ranking, prize_routes[ranking.qid]) for ranking in rankings),
    )


def plan_people_index(people: list[Laureate]) -> list[PageJob]:
    page_count = max(1, -(-len(people) // PEOPLE_PER_PAGE))
    jobs: list[PageJob] = []
    for number in range(1, page_count + 1):
        page_people = people[(number - 1) * PEOPLE_PER_PAGE : number * PEOPLE_PER_PAGE]
        route = PEOPLE_ROUTE if number == 1 else f"{PEOPLE_ROUTE}page-{number}/"
        crumbs = [Breadcrumb("Home", "/")]
        if number == 1:
            title = "Laureates A-Z"
        else:
            title = f"Laureates A-Z: page {number}"
            crumbs.append(Breadcrumb("People", PEOPLE_ROUTE))
        crumbs.append(Breadcrumb(title if number == 1 else f"Page {number}", None))
        jobs.append(
            _page(
                "people.html",
                route,
                title,
                f"Browse every laureate on record, listed by surname. Page {number} of {page_count}.",
                crumbs,
                people=tuple(page_people),
                page_number=number,
                page_count=page_count,
                previous_route=("" if number == 1 else PEOPLE_ROUTE if number == 2 else f"{PEOPLE_ROUTE}page-{number - 1}/"),
                next_route=("" if number == page_count else f"{PEOPLE_ROUTE}page-{number + 1}/"),
            )
        )
    return jobs


def plan_map_pages(records: list[AwardRecord]) -> list[PageJob]:
    atlas_payload = map_json(map_payload(records))
    jobs = [
        _page(
            "map.html",
            MAP_ROUTE,
            "Awards Atlas: Birthplaces and Institutions",
            "Explore where international award recipients were born and the institutions where they worked.",
            (),
            payload=atlas_payload,
            initial_subject="",
        )
    ]
    for subject_name in SUBJECTS:
        jobs.append(
            _page(
                "map.html",
                f"{MAP_ROUTE}{slugify(subject_name)}/",
                f"{subject_name} Awards Atlas: Birthplaces and Institutions",
                f"Map recorded birthplaces and affiliated institutions for international awards classified under {subject_name}.",
                (),
                payload=atlas_payload,
                initial_subject=subject_name,
            )
        )
    return jobs


def plan_explorer_page(
    rankings: list[Ranking],
    records: list[AwardRecord],
    routes_by_laureate: dict[str, str],
    generated: str,
) -> PageJob:
    return _page(
        "explorer.html",
        EXPLORER_ROUTE,
        "Awards Data Explorer",
        "Explore ranked laureates across fourteen international prize families by awards, points, country, and career.",
        (Breadcrumb("Home", "/"), Breadcrumb("Explorer", None)),
        payload=explorer_json(explorer_payload(rankings, records, routes_by_laureate)),
        generated=generated,
    )


def plan_nearby_page(
    records: list[AwardRecord],
    routes_by_laureate: dict[str, str],
    affiliations: list[Affiliation],
) -> PageJob:
    nearby = nearby_payload(records, routes_by_laureate, affiliations)
    return _page(
        "nearby.html",
        NEARBY_ROUTE,
        "Award Winners Near You",
        "Find the laureate birthplaces and institutions closest to you, ranked by distance, using your browser's location.",
        (Breadcrumb("Home", "/"), Breadcrumb("Nearby", None)),
        payload=map_json(nearby),
        places=len(nearby["places"]),
        laureates=len(nearby["people"]),
    )


def plan_about_page(
    rankings: list[Ranking],
    records: list[AwardRecord],
    people: list[Laureate],
    countries: list[Place],
    subjects: list[Subject],
    affiliations: list[Affiliation],
) -> PageJob:
    year_prefixes = [_year_prefix(record.year, record.award_record_id) for record in records]
    latest_year = max(year_prefixes)
    return _page(
        "about.html",
        ABOUT_ROUTE,
        "About This Site",
        _clamp(
            f"A free, static reference to {len(rankings)} international prizes and their {len(people):,} recipients, "
            "sorted by school subject, country, and institution."
        ),
        (Breadcrumb("Home", "/"), Breadcrumb("About", None)),
        totals=(
            (f"{len(people):,}", "laureates"),
            (f"{len(records):,}", "awards"),
            (f"{len(rankings)}", "prizes"),
            (f"{min(year_prefixes)}-{latest_year}", "years"),
            (f"{len(subjects)}", "subjects"),
            (f"{len(countries)}", "countries"),
            (f"{len(affiliations):,}", "institutions"),
        ),
    )


def create_site_plan(
    rankings: list[Ranking],
    records: list[AwardRecord],
    base_url: str,
    generated: str,
    profiles: Iterable[AffiliationProfile] = (),
) -> SitePlan:
    if not rankings or not records:
        raise BuildFailure("ranking or awards table is empty")

    ranking_by_qid = index_rankings(rankings)
    records_by_qid = index_records(records)
    profiles_by_qid = index_profiles(profiles)
    if set(ranking_by_qid) != set(records_by_qid):
        raise BuildFailure("ranking rows do not match live awards")
    for qid, prize_records in records_by_qid.items():
        if ranking_by_qid[qid].prize_name != prize_records[0].prize_name:
            raise BuildFailure(f"ranking prize mismatch qid={qid}")

    rankings = sorted(rankings, key=lambda ranking: ranking.score, reverse=True)
    routes_by_laureate = person_routes(records)
    prize_routes = {ranking.qid: f"/{ranking.slug}/" for ranking in rankings}
    record_routes: dict[str, str] = {}
    jobs: list[PageJob] = []
    for ranking in rankings:
        layout = layout_prize(ranking, records_by_qid[ranking.qid])
        record_routes.update(layout.record_routes)
        jobs.extend(plan_category_pages(layout))
        jobs.append(plan_prize_page(layout))
        jobs.append(plan_winners_page(layout))
        jobs.extend(plan_year_pages(layout, base_url, routes_by_laureate))

    subject_counts = Counter(record.high_school_subject for record in records)
    subject_order = {
        name: index for index, name in enumerate(sorted(subject_counts, key=lambda subject: (-subject_counts[subject], subject)))
    }
    people = plan_people(records, routes_by_laureate, record_routes, subject_order)
    affiliations = plan_affiliations(records, record_routes, profiles_by_qid)
    country_places = {label: plan_country_places(people, route, MEMBERS[label]) for label, route in COUNTRY_VIEWS}
    countries = country_places["Born"]
    affiliation_countries = plan_affiliation_countries(affiliations)
    subjects = plan_subjects(people, subject_counts, affiliations)

    jobs.extend(plan_person_pages(people, base_url))
    jobs.extend(plan_subject_pages(subjects, records, record_routes))
    jobs.extend(plan_country_pages(country_places))
    jobs.extend(plan_affiliation_country_pages(affiliation_countries, records))
    jobs.extend(plan_affiliation_pages(affiliations, records))
    jobs.extend(plan_university_pages(affiliations))
    jobs.append(plan_home_page(rankings, records, people, prize_routes, ranking_by_qid, record_routes))
    jobs.append(plan_awards_page(rankings, prize_routes))
    jobs.extend(plan_people_index(people))
    jobs.extend(plan_map_pages(records))
    jobs.append(plan_explorer_page(rankings, records, routes_by_laureate, generated))
    jobs.append(plan_nearby_page(records, routes_by_laureate, affiliations))
    jobs.append(plan_about_page(rankings, records, people, countries, subjects, affiliations))

    year_prefixes = [_year_prefix(record.year, record.award_record_id) for record in records]
    routes = [job.route for job in jobs]
    if len(routes) != len(set(routes)):
        raise BuildFailure("duplicate public route")
    pages = Counter(job.template for job in jobs)
    return SitePlan(
        tuple(jobs),
        len(rankings),
        pages["category.html"],
        pages["year.html"],
        pages["winner.html"],
        len(records),
        len(people),
        len(countries),
        len(subjects),
        f"{min(year_prefixes)}-{max(year_prefixes)}",
    )


def _sitemap_document(root: str, entries: list[str]) -> bytes:
    body = "\n".join(entries)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<{root} xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}\n</{root}>\n'.encode()


def write_sitemaps(
    output: Path,
    routes: Iterable[str],
    base_url: str,
    *,
    url_limit: int = SITEMAP_URL_LIMIT,
    byte_limit: int = SITEMAP_BYTE_LIMIT,
) -> int:
    locations = [public_url(base_url, route) for route in sorted(routes)]
    entries = [f"  <url><loc>{xml_escape(location)}</loc></url>" for location in locations]
    single = _sitemap_document("urlset", entries)
    if len(entries) <= url_limit and len(single) <= byte_limit:
        (output / "sitemap.xml").write_bytes(single)
        return len(locations)

    empty_document_size = len(_sitemap_document("urlset", []))
    chunks: list[list[str]] = []
    chunk: list[str] = []
    chunk_size = empty_document_size
    for entry in entries:
        entry_size = len(entry.encode()) + (1 if chunk else 0)
        if chunk and (len(chunk) == url_limit or chunk_size + entry_size > byte_limit):
            chunks.append(chunk)
            chunk = [entry]
            chunk_size = empty_document_size + len(entry.encode())
        else:
            chunk.append(entry)
            chunk_size += entry_size
        if chunk_size > byte_limit:
            raise BuildFailure("one sitemap URL exceeds the byte limit")
    if chunk:
        chunks.append(chunk)
    if len(chunks) > url_limit:
        raise BuildFailure("sitemap index exceeds the URL limit")

    index_entries: list[str] = []
    for number, sitemap_entries in enumerate(chunks, start=1):
        filename = f"sitemap-{number:04d}.xml"
        (output / filename).write_bytes(_sitemap_document("urlset", sitemap_entries))
        index_entries.append(f"  <sitemap><loc>{xml_escape(base_url + filename)}</loc></sitemap>")
    index = _sitemap_document("sitemapindex", index_entries)
    if len(index) > byte_limit:
        raise BuildFailure("sitemap index exceeds the byte limit")
    (output / "sitemap.xml").write_bytes(index)
    return len(locations)


def write_robots(output: Path, base_url: str) -> None:
    body = f"User-agent: *\nAllow: /\n\nSitemap: {public_url(base_url, '/sitemap.xml')}\n"
    (output / "robots.txt").write_text(body, encoding="utf-8")


def write_dataset_csv(output: Path, records: Iterable[AwardRecord]) -> None:
    """Dump the award records as RFC 4180 CSV, ordered by award_record_id for reproducible builds."""
    with (output / "awards.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(AWARD_COLUMNS)
        writer.writerows(
            [getattr(record, column) for column in AWARD_COLUMNS]
            for record in sorted(records, key=lambda record: record.award_record_id)
        )


def write_llms_txt(output: Path, base_url: str, plan: SitePlan, rankings: Iterable[Ranking]) -> None:
    """Write /llms.txt: what the site holds, how its URLs are shaped, and where a machine reader should start.

    The pages are already plain HTML, so this file guides rather than restates them. An agent that can build a URL from
    a name does not have to crawl, and one that reads the whole sitemap learns nothing about which page answers what.
    """
    categories: dict[str, list[PageJob]] = {}
    for job in plan.jobs:
        if job.template == "category.html":
            categories.setdefault(job.context["prize"].qid, []).append(job)

    entries: list[str] = []
    for ranking in sorted(rankings, key=lambda ranking: ranking.score, reverse=True):
        prize_route = f"/{ranking.slug}/"
        entries.append(
            f"- [Every {ranking.prize_name} winner]({public_url(base_url, prize_route + WINNERS_SEGMENT + '/')}): "
            f"score {ranking.score}/100. {ranking.blurb} Awarding body: {ranking.url}"
        )
        prize_categories = sorted(categories.get(ranking.qid, ()), key=lambda job: job.route)
        indexes = "its categories and every award year" if prize_categories else "every award year"
        entries.append(f"  - [{ranking.prize_name} by year]({public_url(base_url, prize_route)}): {indexes}")
        for job in prize_categories:
            entries.append(f"  - [{job.title}]({public_url(base_url, job.route)}): {job.description}")
    prizes = "\n".join(entries)

    subjects = "\n".join(
        f"- [{job.title}]({public_url(base_url, job.route)}): {job.description} "
        f"[Recent {job.context['subject'].name} prizes and recipients]"
        f"({public_url(base_url, job.context['subject'].recent_route)}): latest three calendar years in the data."
        for job in sorted((job for job in plan.jobs if job.template == "subject.html"), key=lambda job: job.route)
    )
    institution_count = sum(1 for job in plan.jobs if job.template == "affiliation.html")
    body = f"""# Awards

> A free, static reference to {plan.prize_count} international prize families and the {plan.person_count:,} people and organizations that have
> received them, {plan.year_span}. Every prize, award year, recipient, person, country, institution, and school subject has its own page.

Each of the {len(plan.jobs):,} pages is plain HTML that needs no JavaScript to read, and every route ends in a slash and is served from
`index.html`. {public_url(base_url, "/sitemap.xml")} lists them all. Person and recipient pages embed schema.org JSON-LD — a `Person` or
`Organization` carrying `birthDate`, `birthPlace`, `affiliation`, `award`, and a `sameAs` link to the laureate's Wikidata item — in a
`<script type="application/ld+json">` block, which is the shortest path to one page's facts.

The data is one row per recipient, compiled from each award's official record and cross-checked against Wikipedia and Wikidata. A blank
field, or a key missing from that JSON-LD, means the value could not be confirmed, never that it was estimated. Places carry their
present-day names, so a laureate born in Königsberg in 1904 is listed under Kaliningrad, Russia. The prestige score on each prize, and the
points that rank individuals by it, are editorial judgements rather than measurements.

## Where to start

- [Prizes]({public_url(base_url, "/")}): the {plan.prize_count} award families, ranked by prestige score, each opening onto its categories, years, and recipients
- [People]({public_url(base_url, PEOPLE_ROUTE)}): every recipient by surname; a person's page gathers all of their awards
- Every winner of one prize in a single list: see the {plan.prize_count} `/{{prize}}/{WINNERS_SEGMENT}/` pages named under "Winner lists" below
- [Countries]({public_url(base_url, COUNTRIES_ROUTE)}): {plan.country_count} countries of birth, with companion views by award-time institution and by death
- [Institutions]({public_url(base_url, AFFILIATIONS_ROUTE)}): the universities, laboratories, and organizations where the recognized work was done
- [Universities]({public_url(base_url, UNIVERSITIES_ROUTE)}): universities and colleges alone, ranked by laureate, and
  [by country]({public_url(base_url, UNIVERSITY_COUNTRIES_ROUTE)})
- [Subjects]({public_url(base_url, SUBJECTS_ROUTE)}): the same awards regrouped under {plan.subject_count} school subjects
- [About]({public_url(base_url, ABOUT_ROUTE)}): scope, method, and the biases this collection inherits from the prizes themselves

## URL patterns

Every slug is lowercase ASCII with hyphens for everything else: "Ngô Bao Châu" is `ngo-bao-chau`, "Earth Science" is `earth-science`.

- `/{{prize}}/{WINNERS_SEGMENT}/` — every recipient of one prize in one table: year, category, and a link to each award
- `/{{prize}}/{{category}}/{{year}}/{{name}}/` — one recipient of one award, with the citation. Prizes with a single standing category, or
  with a topic chosen afresh each year, drop the `{{category}}` segment.
- `/{{prize}}/{{category}}/{{year}}/` and `/{{prize}}/{{category}}/` — one award year, and one category across its years
- `/people/{{name}}/` — one person and every award they hold
- `/countries/{{country}}/`, `/countries/awarded/{{country}}/`, `/countries/died/{{country}}/` — laureates by birth, by institution at the
  time of the award, and by death
- `/countries/affiliations/{{country}}/` — the institutions in one country
- `/affiliations/{{institution}}/` — one institution and its laureates
- `/subjects/{{subject}}/` — one school subject
- `/subjects/{{subject}}/recent/` — that subject's prize recipients from its latest recorded year and the two preceding calendar years

The individual country and institution lists — {institution_count:,} institutions alone — are too many to name here; take them from the two
indexes above or build them from these patterns.

## Winner lists

One entry per prize, each with its complete list of recipients first, then the by-year view and any category lists beneath it. A category
list is complete for that category; the by-year page names winners only for the most recent {PRIZE_PAGE_YEARS} award years.

{prizes}

## Subject lists

The same awards regrouped under the school subject each belongs to, so one page gathers every laureate in a field across all {plan.prize_count} prizes.

{subjects}

## Bulk data

These three pages carry their data as embedded JSON rather than prose, so read the script block and skip the markup.

- [Explorer]({public_url(base_url, EXPLORER_ROUTE)}): `<script id="explorer-data" type="application/json">` holds every laureate with their awards,
  countries, and birth year under abbreviated keys — the whole collection in one request.
- [Map]({public_url(base_url, MAP_ROUTE)}): `<script id="map-data" type="application/json">` holds birthplace and institution coordinates by subject.
- [Nearby]({public_url(base_url, NEARBY_ROUTE)}): `<script id="nearby-data" type="application/json">` holds `people` and coordinate-grouped `places` for browser-side proximity.
"""
    (output / "llms.txt").write_text(body, encoding="utf-8")


def _environment(website_dir: Path) -> Environment:
    environment = Environment(
        loader=FileSystemLoader(website_dir / "templates"),
        autoescape=select_autoescape(("html", "xml")),
        undefined=StrictUndefined,
    )
    environment.filters["slugify"] = slugify
    for name in TEMPLATES:
        environment.get_template(name)
    return environment


def _render_job(environment: Environment, staging: Path, base_url: str, corrections_email: str, job: PageJob) -> str:
    target_directory = staging / job.route.strip("/")
    target_directory.mkdir(parents=True, exist_ok=True)
    template = environment.get_template(job.template)
    page_url = public_url(base_url, job.route)
    html = template.render(
        title=job.title,
        description=job.description,
        canonical=page_url,
        breadcrumbs=job.breadcrumbs,
        home_href=relative_route(job.route, "/"),
        favicon_href=relative_file(job.route, "favicon.svg"),
        style_href=relative_file(job.route, "static/style.css"),
        csv_href=relative_file(job.route, "awards.csv"),
        asset_href=lambda target: relative_file(job.route, target) if target else "",
        awards_route=AWARDS_ROUTE,
        people_route=PEOPLE_ROUTE,
        countries_route=COUNTRIES_ROUTE,
        country_affiliations_route=COUNTRY_AFFILIATIONS_ROUTE,
        country_views=COUNTRY_VIEWS,
        affiliations_route=AFFILIATIONS_ROUTE,
        universities_route=UNIVERSITIES_ROUTE,
        university_countries_route=UNIVERSITY_COUNTRIES_ROUTE,
        subjects_route=SUBJECTS_ROUTE,
        explorer_route=EXPLORER_ROUTE,
        nearby_route=NEARBY_ROUTE,
        map_route=MAP_ROUTE,
        about_route=ABOUT_ROUTE,
        structured_data=_structured_data(base_url, job),
        href=lambda target: relative_route(job.route, target),
        correction_href=lambda record_id="": correction_mailto(corrections_email, page_url, record_id),
        **job.context,
    )
    (target_directory / "index.html").write_text(html, encoding="utf-8")
    return job.route


def render_error_page(environment: Environment, output: Path, base_url: str) -> None:
    """Render /404.html.

    Every other page links relatively, which the server resolves against the file's own directory. The error page is
    served for arbitrary request URLs, so its links must be absolute from the deployment root instead.
    """
    root = urlsplit(base_url).path
    html = environment.get_template("404.html").render(
        title="Page not found",
        description="This page does not exist. Browse the ranked awards and their recipients instead.",
        canonical="",
        breadcrumbs=(),
        home_href=root,
        favicon_href=root + "favicon.svg",
        style_href=root + "static/style.css",
        csv_href=root + "awards.csv",
        awards_route=AWARDS_ROUTE,
        people_route=PEOPLE_ROUTE,
        countries_route=COUNTRIES_ROUTE,
        country_affiliations_route=COUNTRY_AFFILIATIONS_ROUTE,
        country_views=COUNTRY_VIEWS,
        affiliations_route=AFFILIATIONS_ROUTE,
        subjects_route=SUBJECTS_ROUTE,
        explorer_route=EXPLORER_ROUTE,
        nearby_route=NEARBY_ROUTE,
        map_route=MAP_ROUTE,
        about_route=ABOUT_ROUTE,
        structured_data="",
        href=lambda target: root + target.lstrip("/"),
        correction_href=lambda record_id="": "",  # The served URL is unknown at build time, so there is nothing to report against.
    )
    (output / "404.html").write_text(html, encoding="utf-8")


def _make_world_readable(root: Path) -> None:
    for path in (root, *root.rglob("*")):
        path.chmod(0o2755 if path.is_dir() else 0o644)


def _promote(staging: Path, dist: Path) -> None:
    backup: Path | None = None
    if dist.exists():
        backup = Path(tempfile.mkdtemp(prefix=".dist-backup-", dir=dist.parent))
        backup.rmdir()
        dist.rename(backup)
    try:
        staging.rename(dist)
    except OSError as promotion_error:
        if backup is not None:
            try:
                backup.rename(dist)
            except OSError as rollback_error:
                raise BuildFailure(f"promotion and rollback failed: {rollback_error}") from promotion_error
        raise
    if backup is not None:
        try:
            shutil.rmtree(backup)
        except OSError:
            print(f"website build warning operation=backup-cleanup path={backup}", file=sys.stderr)


def build_site(database: Path, base_url: str, website_dir: Path = SCRIPT_DIR) -> SitePlan:
    normalized_base_url = normalize_base_url(base_url)
    corrections_email = read_env(website_dir.parent / ".env").get("CORRECTIONS_EMAIL", "")
    print(f"website build config corrections_email={corrections_email or '(unset)'}")
    rankings, profiles, records = read_database(database)
    generated = datetime.datetime.fromtimestamp(database.stat().st_mtime, tz=datetime.UTC).date().isoformat()
    plan = create_site_plan(rankings, records, normalized_base_url, generated, profiles)
    environment = _environment(website_dir)
    staging = Path(tempfile.mkdtemp(prefix=".dist-staging-", dir=website_dir))
    staging.chmod(0o2775)
    dist = website_dir / "dist"
    try:
        shutil.copytree(website_dir / "static", staging / "static")
        shutil.copyfile(website_dir / "static" / "favicon.svg", staging / "favicon.svg")
        with ThreadPoolExecutor(max_workers=8) as executor:
            rendered = executor.map(
                lambda job: _render_job(environment, staging, normalized_base_url, corrections_email, job),
                plan.jobs,
            )
            list(rendered)
        write_sitemaps(staging, (job.route for job in plan.jobs), normalized_base_url)
        write_robots(staging, normalized_base_url)
        write_dataset_csv(staging, records)
        write_llms_txt(staging, normalized_base_url, plan, rankings)
        render_error_page(environment, staging, normalized_base_url)
        _make_world_readable(staging)
        _promote(staging, dist)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return plan


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--database", type=Path, default=DATASET_DIR / "awards.sqlite3")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        plan = build_site(args.database.resolve(), args.base_url)
    except Exception as error:  # noqa: BLE001 - every worker failure must map to exit status 1.
        print(f"website build failed: {error}", file=sys.stderr)
        return 1
    print(
        "website build complete "
        f"prizes={plan.prize_count} categories={plan.category_count} year_pages={plan.year_count} "
        f"winner_pages={plan.winner_count} people={plan.person_count} countries={plan.country_count} subjects={plan.subject_count} "
        f"recipients={plan.recipient_count} "
        f"sitemap_urls={len(plan.jobs)} generated_pages={len(plan.jobs)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
