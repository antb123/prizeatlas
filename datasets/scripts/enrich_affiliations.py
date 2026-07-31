#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""
Enrich affiliations metadata table in awards.sqlite3 from Wikidata.

Fetches English descriptions, P154 (logo image) URLs, P17 (country), and P571 (inception year)
from Wikidata API for all distinct affiliation_wikidata_qid values in awards.sqlite3.
Appends country name and founding year to description if missing.
"""

import json
import sqlite3
import sys
import urllib.parse
import urllib.request

DB_PATH = "awards.sqlite3"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
USER_AGENT = "PrizeAtlas-affiliation-enricher/1.0 (https://prizeatlas.org/)"

# Common Wikidata country QID -> English name
COUNTRY_MAP = {
    "Q30": "United States",
    "Q145": "United Kingdom",
    "Q183": "Germany",
    "Q17": "Japan",
    "Q142": "France",
    "Q16": "Canada",
    "Q39": "Switzerland",
    "Q33": "Finland",
    "Q35": "Sweden",
    "Q55": "Netherlands",
    "Q20": "Norway",
    "Q29": "Spain",
    "Q38": "Italy",
    "Q40": "Austria",
    "Q668": "India",
    "Q148": "China",
    "Q884": "South Korea",
    "Q159": "Russia",
    "Q408": "Australia",
    "Q96": "Mexico",
    "Q155": "Brazil",
    "Q801": "Israel",
    "Q31": "Belgium",
    "Q213": "Czech Republic",
    "Q252": "Indonesia",
    "Q865": "Taiwan",
    "Q411": "Canada",
}


def get_distinct_qids(db_path: str) -> list[str]:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT affiliation_wikidata_qid FROM awards "
        "WHERE affiliation_wikidata_qid IS NOT NULL AND affiliation_wikidata_qid != '' "
        "ORDER BY affiliation_wikidata_qid"
    )
    qids = [row[0] for row in cur.fetchall()]
    conn.close()
    return qids


def fetch_wikidata_batch(qids: list[str]) -> dict:
    params = {
        "action": "wbgetentities",
        "ids": "|".join(qids),
        "props": "descriptions|claims|labels",
        "languages": "en",
        "format": "json",
    }
    url = f"{WIKIDATA_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("entities", {})


def get_country_name(claims: dict) -> str:
    p17 = claims.get("P17", [])
    if not p17:
        return ""
    mainsnak = p17[0].get("mainsnak", {})
    datavalue = mainsnak.get("datavalue", {})
    country_qid = datavalue.get("value", {}).get("id", "")
    return COUNTRY_MAP.get(country_qid, "")


def get_inception_year(claims: dict) -> str:
    p571 = claims.get("P571", [])
    if not p571:
        return ""
    mainsnak = p571[0].get("mainsnak", {})
    datavalue = mainsnak.get("datavalue", {})
    time_str = datavalue.get("value", {}).get("time", "")
    if time_str and len(time_str) >= 5 and time_str[0] in ("+", "-"):
        year = time_str[1:5].lstrip("0")
        if year.isdigit() and len(year) >= 3:
            return year
    return ""


def parse_entity(entity: dict) -> tuple[str, str]:
    claims = entity.get("claims", {})

    # Extract description
    descriptions = entity.get("descriptions", {})
    desc = descriptions.get("en", {}).get("value", "")
    if desc:
        desc = desc[0].upper() + desc[1:]

    # Extract country and ensure it's in description
    country_name = get_country_name(claims)
    if desc and country_name:
        desc_lower = desc.lower()
        country_lower = country_name.lower()
        has_country = (
            country_lower in desc_lower
            or (country_name == "United States" and ("usa" in desc_lower or "u.s." in desc_lower or "united states" in desc_lower or "us" in desc_lower.split()))
            or (country_name == "United Kingdom" and ("uk" in desc_lower or "u.k." in desc_lower or "united kingdom" in desc_lower))
        )
        if not has_country:
            desc = f"{desc}, {country_name}"

    # Extract inception year and ensure founding year is present
    year = get_inception_year(claims)
    if desc and year:
        desc_lower = desc.lower()
        has_year = year in desc_lower or "founded" in desc_lower or "established" in desc_lower or "est." in desc_lower
        if not has_year:
            desc = f"{desc}, founded {year}"

    # Extract logo (P154)
    logo_url = ""
    p154 = claims.get("P154", [])
    if p154:
        mainsnak = p154[0].get("mainsnak", {})
        datavalue = mainsnak.get("datavalue", {})
        filename = datavalue.get("value", "")
        if filename:
            encoded_fn = urllib.parse.quote(filename.replace(" ", "_"))
            logo_url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{encoded_fn}"

    return logo_url, desc


def main() -> None:
    dry_run = "--apply" not in sys.argv
    qids = get_distinct_qids(DB_PATH)
    print(f"Found {len(qids)} distinct affiliation QIDs in {DB_PATH}")

    batch_size = 50
    results = {}

    for i in range(0, len(qids), batch_size):
        batch = qids[i : i + batch_size]
        print(f"Fetching batch {i//batch_size + 1}/{(len(qids)+batch_size-1)//batch_size} ({len(batch)} QIDs)...")
        entities = fetch_wikidata_batch(batch)
        for qid in batch:
            entity = entities.get(qid, {})
            logo_url, desc = parse_entity(entity)
            results[qid] = (logo_url, desc)

    filled_logos = sum(1 for logo, _ in results.values() if logo)
    filled_descs = sum(1 for _, desc in results.values() if desc)
    print(f"Enrichment summary: {len(results)} total, {filled_logos} with logos, {filled_descs} with descriptions")

    if dry_run:
        print("\nDry run mode (--apply to commit to DB). Sample entries:")
        for qid in list(results.keys())[:15]:
            logo, desc = results[qid]
            print(f"  {qid}: desc='{desc}' | logo='{logo}'")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("BEGIN TRANSACTION;")
    rows = [(qid, logo, desc) for qid, (logo, desc) in results.items()]
    cur.executemany(
        "INSERT INTO affiliations (affiliation_wikidata_qid, logo_url, description) "
        "VALUES (?, ?, ?) "
        "ON CONFLICT(affiliation_wikidata_qid) DO UPDATE SET "
        "logo_url=excluded.logo_url, description=excluded.description;",
        rows,
    )
    conn.commit()

    cur.execute("PRAGMA integrity_check;")
    check = cur.fetchone()[0]
    print(f"Database update complete. Integrity check: {check}")
    conn.close()


if __name__ == "__main__":
    main()
