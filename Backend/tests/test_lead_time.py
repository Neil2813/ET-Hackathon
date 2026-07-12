"""
Unit test for disruption signal detection lead-time and ingestion lag metrics endpoint.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from main import app


class TestLeadTimeMetrics(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    @patch("routers.signals._parsed_signals")
    def test_lead_time_metrics_success(self, mock_parsed):
        # Create a mock database return of signals with realistic timestamps and event times
        # gdacs event: event happened 2 hours before we ingested it (lag = 2.0h)
        # usgs event: event happened 0.5 hours before we ingested it (lag = 0.5h)
        # unparsed/no source time event: should be skipped from lag computation
        now = datetime.now(timezone.utc)
        
        mock_parsed.return_value = [
            {
                "id": "gdacs_1",
                "source": "gdacs",
                "event_type": "disaster",
                "title": "Flooding in Region from: 10 Jul 2026",
                "location": "India",
                "severity": 6.5,
                "created_at": (now - timedelta(hours=2)).isoformat(), # ingested 2 hours ago
                "fromdate": (now - timedelta(hours=4)).isoformat(),   # source event happened 4 hours ago (lag = 2h)
            },
            {
                "id": "usgs_1",
                "source": "usgs",
                "event_type": "earthquake",
                "title": "M5.2 Earthquake",
                "location": "Japan",
                "severity": 5.0,
                "created_at": (now - timedelta(hours=1)).isoformat(), # ingested 1 hour ago
                "timestamp": (now - timedelta(hours=1, minutes=30)).isoformat(), # source event happened 1.5 hours ago (lag = 0.5h)
            },
            {
                "id": "no_ts_1",
                "source": "newsapi",
                "event_type": "news",
                "title": "Generic News",
                "location": "Global",
                "severity": 3.0,
                "created_at": now.isoformat(),
            }
        ]

        response = self.client.get("/api/signals/lead-time-metrics?window_signals=10")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify overall structure
        self.assertIn("overall", data)
        self.assertIn("by_source", data)
        self.assertIn("data_window", data)
        
        overall = data["overall"]
        self.assertEqual(overall["total_signals_analyzed"], 2)
        # median of 2.0 and 0.5 is 1.25
        self.assertAlmostEqual(overall["median_ingestion_lag_hours"], 1.25)
        # both lags are <= 1.0 (0.5 is <= 1.0; 2.0 is not, so 50% near real-time)
        self.assertAlmostEqual(overall["near_realtime_pct"], 50.0)

        # Check by source list
        by_source = data["by_source"]
        self.assertEqual(len(by_source), 2) # gdacs and usgs
        
        gdacs = next(s for s in by_source if s["source"] == "gdacs")
        self.assertEqual(gdacs["signal_count"], 1)
        self.assertEqual(gdacs["median_lag_hours"], 2.0)

        usgs = next(s for s in by_source if s["source"] == "usgs")
        self.assertEqual(usgs["signal_count"], 1)
        self.assertEqual(usgs["median_lag_hours"], 0.5)
