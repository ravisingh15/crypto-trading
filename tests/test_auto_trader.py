import pytest
from unittest.mock import patch
from backend.auto_trader import AutoTrader, format_quantity, format_price
from backend.position_tracker import PositionTracker


class TestAutoTraderConfig:
    def test_default_config_fields(self):
        trader = AutoTrader()
        cfg = trader.config
        assert "asset_filter" in cfg
        assert cfg["asset_filter"] == "all"
        assert cfg["paper_mode"] is True
        assert cfg["market_type"] in ["futures", "spot"]
        assert cfg["amount_per_trade"] > 0
        assert cfg["max_positions"] > 0
        assert "total_capital" in cfg
        assert cfg["total_capital"] >= 100
        assert "sizing_mode" in cfg
        assert cfg["sizing_mode"] in ["fixed", "percent_capital", "risk_pct"]
        assert "daily_profit_target" in cfg
        assert "strategy_filter" in cfg
        assert "mtf_filter_enabled" in cfg
        assert cfg["mtf_filter_enabled"] is True
        assert "breakeven_stop_enabled" in cfg
        assert cfg["breakeven_stop_enabled"] is True

    def test_update_config(self):
        trader = AutoTrader()
        trader.update_config({
            "asset_filter": "stocks",
            "amount_per_trade": 100,
            "max_positions": 5,
            "paper_mode": False,
            "total_capital": 5000,
            "sizing_mode": "percent_capital",
            "trade_size_pct": 10.0,
            "trailing_stop_enabled": True,
            "trailing_stop_callback_pct": 2.0,
            "strategy_filter": "RSI",
            "mtf_filter_enabled": False,
            "breakeven_stop_enabled": False,
        })
        cfg = trader.config
        assert cfg["asset_filter"] == "stocks"
        assert cfg["amount_per_trade"] == 100
        assert cfg["max_positions"] == 5
        assert cfg["paper_mode"] is False
        assert cfg["total_capital"] == 5000
        assert cfg["sizing_mode"] == "percent_capital"
        assert cfg["trade_size_pct"] == 10.0
        assert cfg["trailing_stop_enabled"] is True
        assert cfg["trailing_stop_callback_pct"] == 2.0
        assert cfg["strategy_filter"] == "RSI"
        assert cfg["mtf_filter_enabled"] is False
        assert cfg["breakeven_stop_enabled"] is False


class TestAutoTraderSizingCalculations:
    def test_calculate_trade_amount_fixed(self):
        trader = AutoTrader()
        trader.update_config({"sizing_mode": "fixed", "amount_per_trade": 75.0})
        signal = {"symbol": "BTCUSDT", "direction": "BUY", "entry_price": 60000, "stop_loss": 58000}
        amount = trader._calculate_trade_amount(signal)
        assert amount == 75.0

    def test_calculate_trade_amount_percent_capital(self):
        trader = AutoTrader()
        trader.update_config({
            "sizing_mode": "percent_capital",
            "total_capital": 2000.0,
            "trade_size_pct": 5.0  # 5% of 2000 = 100
        })
        signal = {"symbol": "ETHUSDT", "direction": "BUY", "entry_price": 3000, "stop_loss": 2900}
        amount = trader._calculate_trade_amount(signal)
        assert amount == 100.0

    def test_calculate_trade_amount_risk_pct(self):
        trader = AutoTrader()
        trader.update_config({
            "sizing_mode": "risk_pct",
            "total_capital": 1000.0,
            "risk_per_trade_pct": 2.0  # $20 risk budget
        })
        # Entry 100, SL 95 -> 5% SL distance. Position size = 20 / 0.05 = 400.
        signal = {"symbol": "SOLUSDT", "direction": "BUY", "entry_price": 100.0, "stop_loss": 95.0}
        amount = trader._calculate_trade_amount(signal)
        assert amount == 400.0


