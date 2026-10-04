import concurrent.futures
from typing import List, Dict, Any, Optional
import pandas as pd
from backend.binance_client import binance_client
from backend.indicators import enrich_klines_dataframe
from backend.config import STOCK_METADATA, TOP_STOCK_PAIRS
from backend.macro_regime import (
    get_benchmark_dataframe,
    get_macro_summary,
    calculate_relative_strength,
    calculate_market_breadth,
    classify_macro_regime
)

CATEGORY_MAP = {
    # Crypto Categories
    "BTCUSDT": "Layer 1", "ETHUSDT": "Layer 1", "SOLUSDT": "Layer 1", "BNBUSDT": "Layer 1", 
    "ADAUSDT": "Layer 1", "AVAXUSDT": "Layer 1", "NEARUSDT": "Layer 1", "SUIUSDT": "Layer 1",
    "APTUSDT": "Layer 1", "INJUSDT": "Layer 1", "DOTUSDT": "Layer 1", "SEIUSDT": "Layer 1",
    "FETUSDT": "AI", "RENDERUSDT": "AI", "TAOUSDT": "AI", "AGIXUSDT": "AI", "WLDUSDT": "AI",
    "UNIUSDT": "DeFi", "AAVEUSDT": "DeFi", "PENDLEUSDT": "DeFi", "MKRUSDT": "DeFi", "CRVUSDT": "DeFi",
    "DOGEUSDT": "Meme", "PEPEUSDT": "Meme", "SHIBUSDT": "Meme", "WIFUSDT": "Meme", "BONKUSDT": "Meme",
    "ARBUSDT": "Layer 2", "OPUSDT": "Layer 2", "MATICUSDT": "Layer 2", "STRKUSDT": "Layer 2",

    # US Stocks & bStocks Categories
    "TSLABUSDT": "Magnificent 7", "NVDABUSDT": "Magnificent 7", "AAPLBUSDT": "Magnificent 7",
    "MSFTBUSDT": "Magnificent 7", "AMZNBUSDT": "Magnificent 7", "GOOGLBUSDT": "Magnificent 7",
    "METABUSDT": "Magnificent 7",
    "MSTRBUSDT": "Crypto Equities", "COINBUSDT": "Crypto Equities", "HOODBUSDT": "Crypto Equities",
    "IRENBUSDT": "Crypto Equities",
    "AMDBUSDT": "Semiconductors & AI", "TSMBUSDT": "Semiconductors & AI", "ARMBUSDT": "Semiconductors & AI",
    "AVGOBUSDT": "Semiconductors & AI", "QCOMBUSDT": "Semiconductors & AI", "INTCBUSDT": "Semiconductors & AI",
    "SMCIBUSDT": "Semiconductors & AI", "ASMLBUSDT": "Semiconductors & AI",
    "SPYBUSDT": "US Indices & ETFs", "QQQBUSDT": "US Indices & ETFs", "TQQQBUSDT": "US Indices & ETFs",
    "SMHBUSDT": "US Indices & ETFs", "SOXLBUSDT": "US Indices & ETFs", "SOXSBUSDT": "US Indices & ETFs",
    "PLTRBUSDT": "Fintech & Tech", "NFLXBUSDT": "Fintech & Tech", "BABABUSDT": "Fintech & Tech",
    "GMEBUSDT": "Fintech & Tech", "PYPLBUSDT": "Fintech & Tech", "ORCLBUSDT": "Fintech & Tech",
    "IBMBUSDT": "Fintech & Tech", "DELLBUSDT": "Fintech & Tech", "GSBUSDT": "Fintech & Tech",
}

def get_symbol_category(symbol: str) -> str:
    """Get category or sector for any crypto or stock symbol."""
    if symbol in CATEGORY_MAP:
        return CATEGORY_MAP[symbol]
    if binance_client.is_stock_symbol(symbol):
        meta = binance_client.get_stock_metadata(symbol)
        if meta and "sector" in meta:
            return meta["sector"]
        return "US Equities & ETFs"
    return "Altcoin"


