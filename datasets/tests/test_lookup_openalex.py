from __future__ import annotations

import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import lookup_openalex as lookup


def openalex_item(
    ror: str,
    *,
    openalex_id: str = "I136199984",
    display_name: str = "Example University",
) -> dict:
    return {
        "id": f"https://openalex.org/{openalex_id}",
        "display_name": display_name,
        "ror": f"https://ror.org/{ror}",
    }


def make_database(
    path: Path,
    rows: list[tuple[str, str, str, str, str]],
    extras: list[tuple[str, int, str, str]] | None = None,
) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE awards (
                award_record_id TEXT PRIMARY KEY,
                affiliation_name TEXT,
                affiliation_city TEXT,
                affiliation_country TEXT,
                affiliation_wikidata_qid TEXT,
                affiliate_ror TEXT NOT NULL DEFAULT '',
                institution_openalex_id TEXT NOT NULL DEFAULT ''
            ) STRICT;
            CREATE TABLE award_extra_affiliations (
                award_record_id TEXT NOT NULL,
                position INTEGER NOT NULL CHECK (position >= 2),
                affiliation_name TEXT NOT NULL DEFAULT '',
                affiliation_wikidata_qid TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (award_record_id, position)
            ) STRICT;
            """
        )
        connection.executemany(
            """
            INSERT INTO awards (
                award_record_id, affiliation_name, affiliation_city, affiliation_country,
                affiliation_wikidata_qid, affiliate_ror, institution_openalex_id
            ) VALUES (?, ?, '', '', ?, ?, ?)
            """,
            rows,
        )
        if extras:
            connection.executemany(
                """
                INSERT INTO award_extra_affiliations (
                    award_record_id, position, affiliation_name, affiliation_wikidata_qid
                ) VALUES (?, ?, ?, ?)
                """,
                extras,
            )


def http_error(status: int, retry_after: str | None = None) -> urllib.error.HTTPError:
    headers: dict[str, str] = {}
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError(
        url="https://api.openalex.org/institutions",
        code=status,
        msg="error",
        hdrs=headers,
        fp=None,
    )


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self._body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return self._body


class OpenalexLookupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "awards.sqlite3"
        self.env_path = Path(self.tmp.name) / ".env"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_no_selector_fails(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            lookup.main(["--db", str(self.db_path)])
        self.assertEqual(2, raised.exception.code)

    def test_mutually_exclusive_operations(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            lookup.main(["--db", str(self.db_path), "--record-id", "x", "--all"])
        self.assertEqual(2, raised.exception.code)

    def test_duplicate_record_ids_fail(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            lookup.main(["--db", str(self.db_path), "--record-id", "x", "--record-id", "x"])
        self.assertEqual(2, raised.exception.code)

    def test_unknown_record_id_fails_before_network(self) -> None:
        make_database(self.db_path, [])
        with patch.object(lookup, "query_openalex") as mocked:
            result = lookup.main(["--db", str(self.db_path), "--record-id", "missing"])
        self.assertEqual(1, result)
        mocked.assert_not_called()

    def test_all_selects_only_actionable_rows(self) -> None:
        make_database(self.db_path, [
            ("r1", "MIT", "Q49108", "03vek6s52", ""),
            ("r2", "MIT", "Q49108", "03vek6s52", "I999"),
            ("r3", "Harvard", "Q13371", "", ""),
        ])
        with patch.object(lookup, "query_openalex", return_value=(200, openalex_item("03vek6s52"))):
            report = self._run_preview(["--all"])
        ids = [r["award_record_id"] for r in report["results"]]
        self.assertEqual(ids, ["r1"])

    def test_record_id_allows_missing_ror_and_unchanged(self) -> None:
        make_database(self.db_path, [
            ("r1", "Harvard", "Q13371", "", ""),
            ("r2", "MIT", "Q49108", "03vek6s52", "I999"),
        ])
        with patch.object(lookup, "query_openalex") as mocked:
            report = self._run_preview(["--record-id", "r1", "--record-id", "r2"])
        statuses = {r["award_record_id"]: r["status"] for r in report["results"]}
        self.assertEqual(statuses["r1"], "blocked_missing_ror")
        self.assertEqual(statuses["r2"], "unchanged")
        mocked.assert_not_called()

    def test_qid_name_conflict_blocks(self) -> None:
        make_database(self.db_path, [
            ("r1", "MIT Old", "Q49108", "03vek6s52", ""),
        ], extras=[("r1", 2, "MIT New", "Q49108")])
        with patch.object(lookup, "query_openalex") as mocked:
            report = self._run_preview(["--all"])
        self.assertEqual(report["results"][0]["status"], "blocked_qid_name_conflict")
        mocked.assert_not_called()

    def test_name_qid_conflict_blocks(self) -> None:
        make_database(self.db_path, [
            ("r1", "MIT", "Q49108", "03vek6s52", ""),
        ], extras=[("r1", 2, "MIT", "Q99999")])
        with patch.object(lookup, "query_openalex") as mocked:
            report = self._run_preview(["--all"])
        self.assertEqual(report["results"][0]["status"], "blocked_name_qid_conflict")
        mocked.assert_not_called()

    def test_exact_match_confirmed(self) -> None:
        make_database(self.db_path, [("r1", "MIT", "Q49108", "03vek6s52", "")])
        with patch.object(lookup, "query_openalex", return_value=(200, openalex_item("03vek6s52"))):
            report = self._run_preview(["--all"])
        result = report["results"][0]
        self.assertEqual(result["status"], "confirmed")
        self.assertEqual(result["updates"], {"institution_openalex_id": "I136199984"})
        self.assertNotIn("api_key=", result["request_url"])

    def test_wrong_ror_abstains(self) -> None:
        make_database(self.db_path, [("r1", "MIT", "Q49108", "03vek6s52", "")])
        payload = {
            "id": "https://openalex.org/I99999999",
            "display_name": "Wrong",
            "ror": "https://ror.org/00000000",
        }
        with patch.object(lookup, "query_openalex", return_value=(200, payload)):
            report = self._run_preview(["--all"])
        result = report["results"][0]
        self.assertEqual(result["status"], "abstained_not_found")
        self.assertEqual(result["updates"], {})
        self.assertEqual(result["openalex_record"]["ror"], "https://ror.org/00000000")

    def test_404_abstains(self) -> None:
        make_database(self.db_path, [("r1", "MIT", "Q49108", "03vek6s52", "")])
        with patch.object(lookup, "query_openalex", return_value=(404, None)):
            report = self._run_preview(["--all"])
        result = report["results"][0]
        self.assertEqual(result["status"], "abstained_not_found")
        self.assertIsNone(result["openalex_record"])

    def test_http_500_fails(self) -> None:
        make_database(self.db_path, [("r1", "MIT", "Q49108", "03vek6s52", "")])
        with patch.object(lookup, "query_openalex", side_effect=lookup.OpenalexFailure("HTTP 500")):
            result = lookup.main(["--db", str(self.db_path), "--all"])
        self.assertEqual(1, result)

    def test_repeated_ror_shares_one_request(self) -> None:
        make_database(self.db_path, [
            ("r1", "MIT", "Q49108", "03vek6s52", ""),
            ("r2", "MIT", "Q49108", "03vek6s52", ""),
            ("r3", "MIT", "Q49108", "03vek6s52", ""),
        ])
        with patch.object(lookup, "query_openalex", return_value=(200, openalex_item("03vek6s52"))) as mocked:
            report = self._run_preview(["--all"])
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(len(report["results"]), 3)
        for r in report["results"]:
            self.assertEqual(r["status"], "confirmed")

    def test_malformed_openalex_response_fails(self) -> None:
        make_database(self.db_path, [("r1", "MIT", "Q49108", "03vek6s52", "")])
        with patch.object(lookup, "query_openalex", return_value=(200, {"id": "not-a-url"})):
            result = lookup.main(["--db", str(self.db_path), "--all"])
        self.assertEqual(1, result)

    def test_malformed_openalex_id_fails(self) -> None:
        make_database(self.db_path, [("r1", "MIT", "Q49108", "03vek6s52", "")])
        payload = {
            "id": "https://openalex.org/not-a-number",
            "display_name": "X",
            "ror": "https://ror.org/03vek6s52",
        }
        with patch.object(lookup, "query_openalex", return_value=(200, payload)):
            result = lookup.main(["--db", str(self.db_path), "--all"])
        self.assertEqual(1, result)

    def test_apply_writes_only_blank_cells(self) -> None:
        make_database(self.db_path, [("r1", "MIT", "Q49108", "03vek6s52", "")])
        with patch.object(lookup, "query_openalex", return_value=(200, openalex_item("03vek6s52"))):
            report = self._run_preview(["--all"])
        report_path = Path(self.tmp.name) / "report.json"
        report_path.write_text(json.dumps(report))
        with patch.object(lookup, "query_openalex") as mocked:
            result = self._run_apply(report_path)
        self.assertEqual(0, result)
        mocked.assert_not_called()
        with sqlite3.connect(self.db_path) as connection:
            value = connection.execute(
                "SELECT institution_openalex_id FROM awards WHERE award_record_id='r1'"
            ).fetchone()[0]
        self.assertEqual(value, "I136199984")

    def test_apply_rolls_back_on_drift(self) -> None:
        make_database(self.db_path, [
            ("r1", "MIT", "Q49108", "03vek6s52", ""),
            ("r2", "MIT", "Q49108", "03vek6s52", ""),
        ])
        with patch.object(lookup, "query_openalex", return_value=(200, openalex_item("03vek6s52"))):
            report = self._run_preview(["--all"])
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "UPDATE awards SET affiliate_ror = ? WHERE award_record_id IN ('r1', 'r2')",
                ("differentror0",),
            )
            connection.commit()
        report_path = Path(self.tmp.name) / "report.json"
        report_path.write_text(json.dumps(report))
        result = self._run_apply(report_path)
        self.assertEqual(1, result)
        with sqlite3.connect(self.db_path) as connection:
            values = [row[0] for row in connection.execute(
                "SELECT institution_openalex_id FROM awards ORDER BY award_record_id"
            ).fetchall()]
        self.assertEqual(values, ["", ""])

    def test_apply_rejects_unexpected_updates(self) -> None:
        make_database(self.db_path, [])
        bad = {
            "report_version": 1,
            "mode": "preview",
            "database": str(self.db_path),
            "processed": 1,
            "status_totals": {s: 0 for s in lookup.STATUSES} | {"blocked_missing_ror": 1},
            "results": [{
                "award_record_id": "r1",
                "affiliation_name": "MIT",
                "affiliation_wikidata_qid": "Q49108",
                "affiliate_ror": "garbage",
                "institution_openalex_id": "",
                "status": "blocked_missing_ror",
                "reason": "x",
                "updates": {"institution_openalex_id": "I1"},
            }],
        }
        report_path = Path(self.tmp.name) / "report.json"
        report_path.write_text(json.dumps(bad))
        result = self._run_apply(report_path)
        self.assertEqual(1, result)

    def test_env_file_missing_treated_as_no_key(self) -> None:
        self.assertFalse(self.env_path.exists())
        make_database(self.db_path, [("r1", "MIT", "Q49108", "03vek6s52", "")])
        url = self._capture_request_url()
        self.assertNotIn("api_key=", url)

    def test_env_file_provides_key(self) -> None:
        self.env_path.write_text("OPENALEX_API = 'abc123'\n", encoding="utf-8")
        make_database(self.db_path, [("r1", "MIT", "Q49108", "03vek6s52", "")])
        url = self._capture_request_url()
        self.assertIn("api_key=abc123", url)

    def test_env_file_blank_treated_as_unset(self) -> None:
        self.env_path.write_text("OPENALEX_API='   '\n", encoding="utf-8")
        make_database(self.db_path, [("r1", "MIT", "Q49108", "03vek6s52", "")])
        url = self._capture_request_url()
        self.assertNotIn("api_key=", url)

    def test_os_environ_overrides_env_file(self) -> None:
        self.env_path.write_text("OPENALEX_API='fromfile'\n", encoding="utf-8")
        make_database(self.db_path, [("r1", "MIT", "Q49108", "03vek6s52", "")])
        with patch.dict(os.environ, {"OPENALEX_API": "fromenv"}):
            url = self._capture_request_url()
        self.assertIn("api_key=fromenv", url)
        self.assertNotIn("fromfile", url)

    def test_retry_after_honored_once(self) -> None:
        make_database(self.db_path, [("r1", "MIT", "Q49108", "03vek6s52", "")])
        calls = {"n": 0}

        def fake_urlopen(request, timeout=0):
            calls["n"] += 1
            if calls["n"] == 1:
                raise http_error(429, retry_after="0")
            return FakeResponse(json.dumps(openalex_item("03vek6s52")).encode("utf-8"))

        with (
            patch.object(lookup.urllib.request, "urlopen", side_effect=fake_urlopen),
            patch.object(lookup.time, "sleep"),
        ):
            report = self._run_preview(["--all"])
        self.assertEqual(calls["n"], 2)
        self.assertEqual(report["results"][0]["status"], "confirmed")

    def test_repeated_429_fails(self) -> None:
        make_database(self.db_path, [("r1", "MIT", "Q49108", "03vek6s52", "")])

        def fake_urlopen(request, timeout=0):
            raise http_error(429, retry_after="0")

        with (
            patch.object(lookup.urllib.request, "urlopen", side_effect=fake_urlopen),
            patch.object(lookup.time, "sleep"),
        ):
            result = lookup.main(["--db", str(self.db_path), "--all"])
        self.assertEqual(1, result)

    def test_429_without_retry_after_fails(self) -> None:
        make_database(self.db_path, [("r1", "MIT", "Q49108", "03vek6s52", "")])

        def fake_urlopen(request, timeout=0):
            raise http_error(429, retry_after=None)

        with patch.object(lookup.urllib.request, "urlopen", side_effect=fake_urlopen):
            result = lookup.main(["--db", str(self.db_path), "--all"])
        self.assertEqual(1, result)

    def _run_preview(self, args: list[str]) -> dict:
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = lookup.main(["--db", str(self.db_path), *args])
        self.assertEqual(0, result, msg=f"stderr: {stderr.getvalue()}")
        return json.loads(stdout.getvalue())

    def _run_apply(self, report_path: Path) -> int:
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = lookup.main(["--db", str(self.db_path), "--apply", str(report_path)])
        return result

    def _capture_request_url(self) -> str:
        captured: dict[str, str] = {}

        def fake_urlopen(request, timeout=0):
            captured["url"] = request.full_url
            return FakeResponse(json.dumps(openalex_item("03vek6s52")).encode("utf-8"))

        with patch.object(lookup.urllib.request, "urlopen", side_effect=fake_urlopen):
            self._run_preview(["--all"])
        return captured["url"]


if __name__ == "__main__":
    unittest.main()