"""
Strategy signal definitions for crypto trading.

Each strategy function takes a DataFrame with enriched indicators (including regime)
and returns a boolean Series indicating where entry signals occur.

Key design principles:
- Multi-factor confluence: every strategy requires 3+ conditions
- Regime-aware: strategies only fire in appropriate market conditions
- Volume confirmation: most strategies require relative volume support

Strategy categories:
- Trend Following: Pullback, Momentum Continuation, Supertrend Regime
- Breakout: Squeeze Breakout, Volume Breakout, Breakout Retest
- Mean Reversion: Mean Reversion, VWAP Reversion, RSI Divergence
- Order Flow: Taker Volume Pressure
"""
import pandas as pd
import numpy as np


# ============================================================================
# REGIME-FILTERED CONFLUENCE STRATEGIES (Original)
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
# NEW STRATEGIES (Phase 2-3)
# ============================================================================

def strat_taker_pressure_long(df: pd.DataFrame) -> pd.Series:
    """Taker Volume Pressure Long: Institutional buying pressure at support.
    
    Uses taker_buy_ratio from raw Binance data — when buyers are aggressively
    lifting asks (taker buy ratio > 62%), it indicates strong demand.
    
    Confluence:
    1. REGIME: Price above 200 EMA (bull context)
    2. STRUCTURE: Price near lower Bollinger Band (at support)
    3. TRIGGER: Taker buy ratio > 0.62 (strong buying pressure)
    4. CONFIRM: RVOL > 1.3 (above-average volume)
    """
    bull_context = df['close'] > df['ema_200']
    at_support = df['close'] < df['bb_middle']  # Below BB midline = at support zone
    taker_pressure = df['taker_buy_ratio'] > 0.62
    vol_confirm = df['rvol'] > 1.3
    return bull_context & at_support & taker_pressure & vol_confirm


def strat_taker_pressure_short(df: pd.DataFrame) -> pd.Series:
    """Taker Volume Pressure Short: Institutional selling pressure at resistance.
    
    When sellers are aggressively hitting bids (taker buy ratio < 38%),
    it indicates strong supply/distribution.
    
    Confluence:
    1. REGIME: Price below 200 EMA (bear context)
    2. STRUCTURE: Price near upper Bollinger Band (at resistance)
    3. TRIGGER: Taker buy ratio < 0.38 (strong selling pressure)
    4. CONFIRM: RVOL > 1.3 (above-average volume)
    """
    bear_context = df['close'] < df['ema_200']
    at_resistance = df['close'] > df['bb_middle']  # Above BB midline = at resistance zone
    taker_pressure = df['taker_buy_ratio'] < 0.38
    vol_confirm = df['rvol'] > 1.3
    return bear_context & at_resistance & taker_pressure & vol_confirm


def strat_vwap_reversion_long(df: pd.DataFrame) -> pd.Series:
    """VWAP Reversion Long: Buy dips to VWMA in bullish trending markets.
    
    Institutions use VWAP as a benchmark — prices tend to revert to it.
    When price dips below VWMA-21 by more than 1 ATR in a bull regime,
    it's a high-probability mean reversion entry.
    
    Confluence:
    1. REGIME: Supertrend bullish (dir == 1)
    2. STRUCTURE: Price < VWMA-21 by more than 1 ATR (extended below fair value)
    3. TRIGGER: RSI < 35 (oversold)
    4. CONFIRM: RVOL > 1.2 (volume present on the dip)
    """
    regime_ok = df['supertrend_dir'] == 1
    extended = (df['vwma_21'] - df['close']) > df['atr']
    trigger = df['rsi'] < 35
    confirm = df['rvol'] > 1.2
    return regime_ok & extended & trigger & confirm


def strat_vwap_reversion_short(df: pd.DataFrame) -> pd.Series:
    """VWAP Reversion Short: Short rallies above VWMA in bearish markets.
    
    Confluence:
    1. REGIME: Supertrend bearish (dir == -1)
    2. STRUCTURE: Price > VWMA-21 by more than 1 ATR (extended above fair value)
    3. TRIGGER: RSI > 65 (overbought)
    4. CONFIRM: RVOL > 1.2
    """
    regime_ok = df['supertrend_dir'] == -1
    extended = (df['close'] - df['vwma_21']) > df['atr']
    trigger = df['rsi'] > 65
    confirm = df['rvol'] > 1.2
    return regime_ok & extended & trigger & confirm


def strat_rsi_divergence_long(df: pd.DataFrame) -> pd.Series:
    """RSI Bullish Divergence: Buy when price makes lower low but RSI makes higher low.
    
    One of the most reliable reversal signals — indicates momentum is improving
    even as price continues to fall.
    
    Confluence:
    1. REGIME: ADX < 30 (not in a runaway trend — reversals work in ranges)
    2. STRUCTURE: Bull divergence detected (price LL, RSI HL)
    3. TRIGGER: RSI currently between 25-45 (oversold zone)
    4. CONFIRM: RVOL > 1.0 (volume present)
    """
    regime_ok = df['adx'] < 30
    divergence = df['bull_divergence'] == True
    trigger = (df['rsi'] >= 25) & (df['rsi'] <= 45)
    confirm = df['rvol'] > 1.0
    return regime_ok & divergence & trigger & confirm


