# SPDX-License-Identifier: GPL-2.0-or-later
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

from scripts import lookup_nominatim as lookup

RESULT = {"lon": "75.1856983", "lat": "30.9340256", "display_name": "Karyal, Punjab, India", "osm_type": "node", "osm_id": 6006733944}


class NominatimLookupTests(unittest.TestCase):
    def test_search_uses_structured_location_and_cache(self) -> None:
        response = MagicMock()
        response.__enter__.return_value = io.StringIO(json.dumps([RESULT]))
        cache_path = Path(tempfile.mktemp(suffix=".json"))
        with patch.object(lookup.urllib.request, "urlopen", return_value=response) as urlopen, patch.object(lookup.time, "sleep"):
            self.assertEqual([RESULT], lookup.search("Karyal", "India", "Punjab", cache_path))

        query = urllib.parse.parse_qs(urllib.parse.urlparse(urlopen.call_args.args[0].full_url).query)
        self.assertEqual({"city": ["Karyal"], "country": ["India"], "state": ["Punjab"], "format": ["jsonv2"], "limit": ["5"]}, query)
        with patch.object(lookup.urllib.request, "urlopen") as cached_urlopen:
            self.assertEqual([RESULT], lookup.search("Karyal", "India", "Punjab", cache_path))
            cached_urlopen.assert_not_called()
        cache_path.unlink()

    def test_clean_returns_dataset_coordinate_order(self) -> None:
        self.assertEqual("75.1857,30.9340", lookup.clean(RESULT)["dataset_coordinates"])

    def test_main_prints_json(self) -> None:
        stdout = io.StringIO()
        with patch.object(lookup, "search", return_value=[RESULT]), redirect_stdout(stdout):
            self.assertEqual(0, lookup.main(["--city", "Karyal", "--country", "India", "--state", "Punjab"]))

        output = json.loads(stdout.getvalue())
        self.assertEqual("Punjab", output["state"])
        self.assertEqual("75.1857,30.9340", output["results"][0]["dataset_coordinates"])


if __name__ == "__main__":
    unittest.main()
