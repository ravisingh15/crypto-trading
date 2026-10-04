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
# REGIME-FILTERED CONFLUENCE STRATEGIES
# ============================================================================

def strat_trend_pullback_long(df: pd.DataFrame) -> pd.Series:
    """Trend Pullback Buy: Buy RSI dips in confirmed bull trends.
    
    Confluence:
    1. REGIME: Bull trend (price > 50 EMA, or 21 > 50 EMA, or price > 200 EMA) with ADX >= 18
    2. STRUCTURE: EMA 8 > EMA 21 (short-term trend intact)
    3. TRIGGER: RSI pulls back to 38-48 and bounces (was < 48, now >= 42 and < 68)
    4. CONFIRM: RVOL > 0.95
    """
    regime_ok = ((df['close'] > df['ema_50']) | (df['ema_21'] > df['ema_50']) | (df['close'] > df['ema_200'])) & (df['adx'] >= 18)
    structure = df['ema_8'] > df['ema_21']
    trigger = (df['rsi'].shift(1) < 48) & (df['rsi'] >= 42) & (df['rsi'] < 68)
    confirm = df['rvol'] > 0.95
    return regime_ok & structure & trigger & confirm


def strat_trend_pullback_short(df: pd.DataFrame) -> pd.Series:
    """Trend Pullback Short: Short RSI rallies in confirmed bear trends.
    
    Confluence:
    1. REGIME: Macro bear trend (price < 200 EMA AND 50 < 200 EMA) with ADX >= 18
    2. STRUCTURE: EMA 8 < EMA 21 (short-term downtrend intact)
    3. TRIGGER: RSI rallies to 52-62 and rolls over (was > 52, now <= 58 and > 32)
    4. CONFIRM: RVOL > 0.95
    """
    regime_ok = (df['close'] < df['ema_200']) & (df['ema_50'] < df['ema_200']) & (df['adx'] >= 18)
    structure = df['ema_8'] < df['ema_21']
    trigger = (df['rsi'].shift(1) > 52) & (df['rsi'] <= 58) & (df['rsi'] > 32)
    confirm = df['rvol'] > 0.95
    return regime_ok & structure & trigger & confirm


def strat_squeeze_breakout_long(df: pd.DataFrame) -> pd.Series:
    """TTM Squeeze Breakout: Volatility expansion in bull context.
    
    Confluence:
    1. REGIME: Short/mid-term trend bullish (close > 21 EMA or 8 > 21 EMA or close > 200 EMA)
    2. STRUCTURE: BB was inside KC on prev candle (squeeze was active)
    3. TRIGGER: Close breaks above BB upper band
    4. CONFIRM: Volume surge (RVOL > 1.1) + MACD histogram positive
    """
    bull_bias = (df['close'] > df['ema_21']) | (df['ema_8'] > df['ema_21']) | (df['close'] > df['ema_200'])
    squeeze_was_on = (
        (df['bb_upper'].shift(1) < df['kc_upper'].shift(1)) & 
        (df['bb_lower'].shift(1) > df['kc_lower'].shift(1))
    )
    breakout = df['close'] > df['bb_upper']
    vol_confirm = df['rvol'] > 1.1
    macd_confirm = df['macd_hist'] > 0
    return bull_bias & squeeze_was_on & breakout & vol_confirm & macd_confirm


def strat_squeeze_breakout_short(df: pd.DataFrame) -> pd.Series:
    """TTM Squeeze Breakdown: Volatility expansion in bear context.
    
    Confluence:
    1. REGIME: Macro bear trend (close < 200 EMA AND 50 < 200 EMA)
    2. STRUCTURE: BB was inside KC on prev candle (squeeze was active)
    3. TRIGGER: Close breaks below BB lower band
    4. CONFIRM: Volume surge (RVOL > 1.1) + MACD histogram negative
    """
    bear_bias = (df['close'] < df['ema_200']) & (df['ema_50'] < df['ema_200'])
    squeeze_was_on = (
        (df['bb_upper'].shift(1) < df['kc_upper'].shift(1)) & 
        (df['bb_lower'].shift(1) > df['kc_lower'].shift(1))
    )
    breakdown = df['close'] < df['bb_lower']
    vol_confirm = df['rvol'] > 1.1
    macd_confirm = df['macd_hist'] < 0
    return bear_bias & squeeze_was_on & breakdown & vol_confirm & macd_confirm