def strat_rsi_divergence_short(df: pd.DataFrame) -> pd.Series:
    """RSI Bearish Divergence: Short when price makes higher high but RSI makes lower high.
    
    Confluence:
    1. REGIME: ADX < 30 (ranging/weakening trend context)
    2. STRUCTURE: Bear divergence detected (price HH, RSI LH)
    3. TRIGGER: RSI currently between 55-75 (overbought zone)
    4. CONFIRM: RVOL > 1.0
    """
    regime_ok = df['adx'] < 30
    divergence = df['bear_divergence'] == True
    trigger = (df['rsi'] >= 55) & (df['rsi'] <= 75)
    confirm = df['rvol'] > 1.0
    return regime_ok & divergence & trigger & confirm


def strat_breakout_retest_long(df: pd.DataFrame) -> pd.Series:
    """Breakout Retest Long: Buy pullback to breakout level after 20-period high break.
    
    Classic pattern: price breaks above a range, pulls back to retest the
    breakout level as support, then continues higher.
    
    Confluence:
    1. REGIME: ADX > 20 (trending environment)
    2. STRUCTURE: Previous candle broke above 20-period high
    3. TRIGGER: Current candle pulls back near breakout level (within 0.5 ATR)
    4. CONFIRM: RSI 45-65 (not overbought) + RVOL > 1.0
    """
    trending = df['adx'] > 20
    # Previous candle broke the 20-period high
    prev_breakout = df['close'].shift(1) > df['high_20'].shift(2)
    # Current candle pulled back close to the old high (within 0.5 ATR)
    near_breakout_level = (df['high_20'].shift(2) - df['close']).abs() < (0.5 * df['atr'])
    rsi_ok = (df['rsi'] >= 45) & (df['rsi'] <= 65)
    vol_ok = df['rvol'] > 1.0
    return trending & prev_breakout & near_breakout_level & rsi_ok & vol_ok


def strat_breakout_retest_short(df: pd.DataFrame) -> pd.Series:
    """Breakout Retest Short: Short bounce to breakdown level after 20-period low break.
    
    Confluence:
    1. REGIME: ADX > 20 (trending environment)
    2. STRUCTURE: Previous candle broke below 20-period low
    3. TRIGGER: Current candle bounces near breakdown level (within 0.5 ATR)
    4. CONFIRM: RSI 35-55 (not oversold) + RVOL > 1.0
    """
    trending = df['adx'] > 20
    prev_breakdown = df['close'].shift(1) < df['low_20'].shift(2)
    near_breakdown_level = (df['close'] - df['low_20'].shift(2)).abs() < (0.5 * df['atr'])
    rsi_ok = (df['rsi'] >= 35) & (df['rsi'] <= 55)
    vol_ok = df['rvol'] > 1.0
    return trending & prev_breakdown & near_breakdown_level & rsi_ok & vol_ok


# ============================================================================
# STRATEGY REGISTRY
# ============================================================================

STRATEGIES = {
    # LONG strategies (Original)
    'Trend Pullback (Long)':           {'fn': strat_trend_pullback_long,         'direction': 'LONG'},
    'Squeeze Breakout (Long)':         {'fn': strat_squeeze_breakout_long,       'direction': 'LONG'},
    'Momentum Continuation (Long)':    {'fn': strat_momentum_continuation_long,  'direction': 'LONG'},
    'Volume Breakout (Long)':          {'fn': strat_volume_breakout_long,        'direction': 'LONG'},
    'Supertrend Regime (Long)':        {'fn': strat_supertrend_regime_long,      'direction': 'LONG'},
    'Mean Reversion (Long)':           {'fn': strat_mean_reversion_long,         'direction': 'LONG'},
    # SHORT strategies (Original)
    'Trend Pullback (Short)':          {'fn': strat_trend_pullback_short,        'direction': 'SHORT'},
    'Squeeze Breakout (Short)':        {'fn': strat_squeeze_breakout_short,      'direction': 'SHORT'},
    'Momentum Continuation (Short)':   {'fn': strat_momentum_continuation_short, 'direction': 'SHORT'},
    'Supertrend Regime (Short)':       {'fn': strat_supertrend_regime_short,     'direction': 'SHORT'},
    # NEW LONG strategies (Phase 2-3)
    'Taker Pressure (Long)':           {'fn': strat_taker_pressure_long,         'direction': 'LONG'},
    'VWAP Reversion (Long)':           {'fn': strat_vwap_reversion_long,         'direction': 'LONG'},
    'RSI Divergence (Long)':           {'fn': strat_rsi_divergence_long,         'direction': 'LONG'},
    'Breakout Retest (Long)':          {'fn': strat_breakout_retest_long,        'direction': 'LONG'},
    # NEW SHORT strategies (Phase 2-3)
    'Taker Pressure (Short)':          {'fn': strat_taker_pressure_short,        'direction': 'SHORT'},
    'VWAP Reversion (Short)':          {'fn': strat_vwap_reversion_short,        'direction': 'SHORT'},
    'RSI Divergence (Short)':          {'fn': strat_rsi_divergence_short,        'direction': 'SHORT'},
    'Breakout Retest (Short)':         {'fn': strat_breakout_retest_short,       'direction': 'SHORT'},
}
