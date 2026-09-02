"""
Arithmetic tests with numbers small enough to check on paper.

Run: python3 -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cre_underwriter import underwriting
from cre_underwriter.deal import Deal
from cre_underwriter.statutes import Statutes

BASE = {
    "address": "1 Test St",
    "price": 1_000_000.0,
    "units": 10,
    "rentable_sf": 10_000.0,
    "building_sf_assessor": 10_000.0,
    "gross_scheduled_rent_annual": 100_000.0,
    "vacancy_pct": 0.0,
    "operating_expenses_annual": 30_000.0,
    "property_tax_rate_pct": 1.0,
    "direct_assessments_annual": 0.0,
}


def run(**over):
    d = dict(BASE)
    d.update(over)
    return underwriting.run(Deal.from_dict(d), Statutes.load())


class TestRatios(unittest.TestCase):
    def test_price_per_unit(self):
        self.assertEqual(run().num("price_per_unit"), 100_000.0)

    def test_price_per_rentable_sf(self):
        self.assertEqual(run().num("price_per_rentable_sf"), 100.0)

    def test_grm(self):
        self.assertEqual(run().num("gross_rent_multiplier"), 10.0)

    def test_two_square_footages_are_reported_separately(self):
        u = run(rentable_sf=8_000.0)
        self.assertEqual(u.num("price_per_rentable_sf"), 125.0)
        self.assertEqual(u.num("price_per_building_sf_assessor"), 100.0)
        self.assertTrue(any("differ by" in c.text for c in u.caveats))


class TestCapRate(unittest.TestCase):
    def test_cap_rate_uses_the_new_purchase_price_for_tax(self):
        # EGI 100,000 - opex 30,000 - tax (1% of 1,000,000 = 10,000) = 60,000
        u = run()
        self.assertEqual(u.num("property_tax_reassessed_annual"), 10_000.0)
        self.assertEqual(u.num("noi_reassessed"), 60_000.0)
        self.assertEqual(u.num("cap_rate_reassessed_pct"), 6.0)

    def test_sellers_basis_cap_rate_is_higher_when_they_bought_cheap(self):
        # Seller's basis 400,000 -> tax 4,000 -> NOI 66,000 -> 6.6%
        u = run(seller_assessed_value=400_000.0)
        self.assertEqual(u.num("property_tax_sellers_basis_annual"), 4_000.0)
        self.assertAlmostEqual(u.num("cap_rate_sellers_basis_pct"), 6.6)
        self.assertAlmostEqual(u.num("cap_rate_reassessed_pct"), 6.0)
        # Reassessment costs the buyer 60 bps.
        self.assertAlmostEqual(u.num("cap_rate_reassessment_delta_bps"), -60.0)

    def test_reassessment_can_go_the_other_way(self):
        # Seller's basis ABOVE the price: the tax bill falls on transfer.
        u = run(seller_assessed_value=1_500_000.0)
        self.assertGreater(u.num("cap_rate_reassessment_delta_bps"), 0)

    def test_direct_assessments_reduce_noi_and_are_not_ad_valorem(self):
        u = run(direct_assessments_annual=1_000.0)
        self.assertEqual(u.num("property_tax_reassessed_annual"), 11_000.0)
        self.assertEqual(u.num("noi_reassessed"), 59_000.0)

    def test_missing_tax_rate_falls_back_to_the_general_levy_and_says_so(self):
        d = dict(BASE)
        del d["property_tax_rate_pct"]
        u = underwriting.run(Deal.from_dict(d), Statutes.load())
        self.assertEqual(u.num("property_tax_reassessed_annual"), 10_000.0)
        self.assertTrue(any("upper bound" in c.text for c in u.caveats))

    def test_no_expenses_means_no_cap_rate_not_a_guessed_one(self):
        d = dict(BASE)
        del d["operating_expenses_annual"]
        u = underwriting.run(Deal.from_dict(d), Statutes.load())
        self.assertIsNone(u.num("cap_rate_reassessed_pct"))
        self.assertEqual(u["cap_rate_reassessed_pct"].tag, "missing")


class TestVacancy(unittest.TestCase):
    def test_vacancy_reduces_egi(self):
        u = run(vacancy_pct=5.0)
        self.assertEqual(u.num("vacancy_loss_annual"), 5_000.0)
        self.assertEqual(u.num("effective_gross_income"), 95_000.0)

    def test_unsupplied_vacancy_is_tagged_default_not_input(self):
        d = dict(BASE)
        del d["vacancy_pct"]
        deal = Deal.from_dict(d)
        self.assertEqual(deal.vacancy_pct.tag, "default")
        self.assertTrue(deal.vacancy_pct.is_assumption)


class TestRegulatorySpread(unittest.TestCase):
    def test_rso_spread_moves_the_valuation(self):
        u = run()
        self.assertEqual(u.num("value_at_rso_grm"), 900_000.0)
        self.assertEqual(u.num("value_at_non_rso_grm"), 1_200_000.0)
        self.assertEqual(u.num("rso_status_value_spread"), 300_000.0)


class TestReplacement(unittest.TestCase):
    def test_replacement_cost(self):
        # land 200,000 + 10,000 sf x 300 = 3,000,000 hard, +10% soft = 3,300,000
        u = run(land_value=200_000.0, construction_cost_per_sf=300.0, soft_cost_pct=10.0)
        self.assertAlmostEqual(u.num("replacement_cost"), 3_500_000.0, places=3)
        self.assertAlmostEqual(u.num("price_vs_replacement_pct"), 100 / 3.5, places=6)

    def test_no_land_value_means_no_replacement_cost(self):
        u = run(construction_cost_per_sf=300.0)
        self.assertEqual(u["replacement_cost"].tag, "missing")

    def test_solves_backwards_from_a_published_figure(self):
        u = run(
            land_value=200_000.0,
            soft_cost_pct=10.0,
            broker_replacement_estimate=3_500_000.0,
        )
        self.assertAlmostEqual(u.num("broker_replacement_implied_cost_per_sf"), 300.0)


class TestInversion(unittest.TestCase):
    def test_invert_states_what_published_headlines_require(self):
        out = underwriting.invert(1_000_000.0, target_grm=10.0, target_cap_pct=6.0)
        self.assertEqual(out["implied_gross_scheduled_rent"], 100_000.0)
        self.assertEqual(out["implied_noi"], 60_000.0)
        self.assertAlmostEqual(out["implied_total_expense_ratio_pct"], 40.0)


class TestProvenanceDiscipline(unittest.TestCase):
    def test_every_metric_carries_a_tag(self):
        for k, v in run().metrics.items():
            self.assertIn(v.tag, ("auto", "input", "derived", "manual", "default", "missing"), k)

    def test_nothing_derived_is_silently_an_assumption(self):
        u = run()
        self.assertFalse(u["cap_rate_reassessed_pct"].is_assumption)


if __name__ == "__main__":
    unittest.main()
