# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "jinja2==3.1.6",
#     "pillow==11.3.0",
# ]
# ///
# SPDX-License-Identifier: GPL-2.0-or-later
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
import string
import sys
import tempfile
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Any
from urllib.parse import quote, quote_plus, urlsplit, urlunsplit
from xml.sax.saxutils import escape as xml_escape

import tomllib
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from PIL import Image, ImageDraw, ImageFont

SCRIPT_DIR = Path(__file__).resolve().parent
DATASET_DIR = SCRIPT_DIR.parent
I18N_DIR = SCRIPT_DIR / "i18n"
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
YEAR_PREFIX = re.compile(r"([0-9]{4})")
# A biographical note that is only a birth or lifespan restates the Facts panel: "(b. 1946)", "(born 1961)",
# "(1951–2023)", and the empty "(b. -)".
DATE_NOTE = re.compile(r"\(\s*(?:b\.|born)?\s*(?:-|[0-9]{4})(?:\s*[–—-]\s*[0-9]{4})?\s*\)", re.IGNORECASE)
WIKIDATA_QID = re.compile(r"Q[1-9][0-9]*")
SITEMAP_URL_LIMIT = 50_000
SITEMAP_BYTE_LIMIT = 52_428_800
TEMPLATES = (
    "base.html",
    "index.html",
    "awards.html",
    "_awards.html",
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
    "city_per_capita.html",
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
# Caps the ItemList structured-data block so a large page (a century of Nobel winners) doesn't add outsized
# JSON-LD parse weight to first load; the visible HTML list itself is never truncated.
ITEM_LIST_CAP = 200
HOMEPAGE_ROWS = 8
COUNTRIES_ROUTE = "/countries/"
CITIES_ROUTE = "/countries/cities/"
CITIES_PER_CAPITA_ROUTE = "/countries/cities-per-capita/"
COUNTRY_AFFILIATIONS_ROUTE = "/countries/affiliations/"
COUNTRY_AFFILIATIONS_SEGMENT = "affiliations"
COUNTRY_VIEWS = (
    ("Born", COUNTRIES_ROUTE),
    ("Awarded", "/countries/awarded/"),
    ("Died", "/countries/died/"),
)
RESERVED_COUNTRY_SEGMENTS = frozenset({COUNTRY_AFFILIATIONS_SEGMENT, "awarded", "cities", "cities-per-capita", "died"})
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
CITY_POPULATION_FILE = SCRIPT_DIR / "city_populations.csv"
GDP_PER_CAPITA_MIN_AWARDS = 5
HOMEPAGE_AWARD_YEAR_FROM = 2015
HOMEPAGE_AWARD_YEAR_TO = 2025
AFFILIATION_ROWS = 40
# Recorded in the affiliation column but not an institution.
AFFILIATION_BLOCKLIST = frozenset({"Freelance"})
PRIZE_PAGE_YEARS = 30
SUBJECT_RECENT_YEARS = 3
# The prize page shows recent years only. Its complete index of recipients lives one segment below.
WINNERS_SEGMENT = "winners"
DESCRIPTION_LIMIT = 160
SHARE_IMAGE_WIDTH = 1200
SHARE_IMAGE_HEIGHT = 630
SHARE_IMAGE_DIRECTORY = "static/share"
SHARE_IMAGE_FALLBACK = f"{SHARE_IMAGE_DIRECTORY}/default.png"
SHARE_IMAGE_LAUREATES = f"{SHARE_IMAGE_DIRECTORY}/laureates.png"
SHARE_IMAGE_INSTITUTIONS = f"{SHARE_IMAGE_DIRECTORY}/institutions.png"
SHARE_IMAGE_UNIVERSITIES = f"{SHARE_IMAGE_DIRECTORY}/universities.png"
SHARE_IMAGE_MAP = f"{SHARE_IMAGE_DIRECTORY}/map.png"
SHARE_IMAGE_NEARBY = f"{SHARE_IMAGE_DIRECTORY}/nearby.png"
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
LANGUAGE_CODES = ("en", "es", "fr")
LANGUAGE_NAMES = {"en": "English", "es": "Español", "fr": "Français"}
NUMBER_SEPARATORS = {"en": (",", "."), "es": (".", ","), "fr": ("\u202f", ",")}
SEGMENT_DEFAULTS = {
    "awards": "awards",
    "people": "people",
    "countries": "countries",
    "awarded": "awarded",
    "died": "died",
    "cities": "cities",
    "cities-per-capita": "cities-per-capita",
    "country_affiliations": "affiliations",
    "affiliations": "affiliations",
    "universities": "universities",
    "subjects": "subjects",
    "explorer": "explorer",
    "nearby": "nearby",
    "map": "map",
    "about": "about",
    "winners": "winners",
    "recent": "recent",
    "page": "page",
}
IDENTIFIER_FIELDS = (
    ("ORCID", "orc_id", "https://orcid.org/"),
    ("WDATA", "laureate_wikidata_qid", "https://www.wikidata.org/wiki/"),
    ("OpenAlex", "author_openalex_id", "https://openalex.org/authors/"),
    ("ROR", "affiliate_ror", "https://ror.org/"),
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
    "orc_id",
    "affiliate_ror",
    "author_openalex_id",
    "institution_openalex_id",
)


class BuildFailure(Exception):
    """The website cannot be built without violating its contract."""


@dataclass(frozen=True, slots=True)
class Language:
    """One immutable, offline catalogue and its locale-owned route vocabulary."""
    code: str
    prefix: str
    segments: Mapping[str, str]
    ui: Mapping[str, str]
    terms: Mapping[str, Mapping[str, str]]
    ranking: Mapping[str, str]
    labels: Mapping[str, str]
    group: str
    decimal: str
    reviewed: frozenset[str] = frozenset()

    def route(self, *components: str) -> str:
        parts = [self.prefix.strip("/")] if self.prefix else []
        parts.extend(component.strip("/") for component in components if component.strip("/"))
        return "/" + "/".join(parts) + "/" if parts else "/"

    def segment(self, key: str) -> str:
        try:
            return self.segments[key]
        except KeyError as error:
            raise BuildFailure(f"language={self.code} segments missing={key}") from error

    def text(self, key: str, /, count: float | None = None, **fields: object) -> str:
        selected_key = key
        if count is not None and key not in self.ui:
            selected_key = f"{key}.{self.plural_form(count)}"
        try:
            value = self.ui[selected_key]
        except KeyError as error:
            raise BuildFailure(f"language={self.code} ui missing={selected_key}") from error
        if count is not None:
            fields["count"] = format_number(count, self)
        if count is None and not fields and selected_key.endswith((".one", ".other")):
            return value
        required = set(_format_fields(value, self.code, selected_key))
        if set(fields) != required:
            raise BuildFailure(f"language={self.code} ui format={selected_key}")
        try:
            return value.format(**fields)
        except (IndexError, KeyError, TypeError, ValueError) as error:
            raise BuildFailure(f"language={self.code} ui format={selected_key}") from error

    def pattern(self, key: str) -> str:
        """Return a validated UI format pattern for inert browser JSON only."""
        try:
            return self.ui[key]
        except KeyError as error:
            raise BuildFailure(f"language={self.code} ui missing={key}") from error

    def plural_form(self, count: float) -> str:
        return "one" if (self.code == "fr" and count in (0, 1)) or (self.code != "fr" and count == 1) else "other"

    def term(self, section: str, value: str) -> str:
        try:
            return self.terms[section][value]
        except KeyError as error:
            raise BuildFailure(f"language={self.code} terms.{section} missing={value!r}") from error

    def ranking_blurb(self, qid: str) -> str:
        try:
            return self.ranking[qid]
        except KeyError as error:
            raise BuildFailure(f"language={self.code} ranking missing={qid}") from error

    def entity_label(self, qid: str, recorded: str) -> str:
        if self.code == "en" or not qid:
            return recorded
        return self.labels.get(qid, recorded) or recorded

    def city_label(self, city: str, country: str) -> str:
        return self.text("city.label", city=city, country=self.term("country", country))


@dataclass(frozen=True, slots=True)
class Fact:
    kind: str
    label: str
    value: str
    route: str


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
    orc_id: str
    affiliate_ror: str
    author_openalex_id: str
    institution_openalex_id: str
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
    openalex_id: str
    ror: str
    qid: str = ""


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
    language: Language | None = None
    key: str = ""


@dataclass(frozen=True, slots=True)
class ShareCard:
    kind: str
    name: str
    rank: int
    award_count: int
    subjects: tuple[str, ...]
    slug: str


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
    city: str = ""
    country: str = ""


@dataclass(frozen=True, slots=True)
class RankedAffiliation:
    """An institution ranked inside one country or one subject. `count` is laureates within that slice, never the
    institution's worldwide total, so the rows of a page can be compared with each other."""
    affiliation: Affiliation
    count: int
    place: str
    city: str = ""
    country: str = ""


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
    prize_year_routes: dict[str, str]


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


def _catalogue_mapping(value: object, code: str, section: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise BuildFailure(f"language={code} {section} must be a table")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str) or not item:
            raise BuildFailure(f"language={code} {section} invalid={key!r}")
        result[key] = item
    return result


def _format_fields(value: str, code: str, key: str) -> tuple[str, ...]:
    fields: list[str] = []
    try:
        parsed = string.Formatter().parse(value)
    except ValueError as error:
        raise BuildFailure(f"language={code} ui invalid-placeholder={key}") from error
    for _literal, field, _format, _conversion in parsed:
        if field is None:
            continue
        if not field or any(token in field for token in ".["):
            raise BuildFailure(f"language={code} ui invalid-placeholder={key}")
        fields.append(field)
    if len(fields) != len(set(fields)):
        raise BuildFailure(f"language={code} ui duplicate-placeholder={key}")
    return tuple(sorted(fields))


def _language_from_catalogue(code: str, catalogue: Mapping[str, object], labels: Mapping[str, str]) -> Language:
    prefix = catalogue.get("prefix")
    group = catalogue.get("group")
    decimal = catalogue.get("decimal")
    if catalogue.get("code") != code:
        raise BuildFailure(f"language={code} code is invalid")
    if not isinstance(prefix, str) or (prefix and (not prefix.startswith("/") or not prefix.endswith("/"))):
        raise BuildFailure(f"language={code} prefix is invalid")
    if not isinstance(group, str) or not isinstance(decimal, str) or (group, decimal) != NUMBER_SEPARATORS[code]:
        raise BuildFailure(f"language={code} number separators are invalid")
    segments = _catalogue_mapping(catalogue.get("segments"), code, "segments")
    if set(segments) != set(SEGMENT_DEFAULTS):
        missing = sorted(set(SEGMENT_DEFAULTS) - set(segments))
        extra = sorted(set(segments) - set(SEGMENT_DEFAULTS))
        raise BuildFailure(f"language={code} segments keys missing={missing!r} extra={extra!r}")
    for key, value in segments.items():
        if not SLUG.fullmatch(value):
            raise BuildFailure(f"language={code} segments invalid={key}")
    ui = _catalogue_mapping(catalogue.get("ui"), code, "ui")
    for key, value in ui.items():
        _format_fields(value, code, key)
    raw_terms = catalogue.get("terms")
    if not isinstance(raw_terms, dict):
        raise BuildFailure(f"language={code} terms must be a table")
    required_term_sections = {"prize", "category", "country", "subject", "laureate_type"}
    if not required_term_sections.issubset(raw_terms):
        missing = sorted(required_term_sections - set(raw_terms))
        raise BuildFailure(f"language={code} terms missing={missing!r}")
    terms = {section: _catalogue_mapping(raw_terms[section], code, f"terms.{section}") for section in required_term_sections}
    raw_ranking = catalogue.get("ranking")
    if not isinstance(raw_ranking, dict):
        raise BuildFailure(f"language={code} ranking must be a table")
    ranking: dict[str, str] = {}
    for qid, item in raw_ranking.items():
        if not WIKIDATA_QID.fullmatch(qid) or not isinstance(item, dict) or not isinstance(item.get("blurb"), str) or not item["blurb"]:
            raise BuildFailure(f"language={code} ranking invalid={qid!r}")
        ranking[qid] = item["blurb"]
    reviewed = catalogue.get("reviewed")
    if not isinstance(reviewed, list) or not all(isinstance(key, str) for key in reviewed) or len(reviewed) != len(set(reviewed)):
        raise BuildFailure(f"language={code} reviewed is invalid")
    available = {
        *(f"segments.{key}" for key in segments),
        *(f"ui.{key}" for key in ui),
        *(f"terms.{section}.{key}" for section, values in terms.items() for key in values),
        *(f"ranking.{qid}.blurb" for qid in ranking),
    }
    unknown_reviewed = sorted(set(reviewed) - available)
    if unknown_reviewed:
        raise BuildFailure(f"language={code} reviewed missing={unknown_reviewed[0]}")
    return Language(
        code,
        prefix,
        MappingProxyType(segments),
        MappingProxyType(ui),
        MappingProxyType({section: MappingProxyType(values) for section, values in terms.items()}),
        MappingProxyType(ranking),
        MappingProxyType(dict(labels)),
        group,
        decimal,
        frozenset(reviewed),
    )


def _live_catalogue_values(
    rankings: Iterable[Ranking], records: Iterable[AwardRecord]
) -> dict[str, set[str]]:
    rankings = list(rankings)
    records = list(records)
    countries = {
        value.strip()
        for record in records
        for value in (
            record.birth_country,
            record.death_country,
            *(record.citizenship_countries.split(";")),
            *(affiliation.country for affiliation in record.affiliations),
        )
        if value.strip()
    }
    return {
        "prize": {ranking.prize_name for ranking in rankings} | {record.prize_name for record in records},
        "category": {record.category for record in records if _nonblank(record.category)},
        "country": countries,
        "subject": set(SUBJECTS) | {record.high_school_subject for record in records if _nonblank(record.high_school_subject)},
        "laureate_type": {"Individual", "Organization"},
    }


def _required_ui_keys(template_dir: Path) -> set[str]:
    keys = {
        match.group(1)
        for template in TEMPLATES
        for match in re.finditer(r"\b(?:t|browser_t)\(\s*[\"']([^\"']+)[\"']", (template_dir / template).read_text(encoding="utf-8"))
        if not match.group(1).endswith(".")
    }
    keys.update(f"home.total.{key}" for key in ("laureates", "awards", "prizes", "years", "countries", "subjects", "institutions"))
    keys.update(f"fact.{attribute}" for _label, attribute in FACT_FIELDS)
    keys.update(
        {
            "city.label", "home.hero_heading", "awards.heading", "common.all_cities", "meta.award-with-category",
            "meta.error.title", "meta.error.description",
        }
    )
    keys.update(f"view.{view}" for view in ("born", "awarded", "died"))
    keys.update(
        f"crumb.{crumb}"
        for crumb in (
            "home", "awards", "people", "countries", "cities", "institutions", "universities", "by-country", "subjects", "recent",
            "every-winner", "page",
        )
    )
    for view in ("born", "awarded", "died", "cities"):
        keys.update((f"countries.{view}.eyebrow", f"countries.{view}.blurb", f"countries.{view}.caveat", f"country.{view}.eyebrow", f"country.{view}.blurb"))
    metadata = (
        "home", "awards", "people", "prize", "prize-winners", "category", "prize-year", "category-year", "winner", "person",
        "subjects", "subject", "subject-affiliations", "subject-recent", "countries-born", "countries-awarded", "countries-died",
        "cities", "country-born", "country-awarded", "country-died", "city", "cities-per-capita", "affiliation-countries",
        "affiliation-country", "affiliations", "affiliation", "universities", "universities-countries", "map", "map-subject",
        "explorer", "nearby", "about",
    )
    keys.update(f"meta.{name}.{field}" for name in metadata for field in ("title", "description"))
    keys.update(
        {
            "share.laureate-description", "share.institution-description", "share.card.prize-kind", "share.card.rank-label",
            "share.card.award-count-label", "share.card.subjects-label",
        }
    )
    for generic in ("default", "laureates", "institutions", "universities", "map", "nearby"):
        keys.update((f"share.generic.{generic}.title", f"share.generic.{generic}.subtitle"))
    keys.update(
        {
            "llms.title", "llms.intro", "llms.pages", "llms.provenance", "llms.start_heading", "llms.start_prizes",
            "llms.start_people", "llms.start_countries", "llms.start_cities", "llms.start_affiliations", "llms.start_universities",
            "llms.start_subjects", "llms.start_about", "llms.patterns_heading", "llms.patterns", "llms.winner_heading",
            "llms.winner_intro", "llms.subject_heading", "llms.subject_intro", "llms.bulk_heading", "llms.bulk_intro",
            "llms.bulk_explorer", "llms.bulk_map", "llms.bulk_nearby", "llms.prize-winner", "llms.prize-year",
            "llms.prize_year.categories", "llms.prize_year.years", "llms.category", "llms.subject",
        }
    )
    return keys


def _validate_languages(  # noqa: C901 - catalogue preflight is intentionally one explicit validation path.
    languages: tuple[Language, ...], rankings: Iterable[Ranking], records: Iterable[AwardRecord], template_dir: Path
) -> None:
    by_code = {language.code: language for language in languages}
    if tuple(by_code) != LANGUAGE_CODES:
        raise BuildFailure("language codes must be en, es, fr")
    if len({language.prefix for language in languages}) != len(languages):
        raise BuildFailure("language prefixes must be unique")
    english = by_code["en"]
    if english.prefix or dict(english.segments) != SEGMENT_DEFAULTS:
        raise BuildFailure("language=en route segments differ from public English routes")
    values = _live_catalogue_values(rankings, records)
    ranking_qids = {ranking.qid for ranking in rankings}
    english_ui = english.ui
    required_ui = _required_ui_keys(template_dir)
    plural_bases = {key for key in required_ui if f"{key}.one" in english_ui and f"{key}.other" in english_ui}
    required_ui.difference_update(plural_bases)
    required_ui.update(f"{key}.{form}" for key in plural_bases for form in ("one", "other"))
    for language in languages:
        if language.code != "en" and language.prefix != f"/{language.code}/":
            raise BuildFailure(f"language={language.code} prefix is invalid")
        for section, required in values.items():
            missing = sorted(required - set(language.terms[section]))
            if missing:
                raise BuildFailure(f"language={language.code} terms.{section} missing={missing[0]!r}")
        missing_rankings = sorted(ranking_qids - set(language.ranking))
        if missing_rankings:
            raise BuildFailure(f"language={language.code} ranking missing={missing_rankings[0]}")
        if set(language.ui) != set(english_ui):
            missing = sorted(set(english_ui) - set(language.ui))
            extra = sorted(set(language.ui) - set(english_ui))
            raise BuildFailure(f"language={language.code} ui keys missing={missing[:1]!r} extra={extra[:1]!r}")
        missing_ui = sorted(required_ui - set(language.ui))
        if missing_ui:
            raise BuildFailure(f"language={language.code} ui missing={missing_ui[0]}")
        for key, value in language.ui.items():
            if _format_fields(value, language.code, key) != _format_fields(english_ui[key], "en", key):
                raise BuildFailure(f"language={language.code} ui placeholders={key}")
        route_values = (
            *language.segments.values(),
            *(slugify(language.term("category", value)) for value in values["category"]),
            *(slugify(language.term("country", value)) for value in values["country"]),
            *(slugify(language.term("subject", value)) for value in values["subject"]),
        )
        if any(not value for value in route_values):
            raise BuildFailure(f"language={language.code} route value is blank")
        reserved = {
            language.segment("country_affiliations"),
            language.segment("awarded"),
            language.segment("cities"),
            language.segment("cities-per-capita"),
            language.segment("died"),
        }
        for country in values["country"]:
            if slugify(language.term("country", country)) in reserved:
                raise BuildFailure(f"language={language.code} country route collides={country!r}")
        if language.code == "en":
            for section in ("category", "country", "subject"):
                for value in values[section]:
                    if slugify(language.term(section, value)) != slugify(value):
                        raise BuildFailure(f"language=en terms.{section} route changed={value!r}")


def load_languages(
    rankings: Iterable[Ranking], records: Iterable[AwardRecord], i18n_dir: Path = I18N_DIR
) -> tuple[Language, ...]:
    """Load all committed catalogues before planning or creating any output directory."""
    labels_path = i18n_dir / "labels.toml"
    try:
        labels_document = tomllib.loads(labels_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, tomllib.TOMLDecodeError) as error:
        raise BuildFailure("labels catalogue is missing or invalid") from error
    raw_labels = labels_document.get("labels")
    if not isinstance(raw_labels, dict):
        raise BuildFailure("labels catalogue is invalid")
    labels_by_code = {code: {} for code in LANGUAGE_CODES}
    for qid, labels in raw_labels.items():
        if not WIKIDATA_QID.fullmatch(qid) or not isinstance(labels, dict):
            raise BuildFailure(f"labels invalid={qid!r}")
        for code in ("es", "fr"):
            value = labels.get(code, "")
            if not isinstance(value, str):
                raise BuildFailure(f"labels invalid={qid!r}")
            if value:
                labels_by_code[code][qid] = value
    languages: list[Language] = []
    for code in LANGUAGE_CODES:
        source = i18n_dir / f"{code}.toml"
        try:
            document = tomllib.loads(source.read_text(encoding="utf-8"))
        except (FileNotFoundError, tomllib.TOMLDecodeError) as error:
            raise BuildFailure(f"language={code} catalogue is missing or invalid") from error
        languages.append(_language_from_catalogue(code, document, labels_by_code[code]))
    result = tuple(languages)
    _validate_languages(result, rankings, records, i18n_dir.parent / "templates")
    return result


def format_number(value: float, language: Language | str, digits: int | None = None) -> str:
    """Deterministic locale formatting without process-global locale state."""
    if isinstance(language, str):
        try:
            group, decimal = NUMBER_SEPARATORS[language]
        except KeyError as error:
            raise BuildFailure(f"language={language} number is invalid") from error
    else:
        group, decimal = language.group, language.decimal
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise BuildFailure(f"language={language.code if isinstance(language, Language) else language} number is invalid")
    if digits is not None and (not isinstance(digits, int) or digits < 0):
        raise BuildFailure(f"language={language.code if isinstance(language, Language) else language} number digits are invalid")
    if digits is None and isinstance(value, float):
        if value.is_integer():
            rendered = f"{int(value):,}"
        else:
            rounded = Decimal(str(value)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            rendered = f"{rounded:,f}".rstrip("0").rstrip(".")
    else:
        rendered = f"{value:,.{digits}f}" if digits is not None else f"{value:,}"
    whole, separator, fraction = rendered.partition(".")
    localized = whole.replace(",", group)
    return localized if not separator else localized + decimal + fraction


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


def load_city_populations(population_file: Path = CITY_POPULATION_FILE) -> dict[tuple[str, str], tuple[int, int]]:
    """Load reviewed GeoNames city populations as {(city, country): (population, geoname_id)}."""
    populations: dict[tuple[str, str], tuple[int, int]] = {}
    with population_file.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            city, country = row["city"].strip(), row["country"].strip()
            try:
                population, geoname_id = int(row["population"]), int(row["geoname_id"])
            except (KeyError, TypeError, ValueError) as error:
                raise BuildFailure(f"invalid city population city={city!r} country={country!r}") from error
            if not city or not country or population <= 0 or geoname_id <= 0 or (city, country) in populations:
                raise BuildFailure(f"invalid city population city={city!r} country={country!r}")
            populations[city, country] = population, geoname_id
    return populations


def load_gdp_per_capita(population_file: Path = POPULATION_FILE) -> dict[str, dict[str, float]]:
    """Load the two fixed 2024 World Bank GDP-per-capita snapshots."""
    snapshot = json.loads(population_file.read_text(encoding="utf-8"))
    return {
        metric: {name: float(value) for name, value in snapshot["gdp_per_capita"][metric].items()}
        for metric in ("nominal", "ppp")
    }


def plan_awards_gdp_comparison(
    country_names: list[str],
    award_counts: dict[str, int],
    populations: list[int | None],
    gdp_per_capita: dict[str, float],
) -> list[dict[str, int | float]]:
    """Compare award records and GDP per capita on the same per-person basis."""
    rows = [
        {
            "country_idx": index,
            "award_count": count,
            "population": population,
            "awards_per_million": count / population * 1_000_000,
            "gdp_per_capita": gdp,
        }
        for index, name in enumerate(country_names)
        if (count := award_counts.get(name, 0)) >= GDP_PER_CAPITA_MIN_AWARDS
        and (population := populations[index]) is not None
        and population > 0
        and (gdp := gdp_per_capita.get(name)) is not None
        and gdp > 0
    ]
    rows.sort(key=lambda row: (-float(row["awards_per_million"]), country_names[int(row["country_idx"])]))
    return rows


def award_affiliation_country_counts(
    records: Iterable[AwardRecord],
    year_from: int | None = None,
    year_to: int | None = None,
) -> dict[str, int]:
    """Count each award record once per distinct affiliation country in the requested years."""
    counts: dict[str, int] = {}
    for record in records:
        year = _year_prefix(record.year, record.award_record_id)
        if (year_from is not None and year < year_from) or (year_to is not None and year > year_to):
            continue
        for country in {affiliation.country.strip() for affiliation in record.affiliations if _nonblank(affiliation.country)}:
            counts[country] = counts.get(country, 0) + 1
    return counts


def plan_city_awards_per_capita(
    records: Iterable[AwardRecord], population_file: Path = CITY_POPULATION_FILE
) -> list[dict[str, int | float | str]]:
    """Rank award-recipient records by award-time city population."""
    counts: dict[tuple[str, str], int] = {}
    for record in records:
        places = {(affiliation.city.strip(), affiliation.country.strip()) for affiliation in record.affiliations}
        for city, country in places:
            if city and country:
                counts[city, country] = counts.get((city, country), 0) + 1

    populations = load_city_populations(population_file)
    rows = [
        {
            "city": city,
            "country": country,
            "population": population,
            "geoname_id": geoname_id,
            "award_count": count,
            "awards_per_million": count / population * 1_000_000,
        }
        for (city, country), count in counts.items()
        if (population_entry := populations.get((city, country))) is not None
        for population, geoname_id in (population_entry,)
    ]
    rows.sort(key=lambda row: (-float(row["awards_per_million"]), str(row["city"]), str(row["country"])))
    return rows


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
    populations = load_population(country_names, population_file)
    return {
        "families": [{"name": ranking.prize_name, "score": ranking.score} for ranking in rankings],
        "countries": country_names,
        "subjects": list(subjects),
        "population": populations,
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
    name, city, country, _qid = label
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
            label = (
                affiliation.name.strip(),
                affiliation.city.strip(),
                affiliation.country.strip(),
                affiliation.wikidata_qid.strip(),
            )
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
                marker["name"], marker["city"], marker["country"], marker["qid"] = primary
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
                "q": affiliation.qid if affiliation else "",
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


def _resolve_relative_route(source_route: str, value: str) -> str:
    if not value:
        return ""
    joined = posixpath.normpath(posixpath.join(source_route.strip("/") or ".", value.strip()))
    return "/" if joined == "." else f"/{joined.strip('/')}/"


def _localized_location_label(language: Language, city: str, country: str) -> str:
    if city and country:
        return language.city_label(city, country)
    if city:
        return city
    return language.term("country", country) if country else ""


def localized_explorer_payload(
    payload: dict[str, Any], language: Language, route_map: Mapping[str, str]
) -> dict[str, Any]:
    """Add localized labels while retaining all source keys used for joins and ranking."""
    localized = json.loads(json.dumps(payload))
    country_keys = list(localized["countries"])
    subject_keys = list(localized["subjects"])
    family_keys = [family["name"] for family in localized["families"]]
    localized["country_keys"] = country_keys
    localized["subject_keys"] = subject_keys
    localized["family_keys"] = family_keys
    localized["category_labels"] = {
        category: language.term("category", category)
        for person in localized["people"]
        for _year, _family, category, _subject in person["a"]
        if category
    }
    localized["countries"] = [language.term("country", country) for country in country_keys]
    localized["subjects"] = [language.term("subject", subject) for subject in subject_keys]
    for family, name in zip(localized["families"], family_keys, strict=True):
        family["key"] = name
        family["name"] = language.term("prize", name)
    localized_explorer_route = language.route(language.segment("explorer"))
    for person in localized["people"]:
        person["r"] = relative_route(
            localized_explorer_route,
            route_map.get(_resolve_relative_route(EXPLORER_ROUTE, person["r"]), _resolve_relative_route(EXPLORER_ROUTE, person["r"])),
        ) if person["r"] else ""
    for row in localized.get("city_awards_per_capita", ()):
        row["city_label"] = _localized_location_label(language, row["city"], row["country"])
    return localized


def localized_map_payload(payload: dict[str, Any], language: Language) -> dict[str, Any]:
    localized = json.loads(json.dumps(payload))
    countries = {
        marker["country"]
        for markers in localized.values()
        if isinstance(markers, list)
        for marker in markers
        if marker.get("country")
    }
    localized["labels"] = {
        "subjects": {subject: language.term("subject", subject) for subject in SUBJECTS},
        "countries": {country: language.term("country", country) for country in countries},
    }
    for marker in (*localized.get("birth", ()), *localized.get("affiliation", ())):
        city = str(marker.get("city", ""))
        country = str(marker.get("country", ""))
        marker["title_key"] = marker["title"]
        marker["display_city"] = _localized_location_label(language, city, country)
        if marker.get("name"):
            marker["display_title"] = language.entity_label(str(marker.get("qid", "")), str(marker["name"]))
        else:
            marker["display_title"] = city or (language.term("country", country) if country else marker["title"])
        marker["title"] = marker["display_title"]
    return localized


def _localized_where(language: Language, value: str) -> str:
    for country in sorted(language.terms["country"], key=len, reverse=True):
        if value == country:
            return language.term("country", country)
        suffix = f", {country}"
        if value.endswith(suffix):
            return language.city_label(value[: -len(suffix)], country)
    return value


def localized_nearby_payload(
    payload: dict[str, Any], language: Language, route_map: Mapping[str, str]
) -> dict[str, Any]:
    localized = json.loads(json.dumps(payload))
    localized_route = language.route(language.segment("nearby"))
    for person in localized["people"]:
        if person[1]:
            target = _resolve_relative_route(NEARBY_ROUTE, person[1])
            person[1] = relative_route(localized_route, route_map.get(target, target))
    for place in localized["places"]:
        place["name_key"] = place["n"]
        if place["k"] == "a":
            place["n"] = language.entity_label(str(place.get("q", "")), str(place["n"]))
        elif not place["w"] and place["n"] in language.terms["country"]:
            place["n"] = language.term("country", place["n"])
        place["display_where"] = _localized_where(language, place["w"])
        if place["r"]:
            target = _resolve_relative_route(NEARBY_ROUTE, place["r"])
            place["r"] = relative_route(localized_route, route_map.get(target, target))
    return localized


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
                "fields-medal": "static/logos/fields-medal.png",
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
                "kavli-prize": "static/logos/kavli-prize.svg",
                "millennium-technology-prize": "static/logos/millennium-technology-prize.svg",
                "the-brain-prize": "static/logos/the-brain-prize.svg",
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


def share_image_target(job: PageJob) -> str:
    key = job.key
    if key.startswith(("person:", "people:")):
        target = SHARE_IMAGE_LAUREATES
    elif key == "affiliations" or key.startswith("affiliation:"):
        target = SHARE_IMAGE_INSTITUTIONS
    elif key == "universities" or key == "universities:countries":
        target = SHARE_IMAGE_UNIVERSITIES
    elif key == "map":
        target = SHARE_IMAGE_MAP
    elif key == "nearby":
        target = SHARE_IMAGE_NEARBY
    else:
        card = job.context.get("share_card")
        if card is None:
            target = SHARE_IMAGE_FALLBACK
        else:
            if not isinstance(card, ShareCard):
                raise BuildFailure(f"invalid share card route={job.route}")
            if card.kind != "Prize" or not SLUG.fullmatch(card.slug):
                raise BuildFailure(f"invalid share card route={job.route}")
            target = f"{SHARE_IMAGE_DIRECTORY}/prize-{card.slug}.png"
    return _share_path_for_language(target, job.language)


def _share_path_for_language(target: str, language: Language | None) -> str:
    if language is not None and language.code != "en":
        filename = target.rsplit("/", 1)[-1]
        return f"{SHARE_IMAGE_DIRECTORY}/{language.code}/{filename}"
    return target


def _award_phrase(record: AwardRecord, language: Language | None = None) -> str:
    """'{Prize} in {Category} {Year}', or just '{Prize} {Year}' when the prize has no standing categories."""
    if language is not None:
        prize = language.term("prize", record.prize_name)
        if record.category:
            prize = language.text(
                "share.award-with-category",
                prize=prize,
                category=language.term("category", record.category),
            )
    else:
        prize = f"{record.prize_name} in {record.category}" if _nonblank(record.category) else record.prize_name
    return f"{prize} {record.year}"


def share_description(job: PageJob) -> str:
    card = job.context.get("share_card")
    if card is None:
        return job.description
    if not isinstance(card, ShareCard) or card.rank < 1 or card.award_count < 1 or not card.subjects:
        raise BuildFailure(f"invalid share card route={job.route}")
    if card.kind == "Laureate":
        person: Laureate = job.context["person"]
        if job.language is None:
            return f"{_names([_award_phrase(record) for record, _ in person.awards])} — {person.name}"
        return job.language.text(
            "share.laureate-description",
            awards=", ".join(_award_phrase(record, job.language) for record, _ in person.awards),
            name=person.name,
        )
    if card.kind == "Institution":
        affiliation: Affiliation = job.context["affiliation"]
        prizes = list(dict.fromkeys(link.record.prize_name for link in affiliation.awards))
        if job.language is None:
            return f"{_names(prizes)} laureates recorded at {affiliation.name}."
        return job.language.text(
            "share.institution-description",
            prizes=", ".join(job.language.term("prize", prize) for prize in prizes),
            institution=_localized_affiliation_name(job.language, affiliation),
        )
    return job.description


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


def _facts(record: AwardRecord, birth_countries: frozenset[str]) -> tuple[Fact, ...]:
    """Facts panel rows with a stable field identity, minus anything the page already states.

    Type earns a row only for an organisation: 3047 of 3096 records are individuals, so on nearly every page the
    row reads "Individual" and tells the reader what the name above it already said. Birth year is dropped
    whenever a full birth date is present, for the same reason.

    Only a birth country with a generated born-in page links out. Death country has no page for Singapore or Jamaica,
    and citizenship is a list with no view of its own.
    """
    skip = set()
    if record.laureate_type != "Organization":
        skip.add("laureate_type")
    if _nonblank(record.birth_date):
        skip.add("birth_year")
    routes = (
        {"birth_country": f"{COUNTRIES_ROUTE}{slugify(record.birth_country)}/"}
        if record.birth_country in birth_countries
        else {}
    )
    return tuple(
        Fact(attribute, label, getattr(record, attribute), routes.get(attribute, ""))
        for label, attribute in FACT_FIELDS
        if attribute not in skip and _nonblank(getattr(record, attribute))
    )


def _identifiers(record: AwardRecord) -> tuple[tuple[str, str, str], ...]:
    """Facts panel rows as (label, value, url) for the registry ids this award carries.

    The id itself is the link text. Until now it lived only inside an href, so nothing that reads page text —
    a search engine, a retrieval agent — could match the literal "Q80917" against the laureate it names.

    ROR identifies the institution, not the person, and belongs to the affiliation recorded at the time of the award.
    """
    return tuple(
        (label, getattr(record, attribute), prefix + getattr(record, attribute))
        for label, attribute, prefix in IDENTIFIER_FIELDS
        if _nonblank(getattr(record, attribute))
    )


def _note(text: str) -> str:
    """Biographical note with the date-only parentheticals removed, since Facts lists Born and Died already.

    Every one of the 118 "(b. 1946)" notes and all 221 "(1951–2023)" notes restate a field that is already in the
    panel. Notes carrying anything else — "(posthumously awarded)" — keep that remainder.
    """
    return DATE_NOTE.sub("", text).strip(" ;").strip()


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


def _localized_schema_affiliation(language: Language, schema: dict[str, Any], affiliation: AwardAffiliation) -> dict[str, Any]:
    localized = dict(schema)
    localized["name"] = language.entity_label(affiliation.wikidata_qid, affiliation.name)
    return localized


def _localized_schema(job: PageJob, schema: dict[str, Any]) -> dict[str, Any]:
    """Translate schema display fields while retaining names, dates, identifiers, and source prose."""
    language = job.language
    if language is None:
        return schema
    localized = dict(schema)
    record = job.context.get("record")
    if isinstance(record, AwardRecord):
        awards = (record,)
    else:
        person = job.context.get("person")
        awards = tuple(candidate for candidate, _route in person.awards) if isinstance(person, Laureate) else ()
        record = awards[-1] if awards else None
    if awards and "award" in localized:
        labels = [f"{_localized_award_label(language, candidate)}, {candidate.year}" for candidate in awards]
        localized["award"] = labels if isinstance(localized["award"], list) else labels[0]
    if not isinstance(record, AwardRecord):
        return localized
    if _nonblank(record.birth_city) and _nonblank(record.birth_country):
        localized["birthPlace"] = {"@type": "Place", "name": language.city_label(record.birth_city, record.birth_country)}
    elif _nonblank(record.birth_country):
        localized["birthPlace"] = {"@type": "Place", "name": language.term("country", record.birth_country)}
    named = [affiliation for affiliation in record.affiliations if _nonblank(affiliation.name)]
    affiliation_schema = localized.get("affiliation")
    if len(named) == 1 and isinstance(affiliation_schema, dict):
        localized["affiliation"] = _localized_schema_affiliation(language, affiliation_schema, named[0])
    elif named and isinstance(affiliation_schema, list):
        localized["affiliation"] = [
            _localized_schema_affiliation(language, item, affiliation)
            for item, affiliation in zip(affiliation_schema, named, strict=True)
            if isinstance(item, dict)
        ]
    return localized


def _localized_item_list(job: PageJob) -> tuple[tuple[str, str], ...]:
    item_list = job.context.get("item_list")
    if not isinstance(item_list, tuple) or job.language is None:
        return item_list or ()
    language = job.language
    labels: dict[str, str] = {}
    if job.template == "awards.html":
        labels = {route: language.term("prize", ranking.prize_name) for ranking, route in job.context["prizes"]}
    elif job.template == "subjects.html":
        labels = {subject.route: language.term("subject", subject.name) for subject in job.context["subjects"]}
    elif job.template == "countries.html":
        labels = {
            place.route: _localized_place_label(language, place) if job.key == "cities" else language.term("country", place.name)
            for place in job.context["countries"]
        }
    elif job.template == "affiliations.html":
        labels = {affiliation.route: _localized_affiliation_name(language, affiliation) for affiliation in job.context["affiliations"]}
    return tuple((labels.get(route, name), route) for name, route in item_list)


def _structured_data(base_url: str, job: PageJob, route_map: Mapping[str, str] | None = None) -> str:
    route_map = route_map or {}
    localized_route = lambda route: route_map.get(route, route)
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
                        # The last crumb names the page the reader is on. Where it links onward — a winner page
                        # sends the name to the laureate — that link is for the reader, not a step in the trail.
                        **({"item": public_url(base_url, localized_route(crumb.route))} if crumb.route and position < len(job.breadcrumbs) else {}),
                    }
                    for position, crumb in enumerate(job.breadcrumbs, start=1)
                ],
            }
        )
    if schema := job.context.get("schema"):
        if not isinstance(schema, dict):
            raise BuildFailure(f"invalid schema route={job.route}")
        localized_schema = {**_localized_schema(job, schema), "url": public_url(base_url, job.route)}
        if job.language is not None:
            localized_schema["inLanguage"] = job.language.code
        graph.append(localized_schema)
    if item_list := _localized_item_list(job):
        graph.append(
            {
                "@type": "ItemList",
                "itemListElement": [
                    {"@type": "ListItem", "position": position, "name": name, "url": public_url(base_url, localized_route(route))}
                    for position, (name, route) in enumerate(item_list, start=1)
                ],
            }
        )
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
                tuple(sorted(members, key=lambda person: (-len(person.awards), _surname_key(person.name)))),
            )
        )
    countries.sort(key=lambda place: (-len(place.people), place.name))
    return countries


