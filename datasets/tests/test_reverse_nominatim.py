from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import urllib.parse
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import reverse_nominatim as reverse

RESULT = {
    "display_name": "Karyal, Dharamkot Tahsil, Moga, Punjab, India",
    "osm_type": "node",
    "osm_id": 6006733944,
    "address": {"village": "Karyal", "state": "Punjab", "country": "India", "country_code": "in"},
}


class ReverseNominatimTests(unittest.TestCase):
    def test_parse_coordinates_uses_longitude_latitude_order(self) -> None:
        self.assertEqual((75.1857, 30.934), reverse.parse_coordinates("75.1857,30.9340"))
        with self.assertRaisesRegex(ValueError, "longitude,latitude"):
            reverse.parse_coordinates("75.1857")

    def test_lookup_sends_longitude_and_latitude_and_uses_cache(self) -> None:
        response = MagicMock()
        response.__enter__.return_value = io.StringIO(json.dumps(RESULT))
        cache_path = Path(tempfile.mktemp(suffix=".json"))
        with patch.object(reverse.urllib.request, "urlopen", return_value=response) as urlopen, patch.object(reverse.time, "sleep"):
            self.assertEqual(RESULT, reverse.lookup(75.1857, 30.934, cache_path))

        query = urllib.parse.parse_qs(urllib.parse.urlparse(urlopen.call_args.args[0].full_url).query)
        self.assertEqual(["75.1857"], query["lon"])
        self.assertEqual(["30.934"], query["lat"])
        with patch.object(reverse.urllib.request, "urlopen") as cached_urlopen:
            self.assertEqual(RESULT, reverse.lookup(75.1857, 30.934, cache_path))
            cached_urlopen.assert_not_called()
        cache_path.unlink()

    def test_clean_normalizes_village_as_city(self) -> None:
        self.assertEqual(
            {"city": "Karyal", "state": "Punjab", "country": "India", "country_code": "in", "display_name": RESULT["display_name"], "osm_type": "node", "osm_id": 6006733944},
            reverse.clean(RESULT),
        )

    def test_main_prints_json(self) -> None:
        stdout = io.StringIO()
        with patch.object(reverse, "lookup", return_value=RESULT), redirect_stdout(stdout):
            self.assertEqual(0, reverse.main(["--coordinates", "75.1857,30.9340"]))
        self.assertEqual("Karyal", json.loads(stdout.getvalue())["city"])


if __name__ == "__main__":
    unittest.main()
