#!/usr/bin/env python3
"""Enrich crafoord.csv from Wikidata (scripted, cheap, source-verified).

Run from the datasets/ directory. Fills ONLY empty cells:
  source_laureate_id (QID), birth_date, birth_city, birth_country, sex,
  death_date, death_city, death_country.

Validation (rejects wrong-person matches):
  - the Wikidata birth year must equal the row's existing birth_year, else the
    whole row is skipped and reported;
  - a death date is written only if its year matches the death year already in
    biographical_note "(birth-death)", when that note carries one.

Affiliation is intentionally left for a press-release pass (Wikidata gives the
current employer, not the institution held at award time). Resumable via
crafoord_cache.json. Mirrors the proven enrich_fields.py approach.
"""
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from os import path

WIKI = "https://www.wikidata.org/w/api.php"
UA = {"User-Agent": "PrizeAtlas-crafoord-enrich/1.0 (https://prizeatlas.org/)"}
DELAY = 2.5
SEX = {"Q6581097": "Male", "Q6581072": "Female"}

TARGET_FIELDS = (
    "source_laureate_id", "birth_date", "birth_city", "birth_country",
    "sex", "death_date", "death_city", "death_country",
)


def api(params: dict) -> dict:
    time.sleep(DELAY)
    url = WIKI + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    for attempt in range(8):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except (urllib.error.HTTPError, TimeoutError, urllib.error.URLError):
            if attempt < 7:
                time.sleep(min(2 ** attempt * 3 + 2, 60))
                continue
            raise


def search_qid(name: str) -> dict | None:
    data = api({
        "action": "wbsearchentities", "search": name,
        "language": "en", "format": "json", "limit": 1,
    })
    if not data.get("search"):
        return None
    hit = data["search"][0]
    return {"qid": hit["id"], "label": hit.get("label", ""),
            "description": hit.get("description", "")}


def batch_entities(ids: list[str]) -> dict:
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        data = api({
            "action": "wbgetentities", "ids": "|".join(chunk),
            "props": "labels|claims", "languages": "en", "format": "json",
        })
        out.update(data.get("entities", {}))
        time.sleep(1.0)
    return out


def claim_value(ent: dict, prop: str) -> str | dict | None:
    claims = ent.get("claims", {})
    if prop not in claims:
        return None
    snak = claims[prop][0]["mainsnak"]
    if "datavalue" not in snak:
        return None
    v = snak["datavalue"]["value"]
    if isinstance(v, dict) and "id" in v:  # Wikibase item -> Q-id string
        return v["id"]
    return v


def label(ent: dict) -> str:
    return ent.get("labels", {}).get("en", {}).get("value", "")


def place_label(ent: dict, prop: str, ents: dict) -> str:
    qid = claim_value(ent, prop)
    if not qid or qid not in ents:
        return ""
    return label(ents[qid])


def place_country(ent: dict, prop: str, ents: dict) -> str:
    """Country label of the place referenced by prop (via P17)."""
    pq = claim_value(ent, prop)
    if not pq or pq not in ents:
        return ""
    cq = claim_value(ents[pq], "P17")
    return label(ents[cq]) if cq and cq in ents else ""


def iso_date(v: dict) -> str:
    t = v["time"].lstrip("+").split("T")[0]
    if t.endswith("-00-00"):
        return t[:4]
    if t.endswith("-00"):
        return t[:7]
    return t


def note_death_year(note: str) -> str:
    """Death year from a biographical_note like '(1937-2010)', else ''."""
    m = re.search(r"[-–](\d{4})\)", note)
    return m.group(1) if m else ""


def main() -> int:
    with open("crafoord.csv", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        rows = list(reader)

    cache_path = "crafoord_cache.json"
    qids: dict[str, str] = {}
    meta: dict[str, dict] = {}
    if path.exists(cache_path):
        with open(cache_path) as cf:
            qids = json.load(cf)

    # Enrich every row still missing a birth_date.
    targets = [r for r in rows if not r["birth_date"].strip()]
    target_ids = {r["award_record_id"] for r in targets}
    print(f"targets to enrich: {len(targets)}", file=sys.stderr)

    for row in targets:
        name = row["full_name"]
        if qids.get(name):
            continue
        hit = search_qid(name)
        if not hit:
            print(f"NO MATCH: {name}", file=sys.stderr)
            continue
        qids[name] = hit["qid"]
        meta[name] = hit
        with open(cache_path, "w") as cf:
            json.dump(qids, cf)

    # Resolve persons, then their birth/death places, then those places' countries.
    need: set[str] = {qids[r["full_name"]] for r in targets if r["full_name"] in qids}
    ents = batch_entities(list(need))
    places = {claim_value(e, p) for e in ents.values() for p in ("P19", "P20") if claim_value(e, p)}
    need |= {p for p in places if p}
    ents = batch_entities(list(need))
    countries = {claim_value(ents[q], "P17") for q in places if q in ents and claim_value(ents[q], "P17")}
    need |= {c for c in countries if c}
    ents = batch_entities(list(need))

    filled = {k: 0 for k in TARGET_FIELDS}
    mismatches: list[str] = []
    for row in rows:
        if row["award_record_id"] not in target_ids:
            continue
        name = row["full_name"]
        if name not in qids or qids[name] not in ents:
            continue
        ent = ents[qids[name]]

        # --- validation gate: birth year must agree with the row ---
        bdate = claim_value(ent, "P569")
        ent_byear = iso_date(bdate)[:4] if isinstance(bdate, dict) and "time" in bdate else ""
        row_byear = row["birth_year"].strip()
        if row_byear and ent_byear and row_byear != ent_byear:
            mismatches.append(f"{name}: row {row_byear} vs wikidata {ent_byear} ({qids[name]})")
            continue

        row["source_laureate_id"] = qids[name]
        filled["source_laureate_id"] += 1

        if ent_byear:
            row["birth_date"] = iso_date(bdate)
            filled["birth_date"] += 1

        bc = place_label(ent, "P19", ents)
        if bc:
            row["birth_city"] = bc
            filled["birth_city"] += 1
        bcountry = place_country(ent, "P19", ents)
        if bcountry:
            row["birth_country"] = bcountry
            filled["birth_country"] += 1

        sx = claim_value(ent, "P21")
        if sx:
            row["sex"] = SEX.get(sx, label(ents.get(sx, {})))
            if row["sex"]:
                filled["sex"] += 1

        ddate = claim_value(ent, "P570")
        if isinstance(ddate, dict) and "time" in ddate:
            ent_dyear = iso_date(ddate)[:4]
            note_dyear = note_death_year(row["biographical_note"])
            if note_dyear and note_dyear != ent_dyear:
                mismatches.append(f"{name}: death note {note_dyear} vs wikidata {ent_dyear} (kept birth, skipped death)")
            else:
                row["death_date"] = iso_date(ddate)
                filled["death_date"] += 1
                dc = place_label(ent, "P20", ents)
                if dc:
                    row["death_city"] = dc
                    filled["death_city"] += 1
                dcountry = place_country(ent, "P20", ents)
                if dcountry:
                    row["death_country"] = dcountry
                    filled["death_country"] += 1

    with open("crafoord.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)

    print("Applied (empty cells only):")
    for k, v in filled.items():
        print(f"  {k:22} {v}")
    if mismatches:
        print(f"\nVALIDATION MISMATCHES ({len(mismatches)}) — review these names:")
        for m in mismatches:
            print(f"  {m}")
    if meta:
        print("\nNew matches (review):")
        for name, m in meta.items():
            print(f"  {name:30} -> {m['label']} [{m['description']}] {qids[name]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