def plan_city_places(records: Iterable[AwardRecord], people: Iterable[Laureate]) -> list[Place]:
    """Rank affiliation cities by distinct, QID-linked laureates.

    A city is its present-day city/country pair.  Coordinates are evidence for every
    included affiliation, but do not split a city when institutions have different
    points within it.
    """
    people_by_qid = {person.qid: person for person in people}
    members_by_place: dict[tuple[str, str], set[str]] = {}
    for record in records:
        qid = record.laureate_wikidata_qid.strip()
        if not qid:
            continue
        for affiliation in record.affiliations:
            city, country = affiliation.city.strip(), affiliation.country.strip()
            if not city or not country:
                continue
            parse_map_points(affiliation.coordinates, record.award_record_id, "affiliation_coordinates", multiple=False)
            members_by_place.setdefault((city, country), set()).add(qid)

    slugs: dict[str, str] = {}
    cities: list[Place] = []
    for (city, country), members in members_by_place.items():
        name = f"{city}, {country}"
        slug = slugify(f"{city}-{country}")
        if slug in slugs:
            raise BuildFailure(f"duplicate city slug slug={slug} name={name!r} other={slugs[slug]!r}")
        slugs[slug] = name
        cities.append(
            Place(
                name,
                slug,
                f"{CITIES_ROUTE}{slug}/",
                tuple(
                    sorted(
                        (people_by_qid[qid] for qid in members),
                        key=lambda person: (-len(person.awards), _surname_key(person.name)),
                    )
                ),
                city,
                country,
            )
        )
    cities.sort(key=lambda place: (-len(place.people), place.name))
    return cities


