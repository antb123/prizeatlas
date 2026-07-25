# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "jinja2==3.1.6",
# ]
# ///
"""Build the static awards website from awards.sqlite3."""

from __future__ import annotations

import argparse
import posixpath
import re
import shutil
import sqlite3
import sys
import tempfile
import unicodedata
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlsplit, urlunsplit
from xml.sax.saxutils import escape as xml_escape

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

SCRIPT_DIR = Path(__file__).resolve().parent
DATASET_DIR = SCRIPT_DIR.parent
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
YEAR_PREFIX = re.compile(r"([0-9]{4})")
SITEMAP_URL_LIMIT = 50_000
SITEMAP_BYTE_LIMIT = 52_428_800
TEMPLATES = (
    "base.html",
    "index.html",
    "prize.html",
    "category.html",
    "year.html",
    "winner.html",
    "person.html",
    "people.html",
    "404.html",
)
PEOPLE_ROUTE = "/people/"
PEOPLE_PER_PAGE = 200
PRIZE_PAGE_YEARS = 30
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
    "citizenship_countries",
    "affiliation_name",
    "affiliation_city",
    "affiliation_country",
    "death_date",
    "death_city",
    "death_country",
    "biographical_note",
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
    citizenship_countries: str
    affiliation_name: str
    affiliation_city: str
    affiliation_country: str
    death_date: str
    death_city: str
    death_country: str
    biographical_note: str


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


@dataclass(frozen=True, slots=True)
class SitePlan:
    jobs: tuple[PageJob, ...]
    prize_count: int
    category_count: int
    year_count: int
    winner_count: int
    recipient_count: int
    person_count: int


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", errors="ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    if not slug:
        raise BuildFailure("derived slug is empty")
    return slug


def normalize_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
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


def read_database(database: Path) -> tuple[list[Ranking], list[AwardRecord]]:
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
        award_rows = connection.execute(f"SELECT {', '.join(AWARD_COLUMNS)} FROM awards").fetchall()
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
        )
        for row in ranking_rows
    ]
    records = [AwardRecord(*(_text(row[field.name]) for field in fields(AwardRecord))) for row in award_rows]
    return rankings, records


def _page(
    template: str,
    route: str,
    title: str,
    description: str,
    breadcrumbs: Iterable[Breadcrumb],
    **context: Any,
) -> PageJob:
    return PageJob(template, route, title, description, tuple(breadcrumbs), context)


def _by_motivation(pairs: Iterable[tuple[AwardRecord, str]]) -> tuple[tuple[str, tuple[tuple[AwardRecord, str], ...]], ...]:
    """Collapse recipients who share one citation into a single group.

    A shared prize carries one motivation for every recipient. Printing it under each name repeats the same sentence
    two or three times per year. Groups keep the order in which their first recipient appeared.
    """
    groups: dict[str, list[tuple[AwardRecord, str]]] = {}
    for record, route in pairs:
        groups.setdefault(record.motivation, []).append((record, route))
    return tuple((motivation, tuple(members)) for motivation, members in groups.items())


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


def plan_people(records: list[AwardRecord], routes: dict[str, str], record_routes: dict[str, str]) -> list[Laureate]:
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
        )
        for qid, awards in grouped.items()
    ]
    people.sort(key=lambda person: _surname_key(person.name))
    return people


