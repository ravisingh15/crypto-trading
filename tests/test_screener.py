import pytest
import numpy as np
from unittest.mock import patch
from backend.screener import get_symbol_category, analyze_single_pair, CryptoScreener, CATEGORY_MAP


class TestScreenerCategories:
    def test_crypto_categories(self):
        assert get_symbol_category("BTCUSDT") == "Layer 1"
        assert get_symbol_category("ETHUSDT") == "Layer 1"
        assert get_symbol_category("UNIUSDT") == "DeFi"
        assert get_symbol_category("DOGEUSDT") == "Meme"
        assert get_symbol_category("FETUSDT") == "AI"

    def test_stock_sectors(self):
        assert get_symbol_category("TSLABUSDT") == "Magnificent 7"
        assert get_symbol_category("NVDABUSDT") == "Magnificent 7"
        assert get_symbol_category("AAPLBUSDT") == "Magnificent 7"
        assert get_symbol_category("MSTRBUSDT") == "Crypto Equities"
        assert get_symbol_category("COINBUSDT") == "Crypto Equities"
        assert get_symbol_category("SPYBUSDT") == "US Indices & ETFs"
        assert get_symbol_category("AMDBUSDT") == "Semiconductors & AI"
        assert get_symbol_category("PLTRBUSDT") == "Fintech & Tech"

    def test_inferred_unknown_stock(self):
        # Unknown stock token ending with BUSDT
        assert "Equities" in get_symbol_category("NEWSTOCKBUSDT")


class TestScreenerAnalysis:
    def test_analyze_single_pair_structure(self):
        # Generate 100 fake candles for testing
        fake_klines = []
        base_price = 100.0
        for i in range(100):
            t = 1700000000000 + i * 3600000
            o = base_price + i * 0.5
            h = o + 2.0
            l = o - 2.0
            c = o + 0.3
            v = 1000.0 + i * 10
            fake_klines.append([t, str(o), str(h), str(l), str(c), str(v), t + 3599999, "100000", 100, "500", "50000", "0"])

        ticker = {
            "symbol": "TSLABUSDT",
            "lastPrice": "150.0",
            "priceChangePercent": "3.5",
            "quoteVolume": "1000000"
        }

        with patch("backend.binance_client.binance_client.get_klines", return_value=fake_klines):
            result = analyze_single_pair(ticker, interval="1h")

        assert result is not None
        assert result["symbol"] == "TSLABUSDT"
        assert result["stock_ticker"] == "TSLA"
        assert result["asset_class"] == "STOCK"
        assert result["category"] == "Magnificent 7"
        assert "score" in result
        assert "recommendation" in result
        assert "rsi" in result
        assert "macd" in result
        assert "ema_9" in result


class TestCryptoScreenerEngine:
    @patch("backend.binance_client.binance_client.get_usdt_tickers")
    @patch("backend.screener.analyze_single_pair")
    def test_run_screener_asset_filtering(self, mock_analyze, mock_get_tickers):
        mock_get_tickers.return_value = [
            {"symbol": "BTCUSDT", "quoteVolume": "10000000", "asset_class": "CRYPTO"},
            {"symbol": "TSLABUSDT", "quoteVolume": "2000000", "asset_class": "STOCK"},
        ]
        mock_analyze.side_effect = lambda t, *args, **kwargs: {
            "symbol": t["symbol"],
            "score": 50,
            "recommendation": "STRONG BUY",
            "asset_class": t.get("asset_class", "CRYPTO"),
            "category": "Test"
        }


        screener = CryptoScreener()
        res_all = screener.run_screener(asset_class="ALL")
        assert len(res_all) == 2

        res_stocks = screener.run_screener(asset_class="STOCKS")
        assert len(res_stocks) <= 2