def plan_per_capita_places(places: Iterable[Place], population_file: Path = POPULATION_FILE) -> list[tuple[Place, float]]:
    """Rank country places by distinct laureates per million people, matching the Explorer rate views."""
    places = list(places)
    populations = load_population([place.name for place in places], population_file)
    rates = [
        (place, len(place.people) / population * 1_000_000)
        for place, population in zip(places, populations, strict=True)
        if population and len(place.people) >= 5
    ]
    return sorted(rates, key=lambda entry: (-entry[1], entry[0].name))


def plan_income_adjusted_award_rankings(
    country_names: list[str],
    comparison: list[dict[str, int | float]],
) -> list[dict[str, int | float]]:
    """Rank award records per $1 billion of 2024 GDP PPP."""
    rows = [
        {
            **row,
            "rate": float(row["awards_per_million"]) / float(row["gdp_per_capita"]) * 1_000,
        }
        for row in comparison
    ]
    return sorted(rows, key=lambda row: (-float(row["rate"]), country_names[int(row["country_idx"])]))


def plan_income_adjusted_award_rows(
    country_names: list[str],
    rankings: list[dict[str, int | float]],
    places: Iterable[Place],
) -> list[tuple[Place, float]]:
    """Rank homepage countries by award records per $1 billion of 2024 GDP PPP."""
    by_name = {place.name: place for place in places}
    rows: list[tuple[Place, float]] = []
    for row in rankings:
        country = by_name.get(country_names[int(row["country_idx"])])
        if country is not None:
            rows.append((country, float(row["rate"])))
    return rows


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
        openalex_ids = {
            link.record.institution_openalex_id
            for link in awards
            if link.affiliation.position == 1 and _nonblank(link.record.institution_openalex_id)
        }
        rors = {
            link.record.affiliate_ror
            for link in awards
            if link.affiliation.position == 1 and _nonblank(link.record.affiliate_ror)
        }
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
                next(iter(openalex_ids), ""),
                next(iter(rors), ""),
                next(iter(qids)) if len(qids) == 1 else "",
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
        locations: dict[str, list[tuple[str, str]]] = {}
        for link in affiliation.awards:
            laureates.setdefault(link.record.high_school_subject, set()).add(link.record.laureate_wikidata_qid)
            if _nonblank(link.affiliation.city) or _nonblank(link.affiliation.country):
                locations.setdefault(link.record.high_school_subject, []).append(
                    (link.affiliation.city.strip(), link.affiliation.country.strip())
                )
        for subject, qids in laureates.items():
            city, country = _commonest(locations.get(subject, ())) if locations.get(subject) else ("", "")
            members.setdefault(subject, []).append(RankedAffiliation(affiliation, len(qids), ", ".join(part for part in (city, country) if part), city, country))
    return {
        subject: tuple(sorted(rows, key=lambda row: (-row.count, row.affiliation.name)))
        for subject, rows in members.items()
    }


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

    # A category-routed prize also owns one page per year across every category: /nobel-prize/1921/. Nothing else
    # answers "Nobel Prize winners 1921" in one page, because its years are filed under the category.
    prize_year_routes: dict[str, str] = {}
    if routed_categories:
        prize_year_labels: dict[str, str] = {}
        for record in prize_records:
            year_slug = slugify(record.year)
            previous = prize_year_labels.setdefault(year_slug, record.year)
            if previous != record.year:
                raise BuildFailure(f"duplicate year slug qid={ranking.qid}")
            prize_year_routes[record.year] = route + f"{year_slug}/"

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
        prize_year_routes,
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