def analyze_single_pair(
    ticker: Dict[str, Any],
    interval: str = "1h",
    btc_benchmark_df: Optional[pd.DataFrame] = None,
    spy_benchmark_df: Optional[pd.DataFrame] = None,
    macro_info: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """Fetch klines and analyze technical signals + Macro/RS confluence for a single ticker."""
    symbol = ticker["symbol"]
    try:
        raw_klines = binance_client.get_klines(symbol, interval=interval, limit=100)
        if not raw_klines or len(raw_klines) < 30:
            return None
            
        df = enrich_klines_dataframe(raw_klines)
        if df.empty:
            return None
            
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        price = float(ticker.get("lastPrice", 0))
        price_change_24h = float(ticker.get("priceChangePercent", 0))
        quote_volume_24h = float(ticker.get("quoteVolume", 0))
        
        rsi = float(latest["rsi"]) if not np_isnan(latest["rsi"]) else 50.0
        macd = float(latest["macd"]) if not np_isnan(latest["macd"]) else 0.0
        macd_signal = float(latest["macd_signal"]) if not np_isnan(latest["macd_signal"]) else 0.0
        macd_hist = float(latest["macd_hist"]) if not np_isnan(latest["macd_hist"]) else 0.0
        prev_macd_hist = float(prev["macd_hist"]) if not np_isnan(prev["macd_hist"]) else 0.0
        
        ema_9 = float(latest["ema_9"]) if not np_isnan(latest["ema_9"]) else price
        ema_21 = float(latest["ema_21"]) if not np_isnan(latest["ema_21"]) else price
        ema_50 = float(latest["ema_50"]) if not np_isnan(latest["ema_50"]) else price
        rvol = float(latest["rvol"]) if not np_isnan(latest["rvol"]) else 1.0
        atr = float(latest["atr"]) if not np_isnan(latest["atr"]) else 0.0

        is_stock = binance_client.is_stock_symbol(symbol)
        asset_class = "STOCK" if is_stock else "CRYPTO"

        # Signal Logic Scoring (-100 to +100)
        score = 0
        signals = []

        # RSI Conditions
        if rsi < 30:
            score += 35
            signals.append("RSI Oversold")
        elif rsi > 70:
            score -= 35
            signals.append("RSI Overbought")

        # MACD Crossover
        if prev_macd_hist <= 0 and macd_hist > 0:
            score += 30
            signals.append("Bullish MACD Cross")
        elif prev_macd_hist >= 0 and macd_hist < 0:
            score -= 30
            signals.append("Bearish MACD Cross")

        # Trend Alignment (EMA 9 > EMA 21 > EMA 50)
        if price > ema_9 and ema_9 > ema_21 and ema_21 > ema_50:
            score += 25
            signals.append("Uptrend Stack")
        elif price < ema_9 and ema_9 < ema_21 and ema_21 < ema_50:
            score -= 25
            signals.append("Downtrend Stack")

        # Volume Surge
        if rvol > 2.0:
            score += 15
            signals.append("Volume Surge (>2x)")

        # Relative Strength (RS) calculation vs appropriate benchmark
        benchmark_df = spy_benchmark_df if is_stock else btc_benchmark_df
        if benchmark_df is not None and not benchmark_df.empty:
            rs_data = calculate_relative_strength(df, benchmark_df, period=20)
        else:
            rs_data = {"rs_ratio": 1.0, "rs_rating": 50, "rs_status": "IN_LINE", "outperforming": False}

        # Macro Regime Modifier
        if macro_info:
            regime_key = "equity_benchmark" if is_stock else "crypto_benchmark"
            bench_regime = macro_info.get(regime_key, {}).get("regime", "NEUTRAL")
        else:
            bench_regime = "NEUTRAL"

        # Apply Macro Confluence to Score
        if bench_regime in ["BULL_EXPANSION", "BULL_PULLBACK"]:
            if score > 0:
                score += 10
            if rs_data["rs_status"] == "ALPHA_LEADER":
                score += 15
                signals.append("Alpha Leader (RS High)")
        elif bench_regime in ["BEAR_EXPANSION", "BEAR_CORRECTION"]:
            if score > 0:
                score -= 20  # Penalize counter-trend longs in macro bear
            else:
                score -= 15  # Reinforce short bias
            if rs_data["rs_status"] in ["LAGGING", "UNDERPERFORMING"]:
                signals.append("Macro Drag (RS Lag)")

        # Recommendation Category
        if score >= 40:
            recommendation = "STRONG BUY"
        elif score >= 15:
            recommendation = "BUY"
        elif score <= -40:
            recommendation = "STRONG SELL"
        elif score <= -15:
            recommendation = "SELL"
        else:
            recommendation = "NEUTRAL"

        category = get_symbol_category(symbol)
        meta = binance_client.get_stock_metadata(symbol) if is_stock else None

        company_name = meta["name"] if meta else ticker.get("company_name", symbol.replace("USDT", ""))
        stock_ticker = meta["ticker"] if meta else ticker.get("stock_ticker", symbol.replace("USDT", ""))

        return {
            "symbol": symbol,
            "stock_ticker": stock_ticker,
            "company_name": company_name,
            "asset_class": asset_class,
            "category": category,
            "price": price,
            "price_change_24h": round(price_change_24h, 2),
            "quote_volume_24h": round(quote_volume_24h, 2),
            "rsi": round(rsi, 1),
            "macd": round(macd, 4),
            "macd_signal": round(macd_signal, 4),
            "macd_hist": round(macd_hist, 4),
            "ema_9": round(ema_9, 4),
            "ema_21": round(ema_21, 4),
            "ema_50": round(ema_50, 4),
            "rvol": round(rvol, 2),
            "atr": round(atr, 4),
            "rs_ratio": rs_data["rs_ratio"],
            "rs_rating": rs_data["rs_rating"],
            "rs_status": rs_data["rs_status"],
            "macro_regime": bench_regime,
            "score": score,
            "recommendation": recommendation,
            "signals": signals
        }
    except Exception as e:
        return None

def np_isnan(val: Any) -> bool:
    try:
        import numpy as np
        return np.isnan(val)
    except Exception:
        return False

class CryptoScreener:
    def __init__(self):
        pass

    def run_screener(self, interval: str = "1h", max_pairs: int = 70, asset_class: str = "ALL") -> List[Dict[str, Any]]:
        """Fetch pairs filtered by asset_class, rank, and run parallel indicator analysis with macro context."""
        tickers = binance_client.get_usdt_tickers(asset_class=asset_class)
        
        # When scanning ALL, prioritize top stock pairs + top volume crypto so stocks are well represented
        if asset_class.upper() == "ALL":
            stock_tickers = [t for t in tickers if t.get("asset_class") == "STOCK"]
            crypto_tickers = [t for t in tickers if t.get("asset_class") != "STOCK"]
            crypto_sorted = sorted(crypto_tickers, key=lambda t: float(t.get("quoteVolume", 0)), reverse=True)[:45]
            stock_sorted = sorted(stock_tickers, key=lambda t: float(t.get("quoteVolume", 0)), reverse=True)[:25]
            selected_tickers = crypto_sorted + stock_sorted
        elif asset_class.upper() == "STOCKS":
            selected_tickers = sorted(tickers, key=lambda t: float(t.get("quoteVolume", 0)), reverse=True)[:max_pairs]
        else:
            selected_tickers = sorted(tickers, key=lambda t: float(t.get("quoteVolume", 0)), reverse=True)[:max_pairs]
        
        # Fetch Macro Benchmarks in advance for RS calculations
        btc_bench_df = get_benchmark_dataframe("BTCUSDT", interval=interval, limit=100)
        spy_bench_df = get_benchmark_dataframe("SPYBUSDT", interval=interval, limit=100)
        macro_info = get_macro_summary()

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            future_to_symbol = {
                executor.submit(analyze_single_pair, ticker, interval, btc_bench_df, spy_bench_df, macro_info): ticker["symbol"]
                for ticker in selected_tickers
            }
            for future in concurrent.futures.as_completed(future_to_symbol):
                res = future.result()
                if res:
                    results.append(res)
                    
        # Sort final results by recommendation score descending
        results = sorted(results, key=lambda x: x["score"], reverse=True)
        return results

screener_engine = CryptoScreener()
