"""
Unit tests for services/worldbank.py nominal/PPP converters and rupee string formatting.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock

import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from services.worldbank import (
    _fmt_inr,
    _get_inr_rate,
    _get_ppp_rate,
    _latest_value,
    build_vulnerability_narrative,
    fetch_india_energy_vulnerability,
)


class TestWorldBankHelpers(unittest.TestCase):

    def test_fmt_inr_lakh_crore(self):
        # 1.5e12 INR -> ₹1.50 lakh crore (at rate=1.0)
        self.assertEqual(_fmt_inr(1.5e12, rate=1.0), "₹1.50 lakh crore")
        # 3e11 USD at rate 84.0 -> ₹25.2 lakh crore -> ₹25.20 lakh crore
        self.assertEqual(_fmt_inr(3.0e11, rate=84.0), "₹25.20 lakh crore")

    def test_fmt_inr_crore(self):
        # 1.5e8 INR -> ₹15 crore
        self.assertEqual(_fmt_inr(1.5e8, rate=1.0), "₹15 crore")
        self.assertEqual(_fmt_inr(1.2345e8, rate=1.0), "₹12 crore")

    def test_fmt_inr_lakh(self):
        # 5e5 INR -> ₹5 lakh
        self.assertEqual(_fmt_inr(5e5, rate=1.0), "₹5 lakh")
        self.assertEqual(_fmt_inr(6.25e5, rate=1.0), "₹6 lakh")

    def test_fmt_inr_thousands(self):
        # 42000 INR -> ₹42,000
        self.assertEqual(_fmt_inr(42000, rate=1.0), "₹42,000")

    def test_latest_value_extraction(self):
        rows = [
            {"date": "2020", "value": 10.0},
            {"date": "2022", "value": 30.0},
            {"date": "2021", "value": 20.0},
            {"date": "2023", "value": None},
        ]
        self.assertEqual(_latest_value(rows), 30.0)
        self.assertIsNone(_latest_value([]))

    @patch("services.worldbank._wb_get")
    def test_get_inr_rate(self, mock_get):
        mock_get.return_value = [
            {"date": "2023", "value": 82.5},
            {"date": "2022", "value": 81.2},
        ]
        self.assertEqual(_get_inr_rate(), 82.5)

    @patch("services.worldbank._wb_get")
    def test_get_ppp_rate(self, mock_get):
        mock_get.return_value = [
            {"date": "2023", "value": 23.4},
        ]
        self.assertEqual(_get_ppp_rate(), 23.4)

    def test_vulnerability_narrative_generation(self):
        profile = {
            "energy_import_pct": 87.5,
            "fuel_import_pct_merch": 28.2,
            "data_year": "2023",
            "usd_inr_rate": 83.5,
            "ppp_rate": 25.0,
            "ppp_ratio": 3.34,
            "gdp_inr_formatted": "₹280.00 lakh crore",
            "gdp_ppp_intl_formatted": "$10.50T (intl $)",
            "fuel_import_value_inr": "₹24.00 lakh crore",
            "fuel_import_value_ppp_inr": "₹7.20 lakh crore",
            "fuel_import_value_usd_display": "$28.7B",
        }
        narrative = build_vulnerability_narrative(profile)
        self.assertIn("India's GDP (2023)", narrative)
        self.assertIn("₹280.00 lakh crore", narrative)
        self.assertIn("87.5%", narrative)
        self.assertIn("₹7.20 lakh crore", narrative)