def plan_prize_page(layout: PrizeLayout, rank: int, subject_order: dict[str, int]) -> PageJob:
    category_links = (
        tuple(
            (category, layout.route + f"{layout.category_slugs[category]}/")
            for category in sorted(layout.category_slugs)
        )
        if layout.routed_categories
        else ()
    )
    if layout.routed_categories:
        # The prize owns an all-category page per year, and this is the only index that reaches them.
        first_records: dict[str, str] = {}
        for record in layout.records:
            first_records.setdefault(record.year, record.award_record_id)
        direct_years = [
            (year, route, _year_prefix(year, first_records[year]))
            for year, route in layout.prize_year_routes.items()
        ]
    else:
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
        share_card=ShareCard(
            "Prize",
            layout.ranking.prize_name,
            rank,
            len(layout.records),
            tuple(sorted({record.high_school_subject for record in layout.records}, key=subject_order.__getitem__)),
            layout.ranking.slug,
        ),
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
        item_list=tuple(
            (record.full_name, layout.record_routes[record.award_record_id]) for record in ascending[:ITEM_LIST_CAP]
        ),
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


def plan_prize_year_pages(layout: PrizeLayout) -> list[PageJob]:
    """One page per award year across every category of a category-routed prize: /nobel-prize/1921/.

    The category year pages under it stay: this page is their union, and the two scopes answer different questions.
    Year-routed prizes already have exactly this page, so they get nothing here.
    """
    if not layout.routed_categories:
        return []

    by_year: dict[str, list[AwardRecord]] = {}
    for record in layout.records:
        by_year.setdefault(record.year, []).append(record)
    years = sorted(by_year, key=lambda year: _year_prefix(year, by_year[year][0].award_record_id))

    jobs: list[PageJob] = []
    for index, year in enumerate(years):
        ordered_group = sorted(by_year[year], key=lambda record: record.award_record_id)
        roll_call = _names([record.full_name for record in ordered_group])
        earlier = years[index - 1] if index else None
        later = years[index + 1] if index + 1 < len(years) else None
        # A shared citation only ever spans one category, so group inside a category. Left to itself _by_motivation
        # would read two categories whose motivations match — or are both blank — as one shared award.
        by_category: dict[str, list[AwardRecord]] = {}
        for record in ordered_group:
            by_category.setdefault(record.category, []).append(record)
        winners = tuple(
            group
            for category in sorted(by_category)
            for group in _by_motivation(
                (record, layout.record_routes[record.award_record_id]) for record in by_category[category]
            )
        )
        jobs.append(
            _page(
                "year.html",
                layout.prize_year_routes[year],
                f"{layout.ranking.prize_name} {year}: Winners",
                _clamp(f"{layout.ranking.prize_name}, {year}: awarded to {roll_call}."),
                [Breadcrumb("Home", "/"), Breadcrumb(layout.ranking.prize_name, layout.route), Breadcrumb(year, None)],
                prize=layout.ranking,
                category="",
                # The whole point of this page is that it spans categories, so every group has to name its own.
                show_group_categories=True,
                year=year,
                winners=winners,
                earlier_year=(earlier, layout.prize_year_routes[earlier]) if earlier else None,
                later_year=(later, layout.prize_year_routes[later]) if later else None,
            )
        )
    return jobs


