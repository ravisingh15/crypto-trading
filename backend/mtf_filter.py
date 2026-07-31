"""
Multi-Timeframe (MTF) Trend Filter.

Provides a higher-timeframe bias check to filter out counter-trend trades.
Before taking any signal on the trading timeframe (e.g., 1h), this module
checks the 4h chart to confirm the macro trend is aligned.

Usage:
    from backend.mtf_filter import get_htf_bias
    bias = get_htf_bias("BTCUSDT", htf_interval="4h")
    # Returns "BULL", "BEAR", or "NEUTRAL"
"""
import time
from typing import Dict, Optional
from backend.binance_client import binance_client
from backend.indicators import enrich_klines_dataframe


# Cache HTF bias to avoid repeated API calls within a scan cycle
_htf_cache: Dict[str, Dict] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


def get_htf_bias(symbol: str, htf_interval: str = "4h") -> str:
    """
    Determine higher-timeframe trend bias for a symbol.

    Checks:
    1. EMA-50 vs EMA-200 position (macro trend)
    2. Supertrend direction (trend indicator)
    3. ADX strength (trend conviction)
    4. Price vs EMA-200 (above/below macro MA)

    Returns:
        "BULL" — macro uptrend confirmed (3+ bullish signals)
        "BEAR" — macro downtrend confirmed (3+ bearish signals)
        "NEUTRAL" — mixed / no clear trend
    """
    cache_key = f"{symbol}_{htf_interval}"
    now = time.time()

    # Check cache
    if cache_key in _htf_cache:
        cached = _htf_cache[cache_key]
        if now - cached["time"] < _CACHE_TTL_SECONDS:
            return cached["bias"]

    try:
        raw = binance_client.get_klines(symbol, interval=htf_interval, limit=220)
        df = enrich_klines_dataframe(raw)

        if df.empty or len(df) < 200:
            return "NEUTRAL"

        latest = df.iloc[-1]

        bull_signals = 0
        bear_signals = 0

        # Check 1: Price vs EMA-200
        close = float(latest["close"])
        ema_200 = float(latest["ema_200"])
        if close > ema_200:
            bull_signals += 1
        elif close < ema_200:
            bear_signals += 1

        # Check 2: EMA-50 vs EMA-200 (Golden/Death Cross)
        ema_50 = float(latest["ema_50"])
        if ema_50 > ema_200:
            bull_signals += 1
        elif ema_50 < ema_200:
            bear_signals += 1

        # Check 3: Supertrend direction
        st_dir = int(latest["supertrend_dir"])
        if st_dir == 1:
            bull_signals += 1
        elif st_dir == -1:
            bear_signals += 1

        # Check 4: ADX strength + DI direction
        adx = float(latest["adx"])
        plus_di = float(latest["plus_di"])
        minus_di = float(latest["minus_di"])
        if adx >= 20:
            if plus_di > minus_di:
                bull_signals += 1
            elif minus_di > plus_di:
                bear_signals += 1

        # Determine bias
        if bull_signals >= 3:
            bias = "BULL"
        elif bear_signals >= 3:
            bias = "BEAR"
        else:
            bias = "NEUTRAL"

        # Cache the result
        _htf_cache[cache_key] = {"bias": bias, "time": now}
        return bias

    except Exception:
        return "NEUTRAL"


def clear_htf_cache():
    """Clear the HTF bias cache (call at start of each scan cycle)."""
    global _htf_cache
    _htf_cache = {}


def is_signal_aligned(direction: str, htf_bias: str) -> bool:
    """
    Check if a trade direction aligns with the higher-timeframe bias.

    Rules:
    - LONG signals: allowed if HTF is BULL or NEUTRAL
    - SHORT signals: allowed if HTF is BEAR or NEUTRAL
    """
    if direction == "LONG":
        return htf_bias in ("BULL", "NEUTRAL")
    elif direction == "SHORT":
        return htf_bias in ("BEAR", "NEUTRAL")
    return True
