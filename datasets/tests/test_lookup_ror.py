from __future__ import annotations

import io
import json
import sqlite3
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import lookup_ror as lookup


def ror_item(
    qid: str,
    *,
    ror_id: str = "03vek6s52",
    status: str = "active",
    display_name: str = "Example University",
) -> dict:
    return {
        "id": f"https://ror.org/{ror_id}",
        "status": status,
        "names": [{"types": ["ror_display", "label"], "value": display_name}],
        "external_ids": [{"type": "wikidata", "all": [qid], "preferred": qid}],
        "locations": [{
            "geonames_details": {
                "name": "Example City",
                "country_name": "Example Country",
                "country_code": "EX",
            },
        }],
    }


def response(*items: dict, count: int | None = None) -> dict:
    return {
        "number_of_results": len(items) if count is None else count,
        "items": list(items),
    }


class RorLookupTests(unittest.TestCase):
    def create_database(
        self,
        path: Path,
        rows: list[tuple[str, str, str, str]],
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
                    affiliate_ror TEXT NOT NULL DEFAULT ''
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
                    affiliation_wikidata_qid, affiliate_ror
                ) VALUES (?, ?, '', '', ?, ?)
                """,
                rows,
            )
            connection.executemany(
                """
                INSERT INTO award_extra_affiliations (
                    award_record_id, position, affiliation_name, affiliation_wikidata_qid
                ) VALUES (?, ?, ?, ?)
                """,
                extras or [],
            )

    def preview(
        self,
        database: Path,
        record_ids: list[str],
        payload: dict | None = None,
    ) -> dict:
        rows, qid_name_conflicts, name_qid_conflicts = lookup.read_inputs(database, record_ids)
        with (
            patch.object(lookup, "query_ror", return_value=payload or response(ror_item("Q1"))),
            patch.object(lookup.time, "sleep"),
        ):
            results = lookup.research(rows, qid_name_conflicts, name_qid_conflicts)
        return lookup.preview_report(str(database), results)

    def test_selector_is_required_before_database_access(self) -> None:
        with (
            patch.object(lookup, "read_inputs") as read_inputs,
            redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as raised,
        ):
            lookup.main(["--db", "missing.sqlite3"])

        self.assertEqual(2, raised.exception.code)
        read_inputs.assert_not_called()

    def test_operations_are_mutually_exclusive(self) -> None:
        with (
            redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as raised,
        ):
            lookup.main(["--db", "missing.sqlite3", "--all", "--record-id", "row-1"])

        self.assertEqual(2, raised.exception.code)

    def test_duplicate_record_id_fails_before_database_access(self) -> None:
        with (
            patch.object(lookup, "read_inputs") as read_inputs,
            redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as raised,
        ):
            lookup.main(["--db", "missing.sqlite3", "--record-id", "row-1", "--record-id", "row-1"])

        self.assertEqual(2, raised.exception.code)
        read_inputs.assert_not_called()

    def test_unknown_record_id_fails_before_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "awards.sqlite3"
            self.create_database(database, [("row-1", "Example University", "Q1", "")])

            with patch.object(lookup, "query_ror") as query_ror, redirect_stderr(io.StringIO()):
                result = lookup.main(["--db", str(database), "--record-id", "missing"])

        self.assertEqual(1, result)
        query_ror.assert_not_called()

    def test_active_and_inactive_exact_matches_are_confirmed(self) -> None:
        row = lookup.AffiliationRow("row-1", "Stored Name", "Stored City", "Stored Country", "Q1", "")
        for ror_status in ("active", "inactive"):
            with self.subTest(ror_status=ror_status):
                status, reason, matches = lookup.classify_response(
                    "Q1",
                    response(ror_item("Q1", status=ror_status)),
                )

                self.assertEqual("confirmed", status)
                self.assertIn(ror_status, reason)
                self.assertEqual("03vek6s52", matches[0]["ror_id"])
                self.assertEqual(["Q1"], matches[0]["wikidata_external_ids"])

                with patch.object(lookup, "query_ror", return_value=response(ror_item("Q1", status=ror_status))):
                    result = lookup.research([row], set(), set())[0]
                self.assertEqual({"affiliate_ror": "03vek6s52"}, result["updates"])

    def test_withdrawn_false_positive_and_ambiguous_matches_abstain(self) -> None:
        withdrawn = lookup.classify_response("Q1", response(ror_item("Q1", status="withdrawn")))
        false_positive = lookup.classify_response("Q1", response(ror_item("Q2")))
        ambiguous = lookup.classify_response(
            "Q1",
            response(
                ror_item("Q1", ror_id="03vek6s52"),
                ror_item("Q1", ror_id="04abcdf12"),
            ),
        )

        self.assertEqual("blocked_withdrawn", withdrawn[0])
        self.assertEqual("abstained_not_found", false_positive[0])
        self.assertEqual("03vek6s52", false_positive[2][0]["ror_id"])
        self.assertEqual("abstained_ambiguous", ambiguous[0])
        self.assertEqual(2, len(ambiguous[2]))

    def test_result_order_and_scores_do_not_affect_exact_matching(self) -> None:
        false_positive = ror_item("Q2", ror_id="04abcdf12")
        false_positive["score"] = 1.0
        exact = ror_item("Q1", ror_id="03vek6s52")
        exact["score"] = 0.01

        status, _, records = lookup.classify_response("Q1", response(false_positive, exact))

        self.assertEqual("confirmed", status)
        self.assertEqual(
            ["03vek6s52"],
            [record["ror_id"] for record in records if "Q1" in record["wikidata_external_ids"]],
        )

    def test_incomplete_and_malformed_responses_fail(self) -> None:
        cases = (
            response(ror_item("Q1"), count=2),
            {"number_of_results": 1, "items": "not-a-list"},
            response({"id": "https://ror.org/03vek6s52"}),
            response(ror_item("Q1", ror_id="03veki552")),
            response(ror_item("Q1", ror_id="not-an-id")),
        )
        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(lookup.RorFailure):
                lookup.classify_response("Q1", payload)

    def test_both_cross_store_identity_conflicts_block_requests(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "awards.sqlite3"
            self.create_database(
                database,
                [
                    ("row-1", "First University", "Q1", ""),
                    ("row-2", "Second University", "Q2", ""),
                ],
                [
                    ("row-2", 2, "Other Name", "Q1"),
                    ("row-2", 3, "Second University", "Q3"),
                ],
            )
            rows, qid_name_conflicts, name_qid_conflicts = lookup.read_inputs(database, ["row-1", "row-2"])

            with patch.object(lookup, "query_ror") as query_ror:
                results = lookup.research(rows, qid_name_conflicts, name_qid_conflicts)

        self.assertEqual(
            ["blocked_qid_name_conflict", "blocked_name_qid_conflict"],
            [result["status"] for result in results],
        )
        query_ror.assert_not_called()

    def test_missing_malformed_qid_missing_name_and_existing_ror_do_not_query(self) -> None:
        rows = [
            lookup.AffiliationRow("row-1", "Missing", "", "", "", ""),
            lookup.AffiliationRow("row-2", "Malformed", "", "", "q2", ""),
            lookup.AffiliationRow("row-3", "", "", "", "Q3", ""),
            lookup.AffiliationRow("row-4", "Existing", "", "", "Q4", "03vek6s52"),
        ]

        with patch.object(lookup, "query_ror") as query_ror:
            results = lookup.research(rows, set(), set())

        self.assertEqual(
            ["blocked_missing_qid", "blocked_missing_qid", "blocked_missing_name", "unchanged"],
            [result["status"] for result in results],
        )
        query_ror.assert_not_called()

    def test_rows_sharing_qid_use_one_request(self) -> None:
        rows = [
            lookup.AffiliationRow("row-1", "Example University", "", "", "Q1", ""),
            lookup.AffiliationRow("row-2", "Example University", "", "", "Q1", ""),
        ]

        with patch.object(lookup, "query_ror", return_value=response(ror_item("Q1"))) as query_ror:
            results = lookup.research(rows, set(), set())

        query_ror.assert_called_once_with("Q1")
        self.assertEqual(["confirmed", "confirmed"], [result["status"] for result in results])

    def test_transport_failure_is_not_an_abstention(self) -> None:
        row = lookup.AffiliationRow("row-1", "Example University", "", "", "Q1", "")

        with (
            patch.object(lookup, "query_ror", side_effect=lookup.RorFailure("network down")),
            self.assertRaisesRegex(lookup.RorFailure, "network down"),
        ):
            lookup.research([row], set(), set())

    def test_http_429_retries_once_using_retry_after(self) -> None:
        error = urllib.error.HTTPError(
            lookup.API_URL,
            429,
            "rate limited",
            {"Retry-After": "2"},
            None,
        )
        success = io.BytesIO(json.dumps(response(ror_item("Q1"))).encode())

        with (
            patch.object(lookup.urllib.request, "urlopen", side_effect=[error, success]) as urlopen,
            patch.object(lookup.time, "sleep") as sleep,
        ):
            payload = lookup.query_ror("Q1")

        self.assertEqual(1, payload["number_of_results"])
        self.assertEqual(2, urlopen.call_count)
        sleep.assert_called_once_with(2.0)

    def test_repeated_http_429_fails(self) -> None:
        error = urllib.error.HTTPError(
            lookup.API_URL,
            429,
            "rate limited",
            {"Retry-After": "0"},
            None,
        )
        with (
            patch.object(lookup.urllib.request, "urlopen", side_effect=[error, error]),
            patch.object(lookup.time, "sleep"),
            self.assertRaisesRegex(lookup.RorFailure, "without a usable retry"),
        ):
            lookup.query_ror("Q1")

    def test_invalid_json_response_fails_visibly(self) -> None:
        with (
            patch.object(lookup.urllib.request, "urlopen", return_value=io.BytesIO(b"{")),
            self.assertRaisesRegex(lookup.RorFailure, "invalid JSON"),
        ):
            lookup.query_ror("Q1")

    def test_apply_changes_only_blank_ror_and_makes_no_request(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "awards.sqlite3"
            report_path = Path(temporary) / "preview.json"
            self.create_database(
                database,
                [
                    ("row-1", "Example University", "Q1", ""),
                    ("row-2", "Curated University", "Q2", "04abcdf12"),
                ],
            )
            report = self.preview(database, ["row-1", "row-2"])
            report_path.write_text(json.dumps(report), encoding="utf-8")

            output = io.StringIO()
            with (
                patch.object(lookup, "query_ror") as query_ror,
                redirect_stdout(output),
                redirect_stderr(io.StringIO()),
            ):
                exit_code = lookup.main(["--db", str(database), "--apply", str(report_path)])

            with sqlite3.connect(database) as connection:
                stored = connection.execute(
                    "SELECT award_record_id, affiliate_ror FROM awards ORDER BY award_record_id"
                ).fetchall()

        self.assertEqual(0, exit_code)
        query_ror.assert_not_called()
        self.assertEqual([("row-1", "03vek6s52"), ("row-2", "04abcdf12")], stored)
        self.assertEqual(1, json.loads(output.getvalue())["database_apply"]["affected_rows"])

    def test_invalid_report_fails_before_transaction(self) -> None:
        report = lookup.preview_report("awards.sqlite3", [])
        report["status_totals"]["unexpected"] = 1

        with self.assertRaisesRegex(lookup.RorFailure, "status totals"):
            lookup.validate_report(report, "awards.sqlite3")

    def test_report_rejects_unexpected_update_field(self) -> None:
        row = lookup.AffiliationRow("row-1", "Example University", "", "", "Q1", "")
        with patch.object(lookup, "query_ror", return_value=response(ror_item("Q1"))):
            report = lookup.preview_report("awards.sqlite3", lookup.research([row], set(), set()))
        report["results"][0]["updates"]["affiliation_name"] = "Injected"

        with self.assertRaisesRegex(lookup.RorFailure, "confirmed"):
            lookup.validate_report(report, "awards.sqlite3")

    def test_name_qid_and_ror_drift_each_roll_back_the_batch(self) -> None:
        mutations = (
            ("affiliation_name", "Changed University"),
            ("affiliation_wikidata_qid", "Q9"),
            ("affiliate_ror", "04abcdf12"),
        )
        for field, value in mutations:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                database = Path(temporary) / "awards.sqlite3"
                self.create_database(
                    database,
                    [
                        ("row-1", "Example University", "Q1", ""),
                        ("row-2", "Example University", "Q1", ""),
                    ],
                )
                report = self.preview(database, ["row-1", "row-2"])
                with sqlite3.connect(database) as connection:
                    connection.execute(f"UPDATE awards SET {field} = ? WHERE award_record_id = 'row-2'", (value,))

                with self.assertRaisesRegex(lookup.RorFailure, "database drift"):
                    lookup.apply_updates(database, report["results"])

                with sqlite3.connect(database) as connection:
                    first_ror = connection.execute(
                        "SELECT affiliate_ror FROM awards WHERE award_record_id = 'row-1'"
                    ).fetchone()[0]
                self.assertEqual("", first_ror)


if __name__ == "__main__":
    unittest.main()
