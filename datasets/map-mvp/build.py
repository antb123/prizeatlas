#!/usr/bin/env python3
"""Generate the disposable standalone awards map MVP."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sqlite3
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE = ROOT.parent / "awards.sqlite3"
DEFAULT_TEMPLATE = ROOT / "template.html"
DEFAULT_OUTPUT = ROOT / "dist" / "index.html"
YEAR = re.compile(r"^([0-9]{4})")


class BuildError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Point:
    longitude: float
    latitude: float


def parse_points(value: str, record_id: str, field: str, multiple: bool) -> tuple[Point, ...]:
    segments = value.split(";") if multiple else [value]
    if not multiple and ";" in value:
        raise BuildError(f"invalid coordinate record_id={record_id} field={field}")

    points: list[Point] = []
    for segment in segments:
        parts = segment.strip().split(",")
        if len(parts) != 2:
            raise BuildError(f"invalid coordinate record_id={record_id} field={field}")
        try:
            longitude, latitude = (float(part.strip()) for part in parts)
        except ValueError as error:
            raise BuildError(f"invalid coordinate record_id={record_id} field={field}") from error
        if not math.isfinite(longitude) or not math.isfinite(latitude):
            raise BuildError(f"invalid coordinate record_id={record_id} field={field}")
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise BuildError(f"invalid coordinate record_id={record_id} field={field}")
        points.append(Point(longitude, latitude))
    return tuple(points)


def _display_label(kind: str, label: tuple[str, ...]) -> str:
    if kind == "birth":
        city, country = label
        return city or country or "Unnamed birthplace"
    name, city, country = label
    return name or city or country or "Unnamed institution"


def aggregate(rows: list[sqlite3.Row]) -> dict[str, list[dict[str, object]]]:
    groups: dict[str, dict[Point, Counter[tuple[str, ...]]]] = {
        "birth": {},
        "affiliation": {},
    }
    subjects: dict[str, dict[Point, Counter[str]]] = {
        "birth": {},
        "affiliation": {},
    }
    decades: dict[str, dict[Point, Counter[str]]] = {
        "birth": {},
        "affiliation": {},
    }
    subject_decades: dict[str, dict[Point, Counter[tuple[str, str]]]] = {
        "birth": {},
        "affiliation": {},
    }

    for row in rows:
        record_id = row["award_record_id"]
        subject = row["high_school_subject"].strip() or "Other"
        year_match = YEAR.match(row["year"].strip())
        decade = f"{year_match.group(1)[:3]}0s" if year_match else "Unknown"
        birth_coordinates = row["birth_coordinates"].strip()
        if birth_coordinates:
            point = parse_points(birth_coordinates, record_id, "birth_coordinates", multiple=False)[0]
            label = (row["birth_city"].strip(), row["birth_country"].strip())
            groups["birth"].setdefault(point, Counter())[label] += 1
            subjects["birth"].setdefault(point, Counter())[subject] += 1
            decades["birth"].setdefault(point, Counter())[decade] += 1
            subject_decades["birth"].setdefault(point, Counter())[(subject, decade)] += 1

        affiliation_coordinates = row["affiliation_coordinates"].strip()
        if affiliation_coordinates:
            label = (
                row["affiliation_name"].strip(),
                row["affiliation_city"].strip(),
                row["affiliation_country"].strip(),
            )
            for point in parse_points(
                affiliation_coordinates,
                record_id,
                "affiliation_coordinates",
                multiple=True,
            ):
                groups["affiliation"].setdefault(point, Counter())[label] += 1
                subjects["affiliation"].setdefault(point, Counter())[subject] += 1
                decades["affiliation"].setdefault(point, Counter())[decade] += 1
                subject_decades["affiliation"].setdefault(point, Counter())[(subject, decade)] += 1

    result: dict[str, list[dict[str, object]]] = {"birth": [], "affiliation": []}
    for kind, points in groups.items():
        for point, labels in sorted(points.items(), key=lambda item: (item[0].longitude, item[0].latitude)):
            ordered_labels = sorted(labels.items(), key=lambda item: (-item[1], item[0]))
            primary, _ = ordered_labels[0]
            marker: dict[str, object] = {
                "lng": point.longitude,
                "lat": point.latitude,
                "count": sum(labels.values()),
                "title": _display_label(kind, primary),
                "extra_labels": len(labels) - 1,
                "subjects": dict(sorted(subjects[kind][point].items())),
                "decades": dict(sorted(decades[kind][point].items())),
                "subject_decades": {
                    subject: dict(sorted(
                        (decade, count)
                        for (bucket_subject, decade), count in subject_decades[kind][point].items()
                        if bucket_subject == subject
                    ))
                    for subject in sorted(subjects[kind][point])
                },
            }
            if kind == "birth":
                marker["city"], marker["country"] = primary
            else:
                marker["name"], marker["city"], marker["country"] = primary
            result[kind].append(marker)
    return result


def read_markers(database: Path) -> dict[str, list[dict[str, object]]]:
    if not database.is_file():
        raise BuildError(f"database missing path={database}")
    uri = database.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        rows = connection.execute(
            """
            SELECT award_record_id,
                   COALESCE(year, '') AS year,
                   COALESCE(high_school_subject, '') AS high_school_subject,
                   COALESCE(birth_city, '') AS birth_city,
                   COALESCE(birth_country, '') AS birth_country,
                   COALESCE(birth_coordinates, '') AS birth_coordinates,
                   COALESCE(affiliation_name, '') AS affiliation_name,
                   COALESCE(affiliation_city, '') AS affiliation_city,
                   COALESCE(affiliation_country, '') AS affiliation_country,
                   COALESCE(affiliation_coordinates, '') AS affiliation_coordinates
            FROM awards
            ORDER BY award_record_id
            """
        ).fetchall()
    return aggregate(rows)


def compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")


def subject_slug(value: str) -> str:
    return "-".join(re.findall(r"[a-z0-9]+", value.lower()))


def render(template: str, markers: dict[str, list[dict[str, object]]]) -> str:
    placeholder = "__MAP_DATA__"
    if template.count(placeholder) != 1:
        raise BuildError("template must contain exactly one map data placeholder")
    return template.replace(placeholder, compact_json(markers))


def write_atomic(output: Path, document: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=output.parent,
            prefix=".index-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            stream.write(document)
            temporary = Path(stream.name)
        os.replace(temporary, output)
        output.chmod(0o644)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def build(database: Path, template_path: Path, output: Path) -> dict[str, list[dict[str, object]]]:
    markers = read_markers(database)
    document = render(template_path.read_text(encoding="utf-8"), markers)
    write_atomic(output, document)
    subjects = sorted({
        subject
        for kind in markers.values()
        for marker in kind
        for subject in marker["subjects"]
    })
    routes: dict[str, str] = {}
    for subject in subjects:
        slug = subject_slug(subject)
        if not slug or slug in routes:
            raise BuildError(f"subject route collision subject={subject}")
        routes[slug] = subject
        write_atomic(output.parent / slug / "index.html", document)
    return markers


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        markers = build(args.database, args.template, args.output)
    except (BuildError, OSError, sqlite3.Error) as error:
        print(f"map build failed: {error}")
        return 1
    birth_awards = sum(int(marker["count"]) for marker in markers["birth"])
    affiliation_awards = sum(int(marker["count"]) for marker in markers["affiliation"])
    print(
        "map build complete "
        f"birth_locations={len(markers['birth'])} birth_awards={birth_awards} "
        f"affiliation_locations={len(markers['affiliation'])} affiliation_awards={affiliation_awards} "
        f"output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
