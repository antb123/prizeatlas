#!/usr/bin/env python3
"""Collapse affiliation names that are one institution written several ways, and roll constituent units into their parent.

"Massachusetts Institute of Technology" and "Massachusetts Institute of Technology (MIT)" are the same place, and a
ranking that treats them as two puts MIT at 40 when it should be at 64. "Harvard Medical School" is not a different
institution from Harvard either — it is part of it — so it rolls up into "Harvard University" while the unit itself is
kept in affiliation_sub_name and shown, never ranked.

Only names frequent enough to reach a top-N view are mapped; the several hundred that appear once are left alone,
because resolving those needs judgement no text rule supplies.

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

# source -> (canonical name, sub-name). An empty sub-name is a pure spelling alias; a non-empty one means the source
# named a constituent unit, which rolls up into the parent with the unit preserved beside it.
#
# Written out rather than derived: a rule that strips a trailing comma clause would also merge
# "University of California, Berkeley" into "University of California", which are genuinely different places, and a
# rule that merged on "School of" would swallow the sixteen institutions listed under NOT MERGED below.
#
# NOT MERGED — deliberately standalone. Recorded here so a later reader does not "fix" them:
#   London School of Economics (+ ...and Political Science)  constituent of the University of London, but universally
#                                                            ranked as its own institution
#   Stockholm School of Economics                            independent
#   The Netherlands School of Economics                      independent; later folded into Erasmus University, which
#                                                            is not the same entity as at award time
#   Toulouse School of Economics (TSE)                       grande école, ranked standalone
#   Baylor College of Medicine                               separated from Baylor University in 1969
#   New York Medical College                                 independent
#   Albert Einstein College of Medicine                      left Yeshiva University; independent
#   Medical College of Georgia                               parent (Augusta University) absent from the data
#   Jefferson Medical College                                parent (Thomas Jefferson University) absent from the data
#   Department of Scientific and Industrial Research         UK government body, not a university unit
#   Bureau of Public Health Nursing ... Dept of Health       government body
#   Research Division of Infectious Diseases, Children's...  hospital unit, no university parent
#   École municipale de physique et de chimie industrielles  ESPCI Paris, standalone
#   Max-Planck-Institut für Züchtungsforschung, Dept of ...  research institute, not a university
#   CSIRO, Division of Marine Research                       government research agency
#   Laboratories of the Division of Medicine..., Rockefeller foundation, not a university
#   St. Petersburg Department of the Steklov Institute       research institute
#
# Hospitals stay standalone even when closely tied to a university: Massachusetts General, Brigham and Women's,
# Mayo Clinic and St. Jude are legally independent of the schools they teach for.
AFFILIATIONS = {
    # --- spelling and punctuation ---
    "Massachusetts Institute of Technology (MIT)": ("Massachusetts Institute of Technology", ""),
    "Massachusetts Institute of Technology (MIT), USA": ("Massachusetts Institute of Technology", ""),
    "Massachusetts Institute of Technology, Cambridge": ("Massachusetts Institute of Technology", ""),
    "California Institute of Technology (Caltech)": ("California Institute of Technology", ""),
    "The Rockefeller University": ("Rockefeller University", ""),
    "Harvard University, USA": ("Harvard University", ""),
    "Princeton University, USA": ("Princeton University", ""),
    "Princeton University, Princeton": ("Princeton University", ""),
    "Stanford University, USA": ("Stanford University", ""),
    "Stanford University, Stanford": ("Stanford University", ""),
    "Columbia University, USA": ("Columbia University", ""),
    "University of Chicago, USA": ("University of Chicago", ""),
    "University of Cambridge, UK": ("University of Cambridge", ""),
    "University of Oxford, UK": ("University of Oxford", ""),
    "Institute for Advanced Study, USA": ("Institute for Advanced Study", ""),
    "Institute for Advanced Study, Princeton": ("Institute for Advanced Study", ""),
    # The Institute for Advanced Study sits in Princeton but is independent of the university; the source claims it
    # as Princeton's. Kyoto University's own Institute for Advanced Study is a different place and stays separate.
    "Princeton University's Institute for Advanced Studies, USA": ("Institute for Advanced Study", ""),
    "Hebrew University of Jerusalem, Israel": ("Hebrew University of Jerusalem", ""),
    "Collège de France, France": ("Collège de France", ""),
    "University of Toronto, Canada": ("University of Toronto", ""),
    "University of Washington, Seattle": ("University of Washington", ""),
    "Institut des Hautes Études Scientifiques, France": ("Institut des Hautes Études Scientifiques", ""),
    "Institut des Hautes Études Scientifiques, Bures-sur-Yvette": ("Institut des Hautes Études Scientifiques", ""),
    "NIH": ("National Institutes of Health", ""),
    "NIH, National Institutes of Health": ("National Institutes of Health", ""),
    # No campus is named, and inventing one would be fabrication. Labelled so a reader can see the gap.
    "University of California": ("University of California (campus unspecified)", ""),
    # Confirmed by hand from --suggest output. Case, punctuation, and one misspelling.
    "Université Libre de Bruxelles": ("Université libre de Bruxelles", ""),
    "University of Washighton": ("University of Washington", ""),
    "University of California at Berkeley": ("University of California, Berkeley", ""),
    "Karolinska Institute": ("Karolinska Institutet", ""),
    "Technion - Israel Institute of Technology": ("Technion – Israel Institute of Technology", ""),
    "Technion-Israel Institute of Technology": ("Technion – Israel Institute of Technology", ""),
    "Memorial Sloan Kettering Cancer Center": ("Memorial Sloan-Kettering Cancer Center", ""),
    "Brigham and Women's Hospital": ("Brigham and Women’s Hospital", ""),
    "University of Illinois at Urbana-Champaign": ("University of Illinois at Urbana–Champaign", ""),
    "University of Colorado Boulder": ("University of Colorado, Boulder", ""),
    "University College, London": ("University College London", ""),
    "University College of London": ("University College London", ""),
    "Salk Institute of Biological Studies": ("Salk Institute for Biological Studies", ""),
    "Basel Institute of Immunology": ("Basel Institute for Immunology", ""),
    "National Institute of Information and Communications Technology (NICT)": ("National Institute of Information and Communications Technology", ""),
    "Kavli Institute for the Physics and Mathematics of the Universe, University of Tokyo, Japan":
        ("Kavli Institute for the Physics and Mathematics of the Universe, University of Tokyo", ""),
    "Institute of Genetics and Molecular Cellular Biology": ("Institute of Genetics and Molecular and Cellular Biology", ""),
    "National Heart, Lung and Blood Institute, National Institutes of Health": ("National Heart, Lung, and Blood Institute, National Institutes of Health", ""),

    # --- constituent units ---
    # The sub-name is the unit's *current* name, not the name as recorded: Cornell's medical college was renamed in
    # 1998 and UMass's in 2021, and bucketing on the recorded spelling would split one school into two units, which
    # is the same fragmentation this table exists to remove. How fully the name is written varies by parent —
    # "Harvard Medical School" reads correctly in full, "School of Medicine" reads correctly under Johns Hopkins.
    "Massachusetts Institute of Technology, Laboratory for Computer Science": ("Massachusetts Institute of Technology", "Laboratory for Computer Science"),
    "Harvard Medical School": ("Harvard University", "Harvard Medical School"),
    "Harvard School of Public Health": ("Harvard University", "Harvard School of Public Health"),
    "Harvard University, Lyman Laboratory": ("Harvard University", "Lyman Laboratory"),
    "Harvard University, Biological Laboratories": ("Harvard University", "Biological Laboratories"),
    "Johns Hopkins University School of Medicine": ("Johns Hopkins University", "School of Medicine"),
    "Johns Hopkins University, School of Medicine": ("Johns Hopkins University", "School of Medicine"),
    "Johns Hopkins University Medical School": ("Johns Hopkins University", "School of Medicine"),
    "Johns Hopkins University, School of Hygiene and Public Health": ("Johns Hopkins University", "School of Hygiene and Public Health"),
    "Johns Hopkins Institute for Cell Engineering": ("Johns Hopkins University", "Institute for Cell Engineering"),
    "McKusick-Nathans Institute of Genetic Medicine at the Johns Hopkins University": ("Johns Hopkins University", "McKusick-Nathans Institute of Genetic Medicine"),
    "Stanford University School of Medicine": ("Stanford University", "School of Medicine"),
    "Stanford University, School of Medicine": ("Stanford University", "School of Medicine"),
    "Department of Biology, Stanford University": ("Stanford University", "Department of Biology"),
    "University of Massachusetts Medical School": ("University of Massachusetts", "UMass Chan Medical School"),
    "UMass Chan Medical School": ("University of Massachusetts", "UMass Chan Medical School"),
    "University of California School of Medicine": ("University of California (campus unspecified)", "School of Medicine"),
    "University of Pennsylvania School of Medicine": ("University of Pennsylvania", "School of Medicine"),
    "Perelman School of Medicine, University of Pennsylvania": ("University of Pennsylvania", "Perelman School of Medicine"),
    "University of Pennsylvania, Department of Landscape Architecture and Regional Planning":
        ("University of Pennsylvania", "Department of Landscape Architecture and Regional Planning"),
    "Cornell University Medical College": ("Cornell University", "Weill Cornell Medical College"),
    "Weill Cornell Medical College": ("Cornell University", "Weill Cornell Medical College"),
    "Emory University School of Medicine": ("Emory University", "School of Medicine"),
    "Emory University Rollins School of Public Health": ("Emory University", "Rollins School of Public Health"),
    "Yale University School of Medicine": ("Yale University", "School of Medicine"),
    "Yale University, School of Medicine": ("Yale University", "School of Medicine"),
    "Yale School of Medicine": ("Yale University", "School of Medicine"),
    "Vanderbilt University School of Medicine": ("Vanderbilt University", "School of Medicine"),
    "Vanderbilt University Medical School": ("Vanderbilt University", "School of Medicine"),
    "University of Washington School of Medicine": ("University of Washington", "School of Medicine"),
    "University of Washington, Department of Atmospheric Sciences": ("University of Washington", "Department of Atmospheric Sciences"),
    "Boston University School of Medicine": ("Boston University", "School of Medicine"),
    "Kobe University School of Medicine": ("Kobe University", "School of Medicine"),
    "Graduate School of Medicine, Osaka University": ("Osaka University", "Graduate School of Medicine"),
    "Graduate School of Frontier Bioscience, Osaka University": ("Osaka University", "Graduate School of Frontier Bioscience"),
    "New York University School of Medicine": ("New York University", "School of Medicine"),
    "New York University, College of Medicine": ("New York University", "School of Medicine"),
    "NYU Stern School of Business": ("New York University", "Stern School of Business"),
    "University of Michigan Medical School": ("University of Michigan", "Medical School"),
    "University of Pittsburgh School of Medicine": ("University of Pittsburgh", "School of Medicine"),
    "University of Utah School of Medicine": ("University of Utah", "School of Medicine"),
    "University of Cincinnati College of Medicine": ("University of Cincinnati", "College of Medicine"),
    "Washington University School of Medicine": ("Washington University", "School of Medicine"),
    "Western Reserve University School of Medicine": ("Western Reserve University", "School of Medicine"),
    "Tufts Medical College": ("Tufts University", "Medical College"),
    "University of Paris School of Medicine": ("University of Paris", "School of Medicine"),
    "Universite de Paris": ("University of Paris", ""),
    # The one matching row already carries this unit; the normalizer owns affiliation_sub_name and writes it
    # unconditionally, so the reviewed mapping must preserve it.
    "Université de Paris": ("University of Paris", "Laboratoire Immuno-Hématologie"),
    "The John Curtin School of Medical Research, The Australian National University": ("Australian National University", "John Curtin School of Medical Research"),
    "University of Nottingham, School of Physics and Astronomy": ("University of Nottingham", "School of Physics and Astronomy"),
    "University of Reading, Department of Meteorology": ("University of Reading", "Department of Meteorology"),
    "University of Ghent, Department of Genetics": ("Ghent University", "Department of Genetics"),
    "University of Maryland, Department of Economics and School of Public Policy": ("University of Maryland", "Department of Economics and School of Public Policy"),
    # Title case: the lowercase "École normale supérieure" does not exist in the database, and SQLite's BINARY
    # collation would make using it a second spelling of the same school.
    "École normale supérieure, Department of Geology": ("École Normale Supérieure", "Department of Geology"),
    "Weizmann Institute of Science, Department of Computer Science and Applied Mathematics":
        ("Weizmann Institute of Science", "Department of Computer Science and Applied Mathematics"),
    "University of California San Diego, School of Medicine, Department of Pediatrics": ("University of California, San Diego", "School of Medicine, Department of Pediatrics"),
    "Ruijin Hospital, School of Medicine, Shanghai Jiao Tong University": ("Shanghai Jiao Tong University", "Ruijin Hospital, School of Medicine"),
}


class NormalizeFailure(Exception):
    """The affiliations cannot be normalized without guessing."""


# One pass is enough, and re-running is a no-op, only because no target is ever also a source. That property is one
# edit away from breaking and the break is silent: "Washington University" is a parent here and is also a spelling
# variant of "Washington University in St. Louis". Alias the one without reading the other and a single run rewrites
# the existing rows, then recreates the old name from the medical school — splitting the institution in two.
_targets = {name for name, _ in AFFILIATIONS.values()}
if _overlap := _targets & set(AFFILIATIONS):
    raise NormalizeFailure(f"affiliation target is also a source: {sorted(_overlap)}")


def counts(database: Path) -> dict[str, int]:
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        rows = connection.execute(
            "SELECT affiliation_name, COUNT(*) FROM awards WHERE affiliation_name <> '' GROUP BY affiliation_name"
        ).fetchall()
    return dict(rows)


def compounds(database: Path) -> int:
    """Rows naming several institutions at once. A separate problem; counted so it is not forgotten."""
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        return connection.execute("SELECT COUNT(*) FROM awards WHERE affiliation_name LIKE '%;%'").fetchone()[0]


def report(present: dict[str, int]) -> list[tuple[str, str, str, int]]:
    """Each mapping with the rows it moves."""
    merged: list[tuple[str, str, str, int]] = []
    for source, (parent, sub_name) in sorted(AFFILIATIONS.items()):
        if moving := present.get(source, 0):
            merged.append((source, parent, sub_name, moving))
    return merged


def suggest(present: dict[str, int], threshold: float) -> list[tuple[float, str, str, int, int]]:
    """Propose mapping candidates for review. Never applies them.

    Fuzzy similarity cannot decide this on its own: "University of Washington" and "Washington University" score above
    0.9 and are different universities in different states, as are the Berkeley and San Diego campuses. This surfaces
    candidates so a person can judge them; only AFFILIATIONS above is ever written.
    """
    known = set(AFFILIATIONS) | _targets
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


def require_column(database: Path) -> None:
    """Fail before the backup, not mid-transaction, when the schema migration has not been run."""
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(awards)")}
    if "affiliation_sub_name" not in columns:
        raise NormalizeFailure("column affiliation_sub_name missing, run the migration")


def back_up(database: Path) -> Path:
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = database.with_name(f"{database.name}.{stamp}.affiliations.bak")
    shutil.copyfile(database, backup)
    return backup


def apply_affiliations(database: Path) -> int:
    connection = sqlite3.connect(database)
    try:
        with connection:
            changed = 0
            for source, (parent, sub_name) in AFFILIATIONS.items():
                # Deliberately unguarded on affiliation_sub_name: the column is derived and owned by this script, so
                # overwriting it is what makes the pass idempotent.
                cursor = connection.execute(
                    "UPDATE awards SET affiliation_name = ?, affiliation_sub_name = ? WHERE affiliation_name = ?",
                    (parent, sub_name, source),
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
                        help="print fuzzy mapping candidates for review and exit; applies nothing")
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
        for source, parent, sub_name, moving in merges:
            kind = "unit " if sub_name else "alias"
            target = f"'{parent}' + '{sub_name}'" if sub_name else f"'{parent}'"
            print(f"affiliations {kind} rows={moving:3d} '{source}' -> {target}")
        unused = sorted(source for source in AFFILIATIONS if source not in present)
        for source in unused:
            print(f"affiliations mapping unused source='{source}'", file=sys.stderr)

        alias_rows = sum(moving for _, _, sub_name, moving in merges if not sub_name)
        unit_rows = sum(moving for _, _, sub_name, moving in merges if sub_name)
        summary = (f"entries={len(AFFILIATIONS)} alias_rows={alias_rows} unit_rows={unit_rows} "
                   f"compound={compounds(args.database)} unused={len(unused)}")
        if not args.apply:
            print(f"affiliations normalize dry-run {summary}")
            return 0

        require_column(args.database)
        backup = back_up(args.database)
        changed = apply_affiliations(args.database)
    except (NormalizeFailure, sqlite3.Error, OSError) as error:
        print(f"affiliations normalize failed: {error}", file=sys.stderr)
        return 1
    print(f"affiliations normalize complete {summary} rows_changed={changed} backup={backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
