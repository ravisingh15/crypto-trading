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
    """Trend Pullback Buy: Buy RSI dips in confirmed bull trends with active bounce.
    
    Confluence:
    1. REGIME: Bull trend (price > 50 EMA, or 21 > 50 EMA, or price > 200 EMA) with ADX >= 18
    2. STRUCTURE: EMA 8 > EMA 21 (short-term trend intact)
    3. TRIGGER: RSI pulls back to 38-48 and actively bounces (was < 48, now >= 42 and < 68, RSI ticking up or close > open)
    4. CONFIRM: RVOL > 0.95
    """
    regime_ok = ((df['close'] > df['ema_50']) | (df['ema_21'] > df['ema_50']) | (df['close'] > df['ema_200'])) & (df['adx'] >= 18)
    structure = df['ema_8'] > df['ema_21']
    bounce = (df['rsi'] > df['rsi'].shift(1)) | (df['close'] > df['open'])
    trigger = (df['rsi'].shift(1) < 48) & (df['rsi'] >= 42) & (df['rsi'] < 68) & bounce
    confirm = df['rvol'] > 0.95
    return regime_ok & structure & trigger & confirm


def strat_trend_pullback_short(df: pd.DataFrame) -> pd.Series:
    """Trend Pullback Short: Short RSI rallies in confirmed bear trends with active rollover.
    
    Confluence:
    1. REGIME: Macro bear trend (price < 200 EMA AND 50 < 200 EMA) with ADX >= 18
    2. STRUCTURE: EMA 8 < EMA 21 (short-term downtrend intact)
    3. TRIGGER: RSI rallies to 52-62 and actively rolls over (was > 52, now <= 58 and > 32, RSI ticking down or close < open)
    4. CONFIRM: RVOL > 0.95
    """
    regime_ok = (df['close'] < df['ema_200']) & (df['ema_50'] < df['ema_200']) & (df['adx'] >= 18)
    structure = df['ema_8'] < df['ema_21']
    rollover = (df['rsi'] < df['rsi'].shift(1)) | (df['close'] < df['open'])
    trigger = (df['rsi'].shift(1) > 52) & (df['rsi'] <= 58) & (df['rsi'] > 32) & rollover
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


def strat_volume_breakout_short(df: pd.DataFrame) -> pd.Series:
    """Volume Breakdown Short: High-conviction bearish momentum thrust with volume.
    
    Confluence:
    1. REGIME: Bearish structure (Close < 50 EMA or 8 < 21 EMA or Close < 200 EMA)
    2. STRUCTURE: EMA stack aligned (8 < 21)
    3. TRIGGER: MACD histogram crosses negative
    4. CONFIRM: Volume surge (RVOL > 1.2)
    """
    bear_bias = (df['close'] < df['ema_50']) | (df['ema_8'] < df['ema_21']) | (df['close'] < df['ema_200'])
    structure = df['ema_8'] < df['ema_21']
    trigger = (df['macd_hist'].shift(1) >= 0) & (df['macd_hist'] < 0)
    vol_confirm = df['rvol'] > 1.2
    return bear_bias & structure & trigger & vol_confirm


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
    """Mean Reversion Long: Buy extreme dips with confirmation bounce in range markets.
    
    Confluence:
    1. REGIME: Consolidating or dip range (ADX < 30)
    2. STRUCTURE: Low or Close pierced lower Bollinger Band
    3. TRIGGER: RSI < 38 AND StochRSI K < 25
    4. CONFIRM: Confirmation bounce candle (Close >= Open or RSI ticked up) + RVOL > 0.8
    """
    range_ok = df['adx'] < 30
    structure = (df['low'] < df['bb_lower']) | (df['close'] < df['bb_lower'])
    trigger = (df['rsi'] < 38) & (df['stoch_k'] < 25)
    bounce_confirm = (df['close'] >= df['open']) | (df['rsi'] > df['rsi'].shift(1))
    vol_confirm = df['rvol'] > 0.8
    return range_ok & structure & trigger & bounce_confirm & vol_confirm


def strat_mean_reversion_short(df: pd.DataFrame) -> pd.Series:
    """Mean Reversion Short: Short extreme rallies with confirmation rollover in range markets.
    
    Confluence:
    1. REGIME: Consolidating or range environment (ADX < 30)
    2. STRUCTURE: High or Close pierced upper Bollinger Band
    3. TRIGGER: RSI > 62 AND StochRSI K > 75
    4. CONFIRM: Bearish rollover candle (Close <= Open or RSI ticked down) + RVOL > 0.8
    """
    range_ok = df['adx'] < 30
    structure = (df['high'] > df['bb_upper']) | (df['close'] > df['bb_upper'])
    trigger = (df['rsi'] > 62) & (df['stoch_k'] > 75)
    rollover_confirm = (df['close'] <= df['open']) | (df['rsi'] < df['rsi'].shift(1))
    vol_confirm = df['rvol'] > 0.8
    return range_ok & structure & trigger & rollover_confirm & vol_confirm


