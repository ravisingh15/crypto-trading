import pandas as pd
import numpy as np
from typing import List, Any, Dict

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index (RSI) using Wilder's Exponential Smoothing."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    rs = avg_gain / (avg_loss + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
    """Calculate Moving Average Convergence Divergence (MACD)."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return {
        "macd": macd_line,
        "signal": signal_line,
        "hist": histogram
    }

def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average (EMA)."""
    return series.ewm(span=period, adjust=False).mean()

def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Calculate Simple Moving Average (SMA)."""
    return series.rolling(window=period).mean()

def calculate_bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> Dict[str, pd.Series]:
    """Calculate Bollinger Bands (Middle, Upper, Lower, Bandwidth %)."""
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    bandwidth = ((upper - lower) / sma) * 100
    return {
        "middle": sma,
        "upper": upper,
        "lower": lower,
        "bandwidth": bandwidth
    }

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Average True Range (ATR)."""
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    return atr

def calculate_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Dict[str, pd.Series]:
    """Calculate Average Directional Index (ADX) with +DI and -DI.
    ADX > 25 = strong trend, ADX < 20 = no trend (range-bound).
    +DI > -DI = bullish pressure, -DI > +DI = bearish pressure.
    """
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Directional movement
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    plus_dm = pd.Series(plus_dm, index=close.index)
    minus_dm = pd.Series(minus_dm, index=close.index)

    # Wilder's smoothing (same as ATR)
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, min_periods=period, adjust=False).mean() / (atr + 1e-10))
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, min_periods=period, adjust=False).mean() / (atr + 1e-10))

    # DX and ADX
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10))
    adx = dx.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    return {"adx": adx, "plus_di": plus_di, "minus_di": minus_di}

def calculate_rvol(volume: pd.Series, period: int = 20) -> pd.Series:
    """Calculate Relative Volume (RVOL = current volume / N-period average volume)."""
    avg_vol = volume.rolling(window=period).mean()
    rvol = volume / (avg_vol + 1e-10)
    return rvol

def calculate_stoch_rsi(rsi: pd.Series, period: int = 14, smoothK: int = 3, smoothD: int = 3) -> Dict[str, pd.Series]:
    """Calculate Stochastic RSI."""
    rsi_min = rsi.rolling(window=period).min()
    rsi_max = rsi.rolling(window=period).max()
    stoch_rsi = 100 * (rsi - rsi_min) / (rsi_max - rsi_min + 1e-10)
    k = stoch_rsi.rolling(window=smoothK).mean()
    d = k.rolling(window=smoothD).mean()
    return {"k": k, "d": d}

def calculate_keltner_channels(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20, multiplier: float = 1.5) -> Dict[str, pd.Series]:
    """Calculate Keltner Channels (Middle, Upper, Lower)."""
    ema = calculate_ema(close, period)
    atr = calculate_atr(high, low, close, period)
    upper = ema + (atr * multiplier)
    lower = ema - (atr * multiplier)
    return {"middle": ema, "upper": upper, "lower": lower}

def calculate_vwma(close: pd.Series, volume: pd.Series, period: int = 20) -> pd.Series:
    """Calculate Volume-Weighted Moving Average (VWMA)."""
    pv = close * volume
    vwma = pv.rolling(window=period).sum() / (volume.rolling(window=period).sum() + 1e-10)
    return vwma

