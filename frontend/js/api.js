class CryptoAPI {
    constructor(baseURL = "") {
        this.baseURL = baseURL;
    }

    async getMarketSummary() {
        try {
            const response = await fetch(`${this.baseURL}/api/market-summary`);
            if (!response.ok) throw new Error("Failed to fetch market summary");
            return await response.json();
        } catch (error) {
            console.warn("Backend market summary error, attempting fallback", error);
            return null;
        }
    }

    async getScreenerData(interval = "1h", category = "ALL", minVolume = 0) {
        try {
            const params = new URLSearchParams({ interval, category, min_volume: minVolume });
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
            const response = await fetch(`${this.baseURL}/api/klines/${symbol}?interval=${interval}&limit=${limit}`);
            if (!response.ok) throw new Error(`Failed to fetch klines for ${symbol}`);
            return await response.json();
        } catch (error) {
            console.error("Backend klines API error:", error);
            return null;
        }
    }

    async getTradeSignals(interval = "1h", rr = "1:2.0", lookback = 3, minConfidence = 0) {
        try {
            const params = new URLSearchParams({
                interval,
                rr,
                lookback,
                min_confidence: minConfidence,
            });
            const response = await fetch(`${this.baseURL}/api/trade-signals?${params}`);
            if (!response.ok) throw new Error("Failed to fetch trade signals");
            return await response.json();
        } catch (error) {
            console.error("Backend trade-signals API error:", error);
            return { signals: [] };
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

    async getBotJournal(limit = 50) {
        try {
            const response = await fetch(`${this.baseURL}/api/bot/journal?limit=${limit}`);
            if (!response.ok) throw new Error("Failed to fetch journal");
            return await response.json();
        } catch (error) {
            console.error("Bot journal error:", error);
            return { entries: [] };
        }
    }
}

window.cryptoAPI = new CryptoAPI();
