import pytest
from unittest.mock import patch, MagicMock
from backend.binance_client import BinanceClient
from backend.config import STOCK_METADATA, TOP_STOCK_PAIRS


@pytest.fixture
def client():
    return BinanceClient(api_key="test_api_key", secret_key="test_secret_key")


class TestBinanceClientSymbolResolution:
    def test_resolve_stock_tickers(self, client):
        assert client.resolve_symbol("TSLA") == "TSLABUSDT"
        assert client.resolve_symbol("NVDA") == "NVDABUSDT"
        assert client.resolve_symbol("AAPL") == "AAPLBUSDT"
        assert client.resolve_symbol("MSTR") == "MSTRBUSDT"
        assert client.resolve_symbol("SPY") == "SPYBUSDT"
        assert client.resolve_symbol("QQQ") == "QQQBUSDT"
        assert client.resolve_symbol("tsla") == "TSLABUSDT"

    def test_resolve_crypto_tickers(self, client):
        assert client.resolve_symbol("BTC") == "BTCUSDT"
        assert client.resolve_symbol("ETH") == "ETHUSDT"
        assert client.resolve_symbol("SOL") == "SOLUSDT"
        assert client.resolve_symbol("BTCUSDT") == "BTCUSDT"
        assert client.resolve_symbol("ethusdt") == "ETHUSDT"

    def test_resolve_already_resolved_bstock(self, client):
        assert client.resolve_symbol("TSLABUSDT") == "TSLABUSDT"
        assert client.resolve_symbol("NVDABUSDT") == "NVDABUSDT"

    def test_is_stock_symbol(self, client):
        assert client.is_stock_symbol("TSLABUSDT") is True
        assert client.is_stock_symbol("NVDABUSDT") is True
        assert client.is_stock_symbol("AAPLBUSDT") is True
        assert client.is_stock_symbol("TSLA") is True
        assert client.is_stock_symbol("SPYBUSDT") is True
        # Crypto should be False
        assert client.is_stock_symbol("BTCUSDT") is False
        assert client.is_stock_symbol("ETHUSDT") is False
        assert client.is_stock_symbol("BNBUSDT") is False
        assert client.is_stock_symbol("ARBUSDT") is False

    def test_get_stock_metadata(self, client):
        meta_tsla = client.get_stock_metadata("TSLABUSDT")
        assert meta_tsla is not None
        assert meta_tsla["name"] == "Tesla, Inc."
        assert meta_tsla["sector"] == "Magnificent 7"
        assert meta_tsla["ticker"] == "TSLA"

        meta_spy = client.get_stock_metadata("SPYBUSDT")
        assert meta_spy is not None
        assert "S&P 500" in meta_spy["name"]
        assert meta_spy["sector"] == "US Indices & ETFs"

        # Lookup by ticker alias
        meta_nvda = client.get_stock_metadata("NVDA")
        assert meta_nvda is not None
        assert meta_nvda["ticker"] == "NVDA"

        # Crypto returns None
        assert client.get_stock_metadata("BTCUSDT") is None


class TestBinanceClientTickerFiltering:
    @patch.object(BinanceClient, "get_24h_tickers")
    def test_get_usdt_tickers_filtering(self, mock_get_24h, client):
        mock_get_24h.return_value = [
            {"symbol": "BTCUSDT", "quoteVolume": "10000000", "lastPrice": "65000", "priceChangePercent": "2.5"},
            {"symbol": "ETHUSDT", "quoteVolume": "5000000", "lastPrice": "3500", "priceChangePercent": "1.2"},
            {"symbol": "TSLABUSDT", "quoteVolume": "2000000", "lastPrice": "340", "priceChangePercent": "-0.5"},
            {"symbol": "NVDABUSDT", "quoteVolume": "3000000", "lastPrice": "130", "priceChangePercent": "3.1"},
            {"symbol": "LOWVOLUSDT", "quoteVolume": "1000", "lastPrice": "0.1", "priceChangePercent": "0.0"},  # Illiquid
            {"symbol": "BTCBTC", "quoteVolume": "1000000", "lastPrice": "1.0", "priceChangePercent": "0.0"},    # Non-USDT
        ]

        all_tickers = client.get_usdt_tickers(asset_class="ALL")
        symbols_all = [t["symbol"] for t in all_tickers]
        assert "BTCUSDT" in symbols_all
        assert "TSLABUSDT" in symbols_all
        assert "NVDABUSDT" in symbols_all
        assert "LOWVOLUSDT" not in symbols_all
        assert "BTCBTC" not in symbols_all

        # Crypto only
        crypto_tickers = client.get_usdt_tickers(asset_class="CRYPTO")
        symbols_crypto = [t["symbol"] for t in crypto_tickers]
        assert "BTCUSDT" in symbols_crypto
        assert "TSLABUSDT" not in symbols_crypto

        # Stocks only
        stock_tickers = client.get_usdt_tickers(asset_class="STOCKS")
        symbols_stocks = [t["symbol"] for t in stock_tickers]
        assert "TSLABUSDT" in symbols_stocks
        assert "NVDABUSDT" in symbols_stocks
        assert "BTCUSDT" not in symbols_stocks


class TestBinanceClientKlinesAndOrders:
    @patch.object(BinanceClient, "_request")
    def test_get_klines_resolves_symbol(self, mock_request, client):
        mock_request.return_value = [[1700000000000, "100", "110", "90", "105", "1000"]]
        res = client.get_klines("TSLA", interval="1h", limit=10)
        assert len(res) == 1
        # Verify symbol resolved to TSLABUSDT in params
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        assert kwargs["params"]["symbol"] == "TSLABUSDT"

    @patch.object(BinanceClient, "_request")
    def test_place_market_order_resolves_symbol(self, mock_request, client):
        mock_request.return_value = {"orderId": 12345, "status": "FILLED"}
        res = client.place_market_order("NVDA", "BUY", 1.5)
        assert res["orderId"] == 12345
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        assert kwargs["params"]["symbol"] == "NVDABUSDT"
        assert kwargs["params"]["side"] == "BUY"
        assert kwargs["params"]["quantity"] == 1.5