def calculate_supertrend(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 10, multiplier: float = 3.0) -> Dict[str, pd.Series]:
    """Calculate Supertrend indicator (trend direction + trailing stop line)."""
    atr = calculate_atr(high, low, close, period)
    hl2 = (high + low) / 2
    
    basic_ub = hl2 + (multiplier * atr)
    basic_lb = hl2 - (multiplier * atr)
    
    n = len(close)
    final_ub = np.zeros(n)
    final_lb = np.zeros(n)
    supertrend = np.zeros(n)
    direction = np.zeros(n)
    
    close_vals = close.values
    basic_ub_vals = basic_ub.values
    basic_lb_vals = basic_lb.values
    
    for i in range(1, n):
        if basic_ub_vals[i] < final_ub[i-1] or close_vals[i-1] > final_ub[i-1]:
            final_ub[i] = basic_ub_vals[i]
        else:
            final_ub[i] = final_ub[i-1]
            
        if basic_lb_vals[i] > final_lb[i-1] or close_vals[i-1] < final_lb[i-1]:
            final_lb[i] = basic_lb_vals[i]
        else:
            final_lb[i] = final_lb[i-1]
            
        if direction[i-1] == 1:
            if close_vals[i] < final_lb[i]:
                direction[i] = -1
                supertrend[i] = final_ub[i]
            else:
                direction[i] = 1
                supertrend[i] = final_lb[i]
        else:
            if close_vals[i] > final_ub[i]:
                direction[i] = 1
                supertrend[i] = final_lb[i]
            else:
                direction[i] = -1
                supertrend[i] = final_ub[i]
                
    return {
        "supertrend": pd.Series(supertrend, index=close.index),
        "direction": pd.Series(direction, index=close.index)
    }

def enrich_klines_dataframe(raw_klines: List[List[Any]]) -> pd.DataFrame:
    """
    Parse raw Binance klines raw array into a structured DataFrame and calculate 
    all technical indicators.
    """
    if not raw_klines or len(raw_klines) == 0:
        return pd.DataFrame()

    columns = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "number_of_trades",
        "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
    ]
    df = pd.DataFrame(raw_klines, columns=columns)
    
    # Cast numerical columns
    for col in ["open", "high", "low", "close", "volume", "quote_asset_volume"]:
        df[col] = df[col].astype(float)
        
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")

    # Compute Indicators
    df["rsi"] = calculate_rsi(df["close"], period=14)
    
    macd_dict = calculate_macd(df["close"])
    df["macd"] = macd_dict["macd"]
    df["macd_signal"] = macd_dict["signal"]
    df["macd_hist"] = macd_dict["hist"]
    
    df["ema_8"] = calculate_ema(df["close"], 8)
    df["ema_9"] = calculate_ema(df["close"], 9)
    df["ema_21"] = calculate_ema(df["close"], 21)
    df["ema_55"] = calculate_ema(df["close"], 55)
    df["ema_50"] = calculate_ema(df["close"], 50)
    df["ema_200"] = calculate_ema(df["close"], 200)
    
    bb = calculate_bollinger_bands(df["close"], period=20, std_dev=2.0)
    df["bb_middle"] = bb["middle"]
    df["bb_upper"] = bb["upper"]
    df["bb_lower"] = bb["lower"]
    df["bb_bandwidth"] = bb["bandwidth"]
    
    df["atr"] = calculate_atr(df["high"], df["low"], df["close"], period=14)
    df["rvol"] = calculate_rvol(df["volume"], period=20)
    
    stoch = calculate_stoch_rsi(df["rsi"], period=14, smoothK=3, smoothD=3)
    df["stoch_k"] = stoch["k"]
    df["stoch_d"] = stoch["d"]
    
    kc = calculate_keltner_channels(df["high"], df["low"], df["close"], period=20, multiplier=1.5)
    df["kc_middle"] = kc["middle"]
    df["kc_upper"] = kc["upper"]
    df["kc_lower"] = kc["lower"]

    st = calculate_supertrend(df["high"], df["low"], df["close"], period=10, multiplier=3.0)
    df["supertrend"] = st["supertrend"]
    df["supertrend_dir"] = st["direction"]
    
    df["vwma_8"] = calculate_vwma(df["close"], df["volume"], 8)
    df["vwma_21"] = calculate_vwma(df["close"], df["volume"], 21)

    adx_dict = calculate_adx(df["high"], df["low"], df["close"], period=14)
    df["adx"] = adx_dict["adx"]
    df["plus_di"] = adx_dict["plus_di"]
    df["minus_di"] = adx_dict["minus_di"]

    return df
