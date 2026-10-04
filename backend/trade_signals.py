"""
Trade Signal Scanner with ATR-based Stop-Loss / Take-Profit calculation & Macro Regime Confluence.
Scans live Binance data for active strategy signals and returns actionable
trade setups with entry, SL, TP1, TP2, and risk metrics.
"""
import concurrent.futures
import time
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np

from backend.binance_client import binance_client
from backend.indicators import enrich_klines_dataframe
from backend.strategies import STRATEGIES
from backend.macro_regime import (
    get_benchmark_dataframe,
    get_macro_summary,
    calculate_relative_strength
)
from backend.mtf_filter import get_htf_bias, is_signal_aligned, clear_htf_cache


def _get_htf_interval(interval: str) -> str:
    """Map execution interval to higher timeframe for macro trend confluence."""
    mapping = {
        '5m': '1h',
        '15m': '1h',
        '30m': '4h',
        '1h': '4h',
        '2h': '4h',
        '4h': '1d',
        '1d': '1w',
    }
    return mapping.get(str(interval).lower(), '4h')


# Default R:R configurations (optimized with empirical 2.0x ATR SL for crypto wick breathing room)
RR_CONFIGS = {
    '1:1.75 Opt': {'sl_mult': 2.0, 'tp_mult': 3.50},  # Empirical optimal (highest PF & Sharpe)
    '1:2.0 Opt': {'sl_mult': 2.0, 'tp_mult': 4.00},   # Optimized 2:1 with noise-tolerant 2.0x SL
    '1:2.0': {'sl_mult': 2.0, 'tp_mult': 4.00},       # Standard 1:2 updated to 2.0 ATR SL
    '1:1.5': {'sl_mult': 1.5, 'tp_mult': 2.25},
    '1:3.0': {'sl_mult': 1.0, 'tp_mult': 3.00},
}

# Fallback symbols if dynamic fetch fails
FALLBACK_SYMBOLS = [
    'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT',
    'ADAUSDT', 'AVAXUSDT', 'NEARUSDT', 'SUIUSDT', 'APTUSDT', 'INJUSDT',
    'DOTUSDT', 'SEIUSDT', 'FETUSDT', 'RENDERUSDT', 'UNIUSDT', 'AAVEUSDT',
    'PENDLEUSDT', 'ARBUSDT', 'OPUSDT', 'PEPEUSDT', 'WIFUSDT', 'BONKUSDT',
]

STABLECOIN_PAIRS = {
    'USDCUSDT', 'FDUSDUSDT', 'TUSDUSDT', 'USD1USDT', 'RLUSDUSDT', 
    'EURUSDT', 'AEURUSDT', 'USDPUSDT', 'BUSDUSDT', 'DAIUSDT'
}

# Dynamic symbol cache
_dynamic_symbols_cache: Dict[str, Any] = {}
_SYMBOL_CACHE_TTL = 300  # 5 minutes

def _get_dynamic_symbols(max_symbols: int = 35, asset_class: str = "ALL") -> List[str]:

    """
    Dynamically fetch top-N symbols by 24h volume for crypto & US stocks (excluding stablecoins).
    Caches for 5 minutes to avoid hammering the ticker endpoint.
    """
    now = time.time()
    cache_key = f"{asset_class}_{max_symbols}"
    cached = _dynamic_symbols_cache.get(cache_key)
    if cached is not None and now - cached["time"] < _SYMBOL_CACHE_TTL:
        return cached["symbols"]

    try:
        raw_tickers = binance_client.get_usdt_tickers(asset_class=asset_class)
        # Filter out stablecoins
        tickers = [t for t in raw_tickers if t["symbol"] not in STABLECOIN_PAIRS]
        
        if asset_class.upper() == "ALL":
            stock_tickers = [t for t in tickers if t.get("asset_class") == "STOCK"]
            crypto_tickers = [t for t in tickers if t.get("asset_class") != "STOCK"]
            crypto_sorted = sorted(crypto_tickers, key=lambda t: float(t.get("quoteVolume", 0)), reverse=True)[:25]
            stock_sorted = sorted(stock_tickers, key=lambda t: float(t.get("quoteVolume", 0)), reverse=True)[:15]
            symbols = [t["symbol"] for t in (crypto_sorted + stock_sorted)]
        elif asset_class.upper() == "STOCKS":
            stock_tickers = [t for t in tickers if t.get("asset_class") == "STOCK"]
            sorted_tickers = sorted(stock_tickers, key=lambda t: float(t.get("quoteVolume", 0)), reverse=True)
            symbols = [t["symbol"] for t in sorted_tickers[:max_symbols]]
        else:
            crypto_tickers = [t for t in tickers if t.get("asset_class") != "STOCK"]
            sorted_tickers = sorted(crypto_tickers, key=lambda t: float(t.get("quoteVolume", 0)), reverse=True)
            symbols = [t["symbol"] for t in sorted_tickers[:max_symbols]]

        _dynamic_symbols_cache[cache_key] = {"symbols": symbols, "time": now}
        return symbols

    except Exception:
        from backend.config import TOP_STOCK_PAIRS
        if asset_class.upper() == "STOCKS":
            return TOP_STOCK_PAIRS[:max_symbols]
        elif asset_class.upper() == "CRYPTO":
            return FALLBACK_SYMBOLS[:max_symbols]
        return (FALLBACK_SYMBOLS[:20] + TOP_STOCK_PAIRS[:15])[:max_symbols]


