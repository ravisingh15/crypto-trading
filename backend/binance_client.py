import time
import hmac
import hashlib
import requests
from urllib.parse import urlencode
from typing import List, Dict, Any, Optional
from backend.config import (
    API_KEY, SECRET_KEY, BINANCE_BASE_URL, BINANCE_DATA_URL, BINANCE_FUTURES_URL,
    STOCK_METADATA, TOP_STOCK_PAIRS
)

class BinanceClient:
    """
    Robust Binance REST API client supporting public market data queries 
    and HMAC SHA-256 signed private endpoints for both Crypto & US Stock bStocks.
    """

    def __init__(self, api_key: str = API_KEY, secret_key: str = SECRET_KEY):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_urls = [BINANCE_DATA_URL, BINANCE_BASE_URL]
        self.futures_url = BINANCE_FUTURES_URL
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({
                "X-MBX-APIKEY": self.api_key,
                "Content-Type": "application/json"
            })

    def resolve_symbol(self, symbol: str) -> str:
        """
        Intelligently resolves human-readable tickers and stock symbols.
        E.g.:
          'TSLA' -> 'TSLABUSDT'
          'NVDA' -> 'NVDABUSDT'
          'AAPL' -> 'AAPLBUSDT'
          'TSLABUSDT' -> 'TSLABUSDT'
          'BTC' -> 'BTCUSDT'
          'BTCUSDT' -> 'BTCUSDT'
        """
        clean = symbol.strip().upper()
        # Direct match in stock metadata
        if clean in STOCK_METADATA:
            return STOCK_METADATA[clean]["symbol"]
        
        # Suffix matching for bStocks
        if clean.endswith("BUSDT"):
            return clean
        if clean.endswith("USDT"):
            return clean
            
        # Try appending BUSDT for stock ticker or USDT for crypto
        if f"{clean}B" in [k + "B" for k in STOCK_METADATA]:
            return f"{clean}BUSDT"
            
        return f"{clean}USDT"

    def is_stock_symbol(self, symbol: str) -> bool:
        """Check if a symbol represents a US Stock / bStock."""
        sym = symbol.upper()
        if sym in TOP_STOCK_PAIRS:
            return True
        for ticker, meta in STOCK_METADATA.items():
            if sym == meta["symbol"] or sym == ticker:
                return True
        # Check standard bStock naming pattern (ends with BUSDT with length >= 6 and not crypto like BNBUSDT)
        if sym.endswith("BUSDT") and sym not in ["BNBUSDT", "ARBUSDT", "SHIBUSDT", "TRBUSDT", "CKBUSDT", "DGBUSDT"]:
            return True
        return False

    def get_stock_metadata(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Retrieve company name, sector, and ticker for a stock symbol."""
        sym = symbol.upper()
        for ticker, meta in STOCK_METADATA.items():
            if sym == meta["symbol"] or sym == ticker:
                return meta
        # Generate inferred metadata for other bStocks
        if sym.endswith("BUSDT"):
            base_ticker = sym[:-5]  # remove BUSDT
            return {
                "symbol": sym,
                "name": f"{base_ticker} (bStock)",
                "sector": "US Equities & ETFs",
                "ticker": base_ticker
            }
        return None

    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, signed: bool = False) -> Any:
        params = params or {}
        
        if signed:
            if not self.secret_key or not self.api_key:
                raise ValueError("API Key and Secret Key are required for signed Binance requests.")
            params["timestamp"] = int(time.time() * 1000)
            query_string = urlencode(params)
            signature = hmac.new(
                self.secret_key.encode("utf-8"),
                query_string.encode("utf-8"),
                hashlib.sha256
            ).hexdigest()
            params["signature"] = signature

        last_error = None
        for base_url in self.base_urls:
            url = f"{base_url}{path}"
            # Exponential backoff: up to 3 retries per base URL
            for attempt in range(3):
                try:
                    response = self.session.request(method, url, params=params, timeout=10)
                    if response.status_code == 200:
                        return response.json()
                    elif response.status_code == 429:
                        # Rate limit — exponential backoff
                        wait = 0.5 * (2 ** attempt)  # 0.5s, 1s, 2s
                        time.sleep(wait)
                        continue
                    else:
                        response.raise_for_status()
                except Exception as e:
                    last_error = e
                    if attempt < 2:
                        time.sleep(0.3 * (attempt + 1))
                        continue
                    break
                
        if last_error:
            raise last_error
        raise RuntimeError("Failed to complete Binance API request.")

    def get_24h_tickers(self) -> List[Dict[str, Any]]:
        """Fetch 24-hour price change statistics for all symbols."""
        data = self._request("GET", "/api/v3/ticker/24hr")
        if isinstance(data, list):
            return data
        return [data]

    def get_stock_tickers(self) -> List[Dict[str, Any]]:
        """Fetch 24h tickers specifically for US Stocks / bStocks."""
        all_tickers = self.get_24h_tickers()
        stock_tickers = []
        for t in all_tickers:
            sym = t.get("symbol", "")
            if self.is_stock_symbol(sym):
                meta = self.get_stock_metadata(sym)
                t_copy = dict(t)
                t_copy["asset_class"] = "STOCK"
                t_copy["company_name"] = meta["name"] if meta else sym
                t_copy["stock_ticker"] = meta["ticker"] if meta else sym.replace("BUSDT", "")
                t_copy["sector"] = meta["sector"] if meta else "US Equities & ETFs"
                stock_tickers.append(t_copy)
        return stock_tickers

    def get_usdt_tickers(self, asset_class: str = "ALL") -> List[Dict[str, Any]]:
        """
        Fetch 24h tickers filtered for active USDT pairs.
        asset_class: 'ALL', 'CRYPTO', or 'STOCKS'
        """
        all_tickers = self.get_24h_tickers()
        filtered_tickers = []
        for t in all_tickers:
            sym = t.get("symbol", "")
            if not sym.endswith("USDT") or sym.startswith("UP") or sym.startswith("DOWN"):
                continue

            vol = float(t.get("quoteVolume", 0))
            is_stock = self.is_stock_symbol(sym)

            # Stocks might have lower quote volume initially than top crypto, so lower threshold for stocks
            min_vol = 50000 if is_stock else 500000
            if vol < min_vol:
                continue

            if asset_class == "CRYPTO" and is_stock:
                continue
            if asset_class == "STOCKS" and not is_stock:
                continue

            t_copy = dict(t)
            if is_stock:
                meta = self.get_stock_metadata(sym)
                t_copy["asset_class"] = "STOCK"
                t_copy["company_name"] = meta["name"] if meta else sym
                t_copy["stock_ticker"] = meta["ticker"] if meta else sym.replace("BUSDT", "")
                t_copy["sector"] = meta["sector"] if meta else "US Equities & ETFs"
            else:
                t_copy["asset_class"] = "CRYPTO"
                t_copy["company_name"] = sym.replace("USDT", "")
                t_copy["stock_ticker"] = sym.replace("USDT", "")
                t_copy["sector"] = "Crypto"

            filtered_tickers.append(t_copy)

        return filtered_tickers

    def get_klines(self, symbol: str, interval: str = "1h", limit: int = 100,
                    startTime: Optional[int] = None, endTime: Optional[int] = None) -> List[List[Any]]:
        """
        Fetch OHLCV kline/candlestick data for a symbol (supports stock tickers like 'TSLA' or 'TSLABUSDT').
        Intervals: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w
        """
        resolved = self.resolve_symbol(symbol)
        params = {
            "symbol": resolved,
            "interval": interval,
            "limit": limit
        }
        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime
        return self._request("GET", "/api/v3/klines", params=params)

    def get_order_book(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        """Fetch current order book depth for a symbol."""
        resolved = self.resolve_symbol(symbol)
        params = {"symbol": resolved, "limit": limit}
        return self._request("GET", "/api/v3/depth", params=params)

    def get_account_info(self) -> Dict[str, Any]:
        """Fetch private account details and balance balances (Requires valid API key & secret)."""
        return self._request("GET", "/api/v3/account", signed=True)

    def get_symbol_exchange_info(self, symbol: str) -> Dict[str, Any]:
        """Fetch trading rules (lot size, tick size, min notional) for a symbol."""
        resolved = self.resolve_symbol(symbol)
        data = self._request("GET", "/api/v3/exchangeInfo", params={"symbol": resolved})
        if data and "symbols" in data and len(data["symbols"]) > 0:
            return data["symbols"][0]
        raise ValueError(f"No exchange info found for {symbol} ({resolved})")

    def get_symbol_price(self, symbol: str) -> float:
        """Fetch current market price for a symbol."""
        resolved = self.resolve_symbol(symbol)
        data = self._request("GET", "/api/v3/ticker/price", params={"symbol": resolved})
        return float(data.get("price", 0))

    def place_market_order(self, symbol: str, side: str, quantity: float) -> Dict[str, Any]:
        """
        Place a MARKET order.
        side: 'BUY' or 'SELL'
        quantity: amount of base asset
        """
        resolved = self.resolve_symbol(symbol)
        params = {
            "symbol": resolved,
            "side": side.upper(),
            "type": "MARKET",
            "quantity": quantity,
        }
        return self._request("POST", "/api/v3/order", params=params, signed=True)


    def place_limit_order(self, symbol: str, side: str, quantity: float, price: float,
                          time_in_force: str = "GTC") -> Dict[str, Any]:
        """
        Place a LIMIT order.
        side: 'BUY' or 'SELL'
        time_in_force: GTC (Good Til Cancel), IOC, FOK
        """
        resolved = self.resolve_symbol(symbol)
        params = {
            "symbol": resolved,
            "side": side.upper(),
            "type": "LIMIT",
            "timeInForce": time_in_force,
            "quantity": quantity,
            "price": price,
        }
        return self._request("POST", "/api/v3/order", params=params, signed=True)

    def place_stop_loss_order(self, symbol: str, side: str, quantity: float,
                              stop_price: float) -> Dict[str, Any]:
        """
        Place a STOP_LOSS_LIMIT order (used for SL after entry).
        For a LONG trade SL: side='SELL', stopPrice = SL level.
        """
        resolved = self.resolve_symbol(symbol)
        # Use stop price as limit price with small buffer for fills
        buffer = 0.001 if side.upper() == "SELL" else -0.001
        limit_price = stop_price * (1 + buffer)
        params = {
            "symbol": resolved,
            "side": side.upper(),
            "type": "STOP_LOSS_LIMIT",
            "timeInForce": "GTC",
            "quantity": quantity,
            "price": limit_price,
            "stopPrice": stop_price,
        }
        return self._request("POST", "/api/v3/order", params=params, signed=True)

    def place_take_profit_order(self, symbol: str, side: str, quantity: float,
                                stop_price: float) -> Dict[str, Any]:
        """
        Place a TAKE_PROFIT_LIMIT order (used for TP after entry).
        For a LONG trade TP: side='SELL', stopPrice = TP level.
        """
        resolved = self.resolve_symbol(symbol)
        buffer = -0.001 if side.upper() == "SELL" else 0.001
        limit_price = stop_price * (1 + buffer)
        params = {
            "symbol": resolved,
            "side": side.upper(),
            "type": "TAKE_PROFIT_LIMIT",
            "timeInForce": "GTC",
            "quantity": quantity,
            "price": limit_price,
            "stopPrice": stop_price,
        }
        return self._request("POST", "/api/v3/order", params=params, signed=True)

    def place_oco_order(self, symbol: str, side: str, quantity: float,
                        price: float, stop_price: float, stop_limit_price: float) -> Dict[str, Any]:
        """
        Place an OCO (One-Cancels-the-Other) order — combined TP + SL.
        For LONG exit: side='SELL', price=TP level, stopPrice=SL trigger, stopLimitPrice=SL limit.
        """
        resolved = self.resolve_symbol(symbol)
        params = {
            "symbol": resolved,
            "side": side.upper(),
            "quantity": quantity,
            "price": price,                     # Take-profit limit price
            "stopPrice": stop_price,            # Stop-loss trigger price
            "stopLimitPrice": stop_limit_price, # Stop-loss limit price
            "stopLimitTimeInForce": "GTC",
        }
        return self._request("POST", "/api/v3/order/oco", params=params, signed=True)

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch open orders. If symbol is None, returns all open orders."""
        params = {}
        if symbol:
            params["symbol"] = self.resolve_symbol(symbol)
        return self._request("GET", "/api/v3/openOrders", params=params, signed=True)

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancel a specific open order by orderId."""
        resolved = self.resolve_symbol(symbol)
        params = {
            "symbol": resolved,
            "orderId": order_id,
        }
        return self._request("DELETE", "/api/v3/order", params=params, signed=True)


    # ==========================================================================
    # FUTURES API METHODS
    # ==========================================================================

    def _futures_request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None,
                         signed: bool = False) -> Any:
        """Make a request to the Binance Futures API."""
        params = params or {}

        if signed:
            if not self.secret_key or not self.api_key:
                raise ValueError("API Key and Secret Key are required for signed Binance requests.")
            params["timestamp"] = int(time.time() * 1000)
            query_string = urlencode(params)
            signature = hmac.new(
                self.secret_key.encode("utf-8"),
                query_string.encode("utf-8"),
                hashlib.sha256
            ).hexdigest()
            params["signature"] = signature

        url = f"{self.futures_url}{path}"
        try:
            response = self.session.request(method, url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                error_data = response.json() if response.text else {}
                raise RuntimeError(f"Futures API error {response.status_code}: {error_data.get('msg', response.text)}")
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Futures API request failed: {str(e)}")

    def futures_get_24h_tickers(self) -> List[Dict[str, Any]]:
        """Fetch 24-hour price change statistics for all Futures contracts."""
        data = self._futures_request("GET", "/fapi/v1/ticker/24hr")
        if isinstance(data, list):
            return data
        return [data]

    def futures_get_klines(self, symbol: str, interval: str = "5m", limit: int = 30,
                           startTime: Optional[int] = None, endTime: Optional[int] = None) -> List[List[Any]]:
        """Fetch OHLCV candlestick data for a Futures symbol."""
        params: Dict[str, Any] = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": limit
        }
        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime
        return self._futures_request("GET", "/fapi/v1/klines", params=params)

    def futures_get_exchange_info(self, symbol: str) -> Dict[str, Any]:
        """Fetch trading rules for a Futures symbol."""
        data = self._futures_request("GET", "/fapi/v1/exchangeInfo")
        if data and "symbols" in data:
            for s in data["symbols"]:
                if s.get("symbol") == symbol.upper():
                    return s
        raise ValueError(f"No futures exchange info found for {symbol}")

    def futures_get_symbol_price(self, symbol: str) -> float:
        """Fetch current mark price for a Futures symbol."""
        data = self._futures_request("GET", "/fapi/v1/ticker/price",
                                     params={"symbol": symbol.upper()})
        return float(data.get("price", 0))

    def futures_set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """Set leverage for a Futures symbol."""
        params = {
            "symbol": symbol.upper(),
            "leverage": leverage,
        }
        return self._futures_request("POST", "/fapi/v1/leverage", params=params, signed=True)

    def futures_place_market_order(self, symbol: str, side: str, quantity: float) -> Dict[str, Any]:
        """
        Place a Futures MARKET order.
        side: 'BUY' (open long / close short) or 'SELL' (open short / close long)
        """
        params = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": "MARKET",
            "quantity": quantity,
        }
        return self._futures_request("POST", "/fapi/v1/order", params=params, signed=True)

    def futures_place_stop_market(self, symbol: str, side: str, quantity: float,
                                  stop_price: float) -> Dict[str, Any]:
        """
        Place a STOP_MARKET order (used for Stop Loss on Futures).
        For LONG SL: side='SELL', stopPrice = SL level.
        For SHORT SL: side='BUY', stopPrice = SL level.
        """
        params = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": "STOP_MARKET",
            "stopPrice": stop_price,
            "quantity": quantity,
            "reduceOnly": "true",
        }
        return self._futures_request("POST", "/fapi/v1/order", params=params, signed=True)

    def futures_place_take_profit_market(self, symbol: str, side: str, quantity: float,
                                         stop_price: float) -> Dict[str, Any]:
        """
        Place a TAKE_PROFIT_MARKET order (used for TP on Futures).
        For LONG TP: side='SELL', stopPrice = TP level.
        For SHORT TP: side='BUY', stopPrice = TP level.
        """
        params = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": "TAKE_PROFIT_MARKET",
            "stopPrice": stop_price,
            "quantity": quantity,
            "reduceOnly": "true",
        }
        return self._futures_request("POST", "/fapi/v1/order", params=params, signed=True)

    def futures_get_account(self) -> Dict[str, Any]:
        """Fetch Futures account info including balances and positions."""
        return self._futures_request("GET", "/fapi/v2/account", signed=True)

    def futures_get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch open Futures positions. Returns positions with non-zero quantity."""
        data = self._futures_request("GET", "/fapi/v2/positionRisk", signed=True)
        positions = [p for p in data if float(p.get("positionAmt", 0)) != 0]
        if symbol:
            positions = [p for p in positions if p.get("symbol") == symbol.upper()]
        return positions

    def futures_get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch open Futures orders."""
        params = {}
        if symbol:
            params["symbol"] = symbol.upper()
        return self._futures_request("GET", "/fapi/v1/openOrders", params=params, signed=True)

    def futures_cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancel a Futures order."""
        params = {
            "symbol": symbol.upper(),
            "orderId": order_id,
        }
        return self._futures_request("DELETE", "/fapi/v1/order", params=params, signed=True)

    def futures_cancel_all_orders(self, symbol: str) -> Dict[str, Any]:
        """Cancel all open Futures orders for a symbol."""
        params = {"symbol": symbol.upper()}
        return self._futures_request("DELETE", "/fapi/v1/allOpenOrders", params=params, signed=True)

    def futures_get_order_status(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """
        Query the status of a specific Futures order.
        Returns order details including status (NEW, FILLED, CANCELED, etc.)
        and avgPrice for filled orders.
        """
        params = {
            "symbol": symbol.upper(),
            "orderId": order_id,
        }
        return self._futures_request("GET", "/fapi/v1/order", params=params, signed=True)

    def futures_get_user_trades(self, symbol: str, order_id: Optional[int] = None,
                                 limit: int = 50) -> List[Dict[str, Any]]:
        """
        Query recent trades for a Futures symbol (user's fills).
        Can filter by orderId to get fills for a specific order.
        """
        params = {
            "symbol": symbol.upper(),
            "limit": limit,
        }
        if order_id is not None:
            params["orderId"] = order_id
        return self._futures_request("GET", "/fapi/v1/userTrades", params=params, signed=True)


# Global client instance
binance_client = BinanceClient()