def strat_momentum_continuation_long(df: pd.DataFrame) -> pd.Series:
    """Momentum Continuation: Supertrend or EMA alignment + StochRSI recycle.
    
    Confluence:
    1. REGIME: Bullish momentum (Close > 50 EMA or Close > 200 EMA or 8 > 21 EMA) with ADX >= 18
    2. STRUCTURE: Supertrend is bullish (dir == 1) OR EMA 8 > EMA 21
    3. TRIGGER: StochRSI K crosses above D from below 40
    4. CONFIRM: +DI > -DI (directional pressure is bullish)
    """
    regime_ok = ((df['close'] > df['ema_50']) | (df['close'] > df['ema_200']) | (df['ema_8'] > df['ema_21'])) & (df['adx'] >= 18)
    structure = (df['supertrend_dir'] == 1) | (df['ema_8'] > df['ema_21'])
    trigger = (
        (df['stoch_k'].shift(1) <= df['stoch_d'].shift(1)) & 
        (df['stoch_k'] > df['stoch_d']) & 
        (df['stoch_k'].shift(1) < 40)
    )
    confirm = df['plus_di'] > df['minus_di']
    return regime_ok & structure & trigger & confirm


def strat_momentum_continuation_short(df: pd.DataFrame) -> pd.Series:
    """Momentum Continuation Short: Supertrend or EMA alignment + StochRSI rollover.
    
    Confluence:
    1. REGIME: Macro bear trend (Close < 200 EMA AND 50 < 200 EMA) with ADX >= 18
    2. STRUCTURE: Supertrend is bearish (dir == -1) OR EMA 8 < EMA 21
    3. TRIGGER: StochRSI K crosses below D from above 60
    4. CONFIRM: -DI > +DI (directional pressure is bearish)
    """
    regime_ok = (df['close'] < df['ema_200']) & (df['ema_50'] < df['ema_200']) & (df['adx'] >= 18)
    structure = (df['supertrend_dir'] == -1) | (df['ema_8'] < df['ema_21'])
    trigger = (
        (df['stoch_k'].shift(1) >= df['stoch_d'].shift(1)) & 
        (df['stoch_k'] < df['stoch_d']) & 
        (df['stoch_k'].shift(1) > 60)
    )
    confirm = df['minus_di'] > df['plus_di']
    return regime_ok & structure & trigger & confirm


def strat_volume_breakout_long(df: pd.DataFrame) -> pd.Series:
    """Volume Breakout: High-conviction momentum thrust with volume.
    
    Confluence:
    1. REGIME: Bullish structure (Close > 50 EMA or 8 > 21 EMA or Close > 200 EMA)
    2. STRUCTURE: EMA stack aligned (8 > 21)
    3. TRIGGER: MACD histogram crosses positive
    4. CONFIRM: Volume surge (RVOL > 1.2)
    """
    bull_bias = (df['close'] > df['ema_50']) | (df['ema_8'] > df['ema_21']) | (df['close'] > df['ema_200'])
    structure = df['ema_8'] > df['ema_21']
    trigger = (df['macd_hist'].shift(1) <= 0) & (df['macd_hist'] > 0)
    vol_confirm = df['rvol'] > 1.2
    return bull_bias & structure & trigger & vol_confirm


def strat_supertrend_regime_long(df: pd.DataFrame) -> pd.Series:
    """Supertrend Flip with Confirmation: Trend continuation after Supertrend flips bullish.
    
    Confluence:
    1. REGIME: Bullish context (Close > 50 EMA or 8 > 21 EMA or Close > 200 EMA)
    2. STRUCTURE: ADX >= 16 (directional movement)
    3. TRIGGER: Supertrend flips from bearish to bullish
    4. CONFIRM: RSI between 40-72
    """
    regime_ok = (df['close'] > df['ema_50']) | (df['ema_8'] > df['ema_21']) | (df['close'] > df['ema_200'])
    structure = df['adx'] >= 16
    trigger = (df['supertrend_dir'].shift(1) == -1) & (df['supertrend_dir'] == 1)
    confirm = (df['rsi'] >= 40) & (df['rsi'] <= 72)
    return regime_ok & structure & trigger & confirm