def create_site_plan(rankings: list[Ranking], records: list[AwardRecord], base_url: str) -> SitePlan:
    if not rankings or not records:
        raise BuildFailure("ranking or awards table is empty")

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

    live_names: dict[str, str] = {}
    records_by_qid: dict[str, list[AwardRecord]] = {}
    seen_record_ids: set[str] = set()
    for record in records:
        if not record.award_record_id or record.award_record_id in seen_record_ids:
            raise BuildFailure("missing or duplicate award record ID")
        seen_record_ids.add(record.award_record_id)
        if not _nonblank(record.full_name):
            raise BuildFailure(f"missing winner name record_id={record.award_record_id}")
        _year_prefix(record.year, record.award_record_id)
        previous_name = live_names.setdefault(record.award_wikidata_qid, record.prize_name)
        if previous_name != record.prize_name:
            raise BuildFailure(f"inconsistent prize name qid={record.award_wikidata_qid}")
        records_by_qid.setdefault(record.award_wikidata_qid, []).append(record)

    if set(ranking_by_qid) != set(live_names):
        raise BuildFailure("ranking rows do not match live awards")
    for qid, prize_name in live_names.items():
        if ranking_by_qid[qid].prize_name != prize_name:
            raise BuildFailure(f"ranking prize mismatch qid={qid}")

    rankings = sorted(rankings, key=lambda ranking: ranking.score, reverse=True)
    jobs: list[PageJob] = []
    prize_routes = {ranking.qid: f"/{ranking.slug}/" for ranking in rankings}
    jobs.append(
        _page(
            "index.html",
            "/",
            "Prestigious Awards and Winners",
            "Ranked international prizes and winners whose work has made a proven impact on human knowledge.",
            (),
            prizes=tuple((ranking, prize_routes[ranking.qid]) for ranking in rankings),
        )
    )

    category_page_count = 0
    year_page_count = 0
    winner_page_count = 0
    all_record_routes: dict[str, str] = {}
    routes_by_laureate = person_routes(records)

    for ranking in rankings:
        prize_records = records_by_qid[ranking.qid]
        categories = {record.category for record in prize_records if _nonblank(record.category)}
        routed_categories = len(categories) > 1
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
            parent_route = prize_routes[ranking.qid]
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

        for key, grouped_records in year_records.items():
            winner_slugs: dict[str, str] = {}
            for record in grouped_records:
                winner_slug = slugify(record.full_name)
                if winner_slug in winner_slugs:
                    raise BuildFailure(f"duplicate winner slug record_id={record.award_record_id}")
                winner_slugs[winner_slug] = record.award_record_id
                all_record_routes[record.award_record_id] = year_routes[key] + f"{winner_slug}/"

        category_links: list[tuple[str, str]] = []
        if routed_categories:
            for category in sorted(categories):
                category_route = prize_routes[ranking.qid] + f"{category_slugs[category]}/"
                category_links.append((category, category_route))
                category_years = [
                    (
                        year,
                        year_routes[(category, year)],
                        _year_prefix(year, grouped[0].award_record_id),
                        _by_motivation(
                            (record, all_record_routes[record.award_record_id])
                            for record in sorted(grouped, key=lambda item: item.award_record_id)
                        ),
                    )
                    for (record_category, year), grouped in year_records.items()
                    if record_category == category
                ]
                category_years.sort(key=lambda item: item[0], reverse=True)
                category_years.sort(key=lambda item: item[2], reverse=True)
                title = f"{ranking.prize_name} for {category}: Winners by Year"
                jobs.append(
                    _page(
                        "category.html",
                        category_route,
                        title,
                        f"Explore {ranking.prize_name} for {category} winners by year.",
                        (
                            Breadcrumb("Home", "/"),
                            Breadcrumb(ranking.prize_name, prize_routes[ranking.qid]),
                            Breadcrumb(category, None),
                        ),
                        prize=ranking,
                        category=category,
                        years=tuple(category_years),
                    )
                )
                category_page_count += 1

        direct_years: list[tuple[str, str, int]] = []
        if not routed_categories:
            direct_years = [
                (year, route, _year_prefix(year, year_records[(None, year)][0].award_record_id))
                for (category, year), route in year_routes.items()
                if category is None
            ]
            direct_years.sort(key=lambda item: item[0], reverse=True)
            direct_years.sort(key=lambda item: item[2], reverse=True)

        # Adjacent award years within one category, so a year page is never a dead end.
        neighbours: dict[tuple[str | None, str], tuple[tuple[str, str] | None, tuple[str, str] | None]] = {}
        years_by_category: dict[str | None, list[tuple[int, str, str]]] = {}
        for (category_key, year), route in year_routes.items():
            prefix = _year_prefix(year, year_records[(category_key, year)][0].award_record_id)
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

        ordered_records = _descending_records(prize_records)
        recent_prefixes = {
            _year_prefix(record.year, record.award_record_id)
            for record in ordered_records
        }
        recent_prefixes = set(sorted(recent_prefixes, reverse=True)[:PRIZE_PAGE_YEARS])
        recent = [record for record in ordered_records if _year_prefix(record.year, record.award_record_id) in recent_prefixes]

        def group_prize_records(group: list[AwardRecord]) -> tuple[tuple[str, tuple[tuple[AwardRecord, str], ...]], ...]:
            result: list[tuple[str, tuple[tuple[AwardRecord, str], ...]]] = []
            for record in group:
                if result and result[-1][0] == record.year:
                    prior = result[-1][1] + ((record, all_record_routes[record.award_record_id]),)
                    result[-1] = (record.year, prior)
                else:
                    result.append((record.year, ((record, all_record_routes[record.award_record_id]),)))
            return tuple(result)

        prize_title = f"{ranking.prize_name}: Winners by Year"
        jobs.append(
            _page(
                "prize.html",
                prize_routes[ranking.qid],
                prize_title,
                f"Explore {ranking.prize_name} winners, categories, years, and award information.",
                (Breadcrumb("Home", "/"), Breadcrumb(ranking.prize_name, None)),
                prize=ranking,
                routed_categories=routed_categories,
                category_links=tuple(category_links),
                year_links=tuple(direct_years),
                recent_groups=group_prize_records(recent),
                recent_years=PRIZE_PAGE_YEARS,
            )
        )

        for (routed_category, year), grouped_records in year_records.items():
            route = year_routes[(routed_category, year)]
            display_category = next((record.category for record in grouped_records if _nonblank(record.category)), "")
            if display_category:
                title = f"{ranking.prize_name} for {display_category} {year}: Winners"
                description = f"Meet the {ranking.prize_name} for {display_category} winners in {year}."
            else:
                title = f"{ranking.prize_name} {year}: Winners"
                description = f"Meet the {ranking.prize_name} winners in {year}."
            crumbs = [Breadcrumb("Home", "/"), Breadcrumb(ranking.prize_name, prize_routes[ranking.qid])]
            if routed_category is not None:
                crumbs.append(Breadcrumb(routed_category, prize_routes[ranking.qid] + f"{category_slugs[routed_category]}/"))
            crumbs.append(Breadcrumb(year, None))
            ordered_group = sorted(grouped_records, key=lambda record: record.award_record_id)
            jobs.append(
                _page(
                    "year.html",
                    route,
                    title,
                    description,
                    crumbs,
                    prize=ranking,
                    category=display_category,
                    year=year,
                    winners=_by_motivation((record, all_record_routes[record.award_record_id]) for record in ordered_group),
                    earlier_year=neighbours[(routed_category, year)][0],
                    later_year=neighbours[(routed_category, year)][1],
                )
            )
            year_page_count += 1

            for record in ordered_group:
                if _nonblank(record.category):
                    winner_title = f"{ranking.prize_name} for {record.category} {record.year} — {record.full_name}"
                    winner_description = (
                        f"{record.full_name}, winner of the {ranking.prize_name} for {record.category} in {record.year}."
                    )
                else:
                    winner_title = f"{ranking.prize_name} {record.year} — {record.full_name}"
                    winner_description = f"{record.full_name}, winner of the {ranking.prize_name} in {record.year}."
                winner_crumbs = [
                    Breadcrumb("Home", "/"),
                    Breadcrumb(ranking.prize_name, prize_routes[ranking.qid]),
                ]
                if routed_category is not None:
                    winner_crumbs.append(
                        Breadcrumb(routed_category, prize_routes[ranking.qid] + f"{category_slugs[routed_category]}/")
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
                        all_record_routes[record.award_record_id],
                        winner_title,
                        winner_description,
                        winner_crumbs,
                        prize=ranking,
                        record=record,
                        facts=facts,
                        year_route=route,
                        co_laureates=tuple(
                            (other, all_record_routes[other.award_record_id])
                            for other in ordered_group
                            if other.award_record_id != record.award_record_id
                        ),
                        person_route=routes_by_laureate.get(record.laureate_wikidata_qid, ""),
                        wikipedia_url=wikipedia_search_url(record.full_name),
                    )
                )
                winner_page_count += 1

    people = plan_people(records, routes_by_laureate, all_record_routes)
    for person in people:
        jobs.append(
            _page(
                "person.html",
                person.route,
                f"{person.name}: awards and recognition",
                f"Every recorded award won by {person.name}, with the year, category, and citation for each.",
                (Breadcrumb("Home", "/"), Breadcrumb("People", PEOPLE_ROUTE), Breadcrumb(person.name, None)),
                person=person,
            )
        )

    page_count = max(1, -(-len(people) // PEOPLE_PER_PAGE))
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

    routes = [job.route for job in jobs]
    if len(routes) != len(set(routes)):
        raise BuildFailure("duplicate public route")
    return SitePlan(
        tuple(jobs),
        len(rankings),
        category_page_count,
        year_page_count,
        winner_page_count,
        len(records),
        len(people),
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


def _environment(website_dir: Path) -> Environment:
    environment = Environment(
        loader=FileSystemLoader(website_dir / "templates"),
        autoescape=select_autoescape(("html", "xml")),
        undefined=StrictUndefined,
    )
    for name in TEMPLATES:
        environment.get_template(name)
    return environment


def _render_job(environment: Environment, staging: Path, base_url: str, job: PageJob) -> str:
    target_directory = staging / job.route.strip("/")
    target_directory.mkdir(parents=True, exist_ok=True)
    template = environment.get_template(job.template)
    html = template.render(
        title=job.title,
        description=job.description,
        canonical=public_url(base_url, job.route),
        breadcrumbs=job.breadcrumbs,
        home_href=relative_route(job.route, "/"),
        favicon_href=relative_file(job.route, "favicon.svg"),
        style_href=relative_file(job.route, "static/style.css"),
        people_route=PEOPLE_ROUTE,
        href=lambda target: relative_route(job.route, target),
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
        people_route=PEOPLE_ROUTE,
        href=lambda target: root + target.lstrip("/"),
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
    rankings, records = read_database(database)
    plan = create_site_plan(rankings, records, normalized_base_url)
    environment = _environment(website_dir)
    staging = Path(tempfile.mkdtemp(prefix=".dist-staging-", dir=website_dir))
    dist = website_dir / "dist"
    try:
        (staging / "static").mkdir()
        shutil.copyfile(website_dir / "static" / "favicon.svg", staging / "favicon.svg")
        shutil.copyfile(website_dir / "static" / "style.css", staging / "static" / "style.css")
        with ThreadPoolExecutor(max_workers=8) as executor:
            rendered = executor.map(
                lambda job: _render_job(environment, staging, normalized_base_url, job),
                plan.jobs,
            )
            list(rendered)
        write_sitemaps(staging, (job.route for job in plan.jobs), normalized_base_url)
        write_robots(staging, normalized_base_url)
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
        f"winner_pages={plan.winner_count} people={plan.person_count} recipients={plan.recipient_count} "
        f"sitemap_urls={len(plan.jobs)} generated_pages={len(plan.jobs)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
