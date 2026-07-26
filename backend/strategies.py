"""
Strategy signal definitions for crypto trading.

Each strategy function takes a DataFrame with enriched indicators (including regime)
and returns a boolean Series indicating where entry signals occur.

Key design principles:
- Multi-factor confluence: every strategy requires 3+ conditions
- Regime-aware: strategies only fire in appropriate market conditions
- Volume confirmation: most strategies require relative volume support
"""
import pandas as pd
import numpy as np


# ============================================================================
# REGIME-FILTERED CONFLUENCE STRATEGIES
# ============================================================================

def strat_trend_pullback_long(df: pd.DataFrame) -> pd.Series:
    """Trend Pullback Buy: Buy RSI dips in confirmed bull trends.
    
    Confluence:
    1. REGIME: Bull trend (price > 200 EMA, 50 > 200 EMA, ADX > 25)
    2. STRUCTURE: EMA 8 > EMA 21 (short-term trend intact)
    3. TRIGGER: RSI pulls back to 35-45 and bounces (was < 45, now >= 45)
    4. CONFIRM: RVOL > 1.0 (at least average volume)
    """
    regime_ok = (df['close'] > df['ema_200']) & (df['ema_50'] > df['ema_200']) & (df['adx'] >= 25)
    structure = df['ema_8'] > df['ema_21']
    trigger = (df['rsi'].shift(1) < 45) & (df['rsi'] >= 45) & (df['rsi'] < 65)
    confirm = df['rvol'] > 1.0
    return regime_ok & structure & trigger & confirm


def strat_trend_pullback_short(df: pd.DataFrame) -> pd.Series:
    """Trend Pullback Short: Short RSI rallies in confirmed bear trends.
    
    Confluence:
    1. REGIME: Bear trend (price < 200 EMA, 50 < 200 EMA, ADX > 25)
    2. STRUCTURE: EMA 8 < EMA 21 (short-term downtrend intact)
    3. TRIGGER: RSI rallies to 55-65 and rolls over (was > 55, now <= 55)
    4. CONFIRM: RVOL > 1.0
    """
    regime_ok = (df['close'] < df['ema_200']) & (df['ema_50'] < df['ema_200']) & (df['adx'] >= 25)
    structure = df['ema_8'] < df['ema_21']
    trigger = (df['rsi'].shift(1) > 55) & (df['rsi'] <= 55) & (df['rsi'] > 35)
    confirm = df['rvol'] > 1.0
    return regime_ok & structure & trigger & confirm


def strat_squeeze_breakout_long(df: pd.DataFrame) -> pd.Series:
    """TTM Squeeze Breakout: Volatility expansion in bull context.
    
    Confluence:
    1. REGIME: Price above 200 EMA (bull bias)
    2. STRUCTURE: BB was inside KC on prev candle (squeeze was active)
    3. TRIGGER: Close breaks above BB upper band
    4. CONFIRM: Volume surge (RVOL > 1.5) + MACD histogram positive
    """
    bull_bias = df['close'] > df['ema_200']
    squeeze_was_on = (
        (df['bb_upper'].shift(1) < df['kc_upper'].shift(1)) & 
        (df['bb_lower'].shift(1) > df['kc_lower'].shift(1))
    )
    breakout = df['close'] > df['bb_upper']
    vol_confirm = df['rvol'] > 1.5
    macd_confirm = df['macd_hist'] > 0
    return bull_bias & squeeze_was_on & breakout & vol_confirm & macd_confirm


def strat_squeeze_breakout_short(df: pd.DataFrame) -> pd.Series:
    """TTM Squeeze Breakdown: Volatility expansion in bear context.
    
    Confluence:
    1. REGIME: Price below 200 EMA (bear bias)
    2. STRUCTURE: BB was inside KC on prev candle (squeeze was active)
    3. TRIGGER: Close breaks below BB lower band
    4. CONFIRM: Volume surge (RVOL > 1.5) + MACD histogram negative
    """
    bear_bias = df['close'] < df['ema_200']
    squeeze_was_on = (
        (df['bb_upper'].shift(1) < df['kc_upper'].shift(1)) & 
        (df['bb_lower'].shift(1) > df['kc_lower'].shift(1))
    )
    breakdown = df['close'] < df['bb_lower']
    vol_confirm = df['rvol'] > 1.5
    macd_confirm = df['macd_hist'] < 0
    return bear_bias & squeeze_was_on & breakdown & vol_confirm & macd_confirm


def strat_momentum_continuation_long(df: pd.DataFrame) -> pd.Series:
    """Momentum Continuation: Supertrend + StochRSI recycle in strong bull trend.
    
    Confluence:
    1. REGIME: Bull trend (price > 200 EMA, ADX > 25)
    2. STRUCTURE: Supertrend is bullish (dir == 1)
    3. TRIGGER: StochRSI K crosses above D from below 30 (momentum recycles)
    4. CONFIRM: +DI > -DI (directional pressure is bullish)
    """
    regime_ok = (df['close'] > df['ema_200']) & (df['adx'] >= 25)
    structure = df['supertrend_dir'] == 1
    trigger = (
        (df['stoch_k'].shift(1) <= df['stoch_d'].shift(1)) & 
        (df['stoch_k'] > df['stoch_d']) & 
        (df['stoch_k'].shift(1) < 30)
    )
    confirm = df['plus_di'] > df['minus_di']
    return regime_ok & structure & trigger & confirm


