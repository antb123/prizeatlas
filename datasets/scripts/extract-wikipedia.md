I need to extract a lot of information from Wikipedia pages on individuals. Is there a way to tell the pro- what's a good prompt for a program? Is there a specific way that's more effective? Can you check Reddit and/or check other discussion forums to see what's the best strategy for extracting information, and give a snippet?

Best approach

Do not treat this primarily as an LLM scraping problem. Use a hybrid pipeline:

    Wikidata for standardized facts such as birth date, citizenship, occupations, education, positions, employers and awards.

    Wikipedia’s API for the article text, rather than scraping the visual webpage with Selenium.

    An LLM only for facts embedded in prose or fields missing from Wikidata.

    A fixed JSON schema with evidence, followed by deterministic validation.

Wikimedia specifically recommends the Wikidata Query Service for narrowly scoped structured queries, direct entity APIs for known entities, and downloadable dumps when the desired dataset becomes very large. The MediaWiki REST API can return both page metadata and rendered HTML.
What Reddit discussions suggest

The practical advice broadly agrees with this approach: developers recommend Pywikibot or the MediaWiki API instead of hand-scraping, note that infobox layouts vary enough to break generic BeautifulSoup rules, and recommend validating and retrying LLM extraction rather than trusting the initial JSON.
Prompt to give a coding agent

Paste this into Codex, Claude Code, Hermes, or another programming agent:

Build a KISS Python 3.12 command-line program named wiki_people_extract.py that extracts structured biographical information from Wikipedia pages about individuals.
Inputs

Accept a CSV or JSONL file containing:

    record_id

    wikipedia_url or wikipedia_title

    optional language, defaulting to en

Accept a separate JSON Schema file defining the fields to extract. Do not let the model create or modify the schema separately for each person.
Retrieval architecture

For each person:

    Resolve redirects and retrieve the current Wikipedia page using the MediaWiki REST API.

    Record the canonical title, article URL, language, revision ID and retrieval timestamp.

    Retrieve the associated Wikidata QID through the MediaWiki Action API pageprops.

    Retrieve the Wikidata entity JSON.

    Use Wikidata deterministically for fields that have relevant properties.

    Retrieve the Wikipedia article HTML through the MediaWiki REST API.

    Convert the article into ordered text blocks. Each block must contain:

        a unique block ID;

        section heading;

        paragraph or list text;

        article revision ID.

    Exclude navigation boxes, edit controls, unrelated footer material, references lists and external-links sections from the extraction text.

Do not use Selenium, Playwright or browser automation.
Extraction procedure

Use an LLM only for requested fields that:

    are unavailable from Wikidata;

    require interpreting article prose;

    require constructing timelines or relationships from multiple passages.

Process long articles section by section rather than sending an entire article in one request.

The LLM must:

    use only the supplied source blocks and Wikidata data;

    never use prior knowledge;

    never infer an unstated fact;

    return null when information is absent;

    distinguish current, former and historical roles;

    preserve uncertain or approximate dates;

    preserve multiple values as arrays;

    report contradictory claims instead of choosing one silently;

    return the source block ID and a short exact evidence quotation for every extracted value.

Use native structured-output or JSON-schema enforcement when supported by the model provider.
Validation

Validate every result with Pydantic.

Additionally verify programmatically that:

    every returned block ID exists;

    every evidence quotation occurs verbatim in the corresponding source block;

    required fields are present even when their value is null;

    dates are valid ISO dates or explicitly marked as approximate;

    enumerated fields contain only permitted values;

    duplicate facts are merged without losing provenance.

Retry only invalid or missing fields. Do not rerun an entire successfully extracted record.

When Wikipedia and Wikidata disagree, retain both values in a conflicts array containing each value and its source.
Storage and reliability

    Cache raw Wikipedia and Wikidata responses locally, keyed by page and revision ID.

    Save progress after every person so processing can resume.

    Use SQLite for the cache and JSONL for primary output.

    Produce an optional flattened CSV export.

    Use a meaningful contactable User-Agent.

    Process requests sequentially by default.

    Handle redirects, disambiguation pages, missing pages, HTTP 429 and HTTP 503.

    Use exponential backoff with jitter.

    Avoid downloading the same revision twice.

    Log failures to a separate JSONL file.

Output structure

Each output record should contain:

    input record ID;

    canonical person name;

    Wikipedia URL;

    Wikipedia revision ID;

    Wikidata QID;

    structured extracted fields;

    evidence for each field;

    conflicts;

    missing requested fields;

    warnings;

    retrieval timestamp;

    extractor and model versions.

Tests

Include:

    unit tests for HTML-to-block conversion;

    unit tests for Wikidata property normalization;

    tests for redirects and missing pages;

    tests rejecting fabricated evidence quotations;

    an integration test using three people with differently structured articles.

Provide:

    wiki_people_extract.py

    models.py

    requirements.txt or pyproject.toml

    a sample schema;

    a sample input file;

    concise usage instructions.

Keep the implementation simple. Prefer requests, beautifulsoup4, pydantic and the standard library. Do not introduce an agent framework unless it materially simplifies the implementation.

This prompt forces the programming agent to separate retrieval, deterministic processing, probabilistic extraction and validation.
Runtime extraction prompt