class TestAutoTraderSquareOffAndTrailing:
    def test_square_off_position_and_all(self):
        tracker = PositionTracker()
        # Clear existing
        tracker.square_off_all("TEST_CLEANUP")

        # Open a simulated paper position
        tracker.add_position(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.01,
            entry_price=50000.0,
            amount_usdt=50.0,
            sl=48000.0,
            tp=54000.0,
            paper=True,
            strategy="TEST"
        )
        assert tracker.count() == 1

        # Test single square off
        res = tracker.square_off_position("BTCUSDT", "MANUAL_TEST")
        assert res is not None
        assert res["symbol"] == "BTCUSDT"
        assert res["exit_type"] == "MANUAL_TEST"
        assert tracker.count() == 0

        # Open 2 positions and square off all
        tracker.add_position(
            symbol="ETHUSDT",
            side="BUY",
            quantity=0.05,
            entry_price=3000.0,
            amount_usdt=50.0,
            sl=2800.0,
            tp=3400.0,
            paper=True
        )
        tracker.add_position(
            symbol="SOLUSDT",
            side="SELL",
            quantity=0.5,
            entry_price=150.0,
            amount_usdt=50.0,
            sl=160.0,
            tp=130.0,
            paper=True
        )
        assert tracker.count() == 2

        all_res = tracker.square_off_all("SQUARE_OFF_ALL_TEST")
        assert len(all_res) == 2
        assert tracker.count() == 0

    def test_trailing_stop_ratchet(self):
        tracker = PositionTracker()
        tracker.square_off_all("TEST_CLEANUP")

        tracker.add_position(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.01,
            entry_price=50000.0,
            amount_usdt=50.0,
            sl=48000.0,
            tp=100000.0,
            paper=True
        )
        # Update trailing stop with 2% callback offset
        events = tracker.update_trailing_stops(callback_pct=2.0)
        assert len(events) == 1
        assert events[0]["symbol"] == "BTCUSDT"
        assert events[0]["new_sl"] > 48000.0

        pos = tracker.get_position("BTCUSDT")
        assert pos["trailing_sl"] == events[0]["new_sl"]

        # Cleanup
        tracker.square_off_all("TEST_CLEANUP")

    def test_breakeven_stop_ratchet(self):
        tracker = PositionTracker()
        tracker.square_off_all("TEST_CLEANUP")

        # Risk distance = 100 - 90 = 10. +1R target = 110.
        tracker.add_position(
            symbol="TESTUSDT",
            side="BUY",
            quantity=1.0,
            entry_price=100.0,
            amount_usdt=100.0,
            sl=90.0,
            tp=120.0,
            paper=True
        )

        # Simulate price moving to 110.5 (+1.05R profit) via _get_price mock
        with patch.object(tracker, "_get_price", return_value=110.5):
            events = tracker.update_trailing_stops(callback_pct=15.0, breakeven_enabled=True)
            assert len(events) == 1
            assert events[0]["symbol"] == "TESTUSDT"
            assert events[0]["type"] == "BREAKEVEN"
            assert events[0]["new_sl"] >= 100.0  # At or above entry

            pos = tracker.get_position("TESTUSDT")
            assert pos["at_breakeven"] is True
            assert pos["trailing_sl"] >= 100.0

        # Cleanup
        tracker.square_off_all("TEST_CLEANUP")

    @patch("backend.auto_trader.scan_all_signals")
    def test_mtf_trend_filter_rejection(self, mock_scan):
        from backend.position_tracker import position_tracker
        trader = AutoTrader()
        position_tracker.square_off_all("TEST_CLEANUP")
        trader.update_config({"mtf_filter_enabled": True, "paper_mode": True})

        # Signal with counter-trend (htf_aligned = False)
        mock_scan.return_value = [
            {
                "symbol": "BTCUSDT",
                "direction": "LONG",
                "strategy": "Trend Pullback Buy",
                "entry_price": 60000.0,
                "stop_loss": 58000.0,
                "take_profit": 64000.0,
                "confidence": 75,
                "bars_ago": 0,
                "asset_class": "CRYPTO",
                "htf_bias": "BEAR",
                "htf_aligned": False,
                "htf_interval": "4h",
            }
        ]

        result = trader.run_manual_scan()
        assert result["status"] == "scan_completed"
        # The counter-trend signal should be filtered out, so no position is opened
        assert position_tracker.count() == 0


class TestAutoTraderFormatting:
    def test_format_quantity_step_size(self):
        assert format_quantity(1.234567, 0.001) == 1.234
        assert format_quantity(10.999, 1.0) == 10.0
        assert format_quantity(0.0055, 0.01) == 0.0

    def test_format_price_tick_size(self):
        assert format_price(123.456, 0.01) == 123.46
        assert format_price(123.454, 0.01) == 123.45
        assert format_price(1050.2, 0.5) == 1050.0

