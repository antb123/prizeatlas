# /// script
# requires-python = ">=3.12"
# ///
# SPDX-License-Identifier: GPL-2.0-or-later
"""Translate one unreviewed PrizeAtlas catalogue without losing reviewed values.

This is an authoring-time command.  It is deliberately independent of
``website/build.py`` so static builds remain offline and deterministic.
``deepl`` is the supported network provider; set ``DEEPL_AUTH_KEY`` before
using it.  Tests and local review tooling may inject a translator directly
through :func:`translate_catalogue`.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import string
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import tomllib

TARGET_CODES = frozenset({"es", "fr"})
TRANSLATABLE_SECTIONS = ("segments", "ui", "terms", "ranking")
DEEPL_API_URL = "https://api-free.deepl.com/v2/translate"
GOOGLE_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
PLACEHOLDER = re.compile(r"zzxqg([0-9]+)zz")
FORMAT_PLACEHOLDER = re.compile(r"zzxqf([0-9]+)zz")
GLOSSARIES = {
    "es": {
        "PrizeAtlas": "PrizeAtlas",
        "Nobel Prize": "Premio Nobel",
        "Fields Medal": "Medalla Fields",
        "Turing Award": "Premio Turing",
    },
    "fr": {
        "PrizeAtlas": "PrizeAtlas",
        "Nobel Prize": "prix Nobel",
        "Fields Medal": "médaille Fields",
        "Turing Award": "prix Turing",
    },
}


class CatalogueTranslationFailure(Exception):
    """A target catalogue cannot safely be replaced."""


Translator = Callable[[str, str], str]


def log(message: str) -> None:
    print(message, file=sys.stderr)


def toml_key(key: str) -> str:
    return key if re.fullmatch(r"[A-Za-z0-9_-]+", key) else json.dumps(key, ensure_ascii=False)


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as source:
            value = tomllib.load(source)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise CatalogueTranslationFailure(f"could not parse catalogue {path.name}") from error
    if not isinstance(value, dict):
        raise CatalogueTranslationFailure(f"catalogue {path.name} is not a table")
    return value


CataloguePath = tuple[str, ...]


def path_label(path: CataloguePath) -> str:
    return ".".join(path)


def reviewed_label(path: CataloguePath) -> str:
    """Return the durable manifest spelling for an internal catalogue path.

    UI keys such as ``common.awards`` are intentionally TOML-flat quoted keys,
    so only the first table separator belongs to the path.
    """
    if path[0] == "ui":
        return f"ui.{path[1]}"
    return path_label(path)


def iter_strings(value: dict[str, Any], prefix: CataloguePath = ()) -> Iterator[tuple[CataloguePath, str]]:
    for key in sorted(value):
        item = value[key]
        path = prefix + (key,)
        if isinstance(item, dict):
            yield from iter_strings(item, path)
        elif isinstance(item, str):
            yield path, item
        else:
            raise CatalogueTranslationFailure(f"invalid value at {path_label(path)}")


def translatable_values(document: dict[str, Any]) -> dict[CataloguePath, str]:
    values: dict[CataloguePath, str] = {}
    for section in TRANSLATABLE_SECTIONS:
        value = document.get(section)
        if not isinstance(value, dict):
            raise CatalogueTranslationFailure(f"catalogue missing section {section}")
        values.update(iter_strings(value, (section,)))
    return values


def get_path(document: dict[str, Any], path: CataloguePath) -> Any:
    value: Any = document
    for part in path:
        if not isinstance(value, dict) or part not in value:
            raise CatalogueTranslationFailure(f"reviewed key missing: {path_label(path)}")
        value = value[part]
    return value


def set_path(document: dict[str, Any], path: CataloguePath, replacement: str) -> None:
    *parents, final = path
    value: dict[str, Any] = document
    for part in parents:
        child = value.get(part)
        if not isinstance(child, dict):
            raise CatalogueTranslationFailure(f"catalogue path missing: {path_label(path)}")
        value = child
    if not isinstance(value.get(final), str):
        raise CatalogueTranslationFailure(f"catalogue value missing: {path_label(path)}")
    value[final] = replacement


def placeholder_fields(value: str, path: CataloguePath) -> Counter[str]:
    formatter = string.Formatter()
    try:
        parsed = list(formatter.parse(value))
    except ValueError as error:
        raise CatalogueTranslationFailure(f"malformed placeholder key={path_label(path)}") from error

    fields: list[str] = []
    for _, field, format_spec, conversion in parsed:
        if field is None:
            continue
        if not field.isidentifier() or format_spec or conversion:
            raise CatalogueTranslationFailure(f"malformed placeholder key={path_label(path)}")
        fields.append(field)
    counts = Counter(fields)
    if any(count > 1 for count in counts.values()):
        raise CatalogueTranslationFailure(f"duplicated placeholder key={path_label(path)}")
    return counts


def validate_placeholders(source: str, target: str, path: CataloguePath) -> None:
    if placeholder_fields(source, path) != placeholder_fields(target, path):
        raise CatalogueTranslationFailure(f"placeholder mismatch key={path_label(path)}")


def reviewed_keys(document: dict[str, Any], available: dict[CataloguePath, str]) -> set[CataloguePath]:
    reviewed = document.get("reviewed")
    if not isinstance(reviewed, list) or not all(isinstance(key, str) for key in reviewed):
        raise CatalogueTranslationFailure("reviewed must be a list of catalogue keys")
    if len(reviewed) != len(set(reviewed)):
        raise CatalogueTranslationFailure("reviewed contains duplicate keys")
    labels = {reviewed_label(path): path for path in available}
    unknown = sorted(set(reviewed) - set(labels))
    if unknown:
        raise CatalogueTranslationFailure(f"reviewed key missing: {unknown[0]}")
    return {labels[key] for key in reviewed}


def validate_metadata(document: dict[str, Any], code: str) -> None:
    if document.get("code") != code:
        raise CatalogueTranslationFailure(f"target code must be {code}")
    if not isinstance(document.get("prefix"), str):
        raise CatalogueTranslationFailure("target prefix is missing")
    for key in ("group", "decimal"):
        if not isinstance(document.get(key), str) or not document[key]:
            raise CatalogueTranslationFailure(f"target {key} separator is missing")


def validate_structure(source: dict[CataloguePath, str], target: dict[CataloguePath, str]) -> None:
    missing = sorted(set(source) - set(target))
    extra = sorted(set(target) - set(source))
    if missing or extra:
        detail = missing[0] if missing else extra[0]
        raise CatalogueTranslationFailure(f"catalogue structure mismatch key={path_label(detail)}")


def protect_glossary(value: str, code: str) -> tuple[str, list[str]]:
    glossary = GLOSSARIES[code]
    matches = sorted(glossary, key=len, reverse=True)
    replacements: list[str] = []
    protected = value
    for source in matches:
        while source in protected:
            token = f"zzxqg{len(replacements)}zz"
            protected = protected.replace(source, token, 1)
            replacements.append(glossary[source])
    return protected, replacements


def restore_glossary(value: str, replacements: list[str]) -> str:
    indexes = [int(match.group(1)) for match in PLACEHOLDER.finditer(value)]
    if Counter(indexes) != Counter(range(len(replacements))):
        raise CatalogueTranslationFailure("translation changed glossary placeholders")

    def replacement(match: re.Match[str]) -> str:
        index = int(match.group(1))
        return replacements[index]

    restored = PLACEHOLDER.sub(replacement, value)
    return restored


def protect_format_fields(value: str, path: CataloguePath) -> tuple[str, list[str]]:
    """Shield valid ``str.format`` fields from a provider's natural-language pass."""
    fields = list(placeholder_fields(value, path))
    protected = value
    for index, field in enumerate(fields):
        protected = protected.replace(f"{{{field}}}", f"zzxqf{index}zz", 1)
    return protected, fields