def strat_supertrend_regime_short(df: pd.DataFrame) -> pd.Series:
    """Supertrend Flip Short: Trend continuation after Supertrend flips bearish.
    
    Confluence:
    1. REGIME: Macro bear context (Close < 200 EMA AND 50 < 200 EMA)
    2. STRUCTURE: ADX >= 16
    3. TRIGGER: Supertrend flips from bullish to bearish
    4. CONFIRM: RSI between 28-60
    """
    regime_ok = (df['close'] < df['ema_200']) & (df['ema_50'] < df['ema_200'])
    structure = df['adx'] >= 16
    trigger = (df['supertrend_dir'].shift(1) == 1) & (df['supertrend_dir'] == -1)
    confirm = (df['rsi'] >= 28) & (df['rsi'] <= 60)
    return regime_ok & structure & trigger & confirm


def strat_mean_reversion_long(df: pd.DataFrame) -> pd.Series:
    """Mean Reversion Long: Buy extreme dips with confirmation bounce.
    
    Confluence:
    1. REGIME: Consolidating or dip range (ADX < 32)
    2. STRUCTURE: Low pierced lower Bollinger Band
    3. TRIGGER: RSI < 38 AND StochRSI K < 25
    4. CONFIRM: Confirmation bounce candle (Close >= Open or RSI ticked up) + RVOL > 0.8
    """
    range_ok = df['adx'] < 32
    structure = (df['low'] < df['bb_lower']) | (df['close'] < df['bb_lower'])
    trigger = (df['rsi'] < 38) & (df['stoch_k'] < 25)
    bounce_confirm = (df['close'] >= df['open']) | (df['rsi'] > df['rsi'].shift(1))
    vol_confirm = df['rvol'] > 0.8
    return range_ok & structure & trigger & bounce_confirm & vol_confirm


def strat_taker_pressure_long(df: pd.DataFrame) -> pd.Series:
    """Taker Volume Pressure Long: Institutional buying pressure at support.
    
    Confluence:
    1. REGIME: At support zone or pullback (Close < BB middle or RSI < 50)
    2. TRIGGER: Taker buy ratio > 0.58 (strong buyer dominance)
    3. CONFIRM: RVOL > 1.05 (active volume)
    """
    at_support = (df['close'] < df['bb_middle']) | (df['rsi'] < 50) | (df['close'] < df['ema_21'])
    taker_pressure = df['taker_buy_ratio'] > 0.58
    vol_confirm = df['rvol'] > 1.05
    return at_support & taker_pressure & vol_confirm


def strat_taker_pressure_short(df: pd.DataFrame) -> pd.Series:
    """Taker Volume Pressure Short: Institutional selling pressure at resistance.
    
    Confluence:
    1. REGIME: At resistance zone or rally (Close > BB middle or RSI > 50)
    2. TRIGGER: Taker buy ratio < 0.42 (strong seller dominance)
    3. CONFIRM: RVOL > 1.05
    """
    at_resistance = (df['close'] > df['bb_middle']) | (df['rsi'] > 50) | (df['close'] > df['ema_21'])
    taker_pressure = df['taker_buy_ratio'] < 0.42
    vol_confirm = df['rvol'] > 1.05
    return at_resistance & taker_pressure & vol_confirm


def strat_vwap_reversion_long(df: pd.DataFrame) -> pd.Series:
    """VWAP Reversion Long: Buy oversold dips below VWMA in trending/mean-reverting markets.
    
    Confluence:
    1. STRUCTURE: Price < VWMA-21 by more than 0.6 ATR (extended below fair value)
    2. TRIGGER: RSI < 40 (oversold)
    3. CONFIRM: RVOL > 0.9
    """
    extended = (df['vwma_21'] - df['close']) > (0.6 * df['atr'])
    trigger = df['rsi'] < 40
    confirm = df['rvol'] > 0.9
    return extended & trigger & confirm


