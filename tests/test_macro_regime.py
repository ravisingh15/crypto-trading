import pytest
import pandas as pd
import numpy as np
from backend.macro_regime import (
    classify_macro_regime,
    calculate_market_breadth,
    calculate_relative_strength,
    get_macro_summary
)


class TestMacroRegimeClassification:
    def test_bull_expansion_regime(self):
        df = pd.DataFrame([{
            "close": 150.0,
            "ema_21": 140.0,
            "ema_50": 130.0,
            "ema_200": 100.0,
            "adx": 30.0,
            "supertrend_dir": 1,
            "rsi": 60.0
        }] * 60)
        res = classify_macro_regime(df)
        assert res["regime"] == "BULL_EXPANSION"
        assert res["score"] >= 75
        assert res["supertrend_dir"] == 1

    def test_bull_pullback_regime(self):
        df = pd.DataFrame([{
            "close": 115.0,
            "ema_21": 125.0,
            "ema_50": 120.0,
            "ema_200": 100.0,
            "adx": 20.0,
            "supertrend_dir": 1,
            "rsi": 42.0
        }] * 60)
        res = classify_macro_regime(df)
        assert res["regime"] == "BULL_PULLBACK"
        assert res["bias"] == "BULLISH_DIP"

    def test_bear_expansion_regime(self):
        df = pd.DataFrame([{
            "close": 80.0,
            "ema_21": 90.0,
            "ema_50": 95.0,
            "ema_200": 110.0,
            "adx": 32.0,
            "supertrend_dir": -1,
            "rsi": 35.0
        }] * 60)
        res = classify_macro_regime(df)
        assert res["regime"] == "BEAR_EXPANSION"
        assert res["score"] <= -75

    def test_insufficient_data(self):
        res = classify_macro_regime(pd.DataFrame())
        assert res["regime"] == "NEUTRAL"
        assert res["score"] == 0


class TestMarketBreadthEngine:
    def test_market_breadth_calculation(self):
        sample_items = [
            {"symbol": "A", "price": 100, "ema_50": 90, "ema_21": 95, "price_change_24h": 2.5, "recommendation": "STRONG BUY"},
            {"symbol": "B", "price": 105, "ema_50": 100, "ema_21": 102, "price_change_24h": 1.2, "recommendation": "BUY"},
            {"symbol": "C", "price": 80, "ema_50": 85, "ema_21": 82, "price_change_24h": -1.5, "recommendation": "SELL"},
            {"symbol": "D", "price": 120, "ema_50": 110, "ema_21": 115, "price_change_24h": 0.5, "recommendation": "BUY"},
        ]
        breadth = calculate_market_breadth(sample_items)
        assert breadth["total_tracked"] == 4
        # 3 out of 4 above EMA 50 = 75%
        assert breadth["pct_above_ema50"] == 75.0
        # 3 out of 4 advancing = 75%
        assert breadth["advancing_pct"] == 75.0
        assert breadth["sentiment_score"] >= 65
        assert breadth["breadth_label"] in ["BROAD_BULLISH", "MODERATE_BULLISH"]

    def test_empty_market_breadth(self):
        breadth = calculate_market_breadth([])
        assert breadth["total_tracked"] == 0
        assert breadth["breadth_label"] == "NEUTRAL"


class TestRelativeStrengthAlpha:
    def test_relative_strength_outperforming(self):
        # Asset gained 20% (100 -> 120)
        asset_prices = np.linspace(100, 120, 25)
        asset_df = pd.DataFrame({"close": asset_prices})

        # Benchmark gained only 5% (100 -> 105)
        bench_prices = np.linspace(100, 105, 25)
        bench_df = pd.DataFrame({"close": bench_prices})

        rs = calculate_relative_strength(asset_df, bench_df, period=20)
        assert rs["rs_ratio"] > 1.05
        assert rs["rs_rating"] > 50
        assert rs["outperforming"] is True
        assert rs["rs_status"] in ["ALPHA_LEADER", "OUTPERFORMING"]

    def test_relative_strength_lagging(self):
        # Asset dropped 10% (100 -> 90)
        asset_prices = np.linspace(100, 90, 25)
        asset_df = pd.DataFrame({"close": asset_prices})

        # Benchmark gained 5% (100 -> 105)
        bench_prices = np.linspace(100, 105, 25)
        bench_df = pd.DataFrame({"close": bench_prices})

        rs = calculate_relative_strength(asset_df, bench_df, period=20)
        assert rs["rs_ratio"] < 0.95
        assert rs["rs_rating"] < 50
        assert rs["outperforming"] is False
        assert rs["rs_status"] in ["LAGGING", "UNDERPERFORMING"]