def strat_momentum_continuation_short(df: pd.DataFrame) -> pd.Series:
    """Momentum Continuation Short: Supertrend + StochRSI recycle in bear trend.
    
    Confluence:
    1. REGIME: Bear trend (price < 200 EMA, ADX > 25)
    2. STRUCTURE: Supertrend is bearish (dir == -1)
    3. TRIGGER: StochRSI K crosses below D from above 70 (momentum fails)
    4. CONFIRM: -DI > +DI (directional pressure is bearish)
    """
    regime_ok = (df['close'] < df['ema_200']) & (df['adx'] >= 25)
    structure = df['supertrend_dir'] == -1
    trigger = (
        (df['stoch_k'].shift(1) >= df['stoch_d'].shift(1)) & 
        (df['stoch_k'] < df['stoch_d']) & 
        (df['stoch_k'].shift(1) > 70)
    )
    confirm = df['minus_di'] > df['plus_di']
    return regime_ok & structure & trigger & confirm


def strat_volume_breakout_long(df: pd.DataFrame) -> pd.Series:
    """Volume Breakout: High-conviction moves with massive volume in bull context.
    
    Confluence:
    1. REGIME: Price above 200 EMA (bull bias)
    2. STRUCTURE: EMA stack aligned (8 > 21 > 55)
    3. TRIGGER: MACD histogram crosses positive
    4. CONFIRM: Extreme volume surge (RVOL > 1.8)
    """
    bull_bias = df['close'] > df['ema_200']
    structure = (df['ema_8'] > df['ema_21']) & (df['ema_21'] > df['ema_55'])
    trigger = (df['macd_hist'].shift(1) <= 0) & (df['macd_hist'] > 0)
    vol_confirm = df['rvol'] > 1.8
    return bull_bias & structure & trigger & vol_confirm


def strat_supertrend_regime_long(df: pd.DataFrame) -> pd.Series:
    """Supertrend Flip with Macro Filter: Trend continuation after Supertrend flips bullish.
    
    Confluence:
    1. REGIME: Price above 200 EMA + 50 > 200 EMA (confirmed bull)
    2. STRUCTURE: ADX > 20 (some directional movement)
    3. TRIGGER: Supertrend flips from bearish to bullish
    4. CONFIRM: RSI between 40-70 (not overbought)
    """
    regime_ok = (df['close'] > df['ema_200']) & (df['ema_50'] > df['ema_200'])
    structure = df['adx'] > 20
    trigger = (df['supertrend_dir'].shift(1) == -1) & (df['supertrend_dir'] == 1)
    confirm = (df['rsi'] >= 40) & (df['rsi'] <= 70)
    return regime_ok & structure & trigger & confirm


def strat_supertrend_regime_short(df: pd.DataFrame) -> pd.Series:
    """Supertrend Flip Short: Trend continuation after Supertrend flips bearish.
    
    Confluence:
    1. REGIME: Price below 200 EMA + 50 < 200 EMA (confirmed bear)
    2. STRUCTURE: ADX > 20
    3. TRIGGER: Supertrend flips from bullish to bearish
    4. CONFIRM: RSI between 30-60 (not oversold)
    """
    regime_ok = (df['close'] < df['ema_200']) & (df['ema_50'] < df['ema_200'])
    structure = df['adx'] > 20
    trigger = (df['supertrend_dir'].shift(1) == 1) & (df['supertrend_dir'] == -1)
    confirm = (df['rsi'] >= 30) & (df['rsi'] <= 60)
    return regime_ok & structure & trigger & confirm


def strat_mean_reversion_long(df: pd.DataFrame) -> pd.Series:
    """Mean Reversion in Bull Range: Buy extreme dips in sideways-bullish markets.
    
    Confluence:
    1. REGIME: Price above 200 EMA (bullish context) but ADX < 25 (ranging)
    2. STRUCTURE: Close below lower Bollinger Band (extended)
    3. TRIGGER: RSI < 30 AND StochRSI K < 10 (deeply oversold)
    4. CONFIRM: Volume present (RVOL > 0.8)
    """
    bull_range = (df['close'] > df['ema_200']) & (df['adx'] < 25)
    structure = df['close'] < df['bb_lower']
    trigger = (df['rsi'] < 30) & (df['stoch_k'] < 10)
    confirm = df['rvol'] > 0.8
    return bull_range & structure & trigger & confirm


# ============================================================================
# STRATEGY REGISTRY
# ============================================================================

STRATEGIES = {
    # LONG strategies
    'Trend Pullback (Long)':           {'fn': strat_trend_pullback_long,         'direction': 'LONG'},
    'Squeeze Breakout (Long)':         {'fn': strat_squeeze_breakout_long,       'direction': 'LONG'},
    'Momentum Continuation (Long)':    {'fn': strat_momentum_continuation_long,  'direction': 'LONG'},
    'Volume Breakout (Long)':          {'fn': strat_volume_breakout_long,        'direction': 'LONG'},
    'Supertrend Regime (Long)':        {'fn': strat_supertrend_regime_long,      'direction': 'LONG'},
    'Mean Reversion (Long)':           {'fn': strat_mean_reversion_long,         'direction': 'LONG'},
    # SHORT strategies
    'Trend Pullback (Short)':          {'fn': strat_trend_pullback_short,        'direction': 'SHORT'},
    'Squeeze Breakout (Short)':        {'fn': strat_squeeze_breakout_short,      'direction': 'SHORT'},
    'Momentum Continuation (Short)':   {'fn': strat_momentum_continuation_short, 'direction': 'SHORT'},
    'Supertrend Regime (Short)':       {'fn': strat_supertrend_regime_short,     'direction': 'SHORT'},
}