def _calculate_signal_confidence(
    df: pd.DataFrame,
    idx: int,
    direction: str,
    macro_regime: str = "NEUTRAL",
    rs_status: str = "IN_LINE",
    htf_bias: str = "NEUTRAL",
) -> int:
    """
    Calculate a confluence-based confidence score (0-100) for a signal.
    Checks alignment of multiple indicators + Macro Benchmark Regime + Relative Strength + MTF Trend.
    """
    row = df.iloc[idx]
    # Base score for passing strategy rule
    score = 20

    # EMA trend alignment (up to +20)
    if direction == 'LONG':
        if row.get('ema_8', 0) > row.get('ema_21', 0):
            score += 10
        if row.get('ema_21', 0) > row.get('ema_50', 0):
            score += 10
    else:
        if row.get('ema_8', 0) < row.get('ema_21', 0):
            score += 10
        if row.get('ema_21', 0) < row.get('ema_50', 0):
            score += 10

    # RSI zone confirmation (+15)
    rsi = row.get('rsi', 50)
    if direction == 'LONG':
        if rsi <= 68 and rsi >= 35:
            score += 15
        elif rsi < 35:
            score += 10  # Deep oversold dip
        elif rsi > 75:
            score -= 10  # Overextended
    else:
        if rsi >= 32 and rsi <= 65:
            score += 15
        elif rsi > 65:
            score += 10  # Deep overbought
        elif rsi < 25:
            score -= 10  # Overextended dump

    # MACD histogram agreement (+15)
    macd_hist = row.get('macd_hist', 0)
    if direction == 'LONG' and macd_hist > 0:
        score += 15
    elif direction == 'SHORT' and macd_hist < 0:
        score += 15

    # Volume surge (+10)
    rvol = row.get('rvol', 1.0)
    if rvol > 1.2:
        score += 10

    # Supertrend agreement (+10)
    st_dir = row.get('supertrend_dir', 0)
    if direction == 'LONG' and st_dir == 1:
        score += 10
    elif direction == 'SHORT' and st_dir == -1:
        score += 10

    # EMA-200 regime filter (+10)
    close = row.get('close', 0)
    ema_200 = row.get('ema_200', close)
    if direction == 'LONG' and close > ema_200:
        score += 10
    elif direction == 'SHORT' and close < ema_200:
        score += 10

    # Macro Benchmark Alignment (+15 / -10)
    if macro_regime in ["BULL_EXPANSION", "BULL_PULLBACK"]:
        if direction == "LONG":
            score += 15
        else:
            score -= 10
    elif macro_regime == "RANGE_CONSOLIDATION":
        score += 5
    elif macro_regime in ["BEAR_EXPANSION", "BEAR_CORRECTION"]:
        if direction == "SHORT":
            score += 15
        else:
            score -= 10

    # Relative Strength Alpha (+10)
    if direction == "LONG":
        if rs_status in ["ALPHA_LEADER", "OUTPERFORMING"]:
            score += 10
        elif rs_status in ["LAGGING", "UNDERPERFORMING"]:
            score -= 5
    else:
        if rs_status in ["LAGGING", "UNDERPERFORMING"]:
            score += 10
        elif rs_status in ["ALPHA_LEADER", "OUTPERFORMING"]:
            score -= 5

    # MTF Higher Timeframe Alignment (+12 / -15)
    if htf_bias == "BULL":
        if direction == "LONG":
            score += 12
        else:
            score -= 15
    elif htf_bias == "BEAR":
        if direction == "SHORT":
            score += 12
        else:
            score -= 15

    return max(15, min(score, 100))



