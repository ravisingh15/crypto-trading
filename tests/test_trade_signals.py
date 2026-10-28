import pytest
from unittest.mock import patch
from backend.trade_signals import (
    _get_dynamic_symbols,
    scan_all_signals,
    scan_symbol_signals,
    _calculate_signal_confidence,
    _regime_fit,
    _quality_grade,
)


class TestTradeSignalsScanner:
    @patch("backend.binance_client.binance_client.get_usdt_tickers")
    def test_get_dynamic_symbols_asset_classes(self, mock_tickers):
        mock_tickers.return_value = [
            {"symbol": "BTCUSDT", "quoteVolume": "10000000", "asset_class": "CRYPTO"},
            {"symbol": "ETHUSDT", "quoteVolume": "5000000", "asset_class": "CRYPTO"},
            {"symbol": "TSLABUSDT", "quoteVolume": "2000000", "asset_class": "STOCK"},
            {"symbol": "NVDABUSDT", "quoteVolume": "3000000", "asset_class": "STOCK"},
        ]

        symbols_all = _get_dynamic_symbols(max_symbols=10, asset_class="ALL")
        assert "BTCUSDT" in symbols_all
        assert "TSLABUSDT" in symbols_all

        symbols_stocks = _get_dynamic_symbols(max_symbols=10, asset_class="STOCKS")
        assert "TSLABUSDT" in symbols_stocks
        assert "BTCUSDT" not in symbols_stocks

    @patch("backend.trade_signals.scan_symbol_signals")
    @patch("backend.trade_signals._get_dynamic_symbols")
    def test_scan_all_signals_filtering(self, mock_get_syms, mock_scan_sym):
        mock_get_syms.return_value = ["BTCUSDT", "TSLABUSDT"]
        mock_scan_sym.side_effect = lambda sym, *args: [
            {
                "symbol": sym,
                "strategy": "Trend Pullback Buy",
                "direction": "LONG",
                "entry_price": 100.0,
                "stop_loss": 95.0,
                "take_profit": 110.0,
                "confidence": 75 if sym == "TSLABUSDT" else 45,
                "bars_ago": 0,
                "asset_class": "STOCK" if sym == "TSLABUSDT" else "CRYPTO",
            }
        ]

        # Scan with min_confidence=50
        signals = scan_all_signals(min_confidence=50, asset_class="ALL")
        assert len(signals) == 1
        assert signals[0]["symbol"] == "TSLABUSDT"
        assert signals[0]["asset_class"] == "STOCK"

        # Scan with asset_class=CRYPTO
        signals_crypto = scan_all_signals(min_confidence=0, asset_class="CRYPTO")
        for s in signals_crypto:
            assert s["asset_class"] == "CRYPTO"

    @patch("backend.trade_signals.scan_symbol_signals")
    @patch("backend.trade_signals._get_dynamic_symbols")
    def test_scan_all_signals_mtf_aligned_only(self, mock_get_syms, mock_scan_sym):
        mock_get_syms.return_value = ["BTCUSDT", "ETHUSDT"]
        mock_scan_sym.side_effect = lambda sym, *args: [
            {
                "symbol": sym,
                "strategy": "RSI Divergence",
                "direction": "LONG",
                "entry_price": 50000.0,
                "stop_loss": 48000.0,
                "take_profit": 54000.0,
                "confidence": 70,
                "bars_ago": 0,
                "asset_class": "CRYPTO",
                "htf_bias": "BULL" if sym == "BTCUSDT" else "BEAR",
                "htf_aligned": True if sym == "BTCUSDT" else False,
            }
        ]

        # Scan with mtf_aligned_only=True
        aligned_signals = scan_all_signals(min_confidence=0, asset_class="ALL", mtf_aligned_only=True)
        assert len(aligned_signals) == 1
        assert aligned_signals[0]["symbol"] == "BTCUSDT"
        assert aligned_signals[0]["htf_aligned"] is True

        # Scan with mtf_aligned_only=False
        all_signals = scan_all_signals(min_confidence=0, asset_class="ALL", mtf_aligned_only=False)
        assert len(all_signals) == 2

    @patch("backend.trade_signals.scan_symbol_signals")
    @patch("backend.trade_signals._get_dynamic_symbols")
    def test_scan_all_signals_quality_and_best_per_symbol(self, mock_get_syms, mock_scan_sym):
        mock_get_syms.return_value = ["BTCUSDT", "ETHUSDT"]

        def make_signal(symbol, strategy, quality, confidence=70):
            return {
                "symbol": symbol,
                "strategy": strategy,
                "direction": "LONG",
                "entry_price": 100.0,
                "stop_loss": 95.0,
                "take_profit": 110.0,
                "confidence": confidence,
                "quality_score": quality,
                "bars_ago": 0,
                "asset_class": "CRYPTO",
            }

        mock_scan_sym.side_effect = lambda sym, *args: (
            [make_signal(sym, "Strong", 82), make_signal(sym, "Weak", 55)]
            if sym == "BTCUSDT"
            else [make_signal(sym, "Medium", 74)]
        )

        filtered = scan_all_signals(min_confidence=0, asset_class="ALL", min_quality=70)
        assert len(filtered) == 2
        assert all(s["quality_score"] >= 70 for s in filtered)
        assert filtered[0]["strategy"] == "Strong"

        best = scan_all_signals(min_confidence=0, asset_class="ALL", best_per_symbol=True)
        assert len(best) == 2
        assert len({s["symbol"] for s in best}) == 2
        by_symbol = {s["symbol"]: s for s in best}
        assert by_symbol["BTCUSDT"]["strategy"] == "Strong"

    def test_regime_fit_and_quality_grade(self):
        assert _regime_fit("MEAN_REVERSION", "LONG", "BULL_RANGE") == "ALIGNED"
        assert _regime_fit("MEAN_REVERSION", "LONG", "BULL_TREND") == "CONFLICT"
        assert _regime_fit("TREND", "LONG", "BULL_TREND") == "ALIGNED"
        assert _regime_fit("TREND", "SHORT", "BULL_TREND") == "CONFLICT"
        assert _quality_grade(82) == "A+"
        assert _quality_grade(72) == "A"
        assert _quality_grade(60) == "B"
        assert _quality_grade(40) == "C"