def strat_taker_pressure_long(df: pd.DataFrame) -> pd.Series:
    """Taker Volume Pressure Long: Institutional buying pressure at support.
    
    Confluence:
    1. DATA CHECK: Valid taker volume data exists
    2. REGIME: At support zone or pullback (Close < BB middle or RSI < 50)
    3. TRIGGER: Taker buy ratio > 0.58 (strong buyer dominance)
    4. CONFIRM: RVOL > 1.05 (active volume)
    """
    has_taker_data = (df['taker_buy_base_asset_volume'] > 0) if 'taker_buy_base_asset_volume' in df.columns else pd.Series(False, index=df.index)
    at_support = (df['close'] < df['bb_middle']) | (df['rsi'] < 50) | (df['close'] < df['ema_21'])
    taker_pressure = df['taker_buy_ratio'] > 0.58
    vol_confirm = df['rvol'] > 1.05
    return has_taker_data & at_support & taker_pressure & vol_confirm


def strat_taker_pressure_short(df: pd.DataFrame) -> pd.Series:
    """Taker Volume Pressure Short: Institutional selling pressure at resistance.
    
    Confluence:
    1. DATA CHECK: Valid taker volume data exists (> 0)
    2. REGIME: At resistance zone or rally (Close > BB middle or RSI > 50)
    3. TRIGGER: Taker buy ratio < 0.42 (strong seller dominance)
    4. CONFIRM: RVOL > 1.05
    """
    has_taker_data = (df['taker_buy_base_asset_volume'] > 0) if 'taker_buy_base_asset_volume' in df.columns else pd.Series(False, index=df.index)
    at_resistance = (df['close'] > df['bb_middle']) | (df['rsi'] > 50) | (df['close'] > df['ema_21'])
    taker_pressure = (df['taker_buy_ratio'] < 0.42) & (df['taker_buy_ratio'] > 0.0)
    vol_confirm = df['rvol'] > 1.05
    return has_taker_data & at_resistance & taker_pressure & vol_confirm


def strat_vwap_reversion_long(df: pd.DataFrame) -> pd.Series:
    """VWAP Reversion Long: Buy oversold dips extended below VWMA in range markets.
    
    Confluence:
    1. REGIME: Range-bound or non-runaway market (ADX < 28)
    2. STRUCTURE: Price extended below VWMA-21 by more than 1.5 ATR (true deviation)
    3. TRIGGER: RSI < 35 with confirmation bounce candle (Close > Open and RSI ticking up)
    4. CONFIRM: RVOL > 0.9
    """
    range_ok = df['adx'] < 28
    extended = (df['vwma_21'] - df['close']) > (1.5 * df['atr'])
    trigger = (df['rsi'] < 35) & (df['close'] > df['open']) & (df['rsi'] > df['rsi'].shift(1))
    confirm = df['rvol'] > 0.9
    return range_ok & extended & trigger & confirm


def strat_vwap_reversion_short(df: pd.DataFrame) -> pd.Series:
    """VWAP Reversion Short: Short overbought rallies extended above VWMA in range markets.
    
    Confluence:
    1. REGIME: Range-bound or non-runaway market (ADX < 28)
    2. STRUCTURE: Price extended above VWMA-21 by more than 1.5 ATR
    3. TRIGGER: RSI > 65 with confirmation rollover candle (Close < Open and RSI ticking down)
    4. CONFIRM: RVOL > 0.9
    """
    range_ok = df['adx'] < 28
    extended = (df['close'] - df['vwma_21']) > (1.5 * df['atr'])
    trigger = (df['rsi'] > 65) & (df['close'] < df['open']) & (df['rsi'] < df['rsi'].shift(1))
    confirm = df['rvol'] > 0.9
    return range_ok & extended & trigger & confirm


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


def strat_ema_cross_short(df: pd.DataFrame) -> pd.Series:
    """EMA Bearish Death Cross: Fast EMA crosses below Slow EMA with momentum.
    
    Confluence:
    1. REGIME: Bear bias (Price < 50 EMA or Price < 200 EMA)
    2. TRIGGER: EMA 8 crosses below EMA 21
    3. STRUCTURE: MACD Histogram is negative or deteriorating
    4. CONFIRM: RSI between 32-58 + RVOL > 1.0
    """
    bear_bias = (df['close'] < df['ema_50']) | (df['close'] < df['ema_200'])
    cross = (df['ema_8'].shift(1) >= df['ema_21'].shift(1)) & (df['ema_8'] < df['ema_21'])
    macd_decaying = df['macd_hist'] <= df['macd_hist'].shift(1)
    rsi_ok = (df['rsi'] >= 32) & (df['rsi'] <= 58)
    vol_ok = df['rvol'] > 1.0
    return bear_bias & cross & macd_decaying & rsi_ok & vol_ok