def plan_year_pages(
    layout: PrizeLayout,
    base_url: str,
    routes_by_laureate: dict[str, str],
    birth_countries: frozenset[str],
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
            person_route = routes_by_laureate.get(record.laureate_wikidata_qid, "")
            winner_crumbs = [
                Breadcrumb("Home", "/"),
                Breadcrumb(layout.ranking.prize_name, layout.route),
            ]
            if routed_category is not None:
                winner_crumbs.append(
                    Breadcrumb(routed_category, layout.route + f"{layout.category_slugs[routed_category]}/")
                )
            elif _nonblank(record.category):
                # A year-routed prize has no category page to link to, but the category is still where this award
                # sits, and the trail is the only place the page names it.
                winner_crumbs.append(Breadcrumb(record.category, None))
            # The trail is where a reader reaches for the person, so the name carries the link to their other awards.
            winner_crumbs.extend((Breadcrumb(record.year, route), Breadcrumb(record.full_name, person_route or None)))
            jobs.append(
                _page(
                    "winner.html",
                    layout.record_routes[record.award_record_id],
                    winner_title,
                    winner_description,
                    winner_crumbs,
                    record=record,
                    facts=_facts(record, birth_countries),
                    identifiers=_identifiers(record),
                    biographical_note=_note(record.biographical_note),
                    co_laureates=tuple(
                        (other, layout.record_routes[other.award_record_id])
                        for other in ordered_group
                        if other.award_record_id != record.award_record_id
                    ),
                    person_route=person_route,
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


def plan_person_pages(people: list[Laureate], base_url: str, explorer_people: list[dict[str, Any]]) -> list[PageJob]:
    ranking_by_route = {
        row["r"]: (rank, row["c"])
        for rank, row in enumerate(explorer_people, start=1)
        if row["r"]
    }
    jobs: list[PageJob] = []
    for person in people:
        ranking = ranking_by_route.get(relative_route(EXPLORER_ROUTE, person.route))
        if ranking is None or ranking[1] != len(person.awards):
            raise BuildFailure(f"invalid laureate share ranking qid={person.qid}")
        prizes = list(dict.fromkeys(record.prize_name for record, _ in person.awards))
        span = _year_span([record.year for record, _ in person.awards])
        latest = person.awards[-1][0]
        birth_date = next((record.birth_date for record, _ in person.awards if _nonblank(record.birth_date)), "")
        recorded_birth_year = next((record.birth_year for record, _ in person.awards if _nonblank(record.birth_year)), "")
        birth_year = birth_date[:4] if len(birth_date) >= 4 else recorded_birth_year
        birth_country = next((record.birth_country for record, _ in person.awards if _nonblank(record.birth_country)), "")
        death_date = next((record.death_date for record, _ in person.awards if _nonblank(record.death_date)), "")
        lifespan = f"{birth_year}–{death_date[:4]}" if birth_year and len(death_date) >= 4 else ""
        author_openalex_id = next((record.author_openalex_id for record, _ in person.awards if _nonblank(record.author_openalex_id)), "")
        orc_id = next((record.orc_id for record, _ in person.awards if _nonblank(record.orc_id)), "")
        jobs.append(
            _page(
                "person.html",
                person.route,
                f"{person.name} — {_names(prizes, limit=2)} ({span})",
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
                wikipedia_url=wikipedia_search_url(person.name),
                author_openalex_id=author_openalex_id,
                orc_id=orc_id,
                schema={
                    **_laureate_schema(latest, public_url(base_url, person.route)),
                    "award": [f"{record.prize_name}, {record.year}" for record, _ in person.awards],
                },
                share_card=ShareCard(
                    "Laureate",
                    person.name,
                    ranking[0],
                    ranking[1],
                    tuple(name for name, _ in person.subjects),
                    person.route.rstrip("/").rsplit("/", 1)[-1],
                ),
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
            item_list=tuple((subject.name, subject.route) for subject in subjects),
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
                item_list=tuple((place.name, place.route) for place in places[:ITEM_LIST_CAP]),
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
                    return_label="All countries",
                )
            )
    return jobs


def plan_city_pages(cities: list[Place]) -> list[PageJob]:
    """Plan the award-time affiliation city index and its city detail pages."""
    covered = len({person.qid for city in cities for person in city.people})
    jobs = [
        _page(
            "countries.html",
            CITIES_ROUTE,
            "Cities where laureates were awarded",
            _clamp(
                f"The award-time institution cities of {covered:,} laureates across {len(cities)} cities, ranked. "
                "Laureates may appear under more than one city."
            ),
            (Breadcrumb("Home", "/"), Breadcrumb("Cities", None)),
            countries=tuple(cities),
            item_list=tuple((city.name, city.route) for city in cities[:ITEM_LIST_CAP]),
            leader=len(cities[0].people) if cities else 0,
            tab="Cities",
            eyebrow="Awarded in",
            blurb=f"{covered:,} laureates recorded at award-time institutions across {len(cities)} cities.",
            caveat=(
                "A laureate is counted once in every city where an institution was recorded for them. "
                "Different institution points in the same city remain one city."
            ),
            plain_counts=False,
        )
    ]
    for city in cities:
        count = len(city.people)
        laureates = "laureate" if count == 1 else "laureates"
        jobs.append(
            _page(
                "country.html",
                city.route,
                f"Laureates awarded in {city.name}",
                _clamp(f"{count} award-winning {laureates} recorded at institutions in {city.name}, with every prize each won."),
                (Breadcrumb("Home", "/"), Breadcrumb("Cities", CITIES_ROUTE), Breadcrumb(city.name, None)),
                place=city,
                tab="Cities",
                eyebrow="Awarded in",
                blurb=f"{count} {laureates} on record were affiliated with institutions here when their awards were made.",
                view_route=CITIES_ROUTE,
                return_label="All cities",
            )
        )
    return jobs


def plan_city_per_capita_page(rows: list[dict[str, int | float | str]], cities: list[Place]) -> PageJob:
    """Plan the award-recipient city rate table alongside the city ranking."""
    routes = {city.name: city.route for city in cities}
    table_rows = [{**row, "route": routes.get(f"{row['city']}, {row['country']}", "")} for row in rows]
    return _page(
        "city_per_capita.html",
        CITIES_PER_CAPITA_ROUTE,
        "Cities by award records as a share of population",
        "Award-recipient records at award-time institutions as a percentage of reviewed GeoNames city population.",
        (Breadcrumb("Home", "/"), Breadcrumb("Countries", COUNTRIES_ROUTE), Breadcrumb("Cities %", None)),
        cities=tuple(table_rows),
    )


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
            item_list=tuple((affiliation.name, affiliation.route) for affiliation in affiliations[:AFFILIATION_ROWS]),
            leader=affiliations[0].count if affiliations else 0,
            recorded=recorded_affiliations,
            total=len(records),
        )
    ]
    for rank, affiliation in enumerate(affiliations, start=1):
        span = _year_span([link.record.year for link in affiliation.awards])
        award_count = len({link.record.award_record_id for link in affiliation.awards})
        prizes = list(dict.fromkeys(link.record.prize_name for link in affiliation.awards))
        jobs.append(
            _page(
                "affiliation.html",
                affiliation.route,
                f"{affiliation.name} — {_names(prizes, limit=2)} ({span})",
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
                award_count=award_count,
                wikipedia_url=wikipedia_search_url(affiliation.name),
                share_card=ShareCard(
                    "Institution",
                    affiliation.name,
                    rank,
                    award_count,
                    tuple(name for name, _ in affiliation.subjects),
                    affiliation.slug,
                ),
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
    affiliations: list[Affiliation],
    country_places: dict[str, list[Place]],
    prize_routes: dict[str, str],
    ranking_by_qid: dict[str, Ranking],
    record_routes: dict[str, str],
    income_adjusted_awards: list[tuple[Place, float]],
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
    women = sorted(
        (person for person in people if any(record.sex == "Female" for record, _ in person.awards)),
        key=lambda person: (-len(person.awards), _surname_key(person.name)),
    )
    sexed_records = sum(1 for record in records if record.sex in ("Female", "Male"))
    women_pct = round(100 * sum(1 for record in records if record.sex == "Female") / sexed_records) if sexed_records else 0
    top_countries = country_places["Awarded"][:7]
    affiliation_rates = plan_per_capita_places(country_places["Awarded"])
    # Nobel Prize and Fields Medal are the two prizes people actually search for by name; the rest of the
    # roster is named only by count, so both counts must track `rankings` instead of drifting into a stale "dozen".
    other_prize_count = len(rankings) - 2
    # The heading has to hold one line on a 320px phone, so it names one prize and counts the rest. The page title
    # is not width-bound and keeps the fuller phrasing, where "Fields Medal" and "Awards" still earn their search traffic.
    hero_heading = f"Nobel Prize & {len(rankings) - 1} More"
    return _page(
        "index.html",
        "/",
        f"PrizeAtlas: Nobel Prize, Fields Medal & {other_prize_count} More Awards",
        _clamp(
            f"The Nobel Prize, Fields Medal, and {other_prize_count} more: {len(people):,} laureates and "
            f"{len(records):,} awards across {len(rankings)} international prizes, {min(year_prefixes)}-{latest_year}. "
            "Free, fast, and sourced from Wikidata, Wikipedia, and ROR."
        ),
        (),
        hero_heading=hero_heading,
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
        top_women=tuple(women[:HOMEPAGE_ROWS]),
        women_pct=women_pct,
        top_countries=tuple(top_countries),
        affiliation_rates=tuple(affiliation_rates[:HOMEPAGE_ROWS]),
        income_adjusted_awards=tuple(income_adjusted_awards[:HOMEPAGE_ROWS]),
        top_institutions=tuple(affiliations[:HOMEPAGE_ROWS]),
    )


def plan_awards_page(rankings: list[Ranking], prize_routes: dict[str, str]) -> PageJob:
    return _page(
        "awards.html",
        AWARDS_ROUTE,
        "Science Awards including Nobel Prize, Fields Medal, and Others",
        f"Browse {len(rankings)} international awards and their recipients.",
        (Breadcrumb("Home", "/"), Breadcrumb("Awards", None)),
        # The title carries the search terms; the heading only has to hold one line on a phone.
        heading="Science Awards",
        prizes=tuple((ranking, prize_routes[ranking.qid]) for ranking in rankings),
        item_list=tuple((ranking.prize_name, prize_routes[ranking.qid]) for ranking in rankings),
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
                item_list=tuple((person.name, person.route) for person in page_people),
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
            "Map: Birthplaces and Institutions",
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
                f"{subject_name} Map: Birthplaces and Institutions",
                f"Map recorded birthplaces and affiliated institutions for international awards classified under {subject_name}.",
                (),
                payload=atlas_payload,
                initial_subject=subject_name,
            )
        )
    return jobs


def plan_explorer_page(
    payload: dict[str, Any],
    generated: str,
) -> PageJob:
    return _page(
        "explorer.html",
        EXPLORER_ROUTE,
        "Data Explorer",
        "Explore ranked laureates across fourteen international prize families by awards, points, country, and career.",
        (Breadcrumb("Home", "/"), Breadcrumb("Explorer", None)),
        payload=explorer_json(payload),
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
    subject_counts = Counter(record.high_school_subject for record in records)
    subject_order = {
        name: index for index, name in enumerate(sorted(subject_counts, key=lambda subject: (-subject_counts[subject], subject)))
    }
    record_routes: dict[str, str] = {}
    jobs: list[PageJob] = []
    layouts: list[PrizeLayout] = []
    for rank, ranking in enumerate(rankings, start=1):
        layout = layout_prize(ranking, records_by_qid[ranking.qid])
        layouts.append(layout)
        record_routes.update(layout.record_routes)
        jobs.extend(plan_category_pages(layout))
        jobs.append(plan_prize_page(layout, rank, subject_order))
        jobs.append(plan_winners_page(layout))

    people = plan_people(records, routes_by_laureate, record_routes, subject_order)
    cities = plan_city_places(records, people)
    affiliations = plan_affiliations(records, record_routes, profiles_by_qid)
    country_places = {label: plan_country_places(people, route, MEMBERS[label]) for label, route in COUNTRY_VIEWS}
    countries = country_places["Born"]
    birth_countries = frozenset(place.name for place in countries)
    affiliation_countries = plan_affiliation_countries(affiliations)
    subjects = plan_subjects(people, subject_counts, affiliations)
    explorer = explorer_payload(rankings, records, routes_by_laureate)
    city_awards_per_capita = plan_city_awards_per_capita(records)
    explorer["city_awards_per_capita"] = city_awards_per_capita
    homepage_award_counts = award_affiliation_country_counts(records, HOMEPAGE_AWARD_YEAR_FROM, HOMEPAGE_AWARD_YEAR_TO)
    homepage_comparison = plan_awards_gdp_comparison(
        explorer["countries"],
        homepage_award_counts,
        explorer["population"],
        load_gdp_per_capita()["ppp"],
    )
    income_adjusted_rankings = plan_income_adjusted_award_rankings(explorer["countries"], homepage_comparison)
    explorer["income_adjusted_awards"] = income_adjusted_rankings
    income_adjusted_awards = plan_income_adjusted_award_rows(
        explorer["countries"], income_adjusted_rankings, country_places["Awarded"]
    )

    jobs.extend(plan_person_pages(people, base_url, explorer["people"]))
    for layout in layouts:
        jobs.extend(plan_year_pages(layout, base_url, routes_by_laureate, birth_countries))
        jobs.extend(plan_prize_year_pages(layout))
    jobs.extend(plan_subject_pages(subjects, records, record_routes))
    jobs.extend(plan_country_pages(country_places))
    jobs.extend(plan_city_pages(cities))
    jobs.append(plan_city_per_capita_page(city_awards_per_capita, cities))
    jobs.extend(plan_affiliation_country_pages(affiliation_countries, records))
    jobs.extend(plan_affiliation_pages(affiliations, records))
    jobs.extend(plan_university_pages(affiliations))
    jobs.append(
        plan_home_page(
            rankings, records, people, affiliations, country_places, prize_routes, ranking_by_qid, record_routes, income_adjusted_awards
        )
    )
    jobs.append(plan_awards_page(rankings, prize_routes))
    jobs.extend(plan_people_index(people))
    jobs.extend(plan_map_pages(records))
    jobs.append(plan_explorer_page(explorer, generated))
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


def _stable_key(job: PageJob) -> str:  # noqa: C901 - one explicit table of page-family identities.
    """Return the language-independent identity for one canonical planner job."""
    context = job.context
    if job.template == "index.html":
        return "home"
    if job.template == "awards.html":
        return "awards"
    if job.template == "people.html":
        return f"people:{context['page_number']}"
    if job.template == "prize.html":
        return f"prize:{context['prize'].qid}"
    if job.template == "winners.html":
        return f"prize-winners:{context['prize'].qid}"
    if job.template == "category.html":
        return f"category:{context['prize'].qid}:{slugify(context['category'])}"
    if job.template == "winner.html":
        return f"winner:{context['record'].award_record_id}"
    if job.template == "person.html":
        return f"person:{context['person'].qid}"
    if job.template == "year.html":
        prize = context["prize"]
        parts = job.route.strip("/").split("/")
        if len(parts) == 2:
            return f"prize-year:{prize.qid}:{context['year']}"
        return f"category-year:{prize.qid}:{slugify(context['category'])}:{context['year']}"
    if job.template == "countries.html":
        return {"Born": "countries:born", "Awarded": "countries:awarded", "Died": "countries:died", "Cities": "cities"}[context["tab"]]
    if job.template == "country.html":
        if context["tab"] == "Cities":
            return f"city:{context['place'].slug}"
        return f"country:{context['tab'].lower()}:{context['place'].slug}"
    if job.template == "city_per_capita.html":
        return "cities-per-capita"
    if job.template == "affiliation_countries.html":
        return "affiliation-countries"
    if job.template == "affiliation_country.html":
        return f"affiliation-country:{context['place'].slug}"
    if job.template == "affiliations.html":
        return "affiliations"
    if job.template == "affiliation.html":
        return f"affiliation:{context['affiliation'].slug}"
    if job.template == "universities.html":
        return "universities"
    if job.template == "university_countries.html":
        return "universities:countries"
    if job.template == "subjects.html":
        return "subjects"
    if job.template in {"subject.html", "subject_affiliations.html", "subject_recent.html"}:
        view = {
            "subject.html": "people",
            "subject_affiliations.html": "affiliations",
            "subject_recent.html": "recent",
        }[job.template]
        return f"subject:{slugify(context['subject'].name)}:{view}"
    if job.template == "map.html":
        return "map" if not context["initial_subject"] else f"map:{slugify(context['initial_subject'])}"
    if job.template in {"explorer.html", "nearby.html", "about.html"}:
        return job.template.removesuffix(".html")
    raise BuildFailure(f"cannot assign stable key template={job.template} route={job.route}")


def _localized_route(language: Language, job: PageJob, key: str) -> str:  # noqa: C901 - one explicit route table.
    """Rebuild a canonical route from language-owned segments and source identity."""
    context = job.context
    parts = job.route.strip("/").split("/") if job.route != "/" else []
    if key == "home":
        return language.route()
    if key == "awards":
        return language.route(language.segment("awards"))
    if key.startswith("people:"):
        number = int(key.rsplit(":", 1)[1])
        if number == 1:
            return language.route(language.segment("people"))
        return language.route(language.segment("people"), f"{language.segment('page')}-{number}")
    if key.startswith("prize:"):
        return language.route(parts[0])
    if key.startswith("prize-winners:"):
        return language.route(parts[0], language.segment("winners"))
    if key.startswith("category:"):
        return language.route(parts[0], slugify(language.term("category", context["category"])))
    if key.startswith("category-year:"):
        return language.route(parts[0], slugify(language.term("category", context["category"])), slugify(context["year"]))
    if key.startswith("prize-year:"):
        return language.route(parts[0], slugify(context["year"]))
    if key.startswith("winner:"):
        record: AwardRecord = context["record"]
        if len(parts) == 4:
            return language.route(parts[0], slugify(language.term("category", record.category)), parts[2], parts[3])
        return language.route(*parts)
    if key.startswith("person:"):
        return language.route(language.segment("people"), parts[-1])
    if key == "countries:born":
        return language.route(language.segment("countries"))
    if key == "countries:awarded":
        return language.route(language.segment("countries"), language.segment("awarded"))
    if key == "countries:died":
        return language.route(language.segment("countries"), language.segment("died"))
    if key.startswith("country:"):
        _country, view, _slug = key.split(":", 2)
        prefix = [language.segment("countries")]
        if view != "born":
            prefix.append(language.segment(view))
        return language.route(*prefix, slugify(language.term("country", context["place"].name)))
    if key == "cities":
        return language.route(language.segment("countries"), language.segment("cities"))
    if key.startswith("city:"):
        return language.route(language.segment("countries"), language.segment("cities"), context["place"].slug)
    if key == "cities-per-capita":
        return language.route(language.segment("countries"), language.segment("cities-per-capita"))
    if key == "affiliation-countries":
        return language.route(language.segment("countries"), language.segment("country_affiliations"))
    if key.startswith("affiliation-country:"):
        return language.route(
            language.segment("countries"),
            language.segment("country_affiliations"),
            slugify(language.term("country", context["place"].name)),
        )
    if key == "affiliations":
        return language.route(language.segment("affiliations"))
    if key.startswith("affiliation:"):
        return language.route(language.segment("affiliations"), context["affiliation"].slug)
    if key == "universities":
        return language.route(language.segment("universities"))
    if key == "universities:countries":
        return language.route(language.segment("universities"), language.segment("countries"))
    if key == "subjects":
        return language.route(language.segment("subjects"))
    if key.startswith("subject:"):
        _subject, _slug, view = key.split(":", 2)
        subject: Subject = context["subject"]
        route = [language.segment("subjects"), slugify(language.term("subject", subject.name))]
        if view == "affiliations":
            route.append(language.segment("country_affiliations"))
        elif view == "recent":
            route.append(language.segment("recent"))
        return language.route(*route)
    if key == "map":
        return language.route(language.segment("map"))
    if key.startswith("map:"):
        return language.route(language.segment("map"), slugify(language.term("subject", context["initial_subject"])))
    if key in {"explorer", "nearby", "about"}:
        return language.route(language.segment(key))
    raise BuildFailure(f"cannot localize route language={language.code} key={key}")


def _validate_localized_jobs(jobs: Iterable[PageJob]) -> None:
    by_key: dict[str, dict[str, PageJob]] = {}
    route_owners: dict[str, PageJob] = {}
    for job in jobs:
        if job.language is None:
            raise BuildFailure(f"page has no language route={job.route}")
        siblings = by_key.setdefault(job.key, {})
        if job.language.code in siblings:
            raise BuildFailure(f"duplicate locale page key={job.key} language={job.language.code}")
        siblings[job.language.code] = job
        if existing := route_owners.get(job.route):
            raise BuildFailure(
                f"duplicate public route route={job.route} keys={existing.key},{job.key} "
                f"languages={existing.language.code},{job.language.code}"
            )
        route_owners[job.route] = job
    for key, siblings in by_key.items():
        if set(siblings) != set(LANGUAGE_CODES):
            raise BuildFailure(f"locale parity key={key} languages={','.join(sorted(siblings))}")


def _localized_affiliation_name(language: Language, affiliation: Affiliation) -> str:
    return language.entity_label(affiliation.qid, affiliation.name)


def _localized_award_label(language: Language, record: AwardRecord) -> str:
    prize = language.term("prize", record.prize_name)
    return language.text("meta.award-with-category", prize=prize, category=language.term("category", record.category)) if record.category else prize


def _localized_breadcrumbs(language: Language, breadcrumbs: Iterable[Breadcrumb]) -> tuple[Breadcrumb, ...]:
    fixed = {
        "Home": "crumb.home",
        "Awards": "crumb.awards",
        "People": "crumb.people",
        "Countries": "crumb.countries",
        "Cities": "crumb.cities",
        "Institutions": "crumb.institutions",
        "Universities": "crumb.universities",
        "By country": "crumb.by-country",
        "Subjects": "crumb.subjects",
        "Recent": "crumb.recent",
        "Every winner": "crumb.every-winner",
    }
    result: list[Breadcrumb] = []
    for crumb in breadcrumbs:
        label = language.text(fixed[crumb.label]) if crumb.label in fixed else crumb.label
        for section in ("prize", "category", "country", "subject"):
            if crumb.label in language.terms[section]:
                label = language.term(section, crumb.label)
                break
        if crumb.label.startswith("Page "):
            label = language.text("crumb.page", page=crumb.label.removeprefix("Page "))
        result.append(Breadcrumb(label, crumb.route))
    return tuple(result)


def _country_index_people(places: Iterable[Place]) -> int:
    return len({person.qid for place in places for person in place.people})


def _localized_metadata(language: Language, job: PageJob, plan: SitePlan) -> tuple[str, str]:  # noqa: C901 - page metadata follows the explicit page-family map.
    """Produce translated metadata from canonical data without changing planner membership."""
    context = job.context
    key = _stable_key(job)
    years = plan.year_span.split("-", 1)
    year_from, year_to = (years[0], years[-1])
    num = lambda value: format_number(value, language)
    if key == "home":
        fields = {
            "other_prize_count": num(plan.prize_count - 2),
            "people_count": num(plan.person_count),
            "award_count": num(plan.recipient_count),
            "prize_count": num(plan.prize_count),
            "year_from": year_from,
            "year_to": year_to,
        }
        name = "home"
    elif key == "awards":
        fields, name = {"prize_count": num(plan.prize_count)}, "awards"
    elif key.startswith("people:"):
        fields, name = {"page": context["page_number"], "page_count": context["page_count"]}, "people"
    elif key.startswith("prize-winners:"):
        prize = context["prize"]
        fields = {"prize": language.term("prize", prize.prize_name), "recipient_count": num(len(context["winners"])), "year_span": context["span"]}
        name = "prize-winners"
    elif key.startswith("prize:"):
        prize = context["prize"]
        prize_records = [
            candidate.context["record"]
            for candidate in plan.jobs
            if candidate.template == "winner.html" and candidate.context["record"].award_wikidata_qid == prize.qid
        ]
        fields = {
            "prize": language.term("prize", prize.prize_name),
            "recipient_count": num(len(prize_records)),
            "year_span": _year_span([record.year for record in prize_records]),
            "blurb": language.ranking_blurb(prize.qid),
        }
        name = "prize"
    elif key.startswith("category:"):
        prize = context["prize"]
        recipients = sum(len(members) for _year, _route, _prefix, groups in context["years"] for _motivation, members in groups)
        fields = {
            "prize": language.term("prize", prize.prize_name),
            "category": language.term("category", context["category"]),
            "recipient_count": num(recipients),
            "year_span": _year_span([year for year, *_rest in context["years"]]),
        }
        name = "category"
    elif key.startswith("category-year:"):
        fields = {
            "prize": language.term("prize", context["prize"].prize_name),
            "year": context["year"],
            "names": ", ".join(record.full_name for _motivation, members in context["winners"] for record, _route in members),
        }
        name = "category-year"
    elif key.startswith("prize-year:"):
        prize = language.term("prize", context["prize"].prize_name)
        award = (
            language.text("meta.award-with-category", prize=prize, category=language.term("category", context["category"]))
            if context["category"]
            else prize
        )
        fields = {
            "award": award,
            "year": context["year"],
            "names": ", ".join(record.full_name for _motivation, members in context["winners"] for record, _route in members),
        }
        name = "prize-year"
    elif key.startswith("winner:"):
        record: AwardRecord = context["record"]
        first = next((item for item in record.affiliations if item.name), None)
        fields = {
            "name": record.full_name,
            "award": _localized_award_label(language, record),
            "year": record.year,
            "motivation": record.motivation,
            "affiliation": language.text(
                "meta.winner.affiliation",
                institution=language.entity_label(first.wikidata_qid, first.name),
            ) if first else "",
        }
        name = "winner"
    elif key.startswith("person:"):
        person: Laureate = context["person"]
        fields = {
            "name": person.name,
            "prizes": ", ".join(language.term("prize", prize) for prize in dict.fromkeys(record.prize_name for record, _route in person.awards)),
            "year_span": _year_span([record.year for record, _route in person.awards]),
            "award_count": num(len(person.awards)),
        }
        name = "person"
    elif key == "subjects":
        fields, name = {}, "subjects"
    elif key.startswith("subject:"):
        subject: Subject = context["subject"]
        fields = {"subject": language.term("subject", subject.name), "award_count": num(subject.award_count), "person_count": num(len(subject.people))}
        name = {"people": "subject", "affiliations": "subject-affiliations", "recent": "subject-recent"}[key.rsplit(":", 1)[1]]
        if name == "subject-affiliations":
            fields["institution_count"] = num(len(subject.affiliations))
        elif name == "subject-recent":
            fields.update(
                recipient_count=num(context["recent_recipient_count"]),
                prize_count=num(context["recent_prize_count"]),
                year_from=context["recent_start_year"],
                year_to=context["recent_end_year"],
            )
    elif key.startswith("countries:"):
        view = key.split(":", 1)[1]
        places = context["countries"]
        fields = {"person_count": num(_country_index_people(places)), "country_count": num(len(places))}
        name = f"countries-{view}"
    elif key.startswith("country:"):
        _country, view, _slug = key.split(":", 2)
        place: Place = context["place"]
        fields = {"country": language.term("country", place.name), "person_count": num(len(place.people))}
        name = f"country-{view}"
    elif key == "cities":
        places = context["countries"]
        fields, name = {"person_count": num(_country_index_people(places)), "city_count": num(len(places))}, "cities"
    elif key.startswith("city:"):
        place = context["place"]
        fields, name = {"city": _localized_place_label(language, place), "person_count": num(len(place.people))}, "city"
    elif key == "cities-per-capita":
        fields, name = {}, "cities-per-capita"
    elif key == "affiliation-countries":
        fields = {
            "country_count": num(len(context["countries"])),
            "recorded_count": num(context["recorded"]),
            "award_count": num(context["total"]),
        }
        name = "affiliation-countries"
    elif key.startswith("affiliation-country:"):
        place: AffiliationCountry = context["place"]
        fields, name = {"country": language.term("country", place.name), "institution_count": num(len(place.members))}, "affiliation-country"
    elif key == "affiliations":
        fields, name = {"recorded_count": num(context["recorded"]), "award_count": num(context["total"])}, "affiliations"
    elif key.startswith("affiliation:"):
        affiliation: Affiliation = context["affiliation"]
        fields = {
            "institution": _localized_affiliation_name(language, affiliation),
            "prizes": ", ".join(language.term("prize", prize) for prize in dict.fromkeys(link.record.prize_name for link in affiliation.awards)),
            "year_span": _year_span([link.record.year for link in affiliation.awards]),
            "award_count": num(context["award_count"]),
            "person_count": num(affiliation.count),
        }
        name = "affiliation"
    elif key == "universities":
        fields, name = {"university_count": num(context["total"])}, "universities"
    elif key == "universities:countries":
        fields, name = {"university_count": num(context["total"]), "country_count": num(len(context["countries"]))}, "universities-countries"
    elif key == "map":
        fields, name = {}, "map"
    elif key.startswith("map:"):
        fields, name = {"subject": language.term("subject", context["initial_subject"])}, "map-subject"
    elif key in {"explorer", "nearby"}:
        fields, name = {}, key
    elif key == "about":
        fields, name = {"prize_count": num(plan.prize_count), "person_count": num(plan.person_count)}, "about"
    else:
        raise BuildFailure(f"metadata missing key={key}")
    def metadata(field: str) -> str:
        catalogue_key = f"meta.{name}.{field}"
        try:
            required = _format_fields(language.ui[catalogue_key], language.code, catalogue_key)
            values = {key: fields[key] for key in required}
        except KeyError as error:
            raise BuildFailure(f"language={language.code} ui format={catalogue_key}") from error
        return language.text(catalogue_key, **values)

    return metadata("title"), _clamp(metadata("description"))


def create_multilingual_site_plan(
    rankings: list[Ranking],
    records: list[AwardRecord],
    base_url: str,
    generated: str,
    languages: tuple[Language, ...],
    profiles: Iterable[AffiliationProfile] = (),
) -> SitePlan:
    """Plan every locale from one canonical data plan without changing membership or ordering."""
    canonical = create_site_plan(rankings, records, base_url, generated, profiles)
    localized: list[PageJob] = []
    for language in languages:
        for job in canonical.jobs:
            key = _stable_key(job)
            route = _localized_route(language, job, key)
            context = {**job.context, "_canonical_route": job.route}
            if tab := context.get("tab"):
                context["tab"] = {"Born": "born", "Awarded": "awarded", "Died": "died", "Cities": "cities"}[tab]
            title, description = _localized_metadata(language, job, canonical)
            localized.append(
                PageJob(job.template, route, title, description, _localized_breadcrumbs(language, job.breadcrumbs), context, language, key)
            )
    _validate_localized_jobs(localized)
    return SitePlan(
        tuple(localized),
        canonical.prize_count,
        canonical.category_count,
        canonical.year_count,
        canonical.winner_count,
        canonical.recipient_count,
        canonical.person_count,
        canonical.country_count,
        canonical.subject_count,
        canonical.year_span,
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


def write_llms_txt(output: Path, base_url: str, plan: SitePlan, rankings: Iterable[Ranking], language: Language) -> None:
    """Write one localized machine-reader guide from the same plan as the pages."""
    jobs = tuple(job for job in plan.jobs if job.language == language)
    categories: dict[str, list[PageJob]] = {}
    for job in jobs:
        if job.template == "category.html":
            categories.setdefault(job.context["prize"].qid, []).append(job)
    entries: list[str] = []
    for ranking in sorted(rankings, key=lambda ranking: ranking.score, reverse=True):
        prize = next(job for job in jobs if job.key == f"prize:{ranking.qid}")
        winners = next(job for job in jobs if job.key == f"prize-winners:{ranking.qid}")
        entries.append(
            language.text(
                "llms.prize-winner",
                name=language.term("prize", ranking.prize_name),
                url=public_url(base_url, winners.route),
                score=ranking.score,
                blurb=language.ranking_blurb(ranking.qid),
                official_url=ranking.url,
            )
        )
        prize_categories = sorted(categories.get(ranking.qid, ()), key=lambda job: job.route)
        indexes = language.text("llms.prize_year.categories") if prize_categories else language.text("llms.prize_year.years")
        entries.append(language.text("llms.prize-year", name=language.term("prize", ranking.prize_name), url=public_url(base_url, prize.route), indexes=indexes))
        entries.extend(language.text("llms.category", title=job.title, url=public_url(base_url, job.route), description=job.description) for job in prize_categories)
    subjects = "\n".join(
        language.text(
            "llms.subject",
            title=job.title,
            url=public_url(base_url, job.route),
            description=job.description,
            subject=language.term("subject", job.context["subject"].name),
            recent_url=public_url(base_url, next(candidate for candidate in jobs if candidate.key == f"subject:{slugify(job.context['subject'].name)}:recent").route),
        )
        for job in sorted((job for job in jobs if job.template == "subject.html"), key=lambda job: job.route)
    )
    routes = _language_routes(language)
    institution_count = sum(1 for job in jobs if job.template == "affiliation.html")
    body = "\n\n".join(
        (
            language.text("llms.title"),
            language.text(
                "llms.intro",
                prize_count=format_number(plan.prize_count, language),
                person_count=format_number(plan.person_count, language),
                year_span=plan.year_span,
            ),
            language.text("llms.pages", page_count=format_number(len(jobs), language), sitemap_url=public_url(base_url, "/sitemap.xml")),
            language.text("llms.provenance"),
            "\n".join(
                (
                    language.text("llms.start_heading"),
                    language.text(
                        "llms.start_prizes",
                        url=public_url(base_url, language.route()),
                        prize_count=format_number(plan.prize_count, language),
                    ),
                    language.text("llms.start_people", url=public_url(base_url, routes["people_route"])),
                    language.text(
                        "llms.start_countries",
                        url=public_url(base_url, routes["countries_route"]),
                        country_count=format_number(plan.country_count, language),
                    ),
                    language.text("llms.start_cities", url=public_url(base_url, routes["cities_route"])),
                    language.text("llms.start_affiliations", url=public_url(base_url, routes["affiliations_route"])),
                    language.text(
                        "llms.start_universities",
                        url=public_url(base_url, routes["universities_route"]),
                        country_url=public_url(base_url, routes["university_countries_route"]),
                    ),
                    language.text("llms.start_subjects", url=public_url(base_url, routes["subjects_route"]), subject_count=plan.subject_count),
                    language.text("llms.start_about", url=public_url(base_url, routes["about_route"])),
                )
            ),
            "\n".join(
                (
                    language.text("llms.patterns_heading"),
                    language.text(
                        "llms.patterns",
                        winners_segment=language.segment("winners"),
                        institution_count=format_number(institution_count, language),
                    ),
                )
            ),
            "\n".join((language.text("llms.winner_heading"), language.text("llms.winner_intro", years=PRIZE_PAGE_YEARS), "\n".join(entries))),
            "\n".join(
                (
                    language.text("llms.subject_heading"),
                    language.text("llms.subject_intro", prize_count=format_number(plan.prize_count, language)),
                    subjects,
                )
            ),
            "\n".join(
                (
                    language.text("llms.bulk_heading"),
                    language.text("llms.bulk_intro"),
                    language.text("llms.bulk_explorer", url=public_url(base_url, routes["explorer_route"])),
                    language.text("llms.bulk_map", url=public_url(base_url, routes["map_route"])),
                    language.text("llms.bulk_nearby", url=public_url(base_url, routes["nearby_route"])),
                )
            ),
        )
    ) + "\n"
    destination = output / language.prefix.strip("/") if language.prefix else output
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "llms.txt").write_text(body, encoding="utf-8")


def _share_font(size: int, fonts: dict[int, ImageFont.FreeTypeFont]) -> ImageFont.FreeTypeFont:
    if size not in fonts:
        fonts[size] = ImageFont.load_default(size=size)
    return fonts[size]


def _share_text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> float:
    return draw.textlength(text, font=font)


def _share_wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    line = ""
    for word in text.split():
        candidate = f"{line} {word}" if line else word
        if _share_text_width(draw, candidate, font) <= max_width:
            line = candidate
            continue
        if line:
            lines.append(line)
            line = ""
        while _share_text_width(draw, word, font) > max_width:
            split = 1
            while split < len(word) and _share_text_width(draw, word[: split + 1], font) <= max_width:
                split += 1
            lines.append(word[:split])
            word = word[split:]
        line = word
    if line:
        lines.append(line)
    return lines or [""]


def _share_ellipsize(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
    candidate = text.rstrip()
    while candidate and _share_text_width(draw, candidate + "…", font) > max_width:
        candidate = candidate[:-1].rstrip()
    return candidate + "…"


def _share_fit(
    draw: ImageDraw.ImageDraw,
    text: str,
    fonts: dict[int, ImageFont.FreeTypeFont],
    max_width: int,
    max_lines: int,
    start_size: int,
    minimum_size: int,
) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    for size in range(start_size, minimum_size - 1, -2):
        font = _share_font(size, fonts)
        lines = _share_wrap(draw, text, font, max_width)
        if len(lines) <= max_lines:
            return font, lines
    font = _share_font(minimum_size, fonts)
    lines = _share_wrap(draw, text, font, max_width)
    if len(lines) > max_lines:
        remaining = " ".join(lines[max_lines - 1 :])
        lines = [*lines[: max_lines - 1], _share_ellipsize(draw, remaining, font, max_width)]
    return font, lines


def _draw_share_lines(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    lines: Iterable[str],
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
    spacing: int,
) -> None:
    line_height = font.getbbox("Ag")[3] - font.getbbox("Ag")[1] + spacing
    for index, line in enumerate(lines):
        draw.text((x, y + index * line_height), line, font=font, fill=fill)


def _write_share_image(
    target: Path,
    fonts: dict[int, ImageFont.FreeTypeFont],
    page_url: str,
    card: ShareCard | None,
    language: Language,
    generic: str | None = None,
) -> None:
    paper = (244, 240, 231)
    surface = (251, 248, 241)
    ink = (38, 40, 35)
    muted = (101, 103, 95)
    accent = (82, 106, 85)
    rule = (203, 197, 184)
    image = Image.new("RGB", (SHARE_IMAGE_WIDTH, SHARE_IMAGE_HEIGHT), paper)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((48, 42, 1152, 588), radius=30, fill=surface, outline=rule, width=2)
    draw.rounded_rectangle((48, 42, 66, 588), radius=9, fill=accent)
    draw.text((96, 78), "PRIZEATLAS", font=_share_font(28, fonts), fill=accent)

    if card is None:
        generic_key = {None: "default", "Laureates": "laureates", "Institutions": "institutions", "Universities": "universities", "Map": "map", "Nearby": "nearby"}[generic]
        title = language.text(f"share.generic.{generic_key}.title")
        subtitle = language.text(f"share.generic.{generic_key}.subtitle")
        name_font, name_lines = _share_fit(draw, title, fonts, 1008, 2, 66, 46)
        _draw_share_lines(draw, 96, 174, name_lines, name_font, ink, 12)
        draw.text(
            (96, 350),
            subtitle,
            font=_share_font(30, fonts),
            fill=muted,
        )
    else:
        if card.kind != "Prize" or card.rank < 1 or card.award_count < 1 or not card.subjects:
            raise BuildFailure(f"invalid share card slug={card.slug}")
        kind_font = _share_font(24, fonts)
        kind = language.text("share.card.prize-kind").upper()
        draw.text((1104 - _share_text_width(draw, kind, kind_font), 82), kind, font=kind_font, fill=muted)
        name_font, name_lines = _share_fit(draw, language.term("prize", card.name), fonts, 1008, 2, 66, 42)
        _draw_share_lines(draw, 96, 145, name_lines, name_font, ink, 10)
        draw.line((96, 326, 1104, 326), fill=rule, width=2)
        label_font = _share_font(20, fonts)
        value_font = _share_font(50, fonts)
        draw.text((96, 360), language.text("share.card.rank-label").upper(), font=label_font, fill=muted)
        draw.text((96, 388), f"#{format_number(card.rank, language)}", font=value_font, fill=ink)
        draw.text((340, 360), language.text("share.card.award-count-label").upper(), font=label_font, fill=muted)
        draw.text((340, 388), format_number(card.award_count, language), font=value_font, fill=ink)
        draw.text((610, 360), language.text("share.card.subjects-label").upper(), font=label_font, fill=muted)
        subjects_font, subject_lines = _share_fit(
            draw,
            " · ".join(language.term("subject", subject) for subject in card.subjects),
            fonts,
            494,
            3,
            27,
            20,
        )
        _draw_share_lines(draw, 610, 392, subject_lines, subjects_font, ink, 7)

    url_font, url_lines = _share_fit(draw, page_url, fonts, 1008, 2, 22, 16)
    _draw_share_lines(draw, 96, 526, url_lines, url_font, accent, 4)
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, format="PNG", compress_level=9)


def write_share_images(output: Path, base_url: str, jobs: Iterable[PageJob]) -> None:
    jobs = tuple(jobs)
    fonts: dict[int, ImageFont.FreeTypeFont] = {}
    generic_images = (
        (SHARE_IMAGE_FALLBACK, None, "/"),
        (SHARE_IMAGE_LAUREATES, "Laureates", PEOPLE_ROUTE),
        (SHARE_IMAGE_INSTITUTIONS, "Institutions", AFFILIATIONS_ROUTE),
        (SHARE_IMAGE_UNIVERSITIES, "Universities", UNIVERSITIES_ROUTE),
        (SHARE_IMAGE_MAP, "Map", MAP_ROUTE),
        (SHARE_IMAGE_NEARBY, "Nearby", NEARBY_ROUTE),
    )
    languages = {job.language.code: job.language for job in jobs if job.language is not None}
    for language in languages.values():
        routes = _language_routes(language)
        generic_routes = {
            "/": language.route(),
            PEOPLE_ROUTE: routes["people_route"],
            AFFILIATIONS_ROUTE: routes["affiliations_route"],
            UNIVERSITIES_ROUTE: routes["universities_route"],
            MAP_ROUTE: routes["map_route"],
            NEARBY_ROUTE: routes["nearby_route"],
        }
        for target, generic, route in generic_images:
            _write_share_image(
                output / _share_path_for_language(target, language),
                fonts,
                public_url(base_url, generic_routes[route]),
                None,
                language,
                generic,
            )

    owners: dict[str, str] = {}
    for job in jobs:
        card = job.context.get("share_card")
        if not isinstance(card, ShareCard) or card.kind != "Prize":
            continue
        target = share_image_target(job)
        if target in owners:
            raise BuildFailure(f"duplicate share image target={target} routes={owners[target]},{job.route}")
        owners[target] = job.route
        if job.language is None:
            raise BuildFailure(f"share image has no language route={job.route}")
        _write_share_image(output / target, fonts, public_url(base_url, job.route), card, job.language)


def _environment(website_dir: Path) -> Environment:
    environment = Environment(
        loader=FileSystemLoader(website_dir / "templates"),
        autoescape=select_autoescape(("html", "xml")),
        undefined=StrictUndefined,
    )
    environment.filters["slugify"] = slugify
    environment.globals["built"] = datetime.datetime.now(tz=datetime.UTC).date().isoformat()
    for name in TEMPLATES:
        environment.get_template(name)
    return environment


def _language_routes(language: Language) -> dict[str, str]:
    return {
        "awards_route": language.route(language.segment("awards")),
        "people_route": language.route(language.segment("people")),
        "countries_route": language.route(language.segment("countries")),
        "cities_route": language.route(language.segment("countries"), language.segment("cities")),
        "cities_per_capita_route": language.route(language.segment("countries"), language.segment("cities-per-capita")),
        "country_affiliations_route": language.route(language.segment("countries"), language.segment("country_affiliations")),
        "affiliations_route": language.route(language.segment("affiliations")),
        "universities_route": language.route(language.segment("universities")),
        "university_countries_route": language.route(language.segment("universities"), language.segment("countries")),
        "subjects_route": language.route(language.segment("subjects")),
        "explorer_route": language.route(language.segment("explorer")),
        "nearby_route": language.route(language.segment("nearby")),
        "map_route": language.route(language.segment("map")),
        "about_route": language.route(language.segment("about")),
    }


def _localized_place_label(language: Language, place: Place | AffiliationCountry) -> str:
    if city := getattr(place, "city", ""):
        return language.city_label(city, getattr(place, "country", ""))
    return language.term("country", place.name)


def _localized_subject(language: Language, subject: Subject) -> Subject:
    return replace(
        subject,
        affiliations=tuple(
            replace(row, place=_localized_location_label(language, row.city, row.country))
            if row.city or row.country
            else row
            for row in subject.affiliations
        ),
    )


def _localized_ranked_affiliation(language: Language, row: RankedAffiliation) -> RankedAffiliation:
    if not row.city and not row.country:
        return row
    return replace(row, place=_localized_location_label(language, row.city, row.country))


def _localized_affiliation_country(language: Language, place: AffiliationCountry) -> AffiliationCountry:
    return replace(place, members=tuple(_localized_ranked_affiliation(language, row) for row in place.members))


def _localized_fact(language: Language, fact: Fact) -> Fact:
    value = fact.value
    if fact.kind == "laureate_type":
        value = language.term("laureate_type", value)
    elif fact.kind in {"birth_country", "death_country"}:
        value = language.term("country", value)
    elif fact.kind == "citizenship_countries":
        value = "; ".join(language.term("country", country.strip()) for country in value.split(";") if country.strip())
    return Fact(fact.kind, language.text(f"fact.{fact.kind}"), value, fact.route)


def _route_maps(plan: SitePlan) -> dict[str, dict[str, str]]:
    routes = {code: {} for code in LANGUAGE_CODES}
    for job in plan.jobs:
        if job.language is None:
            raise BuildFailure(f"page has no language route={job.route}")
        canonical = job.context.get("_canonical_route")
        if not isinstance(canonical, str):
            raise BuildFailure(f"page has no canonical route key={job.key}")
        routes[job.language.code][canonical] = job.route
    return routes


def _alternates(plan: SitePlan) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for job in plan.jobs:
        result.setdefault(job.key, {})[job.language.code if job.language else ""] = job.route
    for key, entries in result.items():
        if set(entries) != set(LANGUAGE_CODES):
            raise BuildFailure(f"locale parity key={key} languages={','.join(sorted(entries))}")
    return result


def _render_job(
    environment: Environment,
    staging: Path,
    base_url: str,
    corrections_email: str,
    job: PageJob,
    route_map: Mapping[str, str] | None = None,
    alternates: Mapping[str, str] | None = None,
) -> str:
    language = job.language
    if language is None:
        raise BuildFailure(f"page has no language route={job.route}")
    route_map = route_map or {}
    alternates = alternates or {}

    def href(target: str) -> str:
        if not target or urlsplit(target).scheme:
            return target
        if target.startswith("."):
            return target
        return relative_route(job.route, route_map.get(target, target))

    def absolute_href(target: str) -> str:
        return public_url(base_url, route_map.get(target, target))

    context = dict(job.context)
    if totals := context.get("totals"):
        context["totals"] = tuple(
            (format_number(int(value.replace(",", "")), language) if value.replace(",", "").isdigit() else value, label)
            for value, label in totals
        )
    if facts := context.get("facts"):
        context["facts"] = tuple(_localized_fact(language, fact) for fact in facts)
    if job.template == "subject_affiliations.html":
        context["subject"] = _localized_subject(language, context["subject"])
    elif job.template == "affiliation_country.html":
        context["place"] = _localized_affiliation_country(language, context["place"])
    elif job.template == "university_countries.html":
        context["countries"] = tuple(_localized_affiliation_country(language, place) for place in context["countries"])
    if job.template == "explorer.html":
        context["payload"] = explorer_json(localized_explorer_payload(json.loads(context["payload"]), language, route_map))
    elif job.template == "map.html":
        context["payload"] = map_json(localized_map_payload(json.loads(context["payload"]), language))
    elif job.template == "nearby.html":
        context["payload"] = map_json(localized_nearby_payload(json.loads(context["payload"]), language, route_map))
    routes = _language_routes(language)
    country_views = (
        {"key": "born", "label": language.text("view.born"), "route": routes["countries_route"]},
        {"key": "awarded", "label": language.text("view.awarded"), "route": language.route(language.segment("countries"), language.segment("awarded"))},
        {"key": "died", "label": language.text("view.died"), "route": language.route(language.segment("countries"), language.segment("died"))},
    )
    if job.key == "home":
        context["hero_heading"] = language.text("home.hero_heading", more_count=format_number(len(context["prizes"]) - 1, language))
    elif job.key == "awards":
        context["heading"] = language.text("awards.heading")
    elif job.template == "countries.html":
        view = context["tab"]
        places = context["countries"]
        fields = {"person_count": format_number(_country_index_people(places), language), "place_count": format_number(len(places), language)}
        context["eyebrow"] = language.text(f"countries.{view}.eyebrow")
        context["blurb"] = language.text(f"countries.{view}.blurb", **fields)
        context["caveat"] = language.text(f"countries.{view}.caveat")
    elif job.template == "country.html":
        view = context["tab"]
        fields = {"person_count": format_number(len(context["place"].people), language)}
        context["eyebrow"] = language.text(f"country.{view}.eyebrow")
        context["blurb"] = language.text(f"country.{view}.blurb", **fields)
        context["return_label"] = language.text("common.all_cities" if view == "cities" else "common.all_countries")
    target_directory = staging / job.route.strip("/")
    target_directory.mkdir(parents=True, exist_ok=True)
    template = environment.get_template(job.template)
    page_url = public_url(base_url, job.route)
    html = template.render(
        title=job.title,
        description=job.description,
        share_description=share_description(job),
        canonical=page_url,
        share_image=public_url(base_url, f"/{share_image_target(job)}"),
        share_image_width=SHARE_IMAGE_WIDTH,
        share_image_height=SHARE_IMAGE_HEIGHT,
        breadcrumbs=job.breadcrumbs,
        home_href=relative_route(job.route, language.route()),
        favicon_href=relative_file(job.route, "favicon.svg"),
        style_href=relative_file(job.route, "static/style.css"),
        csv_href=relative_file(job.route, "awards.csv"),
        asset_href=lambda target: relative_file(job.route, target) if target else "",
        country_views=country_views,
        structured_data=_structured_data(base_url, job, route_map),
        href=href,
        absolute_href=absolute_href,
        alternates=dict(alternates),
        alternate_hrefs={code: relative_route(job.route, route) for code, route in alternates.items()},
        alternate_urls={code: public_url(base_url, route) for code, route in alternates.items()},
        language=language,
        language_names=LANGUAGE_NAMES,
        language_routes=routes,
        route=job.route,
        stable_key=job.key,
        is_city=job.key.startswith("city:"),
        t=lambda key, **fields: language.text(key, **fields),
        pattern=language.pattern,
        browser_t=language.pattern,
        term=language.term,
        ranking_blurb=language.ranking_blurb,
        entity_label=language.entity_label,
        city_label=language.city_label,
        place_label=lambda place: _localized_place_label(language, place),
        format_number=lambda value, digits=None: format_number(value, language, digits),
        correction_href=lambda record_id="": correction_mailto(corrections_email, page_url, record_id),
        **routes,
        **context,
    )
    (target_directory / "index.html").write_text(html, encoding="utf-8")
    return job.route


def render_error_page(environment: Environment, output: Path, base_url: str, language: Language) -> None:
    """Render /404.html.

    Every other page links relatively, which the server resolves against the file's own directory. The error page is
    served for arbitrary request URLs, so its links must be absolute from the deployment root instead.
    """
    root = urlsplit(base_url).path
    routes = _language_routes(language)
    description = language.text("meta.error.description")
    html = environment.get_template("404.html").render(
        title=language.text("meta.error.title"),
        description=description,
        share_description=description,
        canonical="",
        share_image=public_url(base_url, f"/{SHARE_IMAGE_FALLBACK}"),
        share_image_width=SHARE_IMAGE_WIDTH,
        share_image_height=SHARE_IMAGE_HEIGHT,
        breadcrumbs=(),
        home_href=root,
        favicon_href=root + "favicon.svg",
        style_href=root + "static/style.css",
        csv_href=root + "awards.csv",
        country_views=(),
        structured_data="",
        href=lambda target: root + target.lstrip("/"),
        absolute_href=lambda target: public_url(base_url, target),
        alternates={},
        alternate_urls={},
        language=language,
        language_names=LANGUAGE_NAMES,
        language_routes=routes,
        route="/404.html",
        stable_key="",
        is_city=False,
        t=lambda key, **fields: language.text(key, **fields),
        pattern=language.pattern,
        browser_t=language.pattern,
        term=language.term,
        ranking_blurb=language.ranking_blurb,
        entity_label=language.entity_label,
        city_label=language.city_label,
        place_label=lambda place: _localized_place_label(language, place),
        format_number=lambda value, digits=None: format_number(value, language, digits),
        correction_href=lambda record_id="": "",  # The served URL is unknown at build time, so there is nothing to report against.
        **routes,
    )
    (output / "404.html").write_text(html, encoding="utf-8")


def _make_world_readable(root: Path) -> None:
    for path in (root, *root.rglob("*")):
        path.chmod(0o2775 if path.is_dir() else 0o644)


def _promote(staging: Path, dist: Path) -> None:
    if dist.exists():
        shutil.rmtree(dist)
    staging.rename(dist)


def build_site(database: Path, base_url: str, website_dir: Path = SCRIPT_DIR) -> SitePlan:
    normalized_base_url = normalize_base_url(base_url)
    corrections_email = read_env(website_dir.parent / ".env").get("CORRECTIONS_EMAIL", "")
    print(f"website build config corrections_email={corrections_email or '(unset)'}")
    rankings, profiles, records = read_database(database)
    generated = datetime.datetime.fromtimestamp(database.stat().st_mtime, tz=datetime.UTC).date().isoformat()
    languages = load_languages(rankings, records, website_dir / "i18n")
    plan = create_multilingual_site_plan(rankings, records, normalized_base_url, generated, languages, profiles)
    route_maps = _route_maps(plan)
    alternate_maps = _alternates(plan)
    environment = _environment(website_dir)
    staging = Path(tempfile.mkdtemp(prefix=".dist-staging-", dir=website_dir))
    staging.chmod(0o2775)
    dist = website_dir / "dist"
    try:
        shutil.copytree(website_dir / "static", staging / "static")
        shutil.copyfile(website_dir / "static" / "favicon.svg", staging / "favicon.svg")
        write_share_images(staging, normalized_base_url, plan.jobs)
        with ThreadPoolExecutor(max_workers=8) as executor:
            rendered = executor.map(
                lambda job: _render_job(
                    environment,
                    staging,
                    normalized_base_url,
                    corrections_email,
                    job,
                    route_maps[job.language.code],
                    alternate_maps[job.key],
                ),
                plan.jobs,
            )
            list(rendered)
        write_sitemaps(staging, (job.route for job in plan.jobs), normalized_base_url)
        write_robots(staging, normalized_base_url)
        write_dataset_csv(staging, records)
        for language in languages:
            write_llms_txt(staging, normalized_base_url, plan, rankings, language)
        render_error_page(environment, staging, normalized_base_url, languages[0])
        _make_world_readable(staging)
        _promote(staging, dist)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return plan


def build_home_page(database: Path, base_url: str, website_dir: Path = SCRIPT_DIR) -> None:
    """Update the homepage in an existing site build without rewriting every generated file."""
    normalized_base_url = normalize_base_url(base_url)
    output = website_dir / "dist"
    if not output.is_dir():
        raise BuildFailure("website/dist is missing; run a full website build first")
    corrections_email = read_env(website_dir.parent / ".env").get("CORRECTIONS_EMAIL", "")
    rankings, profiles, records = read_database(database)
    generated = datetime.datetime.fromtimestamp(database.stat().st_mtime, tz=datetime.UTC).date().isoformat()
    languages = load_languages(rankings, records, website_dir / "i18n")
    plan = create_multilingual_site_plan(rankings, records, normalized_base_url, generated, languages, profiles)
    route_maps = _route_maps(plan)
    alternate_maps = _alternates(plan)
    home = next(job for job in plan.jobs if job.key == "home" and job.language and job.language.code == "en")
    _render_job(
        _environment(website_dir),
        output,
        normalized_base_url,
        corrections_email,
        home,
        route_maps["en"],
        alternate_maps["home"],
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--database", type=Path, default=DATASET_DIR / "awards.sqlite3")
    parser.add_argument("--home-only", action="store_true", help="update website/dist/index.html only")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.home_only:
            build_home_page(args.database.resolve(), args.base_url)
            print("website home page complete")
            return 0
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
