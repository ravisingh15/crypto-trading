import time
import hmac
import hashlib
import requests
from urllib.parse import urlencode
from typing import List, Dict, Any, Optional
from backend.config import API_KEY, SECRET_KEY, BINANCE_BASE_URL, BINANCE_DATA_URL

class BinanceClient:
    """
    Robust Binance REST API client supporting public market data queries 
    and HMAC SHA-256 signed private endpoints.
    """

    def __init__(self, api_key: str = API_KEY, secret_key: str = SECRET_KEY):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_urls = [BINANCE_DATA_URL, BINANCE_BASE_URL]
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({
                "X-MBX-APIKEY": self.api_key,
                "Content-Type": "application/json"
            })

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
            try:
                response = self.session.request(method, url, params=params, timeout=10)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    # Rate limit exceeded - attempt fallback
                    time.sleep(0.5)
                    continue
                else:
                    response.raise_for_status()
            except Exception as e:
                last_error = e
                continue
                
        if last_error:
            raise last_error
        raise RuntimeError("Failed to complete Binance API request.")

    def get_24h_tickers(self) -> List[Dict[str, Any]]:
        """Fetch 24-hour price change statistics for all symbols."""
        data = self._request("GET", "/api/v3/ticker/24hr")
        if isinstance(data, list):
            return data
        return [data]

    def get_usdt_tickers(self) -> List[Dict[str, Any]]:
        """Fetch 24h tickers filtered for active USDT pairs."""
        all_tickers = self.get_24h_tickers()
        usdt_tickers = [
            t for t in all_tickers 
            if t.get("symbol", "").endswith("USDT") 
            and not t.get("symbol", "").startswith("UP") 
            and not t.get("symbol", "").startswith("DOWN")
            and float(t.get("quoteVolume", 0)) > 500000  # Filter out illiquid pairs (> $500k volume)
        ]
        return usdt_tickers

    def get_klines(self, symbol: str, interval: str = "1h", limit: int = 100,
                    startTime: Optional[int] = None, endTime: Optional[int] = None) -> List[List[Any]]:
        """
        Fetch OHLCV kline/candlestick data for a symbol.
        Intervals: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w
        startTime/endTime: optional Unix timestamps in milliseconds for pagination
        """
        params = {
            "symbol": symbol.upper(),
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
        params = {"symbol": symbol.upper(), "limit": limit}
        return self._request("GET", "/api/v3/depth", params=params)

    def get_account_info(self) -> Dict[str, Any]:
        """Fetch private account details and balance balances (Requires valid API key & secret)."""
        return self._request("GET", "/api/v3/account", signed=True)

    def get_symbol_exchange_info(self, symbol: str) -> Dict[str, Any]:
        """Fetch trading rules (lot size, tick size, min notional) for a symbol."""
        data = self._request("GET", "/api/v3/exchangeInfo", params={"symbol": symbol.upper()})
        if data and "symbols" in data and len(data["symbols"]) > 0:
            return data["symbols"][0]
        raise ValueError(f"No exchange info found for {symbol}")

    def get_symbol_price(self, symbol: str) -> float:
        """Fetch current market price for a symbol."""
        data = self._request("GET", "/api/v3/ticker/price", params={"symbol": symbol.upper()})
        return float(data.get("price", 0))

    def place_market_order(self, symbol: str, side: str, quantity: float) -> Dict[str, Any]:
        """
        Place a MARKET order.
        side: 'BUY' or 'SELL'
        quantity: amount of base asset
        """
        params = {
            "symbol": symbol.upper(),
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
        params = {
            "symbol": symbol.upper(),
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
        # Use stop price as limit price with small buffer for fills
        buffer = 0.001 if side.upper() == "SELL" else -0.001
        limit_price = stop_price * (1 + buffer)
        params = {
            "symbol": symbol.upper(),
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
        buffer = -0.001 if side.upper() == "SELL" else 0.001
        limit_price = stop_price * (1 + buffer)
        params = {
            "symbol": symbol.upper(),
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
        params = {
            "symbol": symbol.upper(),
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
            params["symbol"] = symbol.upper()
        return self._request("GET", "/api/v3/openOrders", params=params, signed=True)

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancel a specific open order by orderId."""
        params = {
            "symbol": symbol.upper(),
            "orderId": order_id,
        }
        return self._request("DELETE", "/api/v3/order", params=params, signed=True)

# Global client instance
binance_client = BinanceClient()

