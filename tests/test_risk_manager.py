import pytest
from datetime import datetime, timezone, timedelta
from backend.risk_manager import RiskManager


@pytest.fixture
def risk_mgr():
    return RiskManager({
        "max_positions": 3,
        "max_daily_loss": 50,
        "cooldown_hours": 4,
        "max_total_exposure": 500,
        "max_sector_positions": 2,
    })


class TestRiskManagerGates:
    def test_max_positions_gate(self, risk_mgr):
        open_pos = [{"symbol": "BTCUSDT"}, {"symbol": "ETHUSDT"}, {"symbol": "SOLUSDT"}]
        can_trade, reason = risk_mgr.can_trade("TSLABUSDT", 50, open_pos, [], 0)
        assert can_trade is False
        assert "Max positions reached" in reason

    def test_daily_loss_gate(self, risk_mgr):
        can_trade, reason = risk_mgr.can_trade("BTCUSDT", 50, [], [], -60.0)
        assert can_trade is False
        assert "Daily loss limit hit" in reason

    def test_duplicate_symbol_gate(self, risk_mgr):
        open_pos = [{"symbol": "TSLABUSDT", "amount_usdt": 50}]
        can_trade, reason = risk_mgr.can_trade("TSLABUSDT", 50, open_pos, [], 0)
        assert can_trade is False
        assert "Already have open position in TSLABUSDT" in reason

    def test_sector_concentration_stocks(self, risk_mgr):
        # Magnificent 7 positions: AAPL, NVDA (2 positions)
        open_pos = [
            {"symbol": "AAPLBUSDT", "amount_usdt": 50},
            {"symbol": "NVDABUSDT", "amount_usdt": 50},
        ]
        # Trying to open 3rd Magnificent 7 (TSLA) -> should be blocked by sector limit (max 2)
        can_trade, reason = risk_mgr.can_trade("TSLABUSDT", 50, open_pos, [], 0)
        assert can_trade is False
        assert "Sector limit reached" in reason
        assert "Magnificent 7" in reason

        # Trying to open Crypto Equities (MSTR) -> should be allowed
        can_trade_mstr, _ = risk_mgr.can_trade("MSTRBUSDT", 50, open_pos, [], 0)
        assert can_trade_mstr is True

    def test_total_notional_exposure(self, risk_mgr):
        # max_total_exposure = 500
        open_pos = [
            {"symbol": "BTCUSDT", "amount_usdt": 100, "leverage": 4},  # 400 exposure
        ]
        # Adding $50 with 5x leverage -> 250 new exposure -> total 650 > 500
        can_trade, reason = risk_mgr.can_trade("ETHUSDT", 50, open_pos, [], 0, leverage=5)
        assert can_trade is False
        assert "Total exposure would be" in reason
