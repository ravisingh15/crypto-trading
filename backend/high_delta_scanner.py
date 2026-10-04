"""
High Delta 5-Minute Futures Scanner
Identifies high-volatility, fast-moving contracts on Binance USDⓈ-M Futures
where 5-minute candles regularly produce >1% price swings, with built-in 2:1 R:R scalp setups.
"""
import concurrent.futures
import time
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd

from backend.binance_client import binance_client
from backend.indicators import enrich_klines_dataframe
from backend.screener import get_symbol_category

# Stablecoins to exclude from futures scan
STABLECOIN_FUTURES = {
    "USDCUSDT", "FDUSDUSDT", "TUSDUSDT", "BUSDUSDT", "EURUSDT", "DAIUSDT"
}

# In-memory cache for high-delta scan results
_HIGH_DELTA_CACHE: Dict[str, Any] = {
    "data": [],
    "last_scanned": 0.0,
}
_CACHE_TTL_SECONDS = 30  # 30-second cache to protect API rate limits


def calculate_candle_delta_metrics(
    df: pd.DataFrame,
    lookback_bars: int = 12
) -> Optional[Dict[str, Any]]:
    """
    Calculate 5-minute volatility and range velocity metrics.
    
    Parameters:
        df: Enriched DataFrame with OHLCV + ATR + EMAs
        lookback_bars: Number of recent 5m bars to analyze (default 12 = last 1 hour)
        
    Returns:
        Dict with NATR %, average range %, frequency of >1% bars, and 2:1 scalp setup.
    """
    if df is None or len(df) < 15:
        return None

    recent = df.tail(lookback_bars).copy()
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    close = float(latest["close"])
    if close <= 0:
        return None

    # 1. 5-Minute ATR and NATR (Normalized ATR %)
    atr = float(latest.get("atr", 0.0))
    if np.isnan(atr) or atr <= 0:
        atr = close * 0.008  # 0.8% fallback

    natr_5m_pct = (atr / close) * 100.0

    # 2. Bar-by-bar high-to-low range percentages
    bar_opens = recent["open"].values
    bar_highs = recent["high"].values
    bar_lows = recent["low"].values
    bar_closes = recent["close"].values

    ranges_pct = [
        ((h - l) / o) * 100.0
        for h, l, o in zip(bar_highs, bar_lows, bar_opens)
        if o > 0
    ]

    if not ranges_pct:
        return None

    avg_5m_range_pct = float(np.mean(ranges_pct))
    max_5m_range_pct = float(np.max(ranges_pct))
    bars_over_1pct = sum(1 for r in ranges_pct if r >= 1.0)
    pct_bars_over_1pct = (bars_over_1pct / len(ranges_pct)) * 100.0

    # 3. Latest 5m bar change
    latest_open = float(latest["open"])
    latest_bar_change_pct = ((close - latest_open) / latest_open * 100.0) if latest_open > 0 else 0.0

    # 4. Relative Volume on 5m
    rvol = float(latest.get("rvol", 1.0))
    if np.isnan(rvol) or rvol <= 0:
        rvol = 1.0

    # 5. Momentum direction on 5m
    ema_9 = float(latest.get("ema_9", close))
    ema_21 = float(latest.get("ema_21", close))
    rsi = float(latest.get("rsi", 50.0))

    if close > ema_9 >= ema_21 and rsi >= 48:
        direction = "LONG"
        momentum_label = "BULLISH"
    elif close < ema_9 <= ema_21 and rsi <= 52:
        direction = "SHORT"
        momentum_label = "BEARISH"
    elif close > ema_21:
        direction = "LONG"
        momentum_label = "MILD BULL"
    else:
        direction = "SHORT"
        momentum_label = "MILD BEAR"

    # 6. Volatility Tier Classification
    if natr_5m_pct >= 1.8 or avg_5m_range_pct >= 1.5:
        tier = "EXTREME"
        tier_badge = "🔥 EXTREME"
    elif natr_5m_pct >= 1.1 or avg_5m_range_pct >= 1.0:
        tier = "HIGH"
        tier_badge = "⚡ HIGH"
    elif natr_5m_pct >= 0.7 or avg_5m_range_pct >= 0.7:
        tier = "ACTIVE"
        tier_badge = "📈 ACTIVE"
    else:
        tier = "LOW"
        tier_badge = "😴 LOW"

    # 7. Exact 2:1 Scalp Trade Setup (1R Risk, 2R Reward)
    # Stop distance = 1.0 * ATR (with a 0.25% minimum floor to avoid sub-tick slippage)
    min_stop_dist = close * 0.0025
    sl_dist = max(atr, min_stop_dist)
    tp_dist = 2.0 * sl_dist  # Exact 2:1 R:R

    if direction == "LONG":
        entry_price = close
        stop_loss = max(0.00000001, entry_price - sl_dist)
        take_profit = entry_price + tp_dist
    else:
        entry_price = close
        stop_loss = entry_price + sl_dist
        take_profit = max(0.00000001, entry_price - tp_dist)

    sl_dist_pct = (sl_dist / entry_price) * 100.0
    tp_dist_pct = (tp_dist / entry_price) * 100.0

    return {
        "price": close,
        "natr_5m_pct": round(natr_5m_pct, 2),
        "avg_5m_range_pct": round(avg_5m_range_pct, 2),
        "max_5m_range_pct": round(max_5m_range_pct, 2),
        "bars_over_1pct": bars_over_1pct,
        "total_bars_analyzed": len(ranges_pct),
        "pct_bars_over_1pct": round(pct_bars_over_1pct, 1),
        "latest_bar_change_pct": round(latest_bar_change_pct, 2),
        "rvol_5m": round(rvol, 2),
        "rsi_5m": round(rsi, 1),
        "momentum": momentum_label,
        "tier": tier,
        "tier_badge": tier_badge,
        "scalp_setup": {
            "direction": direction,
            "entry": round(entry_price, 6 if entry_price < 1 else 4),
            "stop_loss": round(stop_loss, 6 if entry_price < 1 else 4),
            "take_profit": round(take_profit, 6 if entry_price < 1 else 4),
            "risk_pct": round(sl_dist_pct, 2),
            "reward_pct": round(tp_dist_pct, 2),
            "rr_ratio": 2.0,
        }
    }


