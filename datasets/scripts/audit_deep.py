#!/usr/bin/env python3
"""Deep audit of the prize CSVs. Read-only; prints a report."""
import csv
import glob
import re
import unicodedata
from collections import Counter

SKIP = {"nobel.csv", "nobel-k.csv"}  # nobel.csv is official API data; nobel-k is pending deletion decision


def weird_chars(s: str) -> list[str]:
    """Non-latin-script characters that look like scrape artifacts (Cyrillic, replacement chars)."""
    return sorted({c for c in s if c == "�" or "CYRILLIC" in unicodedata.name(c, "")})


def audit(path: str) -> None:
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    cols = list(rows[0]) if rows else []
    issues = []

    name_col = next((c for c in ("laureate", "full_name") if c in cols), None)
    if name_col:
        dupes = [k for k, v in Counter((r["year"], r[name_col].strip()) for r in rows).items() if v > 1]
        if dupes:
            issues.append(f"duplicate year+laureate: {dupes}")

    for r in rows:
        for c in cols:
            bad = weird_chars(r[c])
            if bad:
                issues.append(f"weird chars {bad} in {c}: {r[name_col or cols[0]][:40]}")
            if r[c] != r[c].strip():
                issues.append(f"untrimmed whitespace in {c}: {r[c][:40]!r}")

    if "year" in cols:
        bad_years = sorted({r["year"] for r in rows if not re.fullmatch(r"\d{4}( \(special\))?(/\d{1,2})?", r["year"])})
        if bad_years:
            issues.append(f"non-standard years: {bad_years}")

    if "country" in cols:
        vals = sorted({v.strip() for r in rows for v in re.split(r"[;/]", r["country"])})
        seps = {s for r in rows for s in (";" if ";" in r["country"] else "", "/" if "/" in r["country"] else "") if s}
        suspects = [v for v in vals if re.search(r"Kingdom of|Empire|Reich|stateless|Unknown|Federation|People's|Democratic Rep|British ", v)]
        if len(seps) > 1:
            issues.append(f"mixed country separators: {seps}")
        if suspects:
            issues.append(f"unnormalized countries: {suspects}")
        junk = [v for v in vals if v and not re.fullmatch(r"[A-Z][A-Za-z. '-]+(\(.*\))?", v)]
        if junk:
            issues.append(f"odd country values: {junk}")

    if "rationale" in cols:
        rats = [r["rationale"].strip() for r in rows]
        top, n = Counter(rats).most_common(1)[0]
        if top and n > 0.4 * len(rows):
            issues.append(f"boilerplate rationale {n}/{len(rows)}: {top[:60]!r}")
        short = sum(1 for r in rats if r and len(r) < 15)
        if short:
            issues.append(f"{short} suspiciously short rationales (<15 chars)")

    empty = {c: sum(1 for r in rows if not r[c].strip()) for c in cols}
    empty = {c: n for c, n in empty.items() if n}
    print(f"{path}: {len(rows)} rows | empties {empty or 'none'}")
    for i in issues:
        print(f"  !! {i}")


for path in sorted(glob.glob("*.csv")):
    if path not in SKIP:
        audit(path)
