import os
from pathlib import Path
from typing import Any, Optional
import base64
from fastapi import FastAPI, Query, HTTPException, Body, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from backend.config import (
    HOST, PORT, DEBUG, BASE_DIR,
    DASHBOARD_USERNAME, DASHBOARD_PASSWORD, SCREENER_ONLY_MODE
)
from backend.binance_client import binance_client
from backend.indicators import enrich_klines_dataframe
from backend.screener import screener_engine
from backend.trade_signals import scan_all_signals
from backend.auto_trader import auto_trader
from backend.trade_journal import trade_journal
from backend.macro_regime import get_macro_summary, calculate_market_breadth
from backend.high_delta_scanner import scan_futures_high_delta


app = FastAPI(
    title="Binance Crypto Screener & Analysis API",
    description="Real-Time Crypto Market Screener, Technical Analysis, and Trading Signals powered by Binance API.",
    version="1.0.0"
)

# Optional HTTP Basic Auth for remote single-user access
@app.middleware("http")
async def basic_auth_middleware(request: Request, call_next):
    if DASHBOARD_PASSWORD:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Basic "):
            return Response(
                status_code=401,
                content="Unauthorized: Access to CypherScreen is password protected.",
                headers={"WWW-Authenticate": 'Basic realm="CypherScreen Screener"'}
            )
        try:
            encoded = auth_header.split(" ", 1)[1]
            decoded = base64.b64decode(encoded).decode("utf-8")
            username, _, password = decoded.partition(":")
            if username != DASHBOARD_USERNAME or password != DASHBOARD_PASSWORD:
                return Response(
                    status_code=401,
                    content="Unauthorized: Invalid credentials.",
                    headers={"WWW-Authenticate": 'Basic realm="CypherScreen Screener"'}
                )
        except Exception:
            return Response(
                status_code=401,
                content="Unauthorized",
                headers={"WWW-Authenticate": 'Basic realm="CypherScreen Screener"'}
            )
    return await call_next(request)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = BASE_DIR / "frontend"

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "Binance Crypto Screener API",
        "screener_only": SCREENER_ONLY_MODE,
        "auth_enabled": bool(DASHBOARD_PASSWORD)
    }

@app.get("/api/config")
def get_app_config():
    """Return runtime public configuration for the UI."""
    return {
        "screener_only": SCREENER_ONLY_MODE,
        "has_keys": bool(binance_client.api_key and binance_client.secret_key),
        "auth_enabled": bool(DASHBOARD_PASSWORD)
    }