The extraction call inside the finished program should use something like this:

You are a strict information-extraction engine.

Extract only the fields defined in REQUESTED_SCHEMA from SOURCE_BLOCKS and WIKIDATA_DATA.

Rules:

    Use no external or prior knowledge.

    Do not infer facts that are not explicitly supported.

    Return null when a requested fact is not present.

    Treat multiple occupations, positions, institutions, awards and relationships as arrays.

    Distinguish current, former and historical roles.

    Preserve the source's date precision. Do not invent a month or day when only a year is stated.

    For every non-null value, return:

        block_ids;

        an exact supporting quotation of no more than 25 words;

        source_type, either wikipedia or wikidata;

        confidence: high, medium or low.

    The quotation must occur verbatim in the identified source block.

    When sources disagree, do not select one silently. Add both claims to conflicts.

    Output valid JSON conforming exactly to REQUESTED_SCHEMA. Output no explanation or Markdown.

REQUESTED_SCHEMA:
{{SCHEMA_JSON}}

WIKIDATA_DATA:
{{WIKIDATA_JSON}}

SOURCE_BLOCKS:
{{SOURCE_BLOCKS_JSON}}

A crucial detail is asking for block IDs and exact evidence, rather than asking the model to generate citations or URLs. Your program can then reject any fact whose quotation is not actually present.
Core Python retrieval snippet

The current MediaWiki REST API offers a with_html page endpoint, while the Action API can return the page’s associated Wikidata item.

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup


USER_AGENT = (
    "WikiPeopleExtractor/0.1 "
    "(https://example.com/project; contact@example.com)"
)

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def get_wikidata_qid(title: str, language: str = "en") -> str | None:
    """Return the Wikidata QID associated with a Wikipedia article."""
    response = session.get(
        f"https://{language}.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "prop": "pageprops",
            "ppprop": "wikibase_item",
            "redirects": 1,
            "titles": title,
            "maxlag": 5,
        },
        timeout=30,
    )
    response.raise_for_status()

    pages = response.json()["query"]["pages"]
    if not pages or pages[0].get("missing"):
        return None

    return pages[0].get("pageprops", {}).get("wikibase_item")


def get_wikidata_entity(qid: str | None) -> dict | None:
    """Retrieve the complete Wikidata entity record."""
    if not qid:
        return None

    response = session.get(
        f"https://www.wikidata.org/wiki/"
        f"Special:EntityData/{qid}.json",
        params={"flavor": "simple"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["entities"][qid]


def get_wikipedia_blocks(
    title: str,
    language: str = "en",
) -> dict:
    """Retrieve a page and convert its prose into auditable text blocks."""
    encoded_title = quote(title.replace(" ", "_"), safe="")
    endpoint = (
        f"https://{language}.wikipedia.org/w/rest.php/v1/"
        f"page/{encoded_title}/with_html"
    )

    response = session.get(endpoint, timeout=30)
    response.raise_for_status()
    page = response.json()

    soup = BeautifulSoup(page["html"], "html.parser")

    for element in soup.select(
        "script, style, table.navbox, table.vertical-navbox, "
        ".mw-editsection, .authority-control, .metadata"
    ):
        element.decompose()

    blocks: list[dict] = []
    section = "Introduction"

    for element in soup.select("h2, h3, p, li"):
        if element.name in {"h2", "h3"}:
            heading = element.get_text(" ", strip=True)
            if heading:
                section = heading
            continue

        text = " ".join(element.stripped_strings)
        if len(text) < 30:
            continue

        blocks.append(
            {
                "id": f"block-{len(blocks) + 1:04d}",
                "section": section,
                "text": text,
            }
        )

    qid = get_wikidata_qid(page["title"], language)

    return {
        "title": page["title"],
        "article_url": (
            f"https://{language}.wikipedia.org/wiki/"
            f"{quote(page['title'].replace(' ', '_'))}"
        ),
        "revision_id": page["latest"]["id"],
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "wikidata_qid": qid,
        "wikidata": get_wikidata_entity(qid),
        "blocks": blocks,
    }


if __name__ == "__main__":
    record = get_wikipedia_blocks("Ada Lovelace")
    print(record["wikidata_qid"])
    print(record["blocks"][:3])

For production use, add caching, retry/backoff, schema validation and exact-quotation checking. Wikimedia requires a meaningful User-Agent, respect for throttling, and non-aggressive request behavior; its API etiquette also recommends maxlag for non-interactive jobs.
At larger scale

For a known list of several hundred or several thousand pages, the API-plus-cache approach is reasonable. For a substantial fraction of all biographies, use Wikidata and Wikipedia dumps locally rather than issuing enormous numbers of API or SPARQL requests. Wikidata’s own guidance says the public query service is for narrowly scoped results and recommends dumps for very large result sets.

The most important design decisions are:

    Define the fields before extraction.

    Use Wikidata before an LLM.

    Attach evidence to every value.

    Validate the evidence mechanically.

    Cache by revision ID.

    Store JSONL first and flatten to CSV later.

Send the fields you need extracted, and I’ll turn this into a compact exact schema with the corresponding Wikidata property mappings.
