"""
Historical Data Fetcher with Binance API Pagination.

Fetches months of candle data by paginating the Binance klines endpoint
using startTime/endTime parameters. Caches results locally as Parquet files
to avoid refetching on every run.

Usage:
    from backend.data_fetcher import fetch_historical_data, load_cached_data

    # Fetch 6 months of 1h data for BTC
    df = fetch_historical_data('BTCUSDT', '1h', months=6)

    # Load from cache if available
    df = load_cached_data('BTCUSDT', '1h')
"""
import pandas as pd
import numpy as np
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

# Interval to milliseconds mapping
INTERVAL_MS = {
    '1m':  60_000,
    '3m':  180_000,
    '5m':  300_000,
    '15m': 900_000,
    '30m': 1_800_000,
    '1h':  3_600_000,
    '2h':  7_200_000,
    '4h':  14_400_000,
    '1d':  86_400_000,
}

# Default cache directory
CACHE_DIR = Path(__file__).resolve().parent.parent / 'data_cache'


def _get_cache_path(symbol: str, interval: str) -> Path:
    """Get the cache file path for a symbol+interval combo."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{symbol}_{interval}.parquet"


def fetch_historical_klines(
    binance_client,
    symbol: str,
    interval: str,
    months: int = 6,
    limit_per_request: int = 1000,
    rate_limit_sleep: float = 0.15,
) -> List[List[Any]]:
    """
    Fetch historical klines by paginating backward from now.
    
    Args:
        binance_client: Binance client instance with get_klines method
        symbol: Trading pair (e.g., 'BTCUSDT')
        interval: Candle interval (e.g., '1h', '4h', '15m')
        months: How many months of data to fetch
        limit_per_request: Max candles per API call (Binance max = 1000)
        rate_limit_sleep: Seconds to sleep between API calls
    
    Returns:
        List of raw kline arrays (concatenated)
    """
    if interval not in INTERVAL_MS:
        raise ValueError(f"Unsupported interval: {interval}. Supported: {list(INTERVAL_MS.keys())}")
    
    interval_ms = INTERVAL_MS[interval]
    
    # Calculate start time
    end_time = int(datetime.utcnow().timestamp() * 1000)
    start_time = int((datetime.utcnow() - timedelta(days=months * 30)).timestamp() * 1000)
    
    all_klines = []
    current_start = start_time
    
    total_expected = (end_time - start_time) // interval_ms
    fetched = 0
    
    print(f"  Fetching {symbol} {interval} data ({months} months, ~{total_expected} candles expected)...")
    
    while current_start < end_time:
        try:
            batch = binance_client.get_klines(
                symbol,
                interval=interval,
                limit=limit_per_request,
                startTime=current_start,
                endTime=end_time,
            )
        except Exception as e:
            print(f"    API error at {datetime.utcfromtimestamp(current_start/1000)}: {e}")
            # Try to continue from next expected window
            current_start += interval_ms * limit_per_request
            time.sleep(rate_limit_sleep * 3)
            continue
        
        if not batch:
            break
        
        all_klines.extend(batch)
        fetched += len(batch)
        
        # Move start to after the last candle we received
        last_open_time = batch[-1][0]
        current_start = last_open_time + interval_ms
        
        if len(batch) < limit_per_request:
            # We've reached the end of available data
            break
        
        time.sleep(rate_limit_sleep)
    
    # Deduplicate by open_time (column 0)
    seen = set()
    unique_klines = []
    for k in all_klines:
        if k[0] not in seen:
            seen.add(k[0])
            unique_klines.append(k)
    
    unique_klines.sort(key=lambda x: x[0])
    print(f"    Fetched {len(unique_klines)} unique candles")
    
    return unique_klines


def fetch_historical_data(
    binance_client,
    symbol: str,
    interval: str,
    months: int = 6,
    enrich_fn=None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Fetch historical data with caching and indicator enrichment.
    
    Args:
        binance_client: Binance client instance
        symbol: Trading pair
        interval: Candle interval
        months: Months of history to fetch
        enrich_fn: Function to enrich DataFrame with indicators (e.g., enrich_klines_dataframe)
        use_cache: Whether to use local Parquet cache
    
    Returns:
        Enriched DataFrame
    """
    cache_path = _get_cache_path(symbol, interval)
    
    # Check cache freshness (re-fetch if older than 4 hours)
    if use_cache and cache_path.exists():
        cache_age_hours = (time.time() - cache_path.stat().st_mtime) / 3600
        if cache_age_hours < 4:
            print(f"  {symbol} {interval}: Loading from cache ({cache_age_hours:.1f}h old)")
            return pd.read_parquet(cache_path)
    
    # Fetch from API
    raw_klines = fetch_historical_klines(binance_client, symbol, interval, months=months)
    
    if not raw_klines:
        print(f"  {symbol} {interval}: No data fetched!")
        return pd.DataFrame()
    
    # Enrich with indicators
    if enrich_fn is not None:
        df = enrich_fn(raw_klines)
    else:
        columns = [
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
        ]
        df = pd.DataFrame(raw_klines, columns=columns)
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
    
    if df.empty:
        return df
    
    # Cache to disk
    try:
        df.to_parquet(cache_path, index=False)
    except Exception as e:
        print(f"  Warning: Could not cache {symbol} {interval}: {e}")
    
    date_range = ""
    if 'open_time' in df.columns:
        date_range = f" ({df['open_time'].iloc[0].strftime('%Y-%m-%d')} to {df['open_time'].iloc[-1].strftime('%Y-%m-%d')})"
    print(f"  {symbol} {interval}: {len(df)} candles loaded{date_range}")
    
    return df


def fetch_multi_symbol(
    binance_client,
    symbols: list,
    interval: str,
    months: int = 6,
    enrich_fn=None,
    use_cache: bool = True,
) -> Dict[str, pd.DataFrame]:
    """
    Fetch historical data for multiple symbols.
    
    Returns:
        Dict mapping symbol -> enriched DataFrame
    """
    datasets = {}
    print(f"\nFetching {len(symbols)} symbols ({interval}, {months} months)...")
    
    for sym in symbols:
        try:
            df = fetch_historical_data(
                binance_client, sym, interval, months=months,
                enrich_fn=enrich_fn, use_cache=use_cache
            )
            if not df.empty and len(df) >= 200:
                datasets[sym] = df
            else:
                print(f"  {sym}: Skipped (too few candles: {len(df) if not df.empty else 0})")
        except Exception as e:
            print(f"  {sym}: Error - {e}")
    
    print(f"Loaded {len(datasets)} / {len(symbols)} symbols successfully.\n")
    return datasets


def load_cached_data(symbol: str, interval: str) -> Optional[pd.DataFrame]:
    """Load cached data if it exists."""
    cache_path = _get_cache_path(symbol, interval)
    if cache_path.exists():
        return pd.read_parquet(cache_path)
    return None


def clear_cache(symbol: Optional[str] = None, interval: Optional[str] = None):
    """Clear cached data files."""
    if symbol and interval:
        path = _get_cache_path(symbol, interval)
        if path.exists():
            path.unlink()
            print(f"Cleared cache: {path.name}")
    else:
        if CACHE_DIR.exists():
            for f in CACHE_DIR.glob("*.parquet"):
                f.unlink()
            print(f"Cleared all cached data")