def strat_vwap_reversion_short(df: pd.DataFrame) -> pd.Series:
    """VWAP Reversion Short: Short overbought rallies above VWMA.
    
    Confluence:
    1. STRUCTURE: Price > VWMA-21 by more than 0.6 ATR
    2. TRIGGER: RSI > 60 (overbought)
    3. CONFIRM: RVOL > 0.9
    """
    extended = (df['close'] - df['vwma_21']) > (0.6 * df['atr'])
    trigger = df['rsi'] > 60
    confirm = df['rvol'] > 0.9
    return extended & trigger & confirm


def strat_rsi_divergence_long(df: pd.DataFrame) -> pd.Series:
    """RSI Bullish Divergence: Buy when price makes lower low but RSI makes higher low.
    
    Confluence:
    1. REGIME: ADX < 35 (reversals thrive outside runaway trends)
    2. STRUCTURE: Bull divergence detected (price LL, RSI HL)
    3. TRIGGER: RSI currently between 22-48
    4. CONFIRM: RVOL > 0.9
    """
    regime_ok = df['adx'] < 35
    divergence = df['bull_divergence'] == True
    trigger = (df['rsi'] >= 22) & (df['rsi'] <= 48)
    confirm = df['rvol'] > 0.9
    return regime_ok & divergence & trigger & confirm


def strat_rsi_divergence_short(df: pd.DataFrame) -> pd.Series:
    """RSI Bearish Divergence: Short when price makes higher high but RSI makes lower high.
    
    Confluence:
    1. REGIME: ADX < 35
    2. STRUCTURE: Bear divergence detected (price HH, RSI LH)
    3. TRIGGER: RSI currently between 52-78
    4. CONFIRM: RVOL > 0.9
    """
    regime_ok = df['adx'] < 35
    divergence = df['bear_divergence'] == True
    trigger = (df['rsi'] >= 52) & (df['rsi'] <= 78)
    confirm = df['rvol'] > 0.9
    return regime_ok & divergence & trigger & confirm


def strat_breakout_retest_long(df: pd.DataFrame) -> pd.Series:
    """Breakout Retest Long: Buy pullback to breakout level with wick absorption tolerance.
    
    Confluence:
    1. REGIME: Trending bull environment (ADX > 16 & Price > 50 EMA)
    2. STRUCTURE: Previous 1-3 candles broke above 20-period high
    3. TRIGGER: Current candle pulls back near breakout level (within 0.85 ATR)
    4. CONFIRM: RSI 38-70 + RVOL > 0.85
    """
    trending = (df['adx'] > 16) & ((df['close'] > df['ema_50']) | (df['close'] > df['ema_200']))
    prev_breakout = df['close'].shift(1) > df['high_20'].shift(2)
    near_breakout_level = (df['high_20'].shift(2) - df['close']).abs() < (0.85 * df['atr'])
    rsi_ok = (df['rsi'] >= 38) & (df['rsi'] <= 70)
    vol_ok = df['rvol'] > 0.85
    return trending & prev_breakout & near_breakout_level & rsi_ok & vol_ok


def strat_breakout_retest_short(df: pd.DataFrame) -> pd.Series:
    """Breakout Retest Short: Short bounce to breakdown level with wick tolerance.
    
    Confluence:
    1. REGIME: Trending bear environment (ADX > 16 & Price < 200 EMA)
    2. STRUCTURE: Previous candle broke below 20-period low
    3. TRIGGER: Current candle bounces near breakdown level (within 0.85 ATR)
    4. CONFIRM: RSI 30-62 + RVOL > 0.85
    """
    trending = (df['adx'] > 16) & (df['close'] < df['ema_200'])
    prev_breakdown = df['close'].shift(1) < df['low_20'].shift(2)
    near_breakdown_level = (df['close'] - df['low_20'].shift(2)).abs() < (0.85 * df['atr'])
    rsi_ok = (df['rsi'] >= 30) & (df['rsi'] <= 62)
    vol_ok = df['rvol'] > 0.85
    return trending & prev_breakdown & near_breakdown_level & rsi_ok & vol_ok


