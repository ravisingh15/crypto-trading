import pytest
import pandas as pd
import numpy as np

from backend.strategies import (
    STRATEGIES,
    STRATEGY_PERFORMANCE,
    get_strategy_stats,
    get_mtf_policy,
    get_strategy_lab_snapshot,
    tier_from_performance,
    strat_trend_pullback_long,
    strat_trend_pullback_short,
    strat_squeeze_breakout_long,
    strat_squeeze_breakout_short,
    strat_momentum_continuation_long,
    strat_momentum_continuation_short,
    strat_volume_breakout_long,
    strat_volume_breakout_short,
    strat_supertrend_regime_long,
    strat_supertrend_regime_short,
    strat_mean_reversion_long,
    strat_mean_reversion_short,
    strat_taker_pressure_long,
    strat_taker_pressure_short,
    strat_vwap_reversion_long,
    strat_vwap_reversion_short,
    strat_rsi_divergence_long,
    strat_rsi_divergence_short,
    strat_ema_cross_long,
    strat_ema_cross_short,
    strat_oversold_bounce_long,
)
from backend.trade_signals import _calculate_signal_confidence


@pytest.fixture
def sample_indicators_df():
    """Create a realistic enriched DataFrame with all necessary indicator columns."""
    n = 100
    dates = pd.date_range("2026-01-01", periods=n, freq="1h")
    np.random.seed(42)
    close = 100.0 + np.cumsum(np.random.randn(n) * 0.5)
    high = close + np.random.rand(n) * 0.8
    low = close - np.random.rand(n) * 0.8
    open_val = (close + low) / 2
    volume = 1000 + np.random.rand(n) * 500

    df = pd.DataFrame({
        "open_time": dates,
        "open": open_val,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "taker_buy_base_asset_volume": volume * 0.5,
        "taker_buy_ratio": 0.5,
        "rsi": pd.Series(50 + np.sin(np.linspace(0, 10, n)) * 25),
        "macd_hist": pd.Series(np.sin(np.linspace(0, 8, n)) * 0.5),
        "ema_8": close * 1.01,
        "ema_21": close * 1.00,
        "ema_50": close * 0.99,
        "ema_200": close * 0.95,
        "bb_upper": close * 1.03,
        "bb_middle": close,
        "bb_lower": close * 0.97,
        "kc_upper": close * 1.04,
        "kc_lower": close * 0.96,
        "atr": pd.Series([1.5] * n),
        "rvol": pd.Series([1.2] * n),
        "stoch_k": pd.Series(50 + np.cos(np.linspace(0, 10, n)) * 30),
        "stoch_d": pd.Series(50 + np.cos(np.linspace(0, 10, n)) * 28),
        "supertrend_dir": pd.Series([1] * n),
        "vwma_21": close * 0.99,
        "adx": pd.Series([22.0] * n),
        "plus_di": pd.Series([25.0] * n),
        "minus_di": pd.Series([15.0] * n),
        "high_20": pd.Series(high).rolling(20, min_periods=1).max(),
        "low_20": pd.Series(low).rolling(20, min_periods=1).min(),
        "bull_divergence": pd.Series([False] * n),
        "bear_divergence": pd.Series([False] * n),
    })
    return df


