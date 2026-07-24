#!/usr/bin/env python3
"""enrich.py — fill blank biographical cells in a laureate CSV from Wikidata.

WHAT IT DOES
    Given awards.sqlite3, it fills ONLY the empty cells of these fields, and
    never overwrites an existing value:

        source_laureate_id  laureate_type  birth_date  birth_year
        birth_city  birth_country  sex  death_date  death_city  death_country

    Affiliation, citizenship, coordinates, motivation and field_language are left
    for other passes (Wikidata gives current employer, not institution-at-award).

    Stdout is one JSON document for data-agent consumption. Progress and retry
    messages go to stderr. Each confirmed result includes guarded SQLite-ready
    proposed updates, with the entity QID named laureate_wikidata_qid.

STRATEGY  (the Wikidata-first half of scripts/extract-wikipedia.md)
    - Every value is a structured Wikidata claim. There is no LLM and no prose
      scraping: the program never uses model "memory" and never infers a fact.
    - Nothing is written unless the person/organisation match is CONFIRMED.

THE CONFIRMATION GATE  (this is the whole safety of the tool)
    For each laureate we gather candidate Wikidata items — the exact Wikipedia
    article (via pageprops), then the top name-search hits, then a name+prize
    search to disambiguate common names — and accept the FIRST candidate that:

        1. is a human            (P31 = Q5), and
        2. whose birth year does NOT contradict the row's existing birth_year, and
        3. is positively confirmed by at least one INDEPENDENT anchor:
              a. the row's existing birth_year equals the item's birth year, OR
              b. the item's "awards received" (P166) includes this prize.

    A candidate that is merely plausible (a human, but no anchor confirms it) is
    NOT written — the row is left blank and reported. This is what makes the tool
    safe on files where birth_year is missing: without an anchor it abstains
    rather than guess. Wrong-person matches (e.g. "Robert May" the reindeer-song
    author vs. the ecologist) are rejected by the birth-year contradiction, and
    the next candidate is tried.

    A named organisation (WHO, Médecins Sans Frontières, ...) is written as
    laureate_type = Organization ONLY when the award anchor (3b) confirms it;
    otherwise it is skipped. This auto-detects organisations without a hand list.

    Deaths carry an extra guard: a Wikidata death year that disagrees with the
    "(birth-death)" hint already in biographical_note is not written.

USAGE
    cd datasets
    uv run python scripts/enrich.py --db awards.sqlite3
    uv run python scripts/enrich.py --db awards.sqlite3 --limit 20

    The legacy CSV interface remains available for read-only reports with
    --dry-run. Requests are sequential and politely backed off, with a
    contactable User-Agent and maxlag per Wikimedia API etiquette.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# --- Wikidata / Wikipedia endpoints -----------------------------------------
WD_API = "https://www.wikidata.org/w/api.php"
WP_API = "https://en.wikipedia.org/w/api.php"
UA = {"User-Agent": "nobel-datasets-enrich/1.0 (https://bpventures.us; datasets cleanup)"}

# --- Wikidata properties (P) and items (Q) we rely on -----------------------
P_INSTANCE_OF = "P31"   # what kind of thing the item is
P_BIRTH_DATE = "P569"
P_DEATH_DATE = "P570"
P_BIRTH_PLACE = "P19"
P_DEATH_PLACE = "P20"
P_SEX = "P21"
P_AWARD = "P166"        # awards received — our identity anchor
P_COUNTRY = "P17"       # country of a place
Q_HUMAN = "Q5"
SEX_LABEL = {"Q6581097": "Male", "Q6581072": "Female"}
# Item types that count as an award-winning organisation (not exhaustive; the
# award anchor P166 does the real confirming, this only says "not a person").
ORG_TYPES = {
    "Q43229",    # organization
    "Q327333",   # government agency
    "Q163740",   # nonprofit organization
    "Q31855",    # research institute
    "Q484652",   # international organization
    "Q79913",    # non-governmental organization
    "Q4438121",  # sports organization (harmless catch-all breadth)
}

# Fields the tool is allowed to write, and only when the cell is empty.
WRITE_FIELDS = (
    "source_laureate_id", "laureate_type", "birth_date", "birth_year",
    "birth_city", "birth_country", "sex", "death_date", "death_city", "death_country",
)
DATABASE_WRITE_FIELDS = (
    "laureate_wikidata_qid", "laureate_type", "birth_date", "birth_year",
    "birth_city", "birth_country", "sex", "death_date", "death_city", "death_country",
)
DATABASE_INPUT_FIELDS = (
    "award_record_id", "category", "prize", "award_wikidata_qid",
    "source_laureate_id", "laureate_wikidata_qid", "laureate_type", "full_name",
    "birth_date", "birth_year", "birth_city", "birth_country", "sex",
    "death_date", "death_city", "death_country", "biographical_note",
)

_ENTITY_CACHE: dict[str, dict] = {}   # in-run QID -> entity, avoids refetching
QID = re.compile(r"Q[1-9][0-9]*")


class DatabaseUpdateError(Exception):
    """Proposed updates cannot be applied without violating the database contract."""


def log(msg: str) -> None:
    """Progress line to stderr (stdout is reserved for the final report)."""
    print(msg, file=sys.stderr, flush=True)


# ----------------------------------------------------------------------------
# HTTP: one polite, retrying GET used for every API call.
# ----------------------------------------------------------------------------
def _get(base: str, params: dict, delay: float) -> dict:
    params = {**params, "format": "json", "maxlag": 5}
    url = base + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    for attempt in range(8):
        time.sleep(delay)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.load(r)
            if "error" in data and data["error"].get("code") == "maxlag":
                time.sleep(5)
                continue
            return data
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            if attempt == 7:
                raise
            time.sleep(min(2 ** attempt * 2 + random.uniform(0, 2), 60))  # backoff + jitter
    return {}


# ----------------------------------------------------------------------------
# Candidate discovery: turn a name into an ordered list of Wikidata QIDs.
# ----------------------------------------------------------------------------
def pageprops_qid(name: str, delay: float) -> str | None:
    """QID of the en.wikipedia article titled `name` (redirects resolved)."""
    data = _get(WP_API, {
        "action": "query", "prop": "pageprops", "ppprop": "wikibase_item",
        "redirects": 1, "titles": name, "formatversion": 2,
    }, delay)
    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return None
    return pages[0].get("pageprops", {}).get("wikibase_item")


def search_entities(term: str, limit: int, delay: float) -> list[dict]:
    """Top Wikidata search hits for `term` as [{id,label,description}]."""
    data = _get(WD_API, {
        "action": "wbsearchentities", "search": term,
        "language": "en", "limit": limit,
    }, delay)
    return [{"id": h["id"], "label": h.get("label", ""), "description": h.get("description", "")}
            for h in data.get("search", [])]


def candidate_qids(row: dict, delay: float) -> list[str]:
    """Ordered, de-duplicated candidate QIDs for a laureate row.

    Order matters: the exact article first, then name search, then a
    name+prize search that helps disambiguate common names.
    """
    name = row["full_name"]
    ordered: list[str] = []
    exact = pageprops_qid(name, delay)
    if exact:
        ordered.append(exact)
    for hit in search_entities(name, 5, delay):
        ordered.append(hit["id"])
    if row["prize"].strip():
        for hit in search_entities(f"{name} {row['prize']}", 3, delay):
            ordered.append(hit["id"])
    seen: set[str] = set()
    return [q for q in ordered if not (q in seen or seen.add(q))]


# ----------------------------------------------------------------------------
# Entity access + small claim helpers.
# ----------------------------------------------------------------------------
def get_entity(qid: str, delay: float) -> dict:
    if qid not in _ENTITY_CACHE:
        data = _get(WD_API, {
            "action": "wbgetentities", "ids": qid,
            "props": "labels|claims", "languages": "en",
        }, delay)
        _ENTITY_CACHE[qid] = data.get("entities", {}).get(qid, {})
    return _ENTITY_CACHE[qid]


def claim_ids(ent: dict, prop: str) -> list[str]:
    """QIDs of every item-valued claim for `prop` (e.g. P31, P166)."""
    out = []
    for c in ent.get("claims", {}).get(prop, []):
        v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(v, dict) and "id" in v:
            out.append(v["id"])
    return out


def claim_time(ent: dict, prop: str) -> dict | None:
    """First time-valued claim for `prop` (P569/P570), or None."""
    for c in ent.get("claims", {}).get(prop, []):
        v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(v, dict) and "time" in v:
            return v
    return None


def label(ent: dict) -> str:
    return ent.get("labels", {}).get("en", {}).get("value", "")


def iso_date(v: dict) -> str:
    """Wikidata time value -> 'YYYY-MM-DD', trimmed to 'YYYY-MM' or 'YYYY'."""
    t = v["time"].lstrip("+").split("T")[0]
    if t.endswith("-00-00"):
        return t[:4]
    if t.endswith("-00"):
        return t[:7]
    return t


def year_of(v: dict | None) -> str:
    return iso_date(v)[:4] if v else ""


def place_city_country(ent: dict, prop: str, delay: float) -> tuple[str, str]:
    ids = claim_ids(ent, prop)
    if not ids:
        return "", ""
    place = get_entity(ids[0], delay)
    countries = claim_ids(place, P_COUNTRY)
    country = label(get_entity(countries[0], delay)) if countries else ""
    return label(place), country


def note_death_year(note: str) -> str:
    """Death year from a biographical_note like '(1937-2010)', else ''."""
    m = re.search(r"[-–](\d{4})\)", note)
    return m.group(1) if m else ""


# ----------------------------------------------------------------------------
# The confirmation gate.
# ----------------------------------------------------------------------------
def classify(ent: dict, row: dict, award_qids: set[str]) -> tuple[str, str]:
    """Decide what to do with a candidate entity.

    Returns (verdict, reason) where verdict is one of:
        "individual"   — confirmed person, write bio
        "organization" — confirmed award-winning organisation, write type only
        "reject"       — this candidate is the wrong entity, try the next one
        "abstain"      — plausible but unconfirmed, write nothing for this row
    """
    types = set(claim_ids(ent, P_INSTANCE_OF))
    award_ok = bool(award_qids & set(claim_ids(ent, P_AWARD)))
    e_year = year_of(claim_time(ent, P_BIRTH_DATE))
    r_year = row["birth_year"].strip()
    year_ok = bool(r_year and e_year and r_year == e_year)
    year_bad = bool(r_year and e_year and r_year != e_year)

    if Q_HUMAN in types:
        if year_bad:
            return "reject", f"birth-year {r_year}≠{e_year}"
        if year_ok:
            return "individual", "birth-year match"
        if award_ok:
            return "individual", "award match"
        return "abstain", "human but no anchor (no birth_year, award not listed)"

    if types & ORG_TYPES:
        if award_ok:
            return "organization", "award match"
        return "abstain", "organisation but award not listed"

    return "reject", "not a person or organisation"


def resolve(row: dict, award_qids: set[str], delay: float) -> tuple[str | None, dict | None, str, str]:
    """Find the first candidate that the gate confirms.

    Returns (qid, entity, verdict, reason). qid is None when every candidate is
    rejected or unconfirmed (the row is then left blank).
    """
    last_reason = "no candidates"
    for qid in candidate_qids(row, delay):
        ent = get_entity(qid, delay)
        verdict, reason = classify(ent, row, award_qids)
        if verdict in ("individual", "organization"):
            return qid, ent, verdict, reason
        last_reason = reason  # remember why the best candidate failed
    return None, None, "abstain", last_reason


# ----------------------------------------------------------------------------
# Award anchor resolution: which Wikidata items *are* this prize?
# ----------------------------------------------------------------------------
def resolve_award_qids(rows: list[dict], delay: float) -> set[str]:
    """QIDs for the prize (and its per-category variants) via label search.

    A hit is kept only if the prize's leading word appears in the hit's label,
    so a junk search result cannot silently become a false identity anchor.
    """
    terms: set[str] = set()
    for r in rows:
        prize, cat = r["prize"].strip(), r["category"].strip()
        if prize:
            terms.add(prize)
        if prize and cat and cat.lower() not in prize.lower():
            terms.add(f"{prize} in {cat}")
    qids: set[str] = set()
    for term in sorted(terms):
        hits = search_entities(term, 1, delay)
        if not hits:
            continue
        key = term.split()[0].lower()
        if key in hits[0]["label"].lower():
            qids.add(hits[0]["id"])
            log(f"award anchor: '{term}' -> {hits[0]['id']} ({hits[0]['label']})")
        else:
            log(f"award anchor: '{term}' -> {hits[0]['label']} REJECTED (label mismatch)")
    return qids


# ----------------------------------------------------------------------------
# Writing: fill empty cells only.
# ----------------------------------------------------------------------------
def fill_row(row: dict, qid: str, ent: dict, verdict: str, delay: float) -> None:
    def put(field: str, value: str) -> None:
        if value and not row[field].strip():
            row[field] = value

    put("source_laureate_id", qid)
    put("laureate_type", "Individual" if verdict == "individual" else "Organization")
    if verdict == "organization":
        return

    bdate = claim_time(ent, P_BIRTH_DATE)
    if bdate:
        put("birth_date", iso_date(bdate))
        put("birth_year", year_of(bdate))
    b_city, b_country = place_city_country(ent, P_BIRTH_PLACE, delay)
    put("birth_city", b_city)
    put("birth_country", b_country)

    sex = claim_ids(ent, P_SEX)
    if sex:
        put("sex", SEX_LABEL.get(sex[0], label(get_entity(sex[0], delay))))

    ddate = claim_time(ent, P_DEATH_DATE)
    if ddate:
        note_year = note_death_year(row["biographical_note"])
        if note_year and note_year != year_of(ddate):
            log(f"  death-year note {note_year} ≠ wikidata {year_of(ddate)} — death skipped")
            return
        put("death_date", iso_date(ddate))
        d_city, d_country = place_city_country(ent, P_DEATH_PLACE, delay)
        put("death_city", d_city)
        put("death_country", d_country)


def write_csv(path: str, header: list[str], rows: list[dict]) -> None:
    """Atomic write: temp file in the same dir, then replace."""
    tmp = path + ".tmp"
    with open(tmp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


def known_qid(row: dict, cache: dict[str, str]) -> str:
    database_id = row.get("laureate_wikidata_qid", "").strip()
    if QID.fullmatch(database_id):
        return database_id
    source_id = row["source_laureate_id"].strip()
    if QID.fullmatch(source_id):
        return source_id
    cached = cache.get(row["full_name"], "").strip()
    return cached if QID.fullmatch(cached) else ""


def proposed_updates(before: dict, after: dict, qid: str) -> dict[str, str]:
    updates = {"laureate_wikidata_qid": qid}
    for field in WRITE_FIELDS:
        if field != "source_laureate_id" and after[field] != before[field]:
            updates[field] = after[field]
    return updates


def read_database_rows(path: str) -> list[dict[str, str]]:
    """Read enrichment inputs from SQLite without holding a write transaction."""
    if not os.path.isfile(path):
        raise DatabaseUpdateError(f"database not found: {path}")

    columns = ", ".join(f'"{field}"' for field in DATABASE_INPUT_FIELDS)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(f"SELECT {columns} FROM awards").fetchall()
        return [
            {field: row[field] or "" for field in DATABASE_INPUT_FIELDS}
            for row in rows
        ]
    finally:
        connection.close()


def apply_database_updates(path: str, results: list[dict]) -> int:
    """Apply nonblank allowlisted result updates atomically."""
    if not os.path.isfile(path):
        raise DatabaseUpdateError(f"database not found: {path}")

    connection = sqlite3.connect(path)
    try:
        connection.execute("BEGIN")
        applied = 0
        for result in results:
            record_id = result.get("award_record_id")
            if not isinstance(record_id, str) or not record_id:
                raise DatabaseUpdateError(f"invalid award_record_id: {record_id!r}")
            if connection.execute("SELECT 1 FROM awards WHERE award_record_id = ?", (record_id,)).fetchone() is None:
                raise DatabaseUpdateError(f"award_record_id not found: {record_id}")

            proposed = result.get("updates", {})
            updates = [
                (field, proposed[field])
                for field in DATABASE_WRITE_FIELDS
                if isinstance(proposed.get(field), str) and proposed[field].strip()
            ]
            if not updates:
                continue

            assignments = [
                f'"{field}" = ?' if field == "laureate_wikidata_qid" else f'"{field}" = COALESCE(NULLIF("{field}", \'\'), ?)'
                for field, _ in updates
            ]
            values = [value for _, value in updates]
            connection.execute(
                f"UPDATE awards SET {', '.join(assignments)} WHERE award_record_id = ?",
                (*values, record_id),
            )
            applied += 1
        connection.commit()
        return applied
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


# ----------------------------------------------------------------------------
# Main.
# ----------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Enrich laureates from Wikidata (empty cells only).")
    ap.add_argument("csv", nargs="?", help="legacy CSV input; use only with --dry-run")
    output = ap.add_mutually_exclusive_group()
    output.add_argument("--dry-run", action="store_true", help="report only; do not write the CSV")
    output.add_argument("--db", help="read from and apply proposed updates to this SQLite database")
    ap.add_argument("--limit", type=int, default=0, help="process at most N target rows (0 = all)")
    ap.add_argument("--delay", type=float, default=2.0, help="seconds to pause before each request")
    args = ap.parse_args(argv)

    if args.db and args.csv:
        ap.error("CSV input cannot be combined with --db")
    if not args.db and not args.csv:
        ap.error("CSV input is required unless --db is used")

    header: list[str] | None = None
    cache_path = ""
    cache: dict[str, str] = {}
    if args.db:
        try:
            rows = read_database_rows(args.db)
        except (DatabaseUpdateError, OSError, sqlite3.Error) as error:
            log(f"database read: path={args.db} outcome=failed error={error}")
            return 1
        award_qids: set[str] = set()
        log("award anchors: using awards.award_wikidata_qid")
    else:
        with open(args.csv, newline="") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames
            rows = list(reader)
        cache_path = f"{os.path.splitext(args.csv)[0]}.enrich-cache.json"
        cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
        award_qids = resolve_award_qids(rows, args.delay)
        log(f"award anchors: {sorted(award_qids) or 'none (relying on birth_year only)'}")

    # Targets: rows not yet enriched, PLUS living individuals to re-check for a
    # newly recorded death (this is the periodic "did someone die" update run).
    def needs_work(r: dict) -> bool:
        if not known_qid(r, cache):                # never identified
            return True
        if not r["laureate_type"].strip():         # identified but type not set yet
            return True
        return r["laureate_type"].strip() == "Individual" and not r["death_date"].strip()

    targets = [r for r in rows if needs_work(r)]
    if args.limit:
        targets = targets[:args.limit]
    log(f"targets: {len(targets)} of {len(rows)} rows")

    stats = {"individual": 0, "organization": 0, "abstain": 0}
    results: list[dict] = []
    for i, row in enumerate(targets, 1):
        name = row["full_name"]
        known = known_qid(row, cache)
        if known:                                 # already identified -> reuse, just fill gaps
            qid = known
            ent = get_entity(qid, args.delay)
            verdict = "individual" if Q_HUMAN in set(claim_ids(ent, P_INSTANCE_OF)) else "organization"
            reason = "known QID (recheck)"
        else:
            row_award_qids = {row["award_wikidata_qid"]} if args.db and QID.fullmatch(row["award_wikidata_qid"]) else award_qids
            qid, ent, verdict, reason = resolve(row, row_award_qids, args.delay)

        if not qid:
            stats["abstain"] += 1
            results.append({
                "award_record_id": row["award_record_id"],
                "full_name": name,
                "status": "abstained",
                "reason": reason,
                "updates": {},
            })
            log(f"[{i}/{len(targets)}] {name} -> abstain ({reason})")
            continue

        before = row.copy()
        fill_row(row, qid, ent, verdict, args.delay)
        cache[name] = qid
        stats[verdict] += 1
        results.append({
            "award_record_id": row["award_record_id"],
            "full_name": name,
            "status": "confirmed",
            "reason": reason,
            "entity_label": label(ent),
            "wikidata_url": f"https://www.wikidata.org/wiki/{qid}",
            "updates": proposed_updates(before, row, qid),
        })
        log(f"[{i}/{len(targets)}] {name} -> {qid} {verdict} ({reason})")
        if not args.dry_run and not args.db:
            json.dump(cache, open(cache_path, "w"))  # save resolution progress

    if not args.dry_run and not args.db and header is not None:
        write_csv(args.csv, header, rows)

    report = {
        "dry_run": args.dry_run,
        "target": args.db or "awards.sqlite3",
        "processed": len(targets),
        "summary": stats,
        "results": results,
    }
    report["input_db" if args.db else "input_csv"] = args.db or args.csv
    exit_code = 0
    if args.db:
        try:
            applied = apply_database_updates(args.db, results)
            report["database_apply"] = {"status": "applied", "rows": applied}
            log(f"database apply: path={args.db} rows={applied} outcome=applied")
        except (DatabaseUpdateError, OSError, sqlite3.Error) as error:
            report["database_apply"] = {"status": "rolled_back", "rows": 0}
            log(f"database apply: path={args.db} outcome=rolled_back error={error}")
            exit_code = 1

    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
