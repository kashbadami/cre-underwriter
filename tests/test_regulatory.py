"""
Overlay tests. No network: every case passes a synthetic Assessor parcel dict,
which is also a check that the overlay depends only on fields the real adapter
actually returns.
"""

import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cre_underwriter.deal import Deal
from cre_underwriter.regulatory import overlay_for
from cre_underwriter.statutes import Statutes

ST = Statutes.load()


def parcel(city="LOS ANGELES CA", year=1955, units=14, lat=34.09, lon=-118.29):
    return {
        "situs_city": city,
        "year_built": year,
        "units": units,
        "sqft_main": 12000.0,
        "sqft_lot": 8000.0,
        "ain": "0000000000",
        "latitude": lat,
        "longitude": lon,
        "current_assessed_total": 1_000_000.0,
        "current_roll_year": "2026",
        "current_land_value": 600_000.0,
        "current_improvement_value": 400_000.0,
    }


def build(price=4_750_000.0, **pk):
    p = parcel(**pk)
    d = Deal.from_dict({"address": "1 Test St", "price": price})
    d.apply_assessor(p, "https://example.invalid/parcel", "2026-09-02")
    return d, overlay_for(d, ST, parcel=p)


def finding(ov, key):
    v = ov.fields.get(key)
    return v.value if v is not None and v.is_known else None


class TestRsoDetermination(unittest.TestCase):
    def test_pre_1978_reads_as_likely_covered(self):
        _, ov = build(year=1955)
        self.assertIn("LIKELY COVERED", finding(ov, "la_city_rso_status"))

    def test_post_1978_reads_as_likely_not_covered(self):
        _, ov = build(year=2019)
        self.assertIn("LIKELY NOT COVERED", finding(ov, "la_city_rso_status"))

    def test_1978_itself_is_indeterminate_not_a_coin_flip(self):
        # The cut-off is 1 October 1978 and the Assessor carries only a year.
        _, ov = build(year=1978)
        self.assertIn("INDETERMINATE", finding(ov, "la_city_rso_status"))

    def test_determination_is_always_offered_as_manual_with_a_url(self):
        _, ov = build(year=1955)
        v = ov.fields["la_city_rso_determination"]
        self.assertEqual(v.tag, "manual")
        self.assertIn("zimas", v.source)

    def test_status_is_derived_never_auto(self):
        # Nobody fetched an RSO status. The tool reasoned to it.
        _, ov = build(year=1955)
        self.assertEqual(ov.fields["la_city_rso_status"].tag, "derived")

    def test_outside_la_city_the_la_ordinance_is_not_applied(self):
        _, ov = build(city="BURBANK CA", year=1955)
        self.assertIn("Not applicable", finding(ov, "la_city_rso_status"))

    def test_no_year_built_means_no_determination(self):
        p = parcel(year=None)
        d = Deal.from_dict({"address": "1 Test St", "price": 1_000_000.0})
        d.apply_assessor(p, "u", "2026-09-02")
        ov = overlay_for(d, ST, parcel=p)
        self.assertEqual(ov.fields["la_city_rso_status"].tag, "missing")

    def test_jurisdiction_caveat_is_always_raised(self):
        _, ov = build()
        self.assertTrue(any("postal city name" in c.text for c in ov.caveats))


class TestAb1482(unittest.TestCase):
    def test_new_construction_is_exempt_and_the_window_rolls(self):
        _, ov = build(year=2019)
        s = finding(ov, "ab_1482_status")
        self.assertIn("EXEMPT", s)
        self.assertIn("2034", s)

    def test_old_building_in_la_city_is_superseded_by_the_rso(self):
        _, ov = build(year=1955)
        self.assertIn("SUPERSEDED", finding(ov, "ab_1482_status"))

    def test_old_building_outside_the_rso_gets_the_state_cap(self):
        _, ov = build(city="BURBANK CA", year=1955)
        self.assertIn("LIKELY APPLIES", finding(ov, "ab_1482_status"))
        self.assertEqual(finding(ov, "ab_1482_max_increase_pct"), 8.7)


