import pytest
import pandas as pd
import numpy as np
from backend.indicators import enrich_klines_dataframe, calculate_rsi, calculate_macd, calculate_bollinger_bands, calculate_atr, calculate_supertrend


@pytest.fixture
def sample_klines():
    data = []
    base = 100.0
    for i in range(120):
        t = 1700000000000 + i * 3600000
        o = base + np.sin(i / 5) * 5 + i * 0.2
        h = o + 1.5
        l = o - 1.5
        c = o + 0.5
        v = 1000 + (i % 10) * 100
        data.append([
            t, str(o), str(h), str(l), str(c), str(v),
            t + 3599999, "100000", 100, "500", "50000", "0"
        ])
    return data


def test_enrich_klines_dataframe(sample_klines):
    df = enrich_klines_dataframe(sample_klines)
    assert not df.empty
    assert len(df) == 120

    # Verify indicator columns
    expected_cols = [
        "rsi", "macd", "macd_signal", "macd_hist",
        "ema_8", "ema_21", "ema_50", "ema_200",
        "bb_upper", "bb_middle", "bb_lower",
        "atr", "supertrend", "supertrend_dir", "rvol"
    ]
    for col in expected_cols:
        assert col in df.columns, f"Missing column: {col}"

    # Verify latest values are valid numbers (not all NaN)
    latest = df.iloc[-1]
    assert not np.isnan(latest["rsi"])
    assert 0 <= latest["rsi"] <= 100
    assert not np.isnan(latest["macd"])
    assert not np.isnan(latest["ema_21"])
    assert not np.isnan(latest["bb_upper"])
    assert latest["bb_upper"] >= latest["bb_lower"]
    assert latest["atr"] > 0
    assert latest["supertrend_dir"] in [1, -1]


def test_rsi_bounds(sample_klines):
    df = enrich_klines_dataframe(sample_klines)
    rsi_vals = df["rsi"].dropna()
    assert (rsi_vals >= 0).all()
    assert (rsi_vals <= 100).all()


def test_empty_klines():
    df = enrich_klines_dataframe([])
    assert df.empty