def strat_ema_cross_long(df: pd.DataFrame) -> pd.Series:
    """EMA Bullish Golden Cross: Fast EMA crosses above Slow EMA with momentum.
    
    Confluence:
    1. REGIME: Bull bias (Price > 50 EMA or Price > 200 EMA)
    2. TRIGGER: EMA 8 crosses above EMA 21
    3. STRUCTURE: MACD Histogram is positive or improving
    4. CONFIRM: RSI between 42-68 + RVOL > 1.0
    """
    bull_bias = (df['close'] > df['ema_50']) | (df['close'] > df['ema_200'])
    cross = (df['ema_8'].shift(1) <= df['ema_21'].shift(1)) & (df['ema_8'] > df['ema_21'])
    macd_improving = df['macd_hist'] >= df['macd_hist'].shift(1)
    rsi_ok = (df['rsi'] >= 42) & (df['rsi'] <= 68)
    vol_ok = df['rvol'] > 1.0
    return bull_bias & cross & macd_improving & rsi_ok & vol_ok


def strat_oversold_bounce_long(df: pd.DataFrame) -> pd.Series:
    """Oversold Dip Bounce: Catches high-probability relief bounces from extreme selling.
    
    Confluence:
    1. STRUCTURE: RSI was oversold (< 35) and crosses back above 35 OR StochRSI crosses from < 20
    2. TRIGGER: Bullish candle (Close > Open)
    3. CONFIRM: MACD histogram ticking up (selling momentum abating) + RVOL > 0.8
    """
    rsi_bounce = (df['rsi'].shift(1) < 35) & (df['rsi'] >= 35)
    stoch_bounce = (
        (df['stoch_k'].shift(1) <= df['stoch_d'].shift(1)) & 
        (df['stoch_k'] > df['stoch_d']) & 
        (df['stoch_k'].shift(1) < 25)
    )
    bull_candle = df['close'] > df['open']
    macd_turning = df['macd_hist'] > df['macd_hist'].shift(1)
    vol_ok = df['rvol'] > 0.8
    return (rsi_bounce | stoch_bounce) & bull_candle & macd_turning & vol_ok


# ============================================================================
# STRATEGY REGISTRY
# ============================================================================

