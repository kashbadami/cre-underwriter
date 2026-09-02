"""
Assessor adapter tests. The network is stubbed, so these run anywhere and test
the disambiguation logic rather than the county's uptime.

The disambiguation is worth testing on its own because it is the one place the
adapter could quietly put the entire report on the wrong building. The search
endpoint is loose — a real query for "1223 N Edgemont St" returns 501 matches
across the county, most sharing only the house number.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cre_underwriter.provenance import Result
from cre_underwriter.sources import assessor

# The real shape of a search hit: five fields, and no parcel status among them.
MATCHES = [
    {"ain": "5540011009", "situs_street": "1223 N EDGEMONT ST",
     "situs_city": "LOS ANGELES CA", "situs_zip": "90029", "legal": "LOT 19"},
    {"ain": "5540011015", "situs_street": "1223 N EDGEMONT ST",
     "situs_city": "LOS ANGELES CA", "situs_zip": "90029", "legal": "EX OF ST LOT 19"},
    {"ain": "2438010010", "situs_street": "1223 N BRIGHTON ST",
     "situs_city": "BURBANK CA", "situs_zip": "91506", "legal": "LOT 10"},
]

DETAILS = {
    # The pre-2018 parcel: deleted, no units, no year built.
    "5540011009": {"ain": "5540011009", "status": "DELETED", "units": None,
                   "year_built": None, "situs_city": "LOS ANGELES CA"},
    # Its successor: the one you want.
    "5540011015": {"ain": "5540011015", "status": "ACTIVE", "units": 14,
                   "year_built": 2019, "situs_city": "LOS ANGELES CA"},
    "2438010010": {"ain": "2438010010", "status": "ACTIVE", "units": 1,
                   "year_built": 1941, "situs_city": "BURBANK CA"},
}


class Stub(unittest.TestCase):
    def setUp(self):
        self._search, self._detail = assessor.search_parcels, assessor.parcel_detail
        assessor.search_parcels = lambda q, **kw: Result(
            ok=True, data={"matches": MATCHES, "total_reported": 501},
            source_url="stub://search")
        assessor.parcel_detail = lambda ain, **kw: (
            Result(ok=True, data=DETAILS[ain], source_url=f"stub://detail/{ain}")
            if ain in DETAILS else Result(ok=False, error="no such AIN"))

    def tearDown(self):
        assessor.search_parcels, assessor.parcel_detail = self._search, self._detail


class TestFindOne(Stub):
    def test_prefers_the_active_successor_over_the_deleted_parcel(self):
        r = assessor.find_one("1223 N Edgemont St")
        self.assertTrue(r.ok)
        self.assertEqual(r.data["ain"], "5540011015")
        self.assertEqual(r.data["year_built"], 2019)

    def test_refuses_when_no_street_matches_exactly(self):
        # The stub always returns the same 3 hits, none on this street.
        r = assessor.find_one("400 S Fake Blvd")
        self.assertFalse(r.ok)
        self.assertIn("no parcel whose situs street matches", r.error)
        # And it shows what it did find rather than just failing.
        self.assertIn("1223 N EDGEMONT ST", r.error)

    def test_never_falls_back_to_the_top_hit(self):
        r = assessor.find_one("400 S Fake Blvd")
        self.assertFalse(r.ok)
        self.assertEqual(r.data, {})

    def test_street_normalisation_tolerates_punctuation_and_trailing_city(self):
        for q in ("1223 N. Edgemont St.", "1223  N EDGEMONT ST, Los Angeles",
                  "1223 n edgemont st"):
            r = assessor.find_one(q)
            self.assertTrue(r.ok, q)
            self.assertEqual(r.data["ain"], "5540011015", q)

    def test_an_ain_bypasses_the_search_entirely(self):
        r = assessor.find_one("5540011015")
        self.assertTrue(r.ok)
        self.assertEqual(r.data["ain"], "5540011015")

    def test_sibling_ains_are_reported_not_hidden(self):
        # Two active parcels with units on the same street would be ambiguous.
        DETAILS["5540011009"]["status"] = "ACTIVE"
        DETAILS["5540011009"]["units"] = 2
        try:
            r = assessor.find_one("1223 N Edgemont St")
            self.assertTrue(r.ok)
            self.assertIn("sibling_ains", r.data)
        finally:
            DETAILS["5540011009"]["status"] = "DELETED"
            DETAILS["5540011009"]["units"] = None


class TestAinHandling(unittest.TestCase):
    def test_looks_like_ain(self):
        self.assertTrue(assessor.looks_like_ain("5540011015"))
        self.assertTrue(assessor.looks_like_ain("5540-011-015"))
        self.assertFalse(assessor.looks_like_ain("1223 N Edgemont St"))
        self.assertFalse(assessor.looks_like_ain("554001101"))

    def test_detail_rejects_a_wrong_length_ain_without_a_request(self):
        r = assessor.parcel_detail("12345")
        self.assertFalse(r.ok)
        self.assertIn("10 digits", r.error)


if __name__ == "__main__":
    unittest.main()