def strat_oversold_bounce_long(df: pd.DataFrame) -> pd.Series:
    """Oversold Dip Bounce: Catches high-probability relief bounces from extreme selling.
    
    Confluence:
    1. REGIME: Bull market dip or range (Price > 200 EMA or 50 > 200 EMA) to avoid bear knife-catching
    2. STRUCTURE: RSI was oversold (< 35) and crosses back above 35 OR StochRSI crosses from < 25
    3. TRIGGER: Bullish candle (Close > Open)
    4. CONFIRM: MACD histogram ticking up (selling momentum abating) + RVOL > 0.8
    """
    regime_ok = (df['close'] > df['ema_200']) | (df['ema_50'] > df['ema_200'])
    rsi_bounce = (df['rsi'].shift(1) < 35) & (df['rsi'] >= 35)
    stoch_bounce = (
        (df['stoch_k'].shift(1) <= df['stoch_d'].shift(1)) & 
        (df['stoch_k'] > df['stoch_d']) & 
        (df['stoch_k'].shift(1) < 25)
    )
    bull_candle = df['close'] > df['open']
    macd_turning = df['macd_hist'] > df['macd_hist'].shift(1)
    vol_ok = df['rvol'] > 0.8
    return regime_ok & (rsi_bounce | stoch_bounce) & bull_candle & macd_turning & vol_ok


# ============================================================================
# STRATEGY REGISTRY
# ============================================================================