STRATEGIES = {
    # LONG strategies
    'RSI Divergence (Long)': {
        'fn': strat_rsi_divergence_long,
        'direction': 'LONG',
        'tier': 'A+',
        'historical_pf': 1.40,
        'historical_wr': 59.3,
        'description': 'Fresh pivot bull divergence with volume confirmation',
    },
    'Trend Pullback (Long)': {
        'fn': strat_trend_pullback_long,
        'direction': 'LONG',
        'tier': 'A+',
        'historical_pf': 1.74,
        'historical_wr': 51.1,
        'description': 'RSI dip bounce in confirmed bullish trend context',
    },
    'Mean Reversion (Long)': {
        'fn': strat_mean_reversion_long,
        'direction': 'LONG',
        'tier': 'A+',
        'historical_pf': 1.75,
        'historical_wr': 47.6,
        'description': 'Extreme band deviation reversion to mean in ranges',
    },
    'EMA Golden Cross (Long)': {
        'fn': strat_ema_cross_long,
        'direction': 'LONG',
        'tier': 'A',
        'historical_pf': 1.56,
        'historical_wr': 48.3,
        'description': 'Fast EMA 8 crossing above EMA 21 in macro bull trend',
    },
    'Supertrend Regime (Long)': {
        'fn': strat_supertrend_regime_long,
        'direction': 'LONG',
        'tier': 'A',
        'historical_pf': 1.50,
        'historical_wr': 48.2,
        'description': 'Supertrend bullish flip with ADX trend confirmation',
    },
    'Squeeze Breakout (Long)': {
        'fn': strat_squeeze_breakout_long,
        'direction': 'LONG',
        'tier': 'A',
        'historical_pf': 1.29,
        'historical_wr': 45.5,
        'description': 'TTM Squeeze volatility expansion with bullish volume spike',
    },
    'Breakout Retest (Long)': {
        'fn': strat_breakout_retest_long,
        'direction': 'LONG',
        'tier': 'B+',
        'historical_pf': 1.28,
        'historical_wr': 44.7,
        'description': 'Pullback and absorption test of prior resistance',
    },
    'VWAP Reversion (Long)': {
        'fn': strat_vwap_reversion_long,
        'direction': 'LONG',
        'tier': 'B+',
        'historical_pf': 1.35,
        'historical_wr': 47.7,
        'description': 'Oversold stretch below volume-weighted average price',
    },
    'Volume Breakout (Long)': {
        'fn': strat_volume_breakout_long,
        'direction': 'LONG',
        'tier': 'B',
        'historical_pf': 1.23,
        'historical_wr': 39.4,
        'description': 'Surge above 20-period high supported by 2x+ volume',
    },
    'Taker Pressure (Long)': {
        'fn': strat_taker_pressure_long,
        'direction': 'LONG',
        'tier': 'B',
        'historical_pf': 1.07,
        'historical_wr': 50.0,
        'description': 'Aggressive order-flow buyer dominance with momentum',
    },
    'Oversold Dip Bounce (Long)': {
        'fn': strat_oversold_bounce_long,
        'direction': 'LONG',
        'tier': 'B',
        'historical_pf': 1.04,
        'historical_wr': 41.5,
        'description': 'Relief bounce from extreme oversold conditions',
    },
    'Momentum Continuation (Long)': {
        'fn': strat_momentum_continuation_long,
        'direction': 'LONG',
        'tier': 'C',
        'historical_pf': 0.91,
        'historical_wr': 37.6,
        'description': 'StochRSI recycle in trending direction (Best on 4H)',
    },
    # SHORT strategies
    'RSI Divergence (Short)': {
        'fn': strat_rsi_divergence_short,
        'direction': 'SHORT',
        'tier': 'A (4H) / C (1H)',
        'historical_pf': 1.99,
        'historical_wr': 52.4,
        'description': 'Price higher high + RSI lower high (Exceptional on 4H swing tops)',
    },
    'Breakout Retest (Short)': {
        'fn': strat_breakout_retest_short,
        'direction': 'SHORT',
        'tier': 'B',
        'historical_pf': 1.13,
        'historical_wr': 36.7,
        'description': 'Breakdown retest under confirmed bear breakdown',
    },
    'Momentum Continuation (Short)': {
        'fn': strat_momentum_continuation_short,
        'direction': 'SHORT',
        'tier': 'C',
        'historical_pf': 0.89,
        'historical_wr': 36.8,
        'description': 'StochRSI rollover in confirmed bear market',
    },
    'VWAP Reversion (Short)': {
        'fn': strat_vwap_reversion_short,
        'direction': 'SHORT',
        'tier': 'C',
        'historical_pf': 0.87,
        'historical_wr': 41.4,
        'description': 'Overbought stretch above VWMA in downtrends',
    },
    'Squeeze Breakout (Short)': {
        'fn': strat_squeeze_breakout_short,
        'direction': 'SHORT',
        'tier': 'C',
        'historical_pf': 0.85,
        'historical_wr': 31.9,
        'description': 'TTM Squeeze downward breakdown in bear market',
    },
    'Trend Pullback (Short)': {
        'fn': strat_trend_pullback_short,
        'direction': 'SHORT',
        'tier': 'C',
        'historical_pf': 0.66,
        'historical_wr': 41.9,
        'description': 'RSI rally roll-over in confirmed bear market',
    },
    'Taker Pressure (Short)': {
        'fn': strat_taker_pressure_short,
        'direction': 'SHORT',
        'tier': 'C',
        'historical_pf': 0.64,
        'historical_wr': 38.6,
        'description': 'Aggressive seller dominance in order flow',
    },
    'Supertrend Regime (Short)': {
        'fn': strat_supertrend_regime_short,
        'direction': 'SHORT',
        'tier': 'C',
        'historical_pf': 0.47,
        'historical_wr': 22.8,
        'description': 'Supertrend bearish flip in macro bear market',
    },
}