def scan_symbol_signals(
    symbol: str,
    interval: str = '1h',
    rr_key: str = '1:2.0',
    limit: int = 200,
    lookback_bars: int = 3,
    btc_benchmark_df: Optional[pd.DataFrame] = None,
    spy_benchmark_df: Optional[pd.DataFrame] = None,
    macro_info: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Scan a single symbol for recent strategy signals.
    Returns trade setups with entry, SL, TP1, TP2, and Macro/RS metrics.
    """
    try:
        raw = binance_client.get_klines(symbol, interval=interval, limit=limit)
        df = enrich_klines_dataframe(raw)
        if df.empty or len(df) < 50:
            return []
    except Exception:
        return []

    is_stock = binance_client.is_stock_symbol(symbol)
    meta = binance_client.get_stock_metadata(symbol) if is_stock else None
    asset_class = "STOCK" if is_stock else "CRYPTO"
    company_name = meta["name"] if meta else symbol.replace("USDT", "")
    stock_ticker = meta["ticker"] if meta else symbol.replace("USDT", "")
    sector = meta["sector"] if meta else "Crypto"

    # Macro Regime Context
    benchmark_df = spy_benchmark_df if is_stock else btc_benchmark_df
    if benchmark_df is not None and not benchmark_df.empty:
        rs_data = calculate_relative_strength(df, benchmark_df, period=20)
    else:
        rs_data = {"rs_ratio": 1.0, "rs_rating": 50, "rs_status": "IN_LINE", "outperforming": False}

    if macro_info:
        regime_key = "equity_benchmark" if is_stock else "crypto_benchmark"
        bench_regime = macro_info.get(regime_key, {}).get("regime", "NEUTRAL")
    else:
        bench_regime = "NEUTRAL"

    rr = RR_CONFIGS.get(rr_key, RR_CONFIGS['1:2.0'])
    sl_mult = rr['sl_mult']
    tp_mult = rr['tp_mult']

    # Higher Timeframe Trend Bias (e.g. 1h -> 4h, 15m -> 1h)
    htf_interval = _get_htf_interval(interval)
    htf_bias = get_htf_bias(symbol, htf_interval)

    signals = []
    scan_start = max(0, len(df) - lookback_bars)

    for strat_name, strat_info in STRATEGIES.items():
        fn = strat_info['fn']
        direction = strat_info['direction']

        try:
            signal_mask = fn(df)
        except Exception:
            continue

        for idx in range(scan_start, len(df)):
            if not signal_mask.iloc[idx]:
                continue

            row = df.iloc[idx]
            entry_price = float(row['close'])
            atr = float(row['atr']) if not np.isnan(row['atr']) else entry_price * 0.01

            if atr <= 0:
                atr = entry_price * 0.01

            sl_dist = sl_mult * atr
            if direction == 'LONG':
                sl_price = entry_price - sl_dist
                tp1_price = entry_price + (1.5 * sl_dist)  # TP1 scale-out at 1.5R
                tp2_price = entry_price + (tp_mult * atr)   # TP2 runner
            else:
                sl_price = entry_price + sl_dist
                tp1_price = entry_price - (1.5 * sl_dist)
                tp2_price = entry_price - (tp_mult * atr)

            sl_distance_pct = abs(entry_price - sl_price) / entry_price * 100
            tp1_distance_pct = abs(tp1_price - entry_price) / entry_price * 100
            tp2_distance_pct = abs(tp2_price - entry_price) / entry_price * 100
            rr_ratio = tp2_distance_pct / sl_distance_pct if sl_distance_pct > 0 else 0

            htf_aligned = is_signal_aligned(direction, htf_bias)

            confidence = _calculate_signal_confidence(
                df, idx, direction,
                macro_regime=bench_regime,
                rs_status=rs_data.get("rs_status", "IN_LINE"),
                htf_bias=htf_bias,
            )

            # Candle age: how many bars ago was this signal?
            bars_ago = len(df) - 1 - idx

            # Taker buy ratio for order flow context
            taker_ratio = None
            if 'taker_buy_ratio' in df.columns:
                tbr = float(row.get('taker_buy_ratio', 0.5))
                if not np.isnan(tbr):
                    taker_ratio = round(tbr, 3)

            signal_data = {
                'symbol': symbol,
                'stock_ticker': stock_ticker,
                'company_name': company_name,
                'asset_class': asset_class,
                'sector': sector,
                'strategy': strat_name,
                'strategy_tier': strat_info.get('tier', 'B'),
                'strategy_desc': strat_info.get('description', ''),
                'historical_pf': strat_info.get('historical_pf', 1.0),
                'historical_wr': strat_info.get('historical_wr', 40.0),
                'direction': direction,
                'entry_price': round(entry_price, 6),
                'stop_loss': round(sl_price, 6),
                'take_profit': round(tp2_price, 6),
                'tp1_price': round(tp1_price, 6),
                'tp2_price': round(tp2_price, 6),
                'atr': round(atr, 6),
                'sl_distance_pct': round(sl_distance_pct, 2),
                'tp1_distance_pct': round(tp1_distance_pct, 2),
                'tp_distance_pct': round(tp2_distance_pct, 2),
                'rr_ratio': round(rr_ratio, 2),
                'confidence': confidence,
                'bars_ago': bars_ago,
                'signal_time': str(row['open_time']),
                'rsi': round(float(row['rsi']), 1) if not np.isnan(row['rsi']) else None,
                'macd_hist': round(float(row['macd_hist']), 4) if not np.isnan(row['macd_hist']) else None,
                'rvol': round(float(row['rvol']), 2) if not np.isnan(row['rvol']) else None,
                'supertrend_dir': int(row['supertrend_dir']),
                'taker_buy_ratio': taker_ratio,
                'macro_regime': bench_regime,
                'rs_ratio': rs_data.get("rs_ratio", 1.0),
                'rs_status': rs_data.get("rs_status", "IN_LINE"),
                'htf_bias': htf_bias,
                'htf_aligned': htf_aligned,
                'htf_interval': htf_interval,
            }
            signals.append(signal_data)

    return signals


def scan_all_signals(
    symbols: Optional[List[str]] = None,
    interval: str = '1h',
    rr_key: str = '1:2.0',
    lookback_bars: int = 3,
    min_confidence: int = 0,
    asset_class: str = "ALL",
    mtf_aligned_only: bool = False,
) -> List[Dict[str, Any]]:
    """
    Scan multiple symbols in parallel for active trade signals with macro context.
    Returns a list of trade setups sorted by confidence score descending.
    """
    # Refresh MTF cache for a fresh scan cycle
    clear_htf_cache()

    if symbols is None:
        symbols = _get_dynamic_symbols(max_symbols=35, asset_class=asset_class)

    btc_bench_df = get_benchmark_dataframe("BTCUSDT", interval=interval, limit=100)
    spy_bench_df = get_benchmark_dataframe("SPYBUSDT", interval=interval, limit=100)
    macro_info = get_macro_summary()

    all_signals = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(
                scan_symbol_signals,
                sym, interval, rr_key, 200, lookback_bars,
                btc_bench_df, spy_bench_df, macro_info
            ): sym
            for sym in symbols
        }
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                all_signals.extend(result)
            except Exception:
                continue

    # Filter by minimum confidence
    if min_confidence > 0:
        all_signals = [s for s in all_signals if s['confidence'] >= min_confidence]

    # Filter by asset class if symbols were provided explicitly
    if asset_class.upper() != "ALL":
        all_signals = [s for s in all_signals if s.get('asset_class') == asset_class.upper()]

    # Filter by MTF alignment if requested
    if mtf_aligned_only:
        all_signals = [s for s in all_signals if s.get('htf_aligned', False)]

    # Sort: confidence desc, then bars_ago asc (freshest first)
    all_signals.sort(key=lambda x: (-x['confidence'], x['bars_ago']))

    return all_signals