class TestSantaMonica(unittest.TestCase):
    def test_santa_monica_gets_its_own_regime_not_the_la_one(self):
        _, ov = build(city="SANTA MONICA CA", year=1955)
        self.assertIn("Separate rent control", finding(ov, "santa_monica_regime"))
        self.assertIn("Not applicable", finding(ov, "la_city_rso_status"))

    def test_the_dollar_cap_is_surfaced_as_a_caveat(self):
        _, ov = build(city="SANTA MONICA CA", year=1955)
        self.assertTrue(any("capped in dollars" in c.text for c in ov.caveats))

    def test_coverage_cutoff_is_manual_because_it_is_not_in_the_config(self):
        _, ov = build(city="SANTA MONICA CA", year=1955)
        self.assertEqual(ov.fields["santa_monica_coverage_cutoff"].tag, "manual")

    def test_la_city_sections_do_not_appear(self):
        _, ov = build(city="SANTA MONICA CA", year=1955)
        self.assertNotIn("santa_monica_regime", build(year=1955)[1].fields)


class TestSb79(unittest.TestCase):
    def test_never_determined(self):
        _, ov = build()
        self.assertEqual(ov.fields["sb_79_transit_upzoning_exposure"].tag, "manual")
        self.assertEqual(finding(ov, "sb_79_transit_upzoning_exposure"), "not determined")

    def test_blocking_caveat_is_raised_from_the_config_flag(self):
        _, ov = build()
        blocking = [c for c in ov.caveats if c.severity == "blocking"]
        self.assertTrue(any("SB 79" in c.text for c in blocking))

    def test_exactly_one_sb79_blocking_caveat(self):
        _, ov = build()
        n = len([c for c in ov.caveats if c.severity == "blocking" and "SB 79" in c.text])
        self.assertEqual(n, 1)


class TestUla(unittest.TestCase):
    def test_below_the_threshold_no_ula_is_due(self):
        _, ov = build(price=4_750_000.0)
        self.assertEqual(finding(ov, "ula_transfer_tax"), 0.0)

    def test_first_tier_is_flat_on_the_whole_price_not_the_increment(self):
        _, ov = build(price=6_000_000.0)
        self.assertEqual(finding(ov, "ula_transfer_tax"), 240_000.0)  # 4% of 6,000,000
        self.assertEqual(finding(ov, "ula_effective_rate_on_price_pct"), 4.0)

    def test_second_tier(self):
        _, ov = build(price=12_000_000.0)
        self.assertEqual(finding(ov, "ula_transfer_tax"), 660_000.0)  # 5.5% of 12,000,000

    def test_base_transfer_tax_is_separate_and_additional(self):
        _, ov = build(price=1_000_000.0)
        self.assertAlmostEqual(finding(ov, "base_documentary_transfer_tax"), 5_600.0)

    def test_not_applicable_outside_la_city(self):
        _, ov = build(city="BURBANK CA", price=12_000_000.0)
        self.assertIn("Not applicable", finding(ov, "ula_transfer_tax"))

    def test_the_config_tier_caveat_reaches_the_reader(self):
        _, ov = build(price=6_000_000.0)
        self.assertTrue(any("CONFIRM IN A BROWSER" in c.text for c in ov.caveats))


class TestNoBareNumbers(unittest.TestCase):
    def test_every_overlay_field_carries_a_tag_and_a_note_or_a_source(self):
        for city, year in (("LOS ANGELES CA", 1955), ("LOS ANGELES CA", 2019),
                           ("SANTA MONICA CA", 1955), ("BURBANK CA", 1955)):
            _, ov = build(city=city, year=year)
            for k, v in ov.fields.items():
                self.assertIn(v.tag, ("auto", "input", "derived", "manual", "default", "missing"))
                self.assertTrue(v.note or v.source, f"{k} has neither a note nor a source")


if __name__ == "__main__":
    unittest.main()