STRATEGIES = {
    # LONG strategies
    'RSI Divergence (Long)': {
        'fn': strat_rsi_divergence_long,
        'direction': 'LONG',
        'type': 'MEAN_REVERSION',
        'preferred_timeframe': '4h',
        'tier': 'A+',
        'historical_pf': 1.55,
        'historical_wr': 51.7,
        'description': 'Fresh pivot bull divergence with volume confirmation (Best on 4H)',
    },
    'Trend Pullback (Long)': {
        'fn': strat_trend_pullback_long,
        'direction': 'LONG',
        'type': 'TREND',
        'preferred_timeframe': '1h',
        'tier': 'A+',
        'historical_pf': 1.26,
        'historical_wr': 41.4,
        'description': 'RSI dip bounce in confirmed bullish trend context',
    },
    'Mean Reversion (Long)': {
        'fn': strat_mean_reversion_long,
        'direction': 'LONG',
        'type': 'MEAN_REVERSION',
        'preferred_timeframe': '1h',
        'tier': 'A+',
        'historical_pf': 1.14,
        'historical_wr': 43.1,
        'description': 'Extreme band deviation reversion to mean in ranges',
    },
    'EMA Golden Cross (Long)': {
        'fn': strat_ema_cross_long,
        'direction': 'LONG',
        'type': 'TREND',
        'preferred_timeframe': '4h',
        'tier': 'A',
        'historical_pf': 1.33,
        'historical_wr': 42.4,
        'description': 'Fast EMA 8 crossing above EMA 21 in macro bull trend (Best on 4H)',
    },
    'Supertrend Regime (Long)': {
        'fn': strat_supertrend_regime_long,
        'direction': 'LONG',
        'type': 'TREND',
        'preferred_timeframe': '1h',
        'tier': 'A',
        'historical_pf': 1.03,
        'historical_wr': 41.3,
        'description': 'Supertrend bullish flip with ADX trend confirmation',
    },
    'Squeeze Breakout (Long)': {
        'fn': strat_squeeze_breakout_long,
        'direction': 'LONG',
        'type': 'BREAKOUT',
        'preferred_timeframe': '1h',
        'tier': 'A',
        'historical_pf': 1.09,
        'historical_wr': 40.3,
        'description': 'TTM Squeeze volatility expansion with bullish volume spike',
    },
    'Breakout Retest (Long)': {
        'fn': strat_breakout_retest_long,
        'direction': 'LONG',
        'type': 'BREAKOUT',
        'preferred_timeframe': '1h',
        'tier': 'A+',
        'historical_pf': 1.19,
        'historical_wr': 43.0,
        'description': 'Pullback and absorption test of prior resistance (Top 1H performer)',
    },
    'VWAP Reversion (Long)': {
        'fn': strat_vwap_reversion_long,
        'direction': 'LONG',
        'type': 'MEAN_REVERSION',
        'preferred_timeframe': '1h',
        'tier': 'A',
        'historical_pf': 1.13,
        'historical_wr': 48.0,
        'description': 'Extreme 1.5 ATR stretch below VWMA with confirmation bounce in ranges',
    },
    'Volume Breakout (Long)': {
        'fn': strat_volume_breakout_long,
        'direction': 'LONG',
        'type': 'BREAKOUT',
        'preferred_timeframe': '1h',
        'tier': 'B',
        'historical_pf': 0.92,
        'historical_wr': 36.5,
        'description': 'Bullish momentum thrust supported by volume surge',
    },
    'Taker Pressure (Long)': {
        'fn': strat_taker_pressure_long,
        'direction': 'LONG',
        'type': 'ORDER_FLOW',
        'preferred_timeframe': '1h',
        'tier': 'B',
        'historical_pf': 0.85,
        'historical_wr': 42.8,
        'description': 'Aggressive order-flow buyer dominance with momentum',
    },
    'Oversold Dip Bounce (Long)': {
        'fn': strat_oversold_bounce_long,
        'direction': 'LONG',
        'type': 'MEAN_REVERSION',
        'preferred_timeframe': '1h',
        'tier': 'B',
        'historical_pf': 0.86,
        'historical_wr': 35.9,
        'description': 'Relief bounce from extreme oversold conditions in non-bear markets',
    },
    'Momentum Continuation (Long)': {
        'fn': strat_momentum_continuation_long,
        'direction': 'LONG',
        'type': 'TREND',
        'preferred_timeframe': '4h',
        'tier': 'A+ (4H)',
        'historical_pf': 1.57,
        'historical_wr': 52.1,
        'description': 'StochRSI recycle in trending direction (Exceptional on 4H)',
    },
    # SHORT strategies
    'RSI Divergence (Short)': {
        'fn': strat_rsi_divergence_short,
        'direction': 'SHORT',
        'type': 'MEAN_REVERSION',
        'preferred_timeframe': '4h',
        'tier': 'A+ (4H)',
        'historical_pf': 1.85,
        'historical_wr': 47.6,
        'description': 'Price higher high + RSI lower high (Exceptional on 4H swing tops)',
    },
    'Breakout Retest (Short)': {
        'fn': strat_breakout_retest_short,
        'direction': 'SHORT',
        'type': 'BREAKOUT',
        'preferred_timeframe': '1h',
        'tier': 'A',
        'historical_pf': 1.11,
        'historical_wr': 38.8,
        'description': 'Breakdown retest under confirmed bear breakdown',
    },
    'Mean Reversion (Short)': {
        'fn': strat_mean_reversion_short,
        'direction': 'SHORT',
        'type': 'MEAN_REVERSION',
        'preferred_timeframe': '1h',
        'tier': 'A',
        'historical_pf': 1.12,
        'historical_wr': 43.0,
        'description': 'Extreme upper band deviation rollover to mean in ranges',
    },
    'Momentum Continuation (Short)': {
        'fn': strat_momentum_continuation_short,
        'direction': 'SHORT',
        'type': 'TREND',
        'preferred_timeframe': '4h',
        'tier': 'C',
        'historical_pf': 0.78,
        'historical_wr': 35.7,
        'description': 'StochRSI rollover in confirmed bear market',
    },
    'VWAP Reversion (Short)': {
        'fn': strat_vwap_reversion_short,
        'direction': 'SHORT',
        'type': 'MEAN_REVERSION',
        'preferred_timeframe': '4h',
        'tier': 'A (4H)',
        'historical_pf': 1.22,
        'historical_wr': 41.7,
        'description': 'Extreme 1.5 ATR stretch above VWMA with rollover in ranges',
    },
    'Squeeze Breakout (Short)': {
        'fn': strat_squeeze_breakout_short,
        'direction': 'SHORT',
        'type': 'BREAKOUT',
        'preferred_timeframe': '4h',
        'tier': 'A (4H) / B (1H)',
        'historical_pf': 1.37,
        'historical_wr': 50.0,
        'description': 'TTM Squeeze downward breakdown in bear market',
    },
    'Trend Pullback (Short)': {
        'fn': strat_trend_pullback_short,
        'direction': 'SHORT',
        'type': 'TREND',
        'preferred_timeframe': '4h',
        'tier': 'B (4H)',
        'historical_pf': 1.05,
        'historical_wr': 46.2,
        'description': 'RSI rally rollover in confirmed bear market',
    },
    'Taker Pressure (Short)': {
        'fn': strat_taker_pressure_short,
        'direction': 'SHORT',
        'type': 'ORDER_FLOW',
        'preferred_timeframe': '1h',
        'tier': 'B',
        'historical_pf': 0.86,
        'historical_wr': 38.4,
        'description': 'Aggressive seller dominance in order flow with valid taker data',
    },
    'Supertrend Regime (Short)': {
        'fn': strat_supertrend_regime_short,
        'direction': 'SHORT',
        'type': 'TREND',
        'preferred_timeframe': '4h',
        'tier': 'A (4H)',
        'historical_pf': 1.48,
        'historical_wr': 50.0,
        'description': 'Supertrend bearish flip in macro bear market (Exceptional on 4H)',
    },
    'EMA Death Cross (Short)': {
        'fn': strat_ema_cross_short,
        'direction': 'SHORT',
        'type': 'TREND',
        'preferred_timeframe': '4h',
        'tier': 'B',
        'historical_pf': 0.87,
        'historical_wr': 37.3,
        'description': 'Fast EMA 8 crossing below EMA 21 in macro bear trend',
    },
    'Volume Breakout (Short)': {
        'fn': strat_volume_breakout_short,
        'direction': 'SHORT',
        'type': 'BREAKOUT',
        'preferred_timeframe': '1h',
        'tier': 'B',
        'historical_pf': 0.83,
        'historical_wr': 35.9,
        'description': 'Bearish momentum breakdown supported by volume surge',
    },
}


