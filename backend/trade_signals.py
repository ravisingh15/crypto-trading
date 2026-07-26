"""
Trade Signal Scanner with ATR-based Stop-Loss / Take-Profit calculation.
Scans live Binance data for active strategy signals and returns actionable
trade setups with entry, SL, TP, and risk metrics.
"""
import concurrent.futures
import time
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np

from backend.binance_client import binance_client
from backend.indicators import enrich_klines_dataframe
from backend.strategies import STRATEGIES


# Default R:R configurations
RR_CONFIGS = {
    '1:1.5': {'sl_mult': 1.5, 'tp_mult': 2.25},
    '1:2.0': {'sl_mult': 1.5, 'tp_mult': 3.00},
    '1:3.0': {'sl_mult': 1.0, 'tp_mult': 3.00},
}

# Symbols to scan
SCAN_SYMBOLS = [
    'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT',
    'ADAUSDT', 'AVAXUSDT', 'NEARUSDT', 'SUIUSDT', 'APTUSDT', 'INJUSDT',
    'DOTUSDT', 'SEIUSDT', 'FETUSDT', 'RENDERUSDT', 'UNIUSDT', 'AAVEUSDT',
    'PENDLEUSDT', 'ARBUSDT', 'OPUSDT', 'PEPEUSDT', 'WIFUSDT', 'BONKUSDT',
]


def _calculate_signal_confidence(df: pd.DataFrame, idx: int, direction: str) -> int:
    """
    Calculate a confluence-based confidence score (0-100) for a signal.
    Checks alignment of multiple indicators at the signal bar.
    """
    row = df.iloc[idx]
    score = 0

    # EMA trend alignment (up to +30)
    if direction == 'LONG':
        if row.get('ema_8', 0) > row.get('ema_21', 0):
            score += 15
        if row.get('ema_21', 0) > row.get('ema_55', 0):
            score += 15
    else:
        if row.get('ema_8', 0) < row.get('ema_21', 0):
            score += 15
        if row.get('ema_21', 0) < row.get('ema_55', 0):
            score += 15

    # RSI zone confirmation (+20)
    rsi = row.get('rsi', 50)
    if direction == 'LONG' and rsi < 45:
        score += 20
    elif direction == 'SHORT' and rsi > 55:
        score += 20

    # MACD histogram agreement (+15)
    macd_hist = row.get('macd_hist', 0)
    if direction == 'LONG' and macd_hist > 0:
        score += 15
    elif direction == 'SHORT' and macd_hist < 0:
        score += 15

    # Volume surge (+15)
    rvol = row.get('rvol', 1.0)
    if rvol > 1.5:
        score += 15

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

    return min(score, 100)


def scan_symbol_signals(
    symbol: str,
    interval: str = '1h',
    rr_key: str = '1:2.0',
    limit: int = 200,
    lookback_bars: int = 3,
) -> List[Dict[str, Any]]:
    """
    Scan a single symbol for recent strategy signals.
    Returns trade setups with entry, SL, TP for signals within the last `lookback_bars` candles.
    """
    try:
        raw = binance_client.get_klines(symbol, interval=interval, limit=limit)
        df = enrich_klines_dataframe(raw)
        if df.empty or len(df) < 60:
            return []
    except Exception:
        return []

    rr = RR_CONFIGS.get(rr_key, RR_CONFIGS['1:2.0'])
    sl_mult = rr['sl_mult']
    tp_mult = rr['tp_mult']

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

            if direction == 'LONG':
                sl_price = entry_price - (sl_mult * atr)
                tp_price = entry_price + (tp_mult * atr)
            else:
                sl_price = entry_price + (sl_mult * atr)
                tp_price = entry_price - (tp_mult * atr)

            sl_distance_pct = abs(entry_price - sl_price) / entry_price * 100
            tp_distance_pct = abs(tp_price - entry_price) / entry_price * 100
            rr_ratio = tp_distance_pct / sl_distance_pct if sl_distance_pct > 0 else 0

            confidence = _calculate_signal_confidence(df, idx, direction)

            # Candle age: how many bars ago was this signal?
            bars_ago = len(df) - 1 - idx

            signal_data = {
                'symbol': symbol,
                'strategy': strat_name,
                'direction': direction,
                'entry_price': round(entry_price, 6),
                'stop_loss': round(sl_price, 6),
                'take_profit': round(tp_price, 6),
                'atr': round(atr, 6),
                'sl_distance_pct': round(sl_distance_pct, 2),
                'tp_distance_pct': round(tp_distance_pct, 2),
                'rr_ratio': round(rr_ratio, 2),
                'confidence': confidence,
                'bars_ago': bars_ago,
                'signal_time': str(row['open_time']),
                'rsi': round(float(row['rsi']), 1) if not np.isnan(row['rsi']) else None,
                'macd_hist': round(float(row['macd_hist']), 4) if not np.isnan(row['macd_hist']) else None,
                'rvol': round(float(row['rvol']), 2) if not np.isnan(row['rvol']) else None,
                'supertrend_dir': int(row['supertrend_dir']),
            }
            signals.append(signal_data)

    return signals


def scan_all_signals(
    symbols: Optional[List[str]] = None,
    interval: str = '1h',
    rr_key: str = '1:2.0',
    lookback_bars: int = 3,
    min_confidence: int = 0,
) -> List[Dict[str, Any]]:
    """
    Scan multiple symbols in parallel for active trade signals.
    Returns a list of trade setups sorted by confidence score descending.
    """
    if symbols is None:
        symbols = SCAN_SYMBOLS

    all_signals = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(scan_symbol_signals, sym, interval, rr_key, 200, lookback_bars): sym
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

    # Sort: confidence desc, then bars_ago asc (freshest first)
    all_signals.sort(key=lambda x: (-x['confidence'], x['bars_ago']))

    return all_signals
