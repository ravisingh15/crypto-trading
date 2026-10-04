class CryptoAPI {
    constructor(baseURL = "") {
        this.baseURL = baseURL;
    }

    async getMarketSummary(assetClass = "ALL") {
        try {
            const params = new URLSearchParams({ asset_class: assetClass });
            const response = await fetch(`${this.baseURL}/api/market-summary?${params}`);
            if (!response.ok) throw new Error("Failed to fetch market summary");
            return await response.json();
        } catch (error) {
            console.warn("Backend market summary error, attempting fallback", error);
            return null;
        }
    }

    async getStocksSummary() {
        try {
            const response = await fetch(`${this.baseURL}/api/stocks/summary`);
            if (!response.ok) throw new Error("Failed to fetch stocks summary");
            return await response.json();
        } catch (error) {
            console.error("Backend stocks summary error:", error);
            return null;
        }
    }

    async getMacroSummary() {
        try {
            const response = await fetch(`${this.baseURL}/api/macro/summary`);
            if (!response.ok) throw new Error("Failed to fetch macro summary");
            return await response.json();
        } catch (error) {
            console.error("Backend macro summary error:", error);
            return null;
        }
    }


    async getScreenerData(interval = "1h", category = "ALL", assetClass = "ALL", minVolume = 0) {
        try {
            const params = new URLSearchParams({ interval, category, asset_class: assetClass, min_volume: minVolume });
            const response = await fetch(`${this.baseURL}/api/screener?${params}`);
            if (!response.ok) throw new Error("Failed to fetch screener data");
            return await response.json();
        } catch (error) {
            console.error("Backend screener API error:", error);
            return { data: [] };
        }
    }

    async getSymbolKlines(symbol, interval = "1h", limit = 100) {
        try {
            const response = await fetch(`${this.baseURL}/api/klines/${encodeURIComponent(symbol)}?interval=${interval}&limit=${limit}`);
            if (!response.ok) throw new Error(`Failed to fetch klines for ${symbol}`);
            return await response.json();
        } catch (error) {
            console.error("Backend klines API error:", error);
            return null;
        }
    }

    async getTradeSignals(interval = "1h", rr = "1:2.0", lookback = 3, minConfidence = 0, assetClass = "ALL", mtfAligned = false) {
        try {
            const params = new URLSearchParams({
                interval,
                rr,
                lookback,
                min_confidence: minConfidence,
                asset_class: assetClass,
                mtf_aligned: mtfAligned,
            });
            const response = await fetch(`${this.baseURL}/api/trade-signals?${params}`);
            if (!response.ok) throw new Error("Failed to fetch trade signals");
            return await response.json();
        } catch (error) {
            console.error("Backend trade-signals API error:", error);
            return { signals: [] };
        }
    }

    async getHighDeltaFutures(minVolume = 5000000, minNatr = 0.5, limit = 40, lookbackBars = 12, forceRefresh = false) {
        try {
            const params = new URLSearchParams({
                min_volume: minVolume,
                min_natr: minNatr,
                limit: limit,
                lookback_bars: lookbackBars,
                force_refresh: forceRefresh,
            });
            const response = await fetch(`${this.baseURL}/api/futures/high-delta?${params}`);
            if (!response.ok) throw new Error("Failed to fetch high delta futures");
            return await response.json();
        } catch (error) {
            console.error("Backend high delta futures error:", error);
            return { count: 0, results: [] };
        }
    }

    async getWallet() {
        try {
            const response = await fetch(`${this.baseURL}/api/wallet`);
            if (!response.ok) throw new Error("Failed to fetch wallet");

            return await response.json();
        } catch (error) {
            console.error("Wallet API error:", error);
            return { error: error.message };
        }
    }

    async placeOrder(orderData) {
        try {
            const response = await fetch(`${this.baseURL}/api/order`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(orderData),
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || "Order failed");
            return result;
        } catch (error) {
            console.error("Order API error:", error);
            return { error: error.message };
        }
    }

    async getOpenOrders(symbol = null) {
        try {
            const params = symbol ? `?symbol=${symbol}` : "";
            const response = await fetch(`${this.baseURL}/api/orders/open${params}`);
            if (!response.ok) throw new Error("Failed to fetch open orders");
            return await response.json();
        } catch (error) {
            console.error("Open orders API error:", error);
            return { orders: [] };
        }
    }

    async cancelOrder(symbol, orderId) {
        try {
            const response = await fetch(`${this.baseURL}/api/order/${symbol}/${orderId}`, {
                method: "DELETE",
            });
            if (!response.ok) throw new Error("Failed to cancel order");
            return await response.json();
        } catch (error) {
            console.error("Cancel order API error:", error);
            return { error: error.message };
        }
    }

    // ================================================
    // Bot Auto-Trader API
    // ================================================

    async startBot() {
        try {
            const response = await fetch(`${this.baseURL}/api/bot/start`, { method: "POST" });
            return await response.json();
        } catch (error) {
            console.error("Bot start error:", error);
            return { error: error.message };
        }
    }

    async stopBot() {
        try {
            const response = await fetch(`${this.baseURL}/api/bot/stop`, { method: "POST" });
            return await response.json();
        } catch (error) {
            console.error("Bot stop error:", error);
            return { error: error.message };
        }
    }

    async getBotStatus() {
        try {
            const response = await fetch(`${this.baseURL}/api/bot/status`);
            if (!response.ok) throw new Error("Failed to fetch bot status");
            return await response.json();
        } catch (error) {
            console.error("Bot status error:", error);
            return { error: error.message };
        }
    }

    async updateBotConfig(config) {
        try {
            const response = await fetch(`${this.baseURL}/api/bot/config`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(config),
            });
            return await response.json();
        } catch (error) {
            console.error("Bot config error:", error);
            return { error: error.message };
        }
    }

    async squareOffAll() {
        try {
            const response = await fetch(`${this.baseURL}/api/bot/square-off-all`, { method: "POST" });
            return await response.json();
        } catch (error) {
            console.error("Square off all error:", error);
            return { error: error.message };
        }
    }

    async squareOffPosition(symbol) {
        try {
            const response = await fetch(`${this.baseURL}/api/bot/square-off/${encodeURIComponent(symbol)}`, { method: "POST" });
            return await response.json();
        } catch (error) {
            console.error(`Square off ${symbol} error:`, error);
            return { error: error.message };
        }
    }

    async emergencyStopBot() {
        try {
            const response = await fetch(`${this.baseURL}/api/bot/emergency-stop`, { method: "POST" });
            return await response.json();
        } catch (error) {
            console.error("Emergency stop error:", error);
            return { error: error.message };
        }
    }

    async scanBotNow() {
        try {
            const response = await fetch(`${this.baseURL}/api/bot/scan-now`, { method: "POST" });
            return await response.json();
        } catch (error) {
            console.error("Manual scan error:", error);
            return { error: error.message };
        }
    }

    async clearBotJournal() {
        try {
            const response = await fetch(`${this.baseURL}/api/bot/journal`, { method: "DELETE" });
            return await response.json();
        } catch (error) {
            console.error("Clear journal error:", error);
            return { error: error.message };
        }
    }

    async getBotAnalytics() {
        try {
            const response = await fetch(`${this.baseURL}/api/bot/analytics`);
            if (!response.ok) throw new Error("Failed to fetch bot analytics");
            return await response.json();
        } catch (error) {
            console.error("Bot analytics error:", error);
            return { error: error.message };
        }
    }
}

window.cryptoAPI = new CryptoAPI();