# ============================================================================
# EMPIRICAL PERFORMANCE REGISTRY
# ============================================================================
# Six-month walk-forward results on the 8 liquid pairs used by run_backtest.py.
# Assumptions: 2.0x ATR stop, 3.5x ATR target (1:1.75 R:R), 48-bar max hold,
# 0.075% taker fee + 0.03% slippage per side (0.21% round-trip), no overlapping
# trades per symbol. Metrics are used to rank live signals by *actual* edge
# instead of treating every strategy as equally trustworthy.
#
# avg_trade_pct is the net average return per trade after friction. It is the
# primary metric for choosing a strategy's best timeframe because it directly
# measures expectancy, while profit factor measures payoff asymmetry.
STRATEGY_PERFORMANCE = {
    'RSI Divergence (Long)': {
        '1h': {'pf': 0.813, 'wr': 41.4, 'trades': 104, 'avg_trade_pct': -0.239, 'return_pct': -5.6, 'max_dd_pct': -15.5, 'sharpe': -1.89},
        '4h': {'pf': 1.554, 'wr': 51.7, 'trades': 29, 'avg_trade_pct': 1.117, 'return_pct': 8.5, 'max_dd_pct': -6.5, 'sharpe': 4.17},
    },
    'Trend Pullback (Long)': {
        '1h': {'pf': 1.265, 'wr': 41.2, 'trades': 97, 'avg_trade_pct': 0.274, 'return_pct': -0.6, 'max_dd_pct': -17.5, 'sharpe': 1.93},
        '4h': {'pf': 0.949, 'wr': 45.5, 'trades': 22, 'avg_trade_pct': -0.136, 'return_pct': 2.6, 'max_dd_pct': -5.7, 'sharpe': -0.45},
    },
    'Mean Reversion (Long)': {
        '1h': {'pf': 0.902, 'wr': 42.6, 'trades': 223, 'avg_trade_pct': -0.110, 'return_pct': -13.0, 'max_dd_pct': -21.7, 'sharpe': -0.93},
        '4h': {'pf': 1.160, 'wr': 43.5, 'trades': 46, 'avg_trade_pct': 0.299, 'return_pct': 3.9, 'max_dd_pct': -14.3, 'sharpe': 1.43},
    },
    'EMA Golden Cross (Long)': {
        '1h': {'pf': 1.000, 'wr': 36.9, 'trades': 344, 'avg_trade_pct': -0.000, 'return_pct': -36.3, 'max_dd_pct': -56.5, 'sharpe': -0.00},
        '4h': {'pf': 1.334, 'wr': 42.4, 'trades': 92, 'avg_trade_pct': 0.623, 'return_pct': 10.0, 'max_dd_pct': -12.7, 'sharpe': 2.91},
    },
    'Supertrend Regime (Long)': {
        '1h': {'pf': 1.023, 'wr': 42.0, 'trades': 312, 'avg_trade_pct': 0.025, 'return_pct': -11.6, 'max_dd_pct': -36.8, 'sharpe': 0.21},
        '4h': {'pf': 1.027, 'wr': 35.4, 'trades': 65, 'avg_trade_pct': 0.051, 'return_pct': -3.4, 'max_dd_pct': -14.1, 'sharpe': 0.28},
    },
    'Squeeze Breakout (Long)': {
        '1h': {'pf': 1.101, 'wr': 41.3, 'trades': 293, 'avg_trade_pct': 0.110, 'return_pct': -2.0, 'max_dd_pct': -25.8, 'sharpe': 0.93},
        '4h': {'pf': 0.788, 'wr': 36.2, 'trades': 69, 'avg_trade_pct': -0.468, 'return_pct': -6.1, 'max_dd_pct': -13.0, 'sharpe': -2.89},
    },
    'Breakout Retest (Long)': {
        '1h': {'pf': 1.205, 'wr': 43.8, 'trades': 329, 'avg_trade_pct': 0.212, 'return_pct': 13.8, 'max_dd_pct': -29.3, 'sharpe': 1.67},
        '4h': {'pf': 0.511, 'wr': 24.6, 'trades': 69, 'avg_trade_pct': -1.343, 'return_pct': -22.1, 'max_dd_pct': -23.8, 'sharpe': -6.53},
    },
    'VWAP Reversion (Long)': {
        '1h': {'pf': 1.131, 'wr': 48.0, 'trades': 102, 'avg_trade_pct': 0.139, 'return_pct': 8.6, 'max_dd_pct': -10.5, 'sharpe': 1.06},
        '4h': {'pf': 1.167, 'wr': 50.0, 'trades': 16, 'avg_trade_pct': 0.288, 'return_pct': 1.3, 'max_dd_pct': -4.6, 'sharpe': 1.38},
    },
    'Volume Breakout (Long)': {
        '1h': {'pf': 0.937, 'wr': 37.3, 'trades': 225, 'avg_trade_pct': -0.073, 'return_pct': -27.1, 'max_dd_pct': -36.6, 'sharpe': -0.64},
        '4h': {'pf': 0.799, 'wr': 35.2, 'trades': 54, 'avg_trade_pct': -0.558, 'return_pct': -5.1, 'max_dd_pct': -6.9, 'sharpe': -2.66},
    },
    'Taker Pressure (Long)': {
        '1h': {'pf': 0.877, 'wr': 43.9, 'trades': 346, 'avg_trade_pct': -0.135, 'return_pct': 0.4, 'max_dd_pct': -29.2, 'sharpe': -1.25},
        '4h': {'pf': 0.647, 'wr': 25.6, 'trades': 43, 'avg_trade_pct': -0.916, 'return_pct': -15.7, 'max_dd_pct': -15.1, 'sharpe': -4.18},
    },
    'Oversold Dip Bounce (Long)': {
        '1h': {'pf': 0.849, 'wr': 35.5, 'trades': 392, 'avg_trade_pct': -0.196, 'return_pct': -49.0, 'max_dd_pct': -56.9, 'sharpe': -1.58},
        '4h': {'pf': 1.615, 'wr': 50.0, 'trades': 102, 'avg_trade_pct': 1.048, 'return_pct': 24.6, 'max_dd_pct': -17.0, 'sharpe': 4.08},
    },
    'Momentum Continuation (Long)': {
        '1h': {'pf': 0.877, 'wr': 37.6, 'trades': 351, 'avg_trade_pct': -0.164, 'return_pct': -34.5, 'max_dd_pct': -47.5, 'sharpe': -1.21},
        '4h': {'pf': 1.567, 'wr': 52.1, 'trades': 96, 'avg_trade_pct': 1.063, 'return_pct': 26.7, 'max_dd_pct': -18.7, 'sharpe': 4.00},
    },
    'RSI Divergence (Short)': {
        '1h': {'pf': 0.784, 'wr': 37.6, 'trades': 125, 'avg_trade_pct': -0.268, 'return_pct': -15.2, 'max_dd_pct': -20.7, 'sharpe': -2.30},
        '4h': {'pf': 1.852, 'wr': 47.6, 'trades': 21, 'avg_trade_pct': 1.364, 'return_pct': 3.4, 'max_dd_pct': -4.2, 'sharpe': 6.13},
    },
    'Breakout Retest (Short)': {
        '1h': {'pf': 1.091, 'wr': 38.5, 'trades': 260, 'avg_trade_pct': 0.104, 'return_pct': -15.3, 'max_dd_pct': -48.4, 'sharpe': 0.81},
        '4h': {'pf': 0.786, 'wr': 32.6, 'trades': 46, 'avg_trade_pct': -0.496, 'return_pct': -7.0, 'max_dd_pct': -11.1, 'sharpe': -2.05},
    },
    'Mean Reversion (Short)': {
        '1h': {'pf': 1.101, 'wr': 42.2, 'trades': 204, 'avg_trade_pct': 0.114, 'return_pct': 8.4, 'max_dd_pct': -18.6, 'sharpe': 0.91},
        '4h': {'pf': 1.125, 'wr': 34.0, 'trades': 47, 'avg_trade_pct': 0.255, 'return_pct': -6.2, 'max_dd_pct': -14.7, 'sharpe': 1.13},
    },
    'Momentum Continuation (Short)': {
        '1h': {'pf': 0.772, 'wr': 35.4, 'trades': 322, 'avg_trade_pct': -0.286, 'return_pct': -37.0, 'max_dd_pct': -53.5, 'sharpe': -2.57},
        '4h': {'pf': 0.331, 'wr': 24.4, 'trades': 41, 'avg_trade_pct': -2.097, 'return_pct': -15.0, 'max_dd_pct': -21.0, 'sharpe': -10.05},
    },
    'VWAP Reversion (Short)': {
        '1h': {'pf': 0.960, 'wr': 38.5, 'trades': 96, 'avg_trade_pct': -0.046, 'return_pct': -3.2, 'max_dd_pct': -16.0, 'sharpe': -0.41},
        '4h': {'pf': 1.223, 'wr': 41.7, 'trades': 24, 'avg_trade_pct': 0.432, 'return_pct': 1.9, 'max_dd_pct': -7.0, 'sharpe': 2.08},
    },
    'Squeeze Breakout (Short)': {
        '1h': {'pf': 1.055, 'wr': 39.0, 'trades': 164, 'avg_trade_pct': 0.049, 'return_pct': -11.7, 'max_dd_pct': -38.1, 'sharpe': 0.54},
        '4h': {'pf': 1.370, 'wr': 50.0, 'trades': 30, 'avg_trade_pct': 0.597, 'return_pct': 8.2, 'max_dd_pct': -10.2, 'sharpe': 4.04},
    },
    'Trend Pullback (Short)': {
        '1h': {'pf': 0.479, 'wr': 35.8, 'trades': 67, 'avg_trade_pct': -0.596, 'return_pct': -13.0, 'max_dd_pct': -17.2, 'sharpe': -7.60},
        '4h': {'pf': 1.053, 'wr': 46.1, 'trades': 13, 'avg_trade_pct': 0.093, 'return_pct': 1.4, 'max_dd_pct': -3.4, 'sharpe': 0.43},
    },
    'Taker Pressure (Short)': {
        '1h': {'pf': 0.860, 'wr': 38.7, 'trades': 455, 'avg_trade_pct': -0.142, 'return_pct': -37.0, 'max_dd_pct': -42.0, 'sharpe': -1.46},
        '4h': {'pf': 0.981, 'wr': 42.6, 'trades': 61, 'avg_trade_pct': -0.034, 'return_pct': -1.1, 'max_dd_pct': -7.5, 'sharpe': -0.18},
    },
    'Supertrend Regime (Short)': {
        '1h': {'pf': 0.896, 'wr': 33.9, 'trades': 118, 'avg_trade_pct': -0.104, 'return_pct': -18.3, 'max_dd_pct': -31.3, 'sharpe': -1.29},
        '4h': {'pf': 1.478, 'wr': 50.0, 'trades': 26, 'avg_trade_pct': 0.809, 'return_pct': 7.6, 'max_dd_pct': -5.7, 'sharpe': 3.20},
    },
    'EMA Death Cross (Short)': {
        '1h': {'pf': 0.867, 'wr': 37.5, 'trades': 323, 'avg_trade_pct': -0.142, 'return_pct': -29.3, 'max_dd_pct': -42.0, 'sharpe': -1.38},
        '4h': {'pf': 0.805, 'wr': 38.0, 'trades': 92, 'avg_trade_pct': -0.437, 'return_pct': -10.5, 'max_dd_pct': -21.5, 'sharpe': -1.94},
    },
    'Volume Breakout (Short)': {
        '1h': {'pf': 0.762, 'wr': 33.6, 'trades': 229, 'avg_trade_pct': -0.292, 'return_pct': -37.3, 'max_dd_pct': -52.0, 'sharpe': -3.20},
        '4h': {'pf': 0.834, 'wr': 35.9, 'trades': 64, 'avg_trade_pct': -0.329, 'return_pct': -5.5, 'max_dd_pct': -22.3, 'sharpe': -1.93},
    },
}


