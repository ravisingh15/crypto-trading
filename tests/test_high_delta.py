import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient

from backend.app import app
from backend.high_delta_scanner import (
    calculate_candle_delta_metrics,
    scan_futures_high_delta,
    _HIGH_DELTA_CACHE
)


class TestHighDeltaScanner(unittest.TestCase):

    def setUp(self):
        # Clear cache before each test
        _HIGH_DELTA_CACHE["data"] = []
        _HIGH_DELTA_CACHE["last_scanned"] = 0.0

    def _create_mock_dataframe(self, n_bars=30, base_price=100.0, swing_pct=1.5):
        """Create a mock 5-minute OHLCV DataFrame with volatility."""
        records = []
        price = base_price
        for i in range(n_bars):
            # Alternate up and down bars with swings
            change = (swing_pct / 100.0) * price if i % 2 == 0 else -(swing_pct / 100.0) * price
            open_p = price
            close_p = price + change
            high_p = max(open_p, close_p) * (1 + 0.005)
            low_p = min(open_p, close_p) * (1 - 0.005)
            records.append({
                "open_time": 1700000000000 + i * 300000,
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "volume": 5000.0,
                "atr": 1.5,
                "rvol": 1.8,
                "ema_9": price * 1.01,
                "ema_21": price * 1.00,
                "rsi": 55.0,
            })
            price = close_p
        return pd.DataFrame(records)

    def test_calculate_candle_delta_metrics_basic(self):
        df = self._create_mock_dataframe(n_bars=30, base_price=100.0, swing_pct=1.5)
        metrics = calculate_candle_delta_metrics(df, lookback_bars=12)

        self.assertIsNotNone(metrics)
        self.assertIn("natr_5m_pct", metrics)
        self.assertIn("avg_5m_range_pct", metrics)
        self.assertIn("bars_over_1pct", metrics)
        self.assertIn("pct_bars_over_1pct", metrics)
        self.assertIn("scalp_setup", metrics)

        # Volatility should be detected
        self.assertGreater(metrics["natr_5m_pct"], 0.5)
        self.assertGreater(metrics["avg_5m_range_pct"], 1.0)
        self.assertGreater(metrics["bars_over_1pct"], 0)

    def test_scalp_setup_2to1_ratio_long(self):
        df = self._create_mock_dataframe(n_bars=30, base_price=100.0)
        # Force bullish momentum
        df["ema_9"] = df["close"] * 0.99
        df["ema_21"] = df["close"] * 0.98
        df["rsi"] = 60.0

        metrics = calculate_candle_delta_metrics(df)
        self.assertIsNotNone(metrics)
        setup = metrics["scalp_setup"]

        self.assertEqual(setup["direction"], "LONG")
        self.assertEqual(setup["rr_ratio"], 2.0)
        # Entry > SL and TP > Entry for LONG
        self.assertLess(setup["stop_loss"], setup["entry"])
        self.assertGreater(setup["take_profit"], setup["entry"])

        # Check exact 2:1 distance math
        sl_dist = setup["entry"] - setup["stop_loss"]
        tp_dist = setup["take_profit"] - setup["entry"]
        self.assertAlmostEqual(tp_dist / sl_dist, 2.0, places=3)

    def test_scalp_setup_2to1_ratio_short(self):
        df = self._create_mock_dataframe(n_bars=30, base_price=100.0)
        # Force bearish momentum
        df["ema_9"] = df["close"] * 1.02
        df["ema_21"] = df["close"] * 1.05
        df["rsi"] = 35.0

        metrics = calculate_candle_delta_metrics(df)
        self.assertIsNotNone(metrics)
        setup = metrics["scalp_setup"]

        self.assertEqual(setup["direction"], "SHORT")
        self.assertEqual(setup["rr_ratio"], 2.0)
        # Entry < SL and TP < Entry for SHORT
        self.assertGreater(setup["stop_loss"], setup["entry"])
        self.assertLess(setup["take_profit"], setup["entry"])

        # Check exact 2:1 distance math
        sl_dist = setup["stop_loss"] - setup["entry"]
        tp_dist = setup["entry"] - setup["take_profit"]
        self.assertAlmostEqual(tp_dist / sl_dist, 2.0, places=3)

    def test_calculate_metrics_insufficient_bars(self):
        df = self._create_mock_dataframe(n_bars=5)
        metrics = calculate_candle_delta_metrics(df)
        self.assertIsNone(metrics)

    @patch("backend.binance_client.binance_client.futures_get_24h_tickers")
    @patch("backend.binance_client.binance_client.futures_get_klines")
    def test_scan_futures_high_delta_mocked(self, mock_klines, mock_tickers):
        mock_tickers.return_value = [
            {"symbol": "BTCUSDT", "quoteVolume": "500000000", "priceChangePercent": "2.5"},
            {"symbol": "SOLUSDT", "quoteVolume": "120000000", "priceChangePercent": "5.0"},
            {"symbol": "USDCUSDT", "quoteVolume": "80000000", "priceChangePercent": "0.0"},  # Should be excluded
            {"symbol": "DEADCOINUSDT", "quoteVolume": "1000", "priceChangePercent": "0.1"},    # Low volume
        ]

        # Return mock raw klines
        mock_klines.return_value = [
            [1700000000000 + i * 300000, "100.0", "102.0", "99.0", "101.5", "500.0",
             1700000300000, "50000.0", 100, "250.0", "25000.0", "0"]
            for i in range(25)
        ]

        res = scan_futures_high_delta(min_volume=5_000_000, min_natr=0.2, limit=10, force_refresh=True)

        self.assertFalse(res.get("cached", True))
        self.assertGreaterEqual(res["count"], 1)
        symbols = [item["symbol"] for item in res["results"]]
        self.assertIn("BTCUSDT", symbols)
        self.assertNotIn("USDCUSDT", symbols)
        self.assertNotIn("DEADCOINUSDT", symbols)

        # Check caching behavior
        cached_res = scan_futures_high_delta(min_volume=5_000_000, min_natr=0.2, limit=10, force_refresh=False)
        self.assertTrue(cached_res.get("cached", False))


class TestHighDeltaAPIEndpoint(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        _HIGH_DELTA_CACHE["data"] = []
        _HIGH_DELTA_CACHE["last_scanned"] = 0.0

    @patch("backend.binance_client.binance_client.futures_get_24h_tickers")
    @patch("backend.binance_client.binance_client.futures_get_klines")
    def test_api_futures_high_delta_success(self, mock_klines, mock_tickers):
        mock_tickers.return_value = [
            {"symbol": "ETHUSDT", "quoteVolume": "80000000", "priceChangePercent": "3.1"}
        ]
        mock_klines.return_value = [
            [1700000000000 + i * 300000, "2500.0", "2525.0", "2490.0", "2510.0", "100.0",
             1700000300000, "250000.0", 50, "50.0", "125000.0", "0"]
            for i in range(25)
        ]

        response = self.client.get("/api/futures/high-delta?min_volume=1000000&min_natr=0.1&force_refresh=true")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("count", data)
        self.assertIn("results", data)
        self.assertIn("last_scanned", data)

        if data["count"] > 0:
            first = data["results"][0]
            self.assertEqual(first["symbol"], "ETHUSDT")
            self.assertIn("natr_5m_pct", first)
            self.assertIn("scalp_setup", first)
            self.assertEqual(first["scalp_setup"]["rr_ratio"], 2.0)


if __name__ == "__main__":
    unittest.main()
