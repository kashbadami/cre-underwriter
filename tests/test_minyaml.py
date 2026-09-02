"""
The bundled YAML reader must agree with PyYAML on the file it exists to read.

If PyYAML is not installed the parity test skips — it cannot compare against
something that is not there — but the structural assertions still run, so a
regression in the parser is caught either way.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cre_underwriter import _minyaml
from cre_underwriter.statutes import DEFAULT_PATH

with open(DEFAULT_PATH, "r", encoding="utf-8") as _fh:
    TEXT = _fh.read()


class TestParityWithPyYaml(unittest.TestCase):
    def test_identical_output_on_the_real_config(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        self.assertEqual(yaml.safe_load(TEXT), _minyaml.load(TEXT))


class TestConstructs(unittest.TestCase):
    def setUp(self):
        self.d = _minyaml.load(TEXT)

    def test_nested_mapping(self):
        self.assertEqual(self.d["la_city_rso"]["allowable_increase_pct"], 3.0)

    def test_dates_stay_strings(self):
        self.assertEqual(self.d["la_city_rso"]["applies_if_built_on_or_before"], "1978-10-01")

    def test_booleans(self):
        self.assertIs(self.d["costa_hawkins"]["vacancy_decontrol"], True)
        self.assertIs(self.d["la_city_rso"]["utility_surcharge_permitted"], False)

    def test_null(self):
        self.assertIsNone(self.d["sb_79"]["verified"])

    def test_flow_sequence(self):
        self.assertEqual(self.d["costa_hawkins"]["statewide_repeal_attempts_rejected"],
                         [2018, 2020, 2024])
        self.assertEqual(self.d["la_city_rso"]["formula_range_pct"], [1.0, 4.0])

    def test_block_sequence_of_flow_mappings(self):
        tiers = self.d["ula"]["tiers_fy_2026_27"]
        self.assertEqual(len(tiers), 2)
        self.assertEqual(tiers[0], {"from_usd": 5400000, "to_usd": 10899999, "rate_pct": 4.0})
        self.assertIsNone(tiers[1]["to_usd"])

    def test_folded_block_scalar_is_one_line_with_no_trailing_newline(self):
        s = self.d["ula"]["base"]
        self.assertNotIn("\n", s)
        self.assertTrue(s.startswith("entire consideration"))

    def test_non_ascii_survives(self):
        self.assertIn("—", self.d["ula"]["exemptions_confidence"])

    def test_comments_do_not_leak_into_values(self):
        for section in self.d.values():
            if not isinstance(section, dict):
                continue
            for v in section.values():
                if isinstance(v, str):
                    self.assertFalse(v.strip().startswith("#"))


class TestRefusesWhatItDoesNotUnderstand(unittest.TestCase):
    def test_anchor_raises(self):
        with self.assertRaises(_minyaml.MiniYamlError):
            _minyaml.load("a: 1\n  b: 2\n")

    def test_tab_indentation_raises(self):
        with self.assertRaises(_minyaml.MiniYamlError):
            _minyaml.load("a:\n\tb: 2\n")

    def test_unterminated_quote_raises(self):
        with self.assertRaises(_minyaml.MiniYamlError):
            _minyaml.load('a: "unclosed\n')


if __name__ == "__main__":
    unittest.main()