def tier_from_performance(pf: float, trades: int) -> str:
    """Map empirical profit factor + sample size to a transparent tier."""
    if trades < 10:
        return 'C'
    if pf >= 1.40 and trades >= 20:
        return 'A+'
    if pf >= 1.15:
        return 'A'
    if pf >= 1.05:
        return 'B+'
    if pf >= 0.95:
        return 'B'
    return 'C'


def _best_timeframe(performance: dict) -> str:
    available = {tf: m for tf, m in performance.items() if m}
    return max(available, key=lambda tf: (available[tf]['avg_trade_pct'], available[tf]['pf']))


def get_strategy_stats(name: str, interval: str = '1h') -> dict:
    """Return empirical stats for a strategy at (or closest to) a timeframe.

    Proxy mapping keeps the UI honest when a user scans 5m/15m/1d, where we do
    not yet have a statistically useful sample. The returned dict includes
    ``is_proxy`` so callers can discount the result.
    """
    info = STRATEGIES.get(name, {})
    performance = info.get('performance') or STRATEGY_PERFORMANCE.get(name, {})
    if not performance:
        return {
            'pf': 1.0, 'wr': 40.0, 'trades': 0, 'avg_trade_pct': 0.0,
            'return_pct': 0.0, 'max_dd_pct': 0.0, 'sharpe': 0.0,
            'timeframe': interval, 'is_proxy': True, 'best_timeframe': interval,
            'tier': 'C', 'sample_quality': 'LOW',
        }

    interval = str(interval).lower()
    is_proxy = False
    if interval in performance and performance[interval]:
        stats_tf = interval
    else:
        if interval in ('5m', '15m', '30m', '2h', '3h'):
            proxy_tf = '1h'
        elif interval in ('1d', '1w'):
            proxy_tf = '4h'
        else:
            proxy_tf = info.get('best_timeframe') or _best_timeframe(performance)
        stats_tf = proxy_tf if proxy_tf in performance else _best_timeframe(performance)
        is_proxy = True

    stats = dict(performance[stats_tf])
    trades = int(stats.get('trades', 0))
    stats.update({
        'timeframe': stats_tf,
        'is_proxy': is_proxy,
        'best_timeframe': info.get('best_timeframe') or _best_timeframe(performance),
        'tier': tier_from_performance(float(stats.get('pf', 0)), trades),
        'sample_quality': 'LOW' if trades < 20 else 'MEDIUM' if trades < 50 else 'HIGH',
    })
    return stats