def restore_format_fields(value: str, fields: list[str], path: CataloguePath) -> str:
    indexes = [int(match.group(1)) for match in FORMAT_PLACEHOLDER.finditer(value)]
    if Counter(indexes) != Counter(range(len(fields))):
        raise CatalogueTranslationFailure(f"translation changed format placeholders key={path_label(path)}")
    return FORMAT_PLACEHOLDER.sub(lambda match: f"{{{fields[int(match.group(1))]}}}", value)


def deepl_translator(auth_key: str, api_url: str = DEEPL_API_URL) -> Translator:
    if not auth_key:
        raise CatalogueTranslationFailure("DEEPL_AUTH_KEY is required for the deepl provider")

    def translate(value: str, code: str) -> str:
        body = json.dumps({"text": [value], "target_lang": code.upper(), "source_lang": "EN"}).encode()
        request = urllib.request.Request(
            api_url,
            data=body,
            headers={"Authorization": f"DeepL-Auth-Key {auth_key}", "Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as error:
            raise CatalogueTranslationFailure(f"translation provider failed with HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
            raise CatalogueTranslationFailure("translation provider failed") from error
        try:
            translated = payload["translations"]
            result = translated[0]["text"]
        except (KeyError, IndexError, TypeError) as error:
            raise CatalogueTranslationFailure("translation provider returned an invalid response") from error
        if not isinstance(result, str) or not result:
            raise CatalogueTranslationFailure("translation provider returned an empty translation")
        return result

    return translate


def google_translator(api_url: str = GOOGLE_TRANSLATE_URL) -> Translator:
    """Return the public Google Translate endpoint adapter used for draft catalogues.

    It requires no credential.  The generated result remains a draft until the
    `reviewed` manifest records a human review, exactly like a DeepL result.
    """

    def translate(value: str, code: str) -> str:
        query = urllib.parse.urlencode({"client": "gtx", "sl": "en", "tl": code, "dt": "t", "q": value})
        request = urllib.request.Request(f"{api_url}?{query}", headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as error:
            raise CatalogueTranslationFailure(f"translation provider failed with HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
            raise CatalogueTranslationFailure("translation provider failed") from error
        if not isinstance(payload, list) or not payload or not isinstance(payload[0], list):
            raise CatalogueTranslationFailure("translation provider returned an invalid response")
        pieces = [part[0] for part in payload[0] if isinstance(part, list) and part and isinstance(part[0], str)]
        result = "".join(pieces)
        if not result:
            raise CatalogueTranslationFailure("translation provider returned an empty translation")
        return result

    return translate


def render_table(path: list[str], table: dict[str, Any], lines: list[str]) -> None:
    lines.append("[" + ".".join(toml_key(part) for part in path) + "]")
    for key in sorted(key for key, value in table.items() if not isinstance(value, dict)):
        value = table[key]
        if not isinstance(value, str):
            raise CatalogueTranslationFailure(f"invalid value at {'.'.join(path + [key])}")
        lines.append(f"{toml_key(key)} = {toml_string(value)}")
    lines.append("")
    for key in sorted(key for key, value in table.items() if isinstance(value, dict)):
        render_table(path + [key], table[key], lines)


def render_catalogue(document: dict[str, Any]) -> str:
    lines = [
        f"code = {toml_string(document['code'])}",
        f"prefix = {toml_string(document['prefix'])}",
        f"group = {toml_string(document['group'])}",
        f"decimal = {toml_string(document['decimal'])}",
        "reviewed = [" + ", ".join(toml_string(key) for key in document["reviewed"]) + "]",
        "",
    ]
    for section in TRANSLATABLE_SECTIONS:
        render_table([section], document[section], lines)
    return "\n".join(lines)


def atomic_write(destination: Path, content: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent, text=True)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def bootstrap_catalogue(source_path: Path, target_path: Path, code: str) -> None:
    """Create the initial complete, explicitly unreviewed target catalogue."""
    if code not in TARGET_CODES:
        raise CatalogueTranslationFailure("target must be es or fr")
    if target_path.exists():
        raise CatalogueTranslationFailure(f"target catalogue already exists: {target_path.name}")
    source_document = load_toml(source_path)
    translatable_values(source_document)
    target_document = copy.deepcopy(source_document)
    target_document.update({"code": code, "prefix": f"/{code}/", "group": "." if code == "es" else "\u202f", "decimal": ",", "reviewed": []})
    atomic_write(target_path, render_catalogue(target_document))


def mark_reviewed(target_path: Path, sections: list[str], keys: list[str]) -> int:
    """Persist human review decisions as parseable catalogue-key manifests."""
    document = load_toml(target_path)
    values = translatable_values(document)
    existing = {reviewed_label(path) for path in reviewed_keys(document, values)}
    selected = set(keys)
    for section in sections:
        selected.update(reviewed_label(path) for path in values if path[0] == section)
    unknown = sorted(selected - {reviewed_label(path) for path in values})
    if unknown:
        raise CatalogueTranslationFailure(f"review key missing: {unknown[0]}")
    document["reviewed"] = sorted(existing | selected)
    atomic_write(target_path, render_catalogue(document))
    return len(selected - existing)


def translate_catalogue(source_path: Path, target_path: Path, code: str, translator: Translator) -> tuple[int, int]:
    """Translate unreviewed values and atomically replace *target_path* after validation."""
    if code not in TARGET_CODES:
        raise CatalogueTranslationFailure("target must be es or fr")

    source_document = load_toml(source_path)
    target_document = load_toml(target_path)
    validate_metadata(target_document, code)
    source_values = translatable_values(source_document)
    target_values = translatable_values(target_document)
    validate_structure(source_values, target_values)
    reviewed = reviewed_keys(target_document, target_values)
    updated = copy.deepcopy(target_document)
    translated_count = 0
    preserved_count = 0

    for path, source_value in source_values.items():
        target_value = target_values[path]
        if path in reviewed:
            validate_placeholders(source_value, target_value, path)
            preserved_count += 1
            continue
        protected_fields, fields = protect_format_fields(source_value, path)
        protected, replacements = protect_glossary(protected_fields, code)
        translated = restore_glossary(translator(protected, code), replacements)
        translated = restore_format_fields(translated, fields, path)
        validate_placeholders(source_value, translated, path)
        set_path(updated, path, translated)
        translated_count += 1

    validate_structure(source_values, translatable_values(updated))
    for path, source_value in source_values.items():
        validate_placeholders(source_value, get_path(updated, path), path)
    atomic_write(target_path, render_catalogue(updated))
    return translated_count, preserved_count


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    dataset_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=sorted(TARGET_CODES), help="catalogue language to regenerate")
    parser.add_argument("--source", type=Path, default=dataset_dir / "website" / "i18n" / "en.toml", help="authoritative English catalogue")
    parser.add_argument("--catalogue", type=Path, help="target catalogue (defaults to website/i18n/<target>.toml)")
    parser.add_argument("--bootstrap", action="store_true", help="create a complete unreviewed target catalogue before its first translation")
    parser.add_argument("--review-section", action="append", choices=TRANSLATABLE_SECTIONS, default=[], help="mark a reviewed catalogue section after human review")
    parser.add_argument("--review-key", action="append", default=[], help="mark one fully qualified key after human review")
    parser.add_argument(
        "--provider",
        choices=("deepl", "google"),
        default="deepl",
        help="authoring translation provider; deepl requires DEEPL_AUTH_KEY, google creates a reviewable draft",
    )
    parser.add_argument("--deepl-api-url", default=os.environ.get("DEEPL_API_URL", DEEPL_API_URL), help="DeepL endpoint; credentials remain in DEEPL_AUTH_KEY")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    destination = args.catalogue or args.source.parent / f"{args.target}.toml"
    try:
        if args.review_section or args.review_key:
            if args.bootstrap:
                raise CatalogueTranslationFailure("cannot bootstrap while recording review")
            recorded = mark_reviewed(destination.resolve(), args.review_section, args.review_key)
            print(f"reviewed={recorded}")
            return 0
        if args.bootstrap:
            bootstrap_catalogue(args.source.resolve(), destination.resolve(), args.target)
            print("translated=0 preserved=0 failed=0")
            return 0
        translator = (
            deepl_translator(os.environ.get("DEEPL_AUTH_KEY", ""), args.deepl_api_url)
            if args.provider == "deepl"
            else google_translator()
        )
        translated, preserved = translate_catalogue(args.source.resolve(), destination.resolve(), args.target, translator)
    except CatalogueTranslationFailure as error:
        log(f"catalogue translation failed: {error}")
        print("translated=0 preserved=0 failed=1")
        return 1
    except OSError:
        log("catalogue translation failed: file operation failed")
        print("translated=0 preserved=0 failed=1")
        return 1
    print(f"translated={translated} preserved={preserved} failed=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