def _process_single_futures_pair(
    ticker: Dict[str, Any],
    lookback_bars: int = 12
) -> Optional[Dict[str, Any]]:
    """Fetch 5m klines and calculate delta metrics for one futures symbol."""
    symbol = ticker.get("symbol", "")
    try:
        raw_klines = binance_client.futures_get_klines(symbol, interval="5m", limit=30)
        if not raw_klines or len(raw_klines) < 15:
            return None

        df = enrich_klines_dataframe(raw_klines)
        metrics = calculate_candle_delta_metrics(df, lookback_bars=lookback_bars)
        if not metrics:
            return None

        volume_24h = float(ticker.get("quoteVolume", 0))
        price_change_24h = float(ticker.get("priceChangePercent", 0))
        category = get_symbol_category(symbol)

        return {
            "symbol": symbol,
            "category": category,
            "market_type": "FUTURES",
            "volume_24h_usdt": round(volume_24h, 2),
            "price_change_24h": round(price_change_24h, 2),
            **metrics,
        }
    except Exception:
        return None


def scan_futures_high_delta(
    min_volume: float = 5_000_000,
    min_natr: float = 0.5,
    limit: int = 40,
    max_scan_pool: int = 60,
    lookback_bars: int = 12,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Scan Binance USDⓈ-M Futures contracts for high 5-minute volatility.
    
    Parameters:
        min_volume: Minimum 24h quote volume in USDT (filters illiquid contracts)
        min_natr: Minimum 5m NATR % (e.g. 0.8% = typical bar spans >=0.8%)
        limit: Max results to return
        max_scan_pool: Number of top liquid futures pairs to analyze
        lookback_bars: Number of 5m bars to measure (12 = 1 hour)
        force_refresh: Bypass the 30-second cache
    """
    now = time.time()
    if not force_refresh and (now - _HIGH_DELTA_CACHE["last_scanned"] < _CACHE_TTL_SECONDS) and _HIGH_DELTA_CACHE["data"]:
        cached_results = _HIGH_DELTA_CACHE["data"]
        # Apply filters to cached data
        filtered = [
            item for item in cached_results
            if item["volume_24h_usdt"] >= min_volume and item["natr_5m_pct"] >= min_natr
        ]
        return {
            "count": len(filtered[:limit]),
            "cached": True,
            "last_scanned": _HIGH_DELTA_CACHE["last_scanned"],
            "results": filtered[:limit],
        }

    try:
        all_tickers = binance_client.futures_get_24h_tickers()
    except Exception as e:
        return {
            "count": 0,
            "error": f"Failed to fetch futures tickers: {str(e)}",
            "results": [],
        }

    # Filter for active USDT perpetual contracts with volume
    candidates = []
    for t in all_tickers:
        sym = t.get("symbol", "")
        if not sym.endswith("USDT") or sym in STABLECOIN_FUTURES:
            continue
        try:
            vol = float(t.get("quoteVolume", 0))
            if vol >= min_volume:
                candidates.append(t)
        except (ValueError, TypeError):
            continue

    # Sort by 24h volume descending to pick the most liquid pool
    candidates = sorted(
        candidates,
        key=lambda t: float(t.get("quoteVolume", 0)),
        reverse=True
    )[:max_scan_pool]

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures_map = {
            executor.submit(_process_single_futures_pair, ticker, lookback_bars): ticker["symbol"]
            for ticker in candidates
        }
        for future in concurrent.futures.as_completed(futures_map):
            res = future.result()
            if res and res["natr_5m_pct"] >= min_natr:
                results.append(res)

    # Sort results by highest 5m NATR % first
    results = sorted(results, key=lambda x: (x["natr_5m_pct"], x["pct_bars_over_1pct"]), reverse=True)

    _HIGH_DELTA_CACHE["data"] = results
    _HIGH_DELTA_CACHE["last_scanned"] = now

    return {
        "count": len(results[:limit]),
        "cached": False,
        "last_scanned": now,
        "results": results[:limit],
    }
