"""
Market Regime Detection Engine.

Classifies each candle into one of 4 market regimes:
- BULL_TREND:  Price > 200 EMA, 50 EMA > 200 EMA, ADX > 25 — strong uptrend
- BEAR_TREND:  Price < 200 EMA, 50 EMA < 200 EMA, ADX > 25 — strong downtrend
- BULL_RANGE:  Price > 200 EMA but ADX < 25 — choppy/sideways in bullish context
- BEAR_RANGE:  Price < 200 EMA but ADX < 25 — choppy/sideways in bearish context

Usage:
    from backend.regime import classify_regime, BULL_TREND, BEAR_TREND
    df = classify_regime(df)  # adds 'regime' column
    bull_mask = df['regime'] == BULL_TREND
"""
import pandas as pd
import numpy as np
from typing import Dict

# Regime labels
BULL_TREND = 'BULL_TREND'
BEAR_TREND = 'BEAR_TREND'
BULL_RANGE = 'BULL_RANGE'
BEAR_RANGE = 'BEAR_RANGE'


def classify_regime(df: pd.DataFrame, adx_trend_threshold: float = 25.0) -> pd.DataFrame:
    """
    Classify each row into a market regime based on EMA structure and ADX strength.
    
    Requires columns: close, ema_50, ema_200, adx
    Adds column: 'regime' (str)
    
    Args:
        df: DataFrame with enriched indicators (from enrich_klines_dataframe)
        adx_trend_threshold: ADX above this = trending, below = ranging
    
    Returns:
        DataFrame with 'regime' column added
    """
    required_cols = ['close', 'ema_50', 'ema_200', 'adx']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}. Run enrich_klines_dataframe first.")
    
    conditions = [
        # BULL_TREND: price above 200 EMA, 50 > 200 EMA, strong trend
        (df['close'] > df['ema_200']) & (df['ema_50'] > df['ema_200']) & (df['adx'] >= adx_trend_threshold),
        # BEAR_TREND: price below 200 EMA, 50 < 200 EMA, strong trend
        (df['close'] < df['ema_200']) & (df['ema_50'] < df['ema_200']) & (df['adx'] >= adx_trend_threshold),
        # BULL_RANGE: bullish context but weak/no trend
        (df['close'] > df['ema_200']) & (df['adx'] < adx_trend_threshold),
        # BEAR_RANGE: bearish context but weak/no trend
        (df['close'] < df['ema_200']) & (df['adx'] < adx_trend_threshold),
    ]
    
    choices = [BULL_TREND, BEAR_TREND, BULL_RANGE, BEAR_RANGE]
    
    # Default: use EMA structure when conditions overlap (e.g. ADX >= 25 but EMAs disagree)
    df = df.copy()
    df['regime'] = np.select(conditions, choices, default=BULL_RANGE)
    
    # Handle the edge case: ADX >= 25 but EMAs disagree with price
    # (e.g., price > 200 EMA but 50 < 200 EMA — early trend reversal)
    # Classify as range until EMAs confirm
    mixed_bull = (df['close'] > df['ema_200']) & (df['ema_50'] <= df['ema_200']) & (df['adx'] >= adx_trend_threshold)
    mixed_bear = (df['close'] < df['ema_200']) & (df['ema_50'] >= df['ema_200']) & (df['adx'] >= adx_trend_threshold)
    df.loc[mixed_bull, 'regime'] = BULL_RANGE
    df.loc[mixed_bear, 'regime'] = BEAR_RANGE
    
    return df


def get_regime_summary(df: pd.DataFrame) -> Dict[str, Dict]:
    """
    Returns a summary of regime distribution in the dataset.
    Useful for understanding what market conditions the backtest covers.
    """
    if 'regime' not in df.columns:
        df = classify_regime(df)
    
    total = len(df)
    summary = {}
    for regime in [BULL_TREND, BEAR_TREND, BULL_RANGE, BEAR_RANGE]:
        count = (df['regime'] == regime).sum()
        summary[regime] = {
            'count': int(count),
            'pct': round(count / total * 100, 1) if total > 0 else 0,
        }
    return summary


def regime_filter_signals(signals: pd.Series, df: pd.DataFrame, allowed_regimes: list) -> pd.Series:
    """
    Filter a boolean signal series to only fire in allowed market regimes.
    
    Args:
        signals: Boolean Series of entry signals
        df: DataFrame with 'regime' column
        allowed_regimes: List of regime constants to allow (e.g., [BULL_TREND, BULL_RANGE])
    
    Returns:
        Filtered boolean Series
    """
    if 'regime' not in df.columns:
        raise ValueError("DataFrame must have 'regime' column. Run classify_regime first.")
    
    regime_mask = df['regime'].isin(allowed_regimes)
    return signals & regime_mask
