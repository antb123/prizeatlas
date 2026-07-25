#!/usr/bin/env python3
"""Collapse affiliation names that are one institution written several ways.

"Massachusetts Institute of Technology" and "Massachusetts Institute of Technology (MIT)" are the same place, and a
ranking that treats them as two puts MIT at 40 when it should be at 64. Only names frequent enough to reach a top-N
view are mapped; the several hundred that appear once are left alone, because resolving those needs judgement no
text rule supplies.

Reports by default and changes nothing. Pass --apply to back up the database and write.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

# Written out rather than derived: a rule that strips a trailing comma clause would also merge
# "University of California, Berkeley" into "University of California", which are genuinely different places.
ALIASES = {
    "Massachusetts Institute of Technology (MIT)": "Massachusetts Institute of Technology",
    "Massachusetts Institute of Technology (MIT), USA": "Massachusetts Institute of Technology",
    "Massachusetts Institute of Technology, Cambridge": "Massachusetts Institute of Technology",
    "California Institute of Technology (Caltech)": "California Institute of Technology",
    "The Rockefeller University": "Rockefeller University",
    "Harvard University, USA": "Harvard University",
    "Princeton University, USA": "Princeton University",
    "Princeton University, Princeton": "Princeton University",
    "Stanford University, USA": "Stanford University",
    "Stanford University, Stanford": "Stanford University",
    "Columbia University, USA": "Columbia University",
    "University of Chicago, USA": "University of Chicago",
    "University of Cambridge, UK": "University of Cambridge",
    "University of Oxford, UK": "University of Oxford",
    "Institute for Advanced Study, USA": "Institute for Advanced Study",
    "Institute for Advanced Study, Princeton": "Institute for Advanced Study",
    "Hebrew University of Jerusalem, Israel": "Hebrew University of Jerusalem",
    "Collège de France, France": "Collège de France",
    "University of Toronto, Canada": "University of Toronto",
    "University of Washington, Seattle": "University of Washington",
    "Institut des Hautes Études Scientifiques, France": "Institut des Hautes Études Scientifiques",
    "Institut des Hautes Études Scientifiques, Bures-sur-Yvette": "Institut des Hautes Études Scientifiques",
    "NIH": "National Institutes of Health",
    "NIH, National Institutes of Health": "National Institutes of Health",
    # No campus is named, and inventing one would be fabrication. Labelled so a reader can see the gap.
    "University of California": "University of California (campus unspecified)",
    # Confirmed by hand from --suggest output. Case, punctuation, and one misspelling.
    "Université Libre de Bruxelles": "Université libre de Bruxelles",
    "University of Washighton": "University of Washington",
    "University of California at Berkeley": "University of California, Berkeley",
    "Karolinska Institute": "Karolinska Institutet",
    "Technion - Israel Institute of Technology": "Technion – Israel Institute of Technology",
    "Technion-Israel Institute of Technology": "Technion – Israel Institute of Technology",
    "Memorial Sloan Kettering Cancer Center": "Memorial Sloan-Kettering Cancer Center",
    "Brigham and Women's Hospital": "Brigham and Women’s Hospital",
    "University of Illinois at Urbana-Champaign": "University of Illinois at Urbana–Champaign",
    "University of Colorado Boulder": "University of Colorado, Boulder",
    "University College, London": "University College London",
    "University College of London": "University College London",
    "Johns Hopkins University, School of Medicine": "Johns Hopkins University School of Medicine",
    "Yale University, School of Medicine": "Yale University School of Medicine",
    "Salk Institute of Biological Studies": "Salk Institute for Biological Studies",
    "Basel Institute of Immunology": "Basel Institute for Immunology",
    "National Institute of Information and Communications Technology (NICT)": "National Institute of Information and Communications Technology",
    "Kavli Institute for the Physics and Mathematics of the Universe, University of Tokyo, Japan": "Kavli Institute for the Physics and Mathematics of the Universe, University of Tokyo",
    "Institute of Genetics and Molecular Cellular Biology": "Institute of Genetics and Molecular and Cellular Biology",
    "National Heart, Lung and Blood Institute, National Institutes of Health": "National Heart, Lung, and Blood Institute, National Institutes of Health",
}


class NormalizeFailure(Exception):
    """The affiliations cannot be normalized without guessing."""


def counts(database: Path) -> dict[str, int]:
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        rows = connection.execute(
            "SELECT affiliation_name, COUNT(*) FROM awards WHERE affiliation_name <> '' GROUP BY affiliation_name"
        ).fetchall()
    return dict(rows)


def report(present: dict[str, int]) -> list[tuple[str, str, int, int]]:
    """Each alias with the rows it moves and the total its target reaches."""
    merged: list[tuple[str, str, int, int]] = []
    for source, target in sorted(ALIASES.items()):
        moving = present.get(source, 0)
        if not moving:
            continue
        merged.append((source, target, moving, present.get(target, 0) + moving))
    return merged


def suggest(present: dict[str, int], threshold: float) -> list[tuple[float, str, str, int, int]]:
    """Propose alias candidates for review. Never applies them.

    Fuzzy similarity cannot decide this on its own: "University of Washington" and "Washington University" score above
    0.9 and are different universities in different states, as are the Berkeley and San Diego campuses. This surfaces
    candidates so a person can judge them; only ALIASES above is ever written.
    """
    known = set(ALIASES) | set(ALIASES.values())
    names = sorted(present)
    candidates: list[tuple[float, str, str, int, int]] = []
    for index, first in enumerate(names):
        for second in names[index + 1 :]:
            if first in known and second in known:
                continue
            # Cheap gate before the quadratic-ish comparison: near-equal lengths, shared opening.
            if abs(len(first) - len(second)) > 25 or first[:4].lower() != second[:4].lower():
                continue
            score = SequenceMatcher(None, first.lower(), second.lower()).ratio()
            if score >= threshold:
                candidates.append((score, first, second, present[first], present[second]))
    candidates.sort(reverse=True)
    return candidates


def back_up(database: Path) -> Path:
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = database.with_name(f"{database.name}.{stamp}.affiliations.bak")
    shutil.copyfile(database, backup)
    return backup


def apply_aliases(database: Path) -> int:
    connection = sqlite3.connect(database)
    try:
        with connection:
            changed = 0
            for source, target in ALIASES.items():
                cursor = connection.execute(
                    "UPDATE awards SET affiliation_name = ? WHERE affiliation_name = ?", (target, source)
                )
                changed += cursor.rowcount
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise NormalizeFailure(f"integrity check failed: {integrity}")
        return changed
    finally:
        connection.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", type=Path, default=Path(__file__).resolve().parents[1] / "awards.sqlite3")
    parser.add_argument("--apply", action="store_true", help="back up the database and write the merged names")
    parser.add_argument("--suggest", type=float, metavar="THRESHOLD", nargs="?", const=0.88,
                        help="print fuzzy alias candidates for review and exit; applies nothing")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        present = counts(args.database)
        if args.suggest is not None:
            for score, first, second, first_rows, second_rows in suggest(present, args.suggest):
                print(f"affiliations candidate score={score:.3f} '{first}' ({first_rows}) ~ '{second}' ({second_rows})")
            return 0
        merges = report(present)
        for source, target, moving, total in merges:
            print(f"affiliations merge rows={moving:3d} total={total:3d} '{source}' -> '{target}'")
        unused = sorted(source for source in ALIASES if source not in present)
        for source in unused:
            print(f"affiliations alias unused source='{source}'", file=sys.stderr)
        if not args.apply:
            print(f"affiliations normalize dry-run aliases={len(merges)} rows={sum(row[2] for row in merges)} unused={len(unused)}")
            return 0
        backup = back_up(args.database)
        changed = apply_aliases(args.database)
    except (NormalizeFailure, sqlite3.Error, OSError) as error:
        print(f"affiliations normalize failed: {error}", file=sys.stderr)
        return 1
    print(f"affiliations normalize complete aliases={len(merges)} rows_changed={changed} backup={backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
