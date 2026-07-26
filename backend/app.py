import os
from pathlib import Path
from typing import Any, Optional
from fastapi import FastAPI, Query, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from backend.config import HOST, PORT, DEBUG, BASE_DIR
from backend.binance_client import binance_client
from backend.indicators import enrich_klines_dataframe
from backend.screener import screener_engine
from backend.trade_signals import scan_all_signals

app = FastAPI(
    title="Binance Crypto Screener & Analysis API",
    description="Real-Time Crypto Market Screener, Technical Analysis, and Trading Signals powered by Binance API.",
    version="1.0.0"
)

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
    return {"status": "ok", "service": "Binance Crypto Screener API"}

@app.get("/api/market-summary")
def get_market_summary():
    """Returns top volume pairs and 24h market stats."""
    try:
        usdt_tickers = binance_client.get_usdt_tickers()
        sorted_by_vol = sorted(usdt_tickers, key=lambda t: float(t.get("quoteVolume", 0)), reverse=True)[:10]
        sorted_by_gain = sorted(usdt_tickers, key=lambda t: float(t.get("priceChangePercent", 0)), reverse=True)[:5]
        sorted_by_loss = sorted(usdt_tickers, key=lambda t: float(t.get("priceChangePercent", 0)))[:5]

        total_usdt_volume = sum(float(t.get("quoteVolume", 0)) for t in usdt_tickers)
        btc_ticker = next((t for t in usdt_tickers if t["symbol"] == "BTCUSDT"), None)
        eth_ticker = next((t for t in usdt_tickers if t["symbol"] == "ETHUSDT"), None)

        return {
            "btc": btc_ticker,
            "eth": eth_ticker,
            "total_pairs_tracked": len(usdt_tickers),
            "total_24h_usdt_volume": round(total_usdt_volume, 2),
            "top_volume": sorted_by_vol,
            "top_gainers": sorted_by_gain,
            "top_losers": sorted_by_loss,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/screener")
def run_screener(
    interval: str = Query("1h", description="Candle timeframe: 15m, 1h, 4h, 1d"),
    category: str = Query("ALL", description="Filter by category: ALL, Layer 1, AI, DeFi, Meme"),
    min_volume: float = Query(0, description="Minimum 24h quote volume in USDT")
):
    """Run real-time technical analysis screener on top Binance USDT pairs."""
    try:
        results = screener_engine.run_screener(interval=interval, max_pairs=60)
        
        # Filtering
        if category and category != "ALL":
            results = [r for r in results if r["category"].upper() == category.upper()]
            
        if min_volume > 0:
            results = [r for r in results if r["quote_volume_24h"] >= min_volume]

        return {
            "timestamp": int(os.times().elapsed if hasattr(os, 'times') else 0),
            "total_results": len(results),
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
    """Fetch raw klines and computed indicators (RSI, MACD, EMA, BB, RVOL) for charting."""
    try:
        raw_klines = binance_client.get_klines(symbol.upper(), interval=interval, limit=limit)
        df = enrich_klines_dataframe(raw_klines)
        if df.empty:
            raise HTTPException(status_code=444, detail="No kline data found for symbol.")

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
            "symbol": symbol.upper(),
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
):
    """Scan live data for active trade signals with ATR-based SL/TP levels."""
    try:
        signals = scan_all_signals(
            interval=interval,
            rr_key=rr,
            lookback_bars=lookback,
            min_confidence=min_confidence,
        )
        return {
            "interval": interval,
            "rr_config": rr,
            "lookback_bars": lookback,
            "total_signals": len(signals),
            "signals": signals,
        }
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
    order_type: str = "MARKET"  # MARKET or LIMIT
    quantity: float
    price: Optional[float] = None  # Required for LIMIT
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@app.post("/api/order")
def place_order(order: OrderRequest):
    """
    Place an order with optional SL/TP.
    For LONG trades: side=BUY for entry, then OCO SELL for SL+TP.
    For SHORT exits: side=SELL for entry, then OCO BUY for SL+TP.
    """
    try:
        symbol = order.symbol.upper()
        side = order.side.upper()

        # Step 1: Get exchange info for proper formatting
        try:
            info = binance_client.get_symbol_exchange_info(symbol)
            filters = {f["filterType"]: f for f in info.get("filters", [])}

            # Extract precision
            lot_size = filters.get("LOT_SIZE", {})
            step_size = float(lot_size.get("stepSize", "0.001"))
            min_qty = float(lot_size.get("minQty", "0.001"))

            price_filter = filters.get("PRICE_FILTER", {})
            tick_size = float(price_filter.get("tickSize", "0.01"))

            # Format quantity to step size precision
            precision_qty = len(str(step_size).rstrip('0').split('.')[-1]) if '.' in str(step_size) else 0
            precision_price = len(str(tick_size).rstrip('0').split('.')[-1]) if '.' in str(tick_size) else 0

            qty = round(order.quantity - (order.quantity % step_size), precision_qty)
            if qty < min_qty:
                raise ValueError(f"Quantity {qty} is below minimum {min_qty}")
        except ValueError:
            raise
        except Exception:
            qty = order.quantity
            precision_price = 2

        # Step 2: Place entry order
        if order.order_type == "MARKET":
            entry_result = binance_client.place_market_order(symbol, side, qty)
        elif order.order_type == "LIMIT":
            if not order.price:
                raise ValueError("Price is required for LIMIT orders")
            formatted_price = round(order.price - (order.price % tick_size), precision_price)
            entry_result = binance_client.place_limit_order(symbol, side, qty, formatted_price)
        else:
            raise ValueError(f"Unsupported order type: {order.order_type}")

        response = {
            "entry_order": entry_result,
            "sl_tp_order": None,
            "message": f"Entry {order.order_type} {side} order placed successfully",
        }

        # Step 3: Place OCO for SL + TP if both provided (only for MARKET fills)
        if order.stop_loss and order.take_profit and order.order_type == "MARKET":
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

# Serve static frontend files if directory exists
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def read_root():
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"message": "Binance Crypto Screener API is running. Frontend index.html not found."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host=HOST, port=PORT, reload=DEBUG)