@app.get("/api/market-summary")
def get_market_summary(asset_class: str = Query("ALL", description="Filter by asset class: ALL, CRYPTO, STOCKS")):
    """Returns top volume pairs and 24h market stats for Crypto & US Stocks."""
    try:
        all_tickers = binance_client.get_usdt_tickers(asset_class="ALL")
        filtered_tickers = binance_client.get_usdt_tickers(asset_class=asset_class)

        sorted_by_vol = sorted(filtered_tickers, key=lambda t: float(t.get("quoteVolume", 0)), reverse=True)[:10]
        sorted_by_gain = sorted(filtered_tickers, key=lambda t: float(t.get("priceChangePercent", 0)), reverse=True)[:5]
        sorted_by_loss = sorted(filtered_tickers, key=lambda t: float(t.get("priceChangePercent", 0)))[:5]

        # Stock specific highlights
        stock_tickers = [t for t in all_tickers if t.get("asset_class") == "STOCK"]
        crypto_tickers = [t for t in all_tickers if t.get("asset_class") != "STOCK"]

        top_stocks_gainers = sorted(stock_tickers, key=lambda t: float(t.get("priceChangePercent", 0)), reverse=True)[:5]
        top_crypto_gainers = sorted(crypto_tickers, key=lambda t: float(t.get("priceChangePercent", 0)), reverse=True)[:5]

        total_usdt_volume = sum(float(t.get("quoteVolume", 0)) for t in filtered_tickers)
        btc_ticker = next((t for t in all_tickers if t["symbol"] == "BTCUSDT"), None)
        eth_ticker = next((t for t in all_tickers if t["symbol"] == "ETHUSDT"), None)
        tsla_ticker = next((t for t in all_tickers if t["symbol"] == "TSLABUSDT"), None)
        nvda_ticker = next((t for t in all_tickers if t["symbol"] == "NVDABUSDT"), None)
        aapl_ticker = next((t for t in all_tickers if t["symbol"] == "AAPLBUSDT"), None)
        mstr_ticker = next((t for t in all_tickers if t["symbol"] == "MSTRBUSDT"), None)
        spy_ticker = next((t for t in all_tickers if t["symbol"] == "SPYBUSDT"), None)

        return {
            "btc": btc_ticker,
            "eth": eth_ticker,
            "tsla": tsla_ticker,
            "nvda": nvda_ticker,
            "aapl": aapl_ticker,
            "mstr": mstr_ticker,
            "spy": spy_ticker,
            "total_pairs_tracked": len(filtered_tickers),
            "crypto_pairs_count": len(crypto_tickers),
            "stock_pairs_count": len(stock_tickers),
            "total_24h_usdt_volume": round(total_usdt_volume, 2),
            "top_volume": sorted_by_vol,
            "top_gainers": sorted_by_gain,
            "top_losers": sorted_by_loss,
            "top_stock_gainers": top_stocks_gainers,
            "top_crypto_gainers": top_crypto_gainers,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stocks/summary")
def get_stocks_summary():
    """Dedicated endpoint for US Stock (bStock) leaders, sectors, and top movers."""
    try:
        stock_tickers = binance_client.get_stock_tickers()
        sorted_by_gain = sorted(stock_tickers, key=lambda t: float(t.get("priceChangePercent", 0)), reverse=True)
        sorted_by_vol = sorted(stock_tickers, key=lambda t: float(t.get("quoteVolume", 0)), reverse=True)

        mag7_symbols = ["AAPLBUSDT", "MSFTBUSDT", "NVDABUSDT", "TSLABUSDT", "AMZNBUSDT", "GOOGLBUSDT", "METABUSDT"]
        mag7_tickers = [t for t in stock_tickers if t["symbol"] in mag7_symbols]

        crypto_equities = ["MSTRBUSDT", "COINBUSDT", "HOODBUSDT", "IRENBUSDT"]
        crypto_eq_tickers = [t for t in stock_tickers if t["symbol"] in crypto_equities]

        etfs = ["SPYBUSDT", "QQQBUSDT", "TQQQBUSDT", "SMHBUSDT", "SOXLBUSDT"]
        etf_tickers = [t for t in stock_tickers if t["symbol"] in etfs]

        return {
            "total_stocks": len(stock_tickers),
            "magnificent_7": mag7_tickers,
            "crypto_equities": crypto_eq_tickers,
            "etfs": etf_tickers,
            "top_gainers": sorted_by_gain[:5],
            "top_volume": sorted_by_vol[:5],
            "all_stocks": stock_tickers
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/macro/summary")
def get_macro_regimes():
    """Retrieve macro trend regimes for Crypto (BTC) and US Equities (SPY/QQQ)."""
    try:
        return get_macro_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/screener")
def run_screener(
    interval: str = Query("1h", description="Candle timeframe: 15m, 1h, 4h, 1d"),
    category: str = Query("ALL", description="Filter by category/sector"),
    asset_class: str = Query("ALL", description="Filter by asset class: ALL, CRYPTO, STOCKS"),
    min_volume: float = Query(0, description="Minimum 24h quote volume in USDT")
):
    """Run real-time technical analysis screener on Binance pairs (Crypto & US Stocks) with Macro Confluence."""
    try:
        results = screener_engine.run_screener(interval=interval, max_pairs=80, asset_class=asset_class)
        
        # Calculate Market Breadth across full scan before category filtering
        breadth = calculate_market_breadth(results)
        macro_summary = get_macro_summary()

        # Filtering by Category/Sector
        if category and category != "ALL":
            results = [r for r in results if r["category"].upper() == category.upper()]
            
        if min_volume > 0:
            results = [r for r in results if r["quote_volume_24h"] >= min_volume]

        return {
            "timestamp": int(os.times().elapsed if hasattr(os, 'times') else 0),
            "asset_class": asset_class,
            "total_results": len(results),
            "market_breadth": breadth,
            "macro_summary": macro_summary,
            "data": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/klines/{symbol}")
def get_symbol_klines(
    symbol: str,
    interval: str = Query("1h", description="Timeframe"),
    limit: int = Query(100, ge=10, le=500)
):
    """Fetch raw klines and computed indicators for charting (supports TSLA, AAPL, BTCUSDT, etc.)."""
    try:
        resolved = binance_client.resolve_symbol(symbol)
        raw_klines = binance_client.get_klines(resolved, interval=interval, limit=limit)
        df = enrich_klines_dataframe(raw_klines)
        if df.empty:
            raise HTTPException(status_code=444, detail=f"No kline data found for {symbol} ({resolved}).")

        is_stock = binance_client.is_stock_symbol(resolved)
        meta = binance_client.get_stock_metadata(resolved) if is_stock else None

        # Format clean JSON output
        records = []
        for idx, row in df.iterrows():
            records.append({
                "time": int(row["open_time"].timestamp()),
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
                "rsi": None if np_isnan(row["rsi"]) else round(row["rsi"], 2),
                "macd": None if np_isnan(row["macd"]) else round(row["macd"], 4),
                "macd_signal": None if np_isnan(row["macd_signal"]) else round(row["macd_signal"], 4),
                "macd_hist": None if np_isnan(row["macd_hist"]) else round(row["macd_hist"], 4),
                "ema_9": None if np_isnan(row["ema_9"]) else round(row["ema_9"], 4),
                "ema_21": None if np_isnan(row["ema_21"]) else round(row["ema_21"], 4),
                "ema_50": None if np_isnan(row["ema_50"]) else round(row["ema_50"], 4),
                "bb_upper": None if np_isnan(row["bb_upper"]) else round(row["bb_upper"], 4),
                "bb_middle": None if np_isnan(row["bb_middle"]) else round(row["bb_middle"], 4),
                "bb_lower": None if np_isnan(row["bb_lower"]) else round(row["bb_lower"], 4),
            })

        return {
            "symbol": resolved,
            "display_ticker": meta["ticker"] if meta else resolved.replace("USDT", ""),
            "company_name": meta["name"] if meta else resolved.replace("USDT", ""),
            "asset_class": "STOCK" if is_stock else "CRYPTO",
            "sector": meta["sector"] if meta else "Crypto",
            "interval": interval,
            "count": len(records),
            "klines": records
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/trade-signals")
def get_trade_signals(
    interval: str = Query("1h", description="Candle timeframe: 15m, 1h, 4h"),
    rr: str = Query("1:2.0", description="Risk:Reward ratio: 1:1.5, 1:2.0, 1:3.0"),
    lookback: int = Query(3, ge=1, le=10, description="Scan last N candles for signals"),
    min_confidence: int = Query(0, ge=0, le=100, description="Minimum confidence score (0-100)"),
    asset_class: str = Query("ALL", description="Filter by asset class: ALL, CRYPTO, STOCKS"),
    mtf_aligned: bool = Query(False, description="Filter by MTF trend aligned signals only"),
):
    """Scan live data for active trade signals across Crypto and US Stocks with MTF Confluence."""
    try:
        signals = scan_all_signals(
            interval=interval,
            rr_key=rr,
            lookback_bars=lookback,
            min_confidence=min_confidence,
            asset_class=asset_class,
            mtf_aligned_only=mtf_aligned,
        )
        return {
            "interval": interval,
            "rr_config": rr,
            "lookback_bars": lookback,
            "asset_class": asset_class,
            "mtf_aligned_only": mtf_aligned,
            "total_signals": len(signals),
            "signals": signals,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/futures/high-delta")
def get_futures_high_delta(
    min_volume: float = Query(5_000_000, description="Minimum 24h quote volume in USDT"),
    min_natr: float = Query(0.5, description="Minimum 5-minute Normalized ATR %"),
    limit: int = Query(40, ge=1, le=100, description="Max contracts to return"),
    lookback_bars: int = Query(12, ge=3, le=24, description="Recent 5m bars to analyze (12 = 1 hr)"),
    force_refresh: bool = Query(False, description="Bypass cache and force live scan")
):
    """Scan Binance USDⓈ-M Futures contracts for high 5-minute delta/volatility and 2:1 scalp setups."""
    try:
        data = scan_futures_high_delta(
            min_volume=min_volume,
            min_natr=min_natr,
            limit=limit,
            lookback_bars=lookback_bars,
            force_refresh=force_refresh
        )
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/wallet")
def get_wallet():
    """Fetch wallet balances enriched with USD values and total portfolio value."""
    try:
        account_data = binance_client.get_account_info()
        raw_balances = [
            b for b in account_data.get("balances", [])
            if float(b["free"]) > 0 or float(b["locked"]) > 0
        ]

        # Fetch all USDT prices for conversion
        try:
            all_tickers = binance_client.get_24h_tickers()
            price_map = {t["symbol"]: float(t["lastPrice"]) for t in all_tickers}
            change_map = {t["symbol"]: float(t["priceChangePercent"]) for t in all_tickers}
        except Exception:
            price_map = {}
            change_map = {}

        enriched = []
        total_usd = 0.0

        for b in raw_balances:
            asset = b["asset"]
            free = float(b["free"])
            locked = float(b["locked"])
            total = free + locked

            # Determine USD value
            if asset == "USDT":
                usd_value = total
                usd_price = 1.0
                change_24h = 0.0
            elif asset == "BUSD":
                usd_value = total
                usd_price = 1.0
                change_24h = 0.0
            else:
                pair = f"{asset}USDT"
                usd_price = price_map.get(pair, 0)
                usd_value = total * usd_price
                change_24h = change_map.get(pair, 0)

            total_usd += usd_value

            enriched.append({
                "asset": asset,
                "free": round(free, 8),
                "locked": round(locked, 8),
                "total": round(total, 8),
                "usd_price": round(usd_price, 6),
                "usd_value": round(usd_value, 2),
                "change_24h": round(change_24h, 2),
            })

        # Sort by USD value descending
        enriched.sort(key=lambda x: x["usd_value"], reverse=True)

        return {
            "can_trade": account_data.get("canTrade", False),
            "account_type": account_data.get("accountType", "SPOT"),
            "total_usd": round(total_usd, 2),
            "asset_count": len(enriched),
            "balances": enriched,
        }
    except ValueError as ve:
        return JSONResponse(status_code=400, content={"error": str(ve)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Failed to fetch wallet: {str(e)}"})


class OrderRequest(BaseModel):
    symbol: str
    side: str  # BUY or SELL
    amount: float  # USDT amount to invest
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@app.post("/api/order")
def place_order(order: OrderRequest):
    """
    Place a market order with optional SL/TP.
    User specifies USDT amount — quantity is computed from current price.
    """
    try:
        if SCREENER_ONLY_MODE:
            return JSONResponse(
                status_code=403,
                content={"error": "Trade execution is disabled. Screener-only mode is active (trades should be placed manually on Binance)."}
            )

        symbol = order.symbol.upper()
        side = order.side.upper()

        if order.amount <= 0:
            raise ValueError("Amount must be greater than 0")

        # Step 1: Get current price and exchange info
        current_price = binance_client.get_symbol_price(symbol)
        if current_price <= 0:
            raise ValueError(f"Could not fetch price for {symbol}")

        try:
            info = binance_client.get_symbol_exchange_info(symbol)
            filters = {f["filterType"]: f for f in info.get("filters", [])}

            # Extract precision
            lot_size = filters.get("LOT_SIZE", {})
            step_size = float(lot_size.get("stepSize", "0.001"))
            min_qty = float(lot_size.get("minQty", "0.001"))

            price_filter = filters.get("PRICE_FILTER", {})
            tick_size = float(price_filter.get("tickSize", "0.01"))

            min_notional = filters.get("MIN_NOTIONAL", filters.get("NOTIONAL", {}))
            min_notional_val = float(min_notional.get("minNotional", "10"))

            # Format quantity to step size precision
            precision_qty = len(str(step_size).rstrip('0').split('.')[-1]) if '.' in str(step_size) else 0
            precision_price = len(str(tick_size).rstrip('0').split('.')[-1]) if '.' in str(tick_size) else 0

            # Compute quantity from USDT amount
            raw_qty = order.amount / current_price
            qty = round(raw_qty - (raw_qty % step_size), precision_qty)

            if qty < min_qty:
                raise ValueError(f"Quantity {qty} is below minimum {min_qty} (try a larger amount)")
            if order.amount < min_notional_val:
                raise ValueError(f"Amount ${order.amount} is below minimum ${min_notional_val}")
        except ValueError:
            raise
        except Exception:
            qty = order.amount / current_price
            precision_price = 2

        # Step 2: Place market entry order
        entry_result = binance_client.place_market_order(symbol, side, qty)

        response = {
            "entry_order": entry_result,
            "sl_tp_order": None,
            "message": f"MARKET {side} order placed — {qty} {symbol.replace('USDT', '')} (~${order.amount:.2f})",
        }

        # Step 3: Place OCO for SL + TP if both provided
        if order.stop_loss and order.take_profit:
            exit_side = "SELL" if side == "BUY" else "BUY"
            sl = round(order.stop_loss - (order.stop_loss % tick_size), precision_price)
            tp = round(order.take_profit - (order.take_profit % tick_size), precision_price)

            # SL limit price with 0.1% buffer for fills
            if exit_side == "SELL":
                sl_limit = round(sl * 0.999, precision_price)
            else:
                sl_limit = round(sl * 1.001, precision_price)

            try:
                oco_result = binance_client.place_oco_order(
                    symbol=symbol,
                    side=exit_side,
                    quantity=qty,
                    price=tp,
                    stop_price=sl,
                    stop_limit_price=sl_limit,
                )
                response["sl_tp_order"] = oco_result
                response["message"] += " + OCO (SL/TP) placed"
            except Exception as oco_err:
                response["sl_tp_error"] = str(oco_err)
                response["message"] += f" (Warning: OCO SL/TP failed: {str(oco_err)})"

        return response

    except ValueError as ve:
        return JSONResponse(status_code=400, content={"error": str(ve)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Order failed: {str(e)}"})


@app.get("/api/orders/open")
def get_open_orders(symbol: str = Query(None, description="Symbol to filter, or omit for all")):
    """List open orders."""
    try:
        orders = binance_client.get_open_orders(symbol)
        return {"count": len(orders), "orders": orders}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.delete("/api/order/{symbol}/{order_id}")
def cancel_an_order(symbol: str, order_id: int):
    """Cancel an open order."""
    try:
        result = binance_client.cancel_order(symbol.upper(), order_id)
        return {"message": "Order cancelled", "result": result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/exchange-info/{symbol}")
def get_exchange_info(symbol: str):
    """Get trading rules for a symbol (lot size, tick size, min notional)."""
    try:
        info = binance_client.get_symbol_exchange_info(symbol.upper())
        filters = {f["filterType"]: f for f in info.get("filters", [])}
        return {
            "symbol": info.get("symbol"),
            "status": info.get("status"),
            "baseAsset": info.get("baseAsset"),
            "quoteAsset": info.get("quoteAsset"),
            "lot_size": filters.get("LOT_SIZE"),
            "price_filter": filters.get("PRICE_FILTER"),
            "min_notional": filters.get("NOTIONAL") or filters.get("MIN_NOTIONAL"),
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


def np_isnan(val: Any) -> bool:
    try:
        import numpy as np
        return np.isnan(val)
    except Exception:
        return False


# ================================================
# Bot Auto-Trader Endpoints
# ================================================

class BotConfigUpdate(BaseModel):
    paper_mode: Optional[bool] = None
    market_type: Optional[str] = None  # "futures" or "spot"
    asset_filter: Optional[str] = None  # "all", "crypto", "stocks"
    total_capital: Optional[float] = None
    sizing_mode: Optional[str] = None  # "fixed", "percent_capital", "risk_pct"
    amount_per_trade: Optional[float] = None
    trade_size_pct: Optional[float] = None
    risk_per_trade_pct: Optional[float] = None
    daily_profit_target: Optional[float] = None
    trailing_stop_enabled: Optional[bool] = None
    trailing_stop_callback_pct: Optional[float] = None
    strategy_filter: Optional[str] = None
    leverage: Optional[int] = None
    min_confidence: Optional[int] = None
    max_positions: Optional[int] = None
    max_daily_loss: Optional[float] = None
    cooldown_hours: Optional[int] = None
    scan_interval_minutes: Optional[int] = None
    candle_interval: Optional[str] = None
    mtf_filter_enabled: Optional[bool] = None
    breakeven_stop_enabled: Optional[bool] = None


@app.post("/api/bot/start")
def bot_start():
    """Start the auto-trading bot."""
    try:
        result = auto_trader.start()
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/bot/stop")
def bot_stop():
    """Stop the auto-trading bot."""
    try:
        result = auto_trader.stop()
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/bot/status")
def bot_status():
    """Get current bot status, config, open positions, capital metrics, and recent log."""
    try:
        return auto_trader.get_status()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/bot/config")
def bot_config(config: BotConfigUpdate):
    """Update bot configuration."""
    try:
        data_dict = config.model_dump() if hasattr(config, "model_dump") else config.dict()
        updates = {k: v for k, v in data_dict.items() if v is not None}
        auto_trader.update_config(updates)
        return {"message": "Config updated", "config": auto_trader.config}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/bot/square-off-all")
def bot_square_off_all():
    """Square off all open bot positions immediately."""
    try:
        result = auto_trader.square_off_all()
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/bot/square-off/{symbol}")
def bot_square_off_symbol(symbol: str):
    """Square off a specific open position immediately."""
    try:
        result = auto_trader.square_off_position(symbol)
        if result is None:
            return JSONResponse(status_code=404, content={"error": f"No open position found for {symbol}"})
        return {"message": f"Position {symbol} squared off", "closed_position": result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/bot/emergency-stop")
def bot_emergency_stop():
    """Panic emergency stop: Stop bot engine and square off all open positions."""
    try:
        result = auto_trader.emergency_stop()
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/bot/scan-now")
def bot_scan_now():
    """Trigger an immediate scan-filter-execute cycle on demand."""
    try:
        result = auto_trader.run_manual_scan()
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/bot/journal")
def bot_journal(
    limit: int = Query(50, description="Number of entries to return"),
    event_type: str = Query(None, description="Filter by event type"),
):
    """Get trade journal entries."""
    try:
        entries = trade_journal.get_recent(limit=limit, event_type=event_type)
        return {"count": len(entries), "entries": entries}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.delete("/api/bot/journal")
def bot_clear_journal():
    """Clear trade journal log entries."""
    try:
        trade_journal.clear()
        return {"message": "Trade journal cleared successfully"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/bot/analytics")
def bot_analytics():
    """Get performance statistics and strategy breakdown."""
    try:
        strategy_stats = trade_journal.get_strategy_stats()
        closures = trade_journal.get_all_closures()
        total_trades = len(closures)
        winning_trades = len([c for c in closures if float(c.get("pnl_usdt", 0)) > 0])
        losing_trades = len([c for c in closures if float(c.get("pnl_usdt", 0)) < 0])
        total_pnl = sum(float(c.get("pnl_usdt", 0)) for c in closures)
        gross_profit = sum(float(c.get("pnl_usdt", 0)) for c in closures if float(c.get("pnl_usdt", 0)) > 0)
        gross_loss = abs(sum(float(c.get("pnl_usdt", 0)) for c in closures if float(c.get("pnl_usdt", 0)) < 0))
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (round(gross_profit, 2) if gross_profit > 0 else 0)
        win_rate = round(winning_trades / total_trades * 100, 1) if total_trades > 0 else 0

        return {
            "total_closed_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate_pct": win_rate,
            "total_realized_pnl": round(total_pnl, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "profit_factor": profit_factor,
            "strategy_stats": strategy_stats,
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})



# Serve static frontend files if directory exists
if FRONTEND_DIR.exists():
    css_dir = FRONTEND_DIR / "css"
    if css_dir.exists():
        app.mount("/css", StaticFiles(directory=str(css_dir)), name="css")

    js_dir = FRONTEND_DIR / "js"
    if js_dir.exists():
        app.mount("/js", StaticFiles(directory=str(js_dir)), name="js")

    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    @app.get("/index")
    @app.get("/index.html")
    @app.get("/dashboard")
    def read_root():
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"message": "Binance Crypto Screener API is running. Frontend index.html not found."}

if __name__ == "__main__":
    import uvicorn
    import webbrowser
    import threading
    import socket

    def is_port_available(port: int, host: str) -> bool:
        targets = [host]
        if host in ("0.0.0.0", ""):
            targets.append("127.0.0.1")
        for h in targets:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.bind((h, port))
            except OSError:
                return False
        return True

    def find_available_port(start_port: int, host: str) -> int:
        port = start_port
        while port < start_port + 200:
            if is_port_available(port, host):
                return port
            port += 1
        return start_port

    active_port = PORT
    if not is_port_available(active_port, HOST):
        fallback_start = 8050 if active_port in (8000, 8001) else active_port + 1
        active_port = find_available_port(fallback_start, HOST)
        os.environ["PORT"] = str(active_port)
        print(f"\n[!] Notice: Port {PORT} is already in use by another application.")
        print(f"[*] Automatically switched to available port: {active_port}")

    display_host = "127.0.0.1" if HOST in ("0.0.0.0", "") else HOST

    def open_browser():
        url = f"http://{display_host}:{active_port}"
        print(f"Opening {url} in your default browser...")
        webbrowser.open(url)

    # Launch browser after a brief delay so server has started
    threading.Timer(1.2, open_browser).start()

    print(f"\n=======================================================")
    print(f"   CypherScreen - Binance Market Screener & Bot")
    print(f"   URL: http://{display_host}:{active_port}")
    print(f"   API Docs: http://{display_host}:{active_port}/docs")
    print(f"=======================================================\n")
    uvicorn.run("backend.app:app", host=HOST, port=active_port, reload=DEBUG)