def get_mtf_policy(name: str) -> str:
    """Trend/breakout setups require HTF alignment; mean-reversion/order-flow do not."""
    strategy_type = STRATEGIES.get(name, {}).get('type', 'TREND')
    return 'required' if strategy_type in ('TREND', 'BREAKOUT') else 'soft'


def get_strategy_lab_snapshot(interval: str = '1h') -> dict:
    """Serializable strategy registry snapshot for the Strategy Lab UI."""
    rows = []
    for name, info in STRATEGIES.items():
        stats = get_strategy_stats(name, interval)
        rows.append({
            'name': name,
            'direction': info.get('direction', 'LONG'),
            'type': info.get('type', 'TREND'),
            'description': info.get('description', ''),
            'preferred_timeframe': info.get('best_timeframe', info.get('preferred_timeframe', '1h')),
            'best_timeframe': info.get('best_timeframe', info.get('preferred_timeframe', '1h')),
            'mtf_policy': get_mtf_policy(name),
            'performance': info.get('performance', {}),
            'active': {
                'timeframe': stats['timeframe'],
                'is_proxy': stats['is_proxy'],
                'pf': round(float(stats['pf']), 3),
                'wr': round(float(stats['wr']), 1),
                'trades': int(stats['trades']),
                'avg_trade_pct': round(float(stats['avg_trade_pct']), 3),
                'return_pct': round(float(stats['return_pct']), 1),
                'max_dd_pct': round(float(stats['max_dd_pct']), 1),
                'sharpe': round(float(stats['sharpe']), 2),
                'tier': stats['tier'],
                'sample_quality': stats['sample_quality'],
            },
        })

    rows.sort(key=lambda r: (r['active']['pf'], r['active']['avg_trade_pct']), reverse=True)
    profitable = [r for r in rows if r['active']['pf'] > 1.0]
    best = rows[0] if rows else None
    return {
        'interval': interval,
        'summary': {
            'total': len(rows),
            'long': sum(1 for r in rows if r['direction'] == 'LONG'),
            'short': sum(1 for r in rows if r['direction'] == 'SHORT'),
            'profitable': len(profitable),
            'avg_pf': round(sum(r['active']['pf'] for r in rows) / len(rows), 2) if rows else 0,
            'best_strategy': best['name'] if best else None,
            'best_pf': best['active']['pf'] if best else 0,
            'best_timeframe': best['best_timeframe'] if best else None,
        },
        'strategies': rows,
    }


# Enrich the public registry with the empirical view. This keeps a single source
# of truth while preserving backward-compatible fields used by older clients.
for _name, _info in STRATEGIES.items():
    _perf = STRATEGY_PERFORMANCE.get(_name)
    if not _perf:
        continue
    _best_tf = _best_timeframe(_perf)
    _best = _perf[_best_tf]
    _info['performance'] = _perf
    _info['best_timeframe'] = _best_tf
    _info['preferred_timeframe'] = _best_tf
    _info['historical_pf'] = round(float(_best['pf']), 3)
    _info['historical_wr'] = round(float(_best['wr']), 1)
    _info['historical_trades'] = int(_best['trades'])
    _info['tier'] = tier_from_performance(float(_best['pf']), int(_best['trades']))
    _info['sample_quality'] = 'LOW' if _best['trades'] < 20 else 'MEDIUM' if _best['trades'] < 50 else 'HIGH'

