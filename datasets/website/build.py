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
from urllib.parse import urlsplit, urlunsplit
from xml.sax.saxutils import escape as xml_escape

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

SCRIPT_DIR = Path(__file__).resolve().parent
DATASET_DIR = SCRIPT_DIR.parent
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
YEAR_PREFIX = re.compile(r"([0-9]{4})")
SITEMAP_URL_LIMIT = 50_000
SITEMAP_BYTE_LIMIT = 52_428_800
TEMPLATES = ("base.html", "index.html", "prize.html", "category.html", "year.html", "winner.html")
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
class SitePlan:
    jobs: tuple[PageJob, ...]
    prize_count: int
    category_count: int
    year_count: int
    winner_count: int
    recipient_count: int


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
                    (year, year_routes[(category, year)], _year_prefix(year, grouped[0].award_record_id))
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

        ordered_records = _descending_records(prize_records)
        recent_prefixes = {
            _year_prefix(record.year, record.award_record_id)
            for record in ordered_records
        }
        recent_prefixes = set(sorted(recent_prefixes, reverse=True)[:30])
        recent = [record for record in ordered_records if _year_prefix(record.year, record.award_record_id) in recent_prefixes]
        older = [record for record in ordered_records if _year_prefix(record.year, record.award_record_id) not in recent_prefixes]

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
                older_groups=group_prize_records(older),
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
                    winners=tuple((record, all_record_routes[record.award_record_id]) for record in ordered_group),
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
                    )
                )
                winner_page_count += 1

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
        style_href=relative_file(job.route, "static/style.css"),
        href=lambda target: relative_route(job.route, target),
        **job.context,
    )
    (target_directory / "index.html").write_text(html, encoding="utf-8")
    return job.route


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
        shutil.copyfile(website_dir / "static" / "style.css", staging / "static" / "style.css")
        with ThreadPoolExecutor(max_workers=8) as executor:
            rendered = executor.map(
                lambda job: _render_job(environment, staging, normalized_base_url, job),
                plan.jobs,
            )
            list(rendered)
        write_sitemaps(staging, (job.route for job in plan.jobs), normalized_base_url)
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
        f"winner_pages={plan.winner_count} recipients={plan.recipient_count} "
        f"sitemap_urls={len(plan.jobs)} generated_pages={len(plan.jobs)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