class TestStrategyFunctions:
    def test_all_strategies_return_boolean_series(self, sample_indicators_df):
        for name, strat in STRATEGIES.items():
            fn = strat["fn"]
            res = fn(sample_indicators_df)
            assert isinstance(res, pd.Series), f"{name} did not return a pd.Series"
            assert res.dtype == bool, f"{name} did not return a boolean Series"
            assert len(res) == len(sample_indicators_df), f"{name} length mismatch"

    def test_new_short_strategies_registered(self):
        expected_new_shorts = [
            "Mean Reversion (Short)",
            "EMA Death Cross (Short)",
            "Volume Breakout (Short)",
        ]
        for name in expected_new_shorts:
            assert name in STRATEGIES, f"{name} not registered in STRATEGIES"
            assert STRATEGIES[name]["direction"] == "SHORT"
            assert callable(STRATEGIES[name]["fn"])
            assert "type" in STRATEGIES[name]
            assert "preferred_timeframe" in STRATEGIES[name]

    def test_zero_taker_volume_guard(self, sample_indicators_df):
        df_zero_taker = sample_indicators_df.copy()
        df_zero_taker["taker_buy_base_asset_volume"] = 0.0
        df_zero_taker["taker_buy_ratio"] = 0.0
        # Make conditions otherwise satisfied
        df_zero_taker["close"] = df_zero_taker["bb_middle"] + 5.0
        df_zero_taker["rsi"] = 55.0
        df_zero_taker["rvol"] = 2.0

        short_signals = strat_taker_pressure_short(df_zero_taker)
        assert not short_signals.any(), "Zero taker volume should NOT produce short signals"

        long_signals = strat_taker_pressure_long(df_zero_taker)
        assert not long_signals.any(), "Zero taker volume should NOT produce long signals"

    def test_adaptive_confidence_scoring(self, sample_indicators_df):
        df = sample_indicators_df.copy()
        idx = 50
        # Setup an extreme mean reversion long scenario: low pierced BB, RSI oversold, range ADX
        df.loc[idx, "low"] = df.loc[idx, "bb_lower"] - 1.0
        df.loc[idx, "close"] = df.loc[idx, "bb_lower"] - 0.5
        df.loc[idx, "open"] = df.loc[idx, "bb_lower"] - 0.8  # close > open (bounce)
        df.loc[idx, "rsi"] = 28.0
        df.loc[idx, "adx"] = 18.0  # ranging
        df.loc[idx, "rvol"] = 1.3
        # EMAs are pointing down (bearish trend context)
        df.loc[idx, "ema_8"] = 90.0
        df.loc[idx, "ema_21"] = 95.0
        df.loc[idx, "macd_hist"] = -0.5

        # Standard trend confidence would penalize this severely
        trend_score = _calculate_signal_confidence(
            df, idx, direction="LONG", strategy_type="TREND", macro_regime="RANGE_CONSOLIDATION"
        )

        # Adaptive mean reversion confidence recognizes the dip bounce setup
        mr_score = _calculate_signal_confidence(
            df, idx, direction="LONG", strategy_type="MEAN_REVERSION", macro_regime="RANGE_CONSOLIDATION"
        )

        assert mr_score >= 60, f"Mean reversion score {mr_score} should be >= 60 for high quality setup"
        assert mr_score > trend_score, f"MR score ({mr_score}) should exceed trend score ({trend_score})"


class TestStrategyPerformanceRegistry:
    def test_registry_is_enriched_with_empirical_stats(self):
        for name in STRATEGY_PERFORMANCE:
            assert name in STRATEGIES, f"{name} missing from STRATEGIES"
            info = STRATEGIES[name]
            assert info["tier"] in ("A+", "A", "B+", "B", "C")
            assert info["best_timeframe"] in ("1h", "4h")
            assert info["historical_trades"] > 0
            assert info["sample_quality"] in ("LOW", "MEDIUM", "HIGH")

    def test_get_strategy_stats_uses_exact_timeframe_then_proxy(self):
        exact = get_strategy_stats("RSI Divergence (Short)", "4h")
        assert exact["timeframe"] == "4h"
        assert exact["is_proxy"] is False
        assert exact["pf"] > 1.5
        assert exact["tier"] == "A+"

        proxy = get_strategy_stats("RSI Divergence (Short)", "5m")
        assert proxy["is_proxy"] is True
        assert proxy["timeframe"] == "1h"

        fallback = get_strategy_stats("RSI Divergence (Short)", "1d")
        assert fallback["is_proxy"] is True
        assert fallback["timeframe"] == "4h"

    def test_mtf_policy_is_strategy_aware(self):
        assert get_mtf_policy("Trend Pullback (Long)") == "required"
        assert get_mtf_policy("Breakout Retest (Long)") == "required"
        assert get_mtf_policy("Mean Reversion (Long)") == "soft"
        assert get_mtf_policy("Taker Pressure (Short)") == "soft"
        assert get_mtf_policy("RSI Divergence (Short)") == "soft"

    def test_tier_thresholds(self):
        assert tier_from_performance(1.50, 25) == "A+"
        assert tier_from_performance(1.50, 5) == "C"
        assert tier_from_performance(1.20, 30) == "A"
        assert tier_from_performance(1.06, 30) == "B+"
        assert tier_from_performance(0.96, 30) == "B"
        assert tier_from_performance(0.80, 30) == "C"

    def test_strategy_lab_snapshot(self):
        snap = get_strategy_lab_snapshot("4h")
        assert snap["interval"] == "4h"
        assert snap["summary"]["total"] == len(STRATEGIES)
        assert snap["summary"]["long"] + snap["summary"]["short"] == len(STRATEGIES)
        assert snap["summary"]["profitable"] > 0
        assert snap["summary"]["best_strategy"]
        assert len(snap["strategies"]) == len(STRATEGIES)
        pfs = [row["active"]["pf"] for row in snap["strategies"]]
        assert pfs == sorted(pfs, reverse=True)
        assert all("performance" in row for row in snap["strategies"])
        assert all("mtf_policy" in row for row in snap["strategies"])
