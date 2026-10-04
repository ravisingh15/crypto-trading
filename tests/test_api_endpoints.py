import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from backend.app import app


@pytest.fixture
def client():
    return TestClient(app)


class TestAPIEndpoints:
    def test_health_check(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_market_summary_all(self, client):
        r = client.get("/api/market-summary?asset_class=ALL")
        assert r.status_code == 200
        data = r.json()
        assert "total_pairs_tracked" in data
        assert "crypto_pairs_count" in data
        assert "stock_pairs_count" in data
        assert "top_volume" in data

    def test_stocks_summary_dedicated(self, client):
        r = client.get("/api/stocks/summary")
        assert r.status_code == 200
        data = r.json()
        assert "total_stocks" in data
        assert "magnificent_7" in data
        assert "crypto_equities" in data
        assert "etfs" in data

    def test_screener_stocks(self, client):
        r = client.get("/api/screener?asset_class=STOCKS&interval=1h")
        assert r.status_code == 200
        data = r.json()
        assert "total_results" in data
        assert "data" in data
        if data["total_results"] > 0:
            item = data["data"][0]
            assert item["asset_class"] == "STOCK"
            assert "score" in item
            assert "recommendation" in item

    def test_klines_friendly_ticker(self, client):
        r = client.get("/api/klines/TSLA?interval=1h&limit=10")
        assert r.status_code == 200
        data = r.json()
        assert data["symbol"] == "TSLABUSDT"
        assert data["display_ticker"] == "TSLA"
        assert data["asset_class"] == "STOCK"
        assert len(data["klines"]) > 0

    def test_trade_signals(self, client):
        r = client.get("/api/trade-signals?asset_class=ALL&interval=1h")
        assert r.status_code == 200
        data = r.json()
        assert "signals" in data
        assert "total_signals" in data

    def test_5m_screener_and_signals(self, client):
        r_scr = client.get("/api/screener?interval=5m&asset_class=CRYPTO")
        assert r_scr.status_code == 200
        data_scr = r_scr.json()
        assert "data" in data_scr

        r_sig = client.get("/api/trade-signals?interval=5m&asset_class=ALL")
        assert r_sig.status_code == 200
        data_sig = r_sig.json()
        assert data_sig["interval"] == "5m"
        assert "signals" in data_sig


    def test_bot_status(self, client):
        r = client.get("/api/bot/status")
        assert r.status_code == 200
        data = r.json()
        assert "running" in data
        assert "config" in data
        assert "stats" in data
        assert "total_capital" in data
        assert "deployed_capital" in data
        assert "free_capital" in data

    def test_bot_config_update(self, client):
        r = client.post("/api/bot/config", json={
            "asset_filter": "stocks",
            "amount_per_trade": 75.0,
            "min_confidence": 65,
            "total_capital": 2500.0,
            "sizing_mode": "percent_capital",
            "trade_size_pct": 8.0,
            "daily_profit_target": 150.0,
            "trailing_stop_enabled": True,
            "trailing_stop_callback_pct": 1.8,
            "strategy_filter": "MACD"
        })
        assert r.status_code == 200
        data = r.json()
        assert data["config"]["asset_filter"] == "stocks"
        assert data["config"]["amount_per_trade"] == 75.0
        assert data["config"]["total_capital"] == 2500.0
        assert data["config"]["sizing_mode"] == "percent_capital"
        assert data["config"]["trade_size_pct"] == 8.0
        assert data["config"]["daily_profit_target"] == 150.0
        assert data["config"]["trailing_stop_enabled"] is True
        assert data["config"]["strategy_filter"] == "MACD"

    def test_bot_actions_and_analytics(self, client):
        # Test scan now
        r_scan = client.post("/api/bot/scan-now")
        assert r_scan.status_code == 200
        assert r_scan.json()["status"] == "scan_completed"

        # Test square off all
        r_sq = client.post("/api/bot/square-off-all")
        assert r_sq.status_code == 200
        assert r_sq.json()["status"] == "squared_off_all"

        # Test emergency stop
        r_em = client.post("/api/bot/emergency-stop")
        assert r_em.status_code == 200
        assert r_em.json()["status"] == "emergency_stopped"

        # Test analytics
        r_an = client.get("/api/bot/analytics")
        assert r_an.status_code == 200
        data_an = r_an.json()
        assert "win_rate_pct" in data_an
        assert "total_realized_pnl" in data_an

        # Test clear journal
        r_del = client.delete("/api/bot/journal")
        assert r_del.status_code == 200
        assert "message" in r_del.json()


    def test_macro_summary_endpoint(self, client):
        r = client.get("/api/macro/summary")
        assert r.status_code == 200
        data = r.json()
        assert "crypto_benchmark" in data
        assert "equity_benchmark" in data
        assert "regime" in data["crypto_benchmark"]
        assert "regime" in data["equity_benchmark"]

    def test_frontend_static_routes(self, client):
        r_root = client.get("/")
        assert r_root.status_code == 200
        assert "CYPHER" in r_root.text or "Screener" in r_root.text

    def test_app_config_endpoint(self, client):
        r = client.get("/api/config")
        assert r.status_code == 200
        data = r.json()
        assert "screener_only" in data
        assert "has_keys" in data
        assert "auth_enabled" in data

    def test_screener_only_blocks_order(self, client):
        with patch("backend.app.SCREENER_ONLY_MODE", True):
            r = client.post("/api/order", json={
                "symbol": "BTCUSDT",
                "side": "BUY",
                "amount": 50.0
            })
            assert r.status_code == 403
            assert "Screener-only mode is active" in r.json()["error"]



