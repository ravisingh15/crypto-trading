document.addEventListener("DOMContentLoaded", () => {
    let currentScreenerData = [];
    let currentSortColumn = "score";
    let currentSortAscending = false;
    let selectedSymbolData = null;
    let currentAssetClass = "ALL";

    const chartRenderer = new CanvasCandleChart('candle-chart');

    // DOM Elements
    const searchInput = document.getElementById("search-input");
    const categorySelect = document.getElementById("category-select");
    const timeframeSelect = document.getElementById("timeframe-select");
    const signalFilterSelect = document.getElementById("signal-filter-select");
    const tableBody = document.getElementById("table-body");
    const recordsCount = document.getElementById("records-count");
    const btnRefresh = document.getElementById("btn-refresh");
    const btnScreenerRefresh = document.getElementById("btn-screener-refresh");
    const autoRefreshSelect = document.getElementById("auto-refresh-select");
    const lastRefreshedTimeEl = document.getElementById("last-refreshed-time");
    let lastRefreshedDate = null;
    let autoRefreshTimer = null;

    // Ticker & Stats
    const liveTickerStrip = document.getElementById("live-ticker-strip");
    const topVolSymbol = document.getElementById("top-vol-symbol");
    const topVolVal = document.getElementById("top-vol-val");
    const topGainerSymbol = document.getElementById("top-gainer-symbol");
    const topGainerVal = document.getElementById("top-gainer-val");
    const strongBuyCount = document.getElementById("strong-buy-count");
    const sentimentVal = document.getElementById("sentiment-val");
    const sentimentSub = document.getElementById("sentiment-sub");

    // Macro Ribbon Elements
    const macroBtcRegime = document.getElementById("macro-btc-regime");
    const macroSpyRegime = document.getElementById("macro-spy-regime");
    const breadthProgressFill = document.getElementById("breadth-progress-fill");
    const breadthPctLabel = document.getElementById("breadth-pct-label");
    const macroPhaseLabel = document.getElementById("macro-phase-label");

    // Modal Elements
    const chartModal = document.getElementById("chart-modal");
    const modalSymbol = document.getElementById("modal-symbol");
    const modalCompanyName = document.getElementById("modal-company-name");
    const modalAssetClass = document.getElementById("modal-asset-class");
    const modalCategory = document.getElementById("modal-category");
    const modalRecommendation = document.getElementById("modal-recommendation");
    const modalSignalsList = document.getElementById("modal-signals-list");
    const btnCloseModal = document.getElementById("btn-close-modal");

    // Risk Calculator
    const calcAccount = document.getElementById("calc-account");
    const calcRisk = document.getElementById("calc-risk");
    const calcPosSize = document.getElementById("calc-pos-size");
    const calcSlTarget = document.getElementById("calc-sl-target");
    const calcTpTarget = document.getElementById("calc-tp-target");

    // Asset Class Switcher Listeners
    document.querySelectorAll(".asset-pill").forEach(pill => {
        pill.addEventListener("click", () => {
            document.querySelectorAll(".asset-pill").forEach(p => p.classList.remove("active"));
            pill.classList.add("active");
            currentAssetClass = pill.dataset.asset || "ALL";
            refreshData(true);
        });
    });

    // Event Listeners
    if (btnRefresh) {
        btnRefresh.addEventListener("click", () => {
            fetchMarketSummary();
            fetchMacroSummary();
            refreshData(true);
        });
    }
    if (btnScreenerRefresh) {
        btnScreenerRefresh.addEventListener("click", () => {
            refreshData(true);
        });
    }
    if (autoRefreshSelect) {
        autoRefreshSelect.addEventListener("change", setupAutoRefresh);
    }
    categorySelect.addEventListener("change", () => refreshData(true));
    timeframeSelect.addEventListener("change", () => refreshData(true));
    signalFilterSelect.addEventListener("change", renderTable);
    searchInput.addEventListener("input", renderTable);
    btnCloseModal.addEventListener("click", closeModal);

    calcAccount.addEventListener("input", updateRiskCalculator);
    calcRisk.addEventListener("input", updateRiskCalculator);

    // Sort Headers Click Listener
    document.querySelectorAll("th.sortable").forEach(th => {
        th.addEventListener("click", () => {
            const col = th.dataset.sort;
            if (currentSortColumn === col) {
                currentSortAscending = !currentSortAscending;
            } else {
                currentSortColumn = col;
                currentSortAscending = false;
            }
            renderTable();
        });
    });

    // Initial Load
    fetchMarketSummary();
    fetchMacroSummary();
    refreshData(true);
    setupAutoRefresh();

    // Live relative timestamp updater every second
    setInterval(renderLastRefreshed, 1000);

    function updateLastRefreshedTimestamp() {
        lastRefreshedDate = new Date();
        renderLastRefreshed();
    }

    function renderLastRefreshed() {
        if (!lastRefreshedTimeEl) return;
        if (!lastRefreshedDate) {
            lastRefreshedTimeEl.textContent = "Updating...";
            return;
        }
        const now = new Date();
        const diffSec = Math.max(0, Math.floor((now - lastRefreshedDate) / 1000));
        const timeStr = lastRefreshedDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

        let agoStr = '';
        if (diffSec < 5) {
            agoStr = 'Just now';
        } else if (diffSec < 60) {
            agoStr = `${diffSec}s ago`;
        } else if (diffSec < 3600) {
            const m = Math.floor(diffSec / 60);
            agoStr = `${m}m ago`;
        } else {
            const h = Math.floor(diffSec / 3600);
            agoStr = `${h}h ago`;
        }

        lastRefreshedTimeEl.textContent = `Updated: ${timeStr} (${agoStr})`;
        lastRefreshedTimeEl.title = `Last refreshed at ${lastRefreshedDate.toLocaleString()}`;
    }

    function setupAutoRefresh() {
        if (autoRefreshTimer) {
            clearInterval(autoRefreshTimer);
            autoRefreshTimer = null;
        }

        const intervalVal = autoRefreshSelect ? autoRefreshSelect.value : "60000";
        if (intervalVal === "off") return;

        const ms = parseInt(intervalVal, 10) || 60000;
        autoRefreshTimer = setInterval(() => {
            fetchMarketSummary();
            fetchMacroSummary();
            refreshData(false);
        }, ms);
    }

    async function fetchMacroSummary() {
        try {
            const macro = await window.cryptoAPI.getMacroSummary();
            if (!macro) return;

            if (macro.crypto_benchmark && macroBtcRegime) {
                const btc = macro.crypto_benchmark;
                macroBtcRegime.textContent = btc.regime.replace(/_/g, ' ');
                macroBtcRegime.className = `macro-regime-pill ${btc.regime.toLowerCase().replace(/_/g, '-')}`;
            }

            if (macro.equity_benchmark && macroSpyRegime) {
                const spy = macro.equity_benchmark;
                macroSpyRegime.textContent = spy.regime.replace(/_/g, ' ');
                macroSpyRegime.className = `macro-regime-pill ${spy.regime.toLowerCase().replace(/_/g, '-')}`;
            }
        } catch (e) {
            console.warn("Error fetching macro summary", e);
        }
    }

    async function fetchMarketSummary() {
        const summary = await window.cryptoAPI.getMarketSummary(currentAssetClass);
        if (!summary) return;

        // Render Live Ticker Pills (mix of top volume crypto & top stocks)
        let pillsData = [];
        if (summary.top_volume && summary.top_volume.length > 0) {
            pillsData = summary.top_volume.slice(0, 4);
        }
        if (summary.top_stock_gainers && summary.top_stock_gainers.length > 0) {
            pillsData = pillsData.concat(summary.top_stock_gainers.slice(0, 3));
        }

        if (pillsData.length > 0) {
            liveTickerStrip.innerHTML = pillsData.map(t => {
                const change = parseFloat(t.priceChangePercent);
                const colorClass = change >= 0 ? 'positive' : 'negative';
                const sign = change >= 0 ? '+' : '';
                const isStock = t.asset_class === "STOCK" || (t.symbol && t.symbol.endsWith("BUSDT") && t.symbol !== "BNBUSDT");
                const displayName = t.stock_ticker || t.symbol.replace('USDT', '').replace('BUSDT', '');
                const pillClass = isStock ? 'ticker-pill stock-pill' : 'ticker-pill';
                const tag = isStock ? '<span style="font-size:9px; color:#c084fc; font-weight:700;">bStock</span>' : '';
                return `
                    <div class="${pillClass}">
                        <span class="symbol">${displayName} ${tag}</span>
                        <span class="price">$${parseFloat(t.lastPrice).toLocaleString()}</span>
                        <span class="${colorClass}">${sign}${change.toFixed(2)}%</span>
                    </div>
                `;
            }).join('');
        }

        // Stats Cards
        if (summary.top_volume && summary.top_volume[0]) {
            const topVol = summary.top_volume[0];
            topVolSymbol.textContent = topVol.stock_ticker || topVol.symbol;
            topVolVal.textContent = `24h Vol: $${(parseFloat(topVol.quoteVolume) / 1e6).toFixed(1)}M`;
        }

        if (summary.top_gainers && summary.top_gainers[0]) {
            const topG = summary.top_gainers[0];
            topGainerSymbol.textContent = topG.stock_ticker || topG.symbol;
            topGainerVal.textContent = `+${parseFloat(topG.priceChangePercent).toFixed(2)}%`;
        }
    }

    async function refreshData(isManual = false) {
        if (isManual || currentScreenerData.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="12" class="loading-cell">
                        <div class="spinner"></div> Scanning Binance pairs &amp; evaluating macro trend regimes...
                    </td>
                </tr>
            `;
        }

        if (btnRefresh) btnRefresh.classList.add('refreshing');
        if (btnScreenerRefresh) btnScreenerRefresh.classList.add('refreshing');

        try {
            const timeframe = timeframeSelect.value;
            const category = categorySelect.value;
            const res = await window.cryptoAPI.getScreenerData(timeframe, category, currentAssetClass);

            currentScreenerData = res.data || [];

            // Update Market Breadth Gauge
            if (res.market_breadth) {
                const mb = res.market_breadth;
                if (breadthProgressFill) breadthProgressFill.style.width = `${mb.pct_above_ema50}%`;
                if (breadthPctLabel) breadthPctLabel.textContent = `${mb.pct_above_ema50}% Bullish (${mb.advancing_pct}% Adv)`;
                if (macroPhaseLabel) macroPhaseLabel.textContent = mb.market_phase;
            }

            updateSentimentStats();
            renderTable();
            updateLastRefreshedTimestamp();
        } catch (err) {
            console.error("Error refreshing screener data:", err);
        } finally {
            if (btnRefresh) btnRefresh.classList.remove('refreshing');
            if (btnScreenerRefresh) btnScreenerRefresh.classList.remove('refreshing');
        }
    }



    function updateSentimentStats() {
        const strongBuy = currentScreenerData.filter(d => d.recommendation === "STRONG BUY").length;
        const buy = currentScreenerData.filter(d => d.recommendation === "BUY").length;
        const sell = currentScreenerData.filter(d => d.recommendation.includes("SELL")).length;

        strongBuyCount.textContent = strongBuy;

        const total = currentScreenerData.length || 1;
        const bullishRatio = ((strongBuy + buy) / total) * 100;

        if (bullishRatio >= 50) {
            sentimentVal.textContent = "BULLISH 🚀";
            sentimentVal.style.color = "var(--green-bull)";
            sentimentSub.textContent = `${bullishRatio.toFixed(0)}% pairs with Buy signals`;
        } else if (bullishRatio <= 20) {
            sentimentVal.textContent = "BEARISH 📉";
            sentimentVal.style.color = "var(--red-bear)";
            sentimentSub.textContent = `${(100 - bullishRatio).toFixed(0)}% neutral/sell bias`;
        } else {
            sentimentVal.textContent = "NEUTRAL ⚖️";
            sentimentVal.style.color = "var(--text-secondary)";
            sentimentSub.textContent = "Balanced market state";
        }
    }

    function renderTable() {
        if (!currentScreenerData || currentScreenerData.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="11" style="text-align:center;">No assets matched the filter criteria.</td></tr>`;
            recordsCount.textContent = "0 Pairs";
            return;
        }

        let filtered = [...currentScreenerData];

        // Search Filter (matches symbol, stock ticker, or company name)
        const query = searchInput.value.trim().toUpperCase();
        if (query) {
            filtered = filtered.filter(item => {
                const sym = (item.symbol || '').toUpperCase();
                const ticker = (item.stock_ticker || '').toUpperCase();
                const name = (item.company_name || '').toUpperCase();
                return sym.includes(query) || ticker.includes(query) || name.includes(query);
            });
        }

        // Signal Filter
        const signalFilter = signalFilterSelect.value;
        if (signalFilter === "STRONG BUY") {
            filtered = filtered.filter(item => item.recommendation === "STRONG BUY");
        } else if (signalFilter === "BUY") {
            filtered = filtered.filter(item => item.recommendation === "STRONG BUY" || item.recommendation === "BUY");
        } else if (signalFilter === "SELL") {
            filtered = filtered.filter(item => item.recommendation.includes("SELL"));
        }

        // Sorting
        filtered.sort((a, b) => {
            let valA = a[currentSortColumn];
            let valB = b[currentSortColumn];

            if (typeof valA === "string") {
                valA = valA.toLowerCase();
                valB = valB.toLowerCase();
            }

            if (valA < valB) return currentSortAscending ? -1 : 1;
            if (valA > valB) return currentSortAscending ? 1 : -1;
            return 0;
        });

        recordsCount.textContent = `Showing ${filtered.length} Pairs`;

        tableBody.innerHTML = filtered.map(item => {
            const priceChangeClass = item.price_change_24h >= 0 ? "positive" : "negative";
            const priceChangeSign = item.price_change_24h >= 0 ? "+" : "";
            const volFormatted = (item.quote_volume_24h / 1e6).toFixed(2) + "M";

            let recBadge = "badge-neutral";
            if (item.recommendation === "STRONG BUY") recBadge = "badge-strong-buy";
            else if (item.recommendation === "BUY") recBadge = "badge-buy";
            else if (item.recommendation.includes("SELL")) recBadge = "badge-sell";

            // RSI Color Code
            let rsiClass = "";
            if (item.rsi < 30) rsiClass = "positive";
            else if (item.rsi > 70) rsiClass = "negative";

            const isStock = item.asset_class === "STOCK";
            const assetBadgeClass = isStock ? "badge-stock" : "badge-crypto";
            const assetBadgeText = isStock ? "US STOCK" : "CRYPTO";
            const displayName = item.stock_ticker || item.symbol.replace("USDT", "");
            const companySub = item.company_name && item.company_name !== displayName ? item.company_name : item.symbol;

            // RS Alpha Badge
            let rsBadgeClass = "badge-rs-neutral";
            let rsIcon = "⚖️";
            const rsRating = item.rs_rating || 50;
            if (item.rs_status === "ALPHA_LEADER") {
                rsBadgeClass = "badge-rs-leader";
                rsIcon = "💎";
            } else if (item.rs_status === "OUTPERFORMING") {
                rsBadgeClass = "badge-rs-outperform";
                rsIcon = "📈";
            } else if (item.rs_status === "LAGGING" || item.rs_status === "UNDERPERFORMING") {
                rsBadgeClass = "badge-rs-lag";
                rsIcon = "📉";
            }

            return `
                <tr>
                    <td>
                        <div class="symbol-col-wrap">
                            <div class="symbol-main-row">
                                <strong>${displayName}</strong>
                                <span class="badge-asset ${assetBadgeClass}">${assetBadgeText}</span>
                            </div>
                            <span class="company-subtext" title="${companySub}">${companySub}</span>
                        </div>
                    </td>
                    <td><span class="badge badge-neutral">${item.category}</span></td>
                    <td style="font-family: monospace;">$${item.price < 1 ? item.price : item.price.toLocaleString()}</td>
                    <td class="${priceChangeClass}">${priceChangeSign}${item.price_change_24h}%</td>
                    <td class="${rsiClass}">${item.rsi}</td>
                    <td style="font-family: monospace;" class="${item.macd_hist >= 0 ? 'positive' : 'negative'}">${item.macd_hist}</td>
                    <td>${item.rvol}x</td>
                    <td><span class="badge-rs ${rsBadgeClass}">${rsIcon} ${rsRating}</span></td>
                    <td style="font-family: monospace;">$${volFormatted}</td>
                    <td><strong>${item.score}</strong></td>
                    <td><span class="badge ${recBadge}">${item.recommendation}</span></td>
                    <td>
                        <button class="btn btn-outline btn-chart" data-symbol="${item.symbol}">Chart 📈</button>
                    </td>
                </tr>
            `;
        }).join("");


        // Attach Chart Click Handlers
        document.querySelectorAll(".btn-chart").forEach(btn => {
            btn.addEventListener("click", () => {
                const sym = btn.dataset.symbol;
                const match = currentScreenerData.find(d => d.symbol === sym);
                if (match) openModal(match);
            });
        });
    }

    async function openModal(data) {
        selectedSymbolData = data;
        modalSymbol.textContent = data.stock_ticker || data.symbol;
        if (modalCompanyName) {
            modalCompanyName.textContent = data.company_name || data.symbol;
        }
        if (modalAssetClass) {
            modalAssetClass.textContent = data.asset_class || "CRYPTO";
            modalAssetClass.className = `badge badge-asset ${data.asset_class === 'STOCK' ? 'badge-stock' : 'badge-crypto'}`;
        }
        modalCategory.textContent = data.category;
        modalRecommendation.textContent = data.recommendation;

        modalSignalsList.innerHTML = data.signals.map(sig => `
            <div class="signal-tag" style="background:rgba(255,255,255,0.05); padding:6px 10px; border-radius:6px; font-size:12px; border:1px solid var(--border-color);">
                ⚡ ${sig}
            </div>
        `).join('') || '<div style="font-size:12px; color:var(--text-muted);">No major alert flags active</div>';

        updateRiskCalculator();
        chartModal.classList.add("active");
        currentActiveTradeSetup = null;

        // Sync modal timeframe buttons with current screener timeframe
        const timeframe = timeframeSelect.value || "1h";
        currentModalTimeframe = timeframe;
        document.querySelectorAll(".modal-tf-group .modal-tf-btn").forEach(b => {
            if (b.dataset.tf === timeframe) b.classList.add("active");
            else b.classList.remove("active");
        });

        // Fetch & Draw Chart
        const klineRes = await window.cryptoAPI.getSymbolKlines(data.symbol, currentModalTimeframe, 100);
        if (klineRes && klineRes.klines) {
            chartRenderer.render(klineRes.klines, data.symbol, null, currentModalTimeframe);
        }
    }

    let currentModalTimeframe = "1h";
    let currentActiveTradeSetup = null;

    document.querySelectorAll(".modal-tf-group .modal-tf-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
            document.querySelectorAll(".modal-tf-group .modal-tf-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            currentModalTimeframe = btn.dataset.tf || "1h";
            const sym = selectedSymbolData ? selectedSymbolData.symbol : null;
            if (sym) {
                const klineRes = await window.cryptoAPI.getSymbolKlines(sym, currentModalTimeframe, 100);
                if (klineRes && klineRes.klines) {
                    chartRenderer.render(klineRes.klines, sym, currentActiveTradeSetup, currentModalTimeframe);
                }
            }
        });
    });

    async function openChartForSetup(setup) {
        selectedSymbolData = {
            symbol: setup.symbol,
            price: setup.entry,
            category: setup.strategy || "Strategy Setup",
            recommendation: `${setup.direction} SETUP`,
            signals: [
                `Strategy: ${setup.strategy || 'Algorithm'}`,
                `Entry: $${setup.entry}`,
                `Stop Loss: $${setup.sl}`,
                `Take Profit: $${setup.tp}`,
            ]
        };
        currentActiveTradeSetup = setup;

        modalSymbol.textContent = setup.symbol;
        if (modalCompanyName) modalCompanyName.textContent = setup.company || setup.symbol.replace("USDT", "");
        if (modalAssetClass) {
            const isStock = setup.asset === "STOCK";
            modalAssetClass.textContent = isStock ? "US STOCK" : "CRYPTO";
            modalAssetClass.className = `badge ${isStock ? 'badge-stock' : 'badge-asset'}`;
        }
        modalCategory.textContent = setup.strategy || "Strategy Setup";
        modalRecommendation.textContent = `${setup.direction} SETUP`;

        modalSignalsList.innerHTML = `
            <div class="signal-tag" style="background:rgba(0,210,255,0.1); padding:8px 12px; border-radius:6px; font-size:12px; border:1px solid rgba(0,210,255,0.3); color:#00d2ff;">
                ⚡ Strategy: <strong>${setup.strategy || 'Algorithm'}</strong> (${setup.direction})
            </div>
            <div class="signal-tag" style="background:rgba(255,255,255,0.05); padding:8px 12px; border-radius:6px; font-size:12px; border:1px solid var(--border-color);">
                📍 Entry: <strong>$${setup.entry}</strong> | 🛑 SL: <strong style="color:var(--red-bear);">$${setup.sl}</strong> | 🎯 TP: <strong style="color:var(--green-bull);">$${setup.tp}</strong>
            </div>
        `;

        chartModal.classList.add("active");

        const timeframe = timeframeSelect.value || "1h";
        currentModalTimeframe = timeframe;
        document.querySelectorAll(".modal-tf-group .modal-tf-btn").forEach(b => {
            if (b.dataset.tf === timeframe) b.classList.add("active");
            else b.classList.remove("active");
        });

        const klineRes = await window.cryptoAPI.getSymbolKlines(setup.symbol, currentModalTimeframe, 100);
        if (klineRes && klineRes.klines) {
            chartRenderer.render(klineRes.klines, setup.symbol, currentActiveTradeSetup, currentModalTimeframe);
        }
    }



    function closeModal() {
        chartModal.classList.remove("active");
    }

    function updateRiskCalculator() {
        if (!selectedSymbolData) return;

        const account = parseFloat(calcAccount.value) || 1000;
        const riskPct = parseFloat(calcRisk.value) || 2;
        const price = selectedSymbolData.price;
        const atr = selectedSymbolData.atr || (price * 0.02);

        const dollarRisk = account * (riskPct / 100);
        const stopDistance = 1.5 * atr;
        const stopLossPrice = Math.max(0, price - stopDistance);
        const takeProfitPrice = price + (2 * stopDistance);

        const sharesOrUnits = stopDistance > 0 ? (dollarRisk / stopDistance) : 0;
        const positionSizeDollars = sharesOrUnits * price;

        calcPosSize.textContent = `$${positionSizeDollars.toFixed(2)}`;
        calcSlTarget.textContent = `$${stopLossPrice.toFixed(4)} (-${((stopDistance / price) * 100).toFixed(2)}%)`;
        calcTpTarget.textContent = `$${takeProfitPrice.toFixed(4)} (+${(((2 * stopDistance) / price) * 100).toFixed(2)}%)`;
    }

    // ================================================
    // Unified Tab Navigation (Screener, High Delta, Signals, Wallet, Bot)
    // ================================================
    const tabBtns = document.querySelectorAll('.tab-btn');
    const screenerPanel = document.getElementById('screener-panel');
    const screenerTableSection = document.getElementById('screener-table-section');
    const highDeltaPanel = document.getElementById('high-delta-panel');
    const signalsPanel = document.getElementById('signals-panel');
    const walletPanel = document.getElementById('wallet-panel');
    const botPanel = document.getElementById('bot-panel');

    function switchTab(tab) {
        tabBtns.forEach(b => {
            if (b.dataset.tab === tab) {
                b.classList.add('active');
            } else {
                b.classList.remove('active');
            }
        });

        // Hide all panels first
        if (screenerPanel) screenerPanel.style.display = 'none';
        if (screenerTableSection) screenerTableSection.style.display = 'none';
        if (highDeltaPanel) highDeltaPanel.style.display = 'none';
        if (signalsPanel) signalsPanel.style.display = 'none';
        if (walletPanel) walletPanel.style.display = 'none';
        if (botPanel) botPanel.style.display = 'none';

        if (tab === 'screener') {
            if (screenerPanel) screenerPanel.style.display = '';
            if (screenerTableSection) screenerTableSection.style.display = '';
        } else if (tab === 'high-delta') {
            if (highDeltaPanel) highDeltaPanel.style.display = '';
            if (!deltaScanDone) {
                scanHighDelta();
            }
        } else if (tab === 'signals') {
            if (signalsPanel) signalsPanel.style.display = '';
            if (!signalsScanDone) {
                scanTradeSignals();
            }
        } else if (tab === 'wallet') {
            if (walletPanel) walletPanel.style.display = '';
            if (!walletLoadedOnce) {
                loadWallet();
            }
        } else if (tab === 'bot') {
            if (botPanel) botPanel.style.display = '';
            loadBotStatus();
        }
    }

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            switchTab(btn.dataset.tab);
        });
    });

    // ================================================
    // Trade Signals Panel Logic
    // ================================================
    const btnScanSignals = document.getElementById('btn-scan-signals');
    const rrSelect = document.getElementById('rr-select');
    const signalTimeframeSelect = document.getElementById('signal-timeframe-select');
    const confidenceSelect = document.getElementById('confidence-select');
    const signalAssetSelect = document.getElementById('signal-asset-select');
    const directionFilter = document.getElementById('direction-filter');
    const signalSearchInput = document.getElementById('signal-search-input');
    const signalMtfFilter = document.getElementById('signal-mtf-filter');
    const signalTierFilter = document.getElementById('signal-tier-filter');
    const signalCardsGrid = document.getElementById('signal-cards-grid');
    const signalRecordsCount = document.getElementById('signal-records-count');
    const signalCountBadge = document.getElementById('signal-count-badge');

    let signalsScanDone = false;
    let currentSignals = [];

    btnScanSignals.addEventListener('click', scanTradeSignals);

    async function scanTradeSignals() {
        const interval = signalTimeframeSelect.value;
        const rr = rrSelect.value;
        const minConfidence = parseInt(confidenceSelect.value);
        const assetClass = signalAssetSelect ? signalAssetSelect.value : 'ALL';

        // Show loading state
        signalCardsGrid.innerHTML = `
            <div class="signal-loading glass-card">
                <div class="spinner"></div>
                <p>Scanning pairs for active entry signals on <strong>${interval}</strong> timeframe...</p>
            </div>
        `;
        btnScanSignals.disabled = true;
        btnScanSignals.textContent = '⏳ Scanning...';

        try {
            const res = await window.cryptoAPI.getTradeSignals(interval, rr, 3, minConfidence, assetClass);
            currentSignals = res.signals || [];
            signalsScanDone = true;
            renderSignalCards();
        } catch (err) {
            signalCardsGrid.innerHTML = `
                <div class="signal-loading glass-card">
                    <p style="color: var(--red-bear);">❌ Failed to scan signals. Is the backend running?</p>
                </div>
            `;
        }

        btnScanSignals.disabled = false;
        btnScanSignals.innerHTML = '<span class="scan-icon">🎯</span> Scan Now';
    }

    function renderSignalCards() {
        let filtered = [...currentSignals];

        // Search text filter
        const query = signalSearchInput ? signalSearchInput.value.trim().toLowerCase() : '';
        if (query) {
            filtered = filtered.filter(s => {
                const sym = (s.symbol || '').toLowerCase();
                const ticker = (s.stock_ticker || '').toLowerCase();
                const strat = (s.strategy || '').toLowerCase();
                const comp = (s.company_name || '').toLowerCase();
                return sym.includes(query) || ticker.includes(query) || strat.includes(query) || comp.includes(query);
            });
        }

        // Direction filter
        const dirFilter = directionFilter ? directionFilter.value : 'ALL';
        if (dirFilter !== 'ALL') {
            filtered = filtered.filter(s => s.direction === dirFilter);
        }

        // MTF Filter
        const mtfVal = signalMtfFilter ? signalMtfFilter.value : 'ALL';
        if (mtfVal === 'ALIGNED') {
            filtered = filtered.filter(s => s.htf_aligned === true);
        } else if (mtfVal === 'BULL') {
            filtered = filtered.filter(s => s.htf_bias === 'BULL');
        } else if (mtfVal === 'BEAR') {
            filtered = filtered.filter(s => s.htf_bias === 'BEAR');
        }

        // Tier / Profitability Filter
        const tierVal = signalTierFilter ? signalTierFilter.value : 'ALL';
        if (tierVal === 'PROFITABLE') {
            filtered = filtered.filter(s => s.tier === 'A+' || s.tier === 'A' || s.tier === 'B+' || (s.historical_pf && s.historical_pf >= 1.0));
        } else if (tierVal === 'A_PLUS') {
            filtered = filtered.filter(s => s.tier === 'A+');
        } else if (tierVal === 'TIER_A') {
            filtered = filtered.filter(s => s.tier === 'A+' || s.tier === 'A');
        }

        signalRecordsCount.textContent = `${filtered.length} Active Signal${filtered.length !== 1 ? 's' : ''}`;
        signalCountBadge.textContent = filtered.length;

        if (filtered.length === 0) {
            signalCardsGrid.innerHTML = `
                <div class="signal-loading glass-card">
                    <p>No active trade signals found matching filters. Try adjusting your MTF, tier, or confidence criteria.</p>
                </div>
            `;
            return;
        }

        signalCardsGrid.innerHTML = filtered.map(sig => {
            const dirClass = sig.direction === 'LONG' ? 'long' : 'short';
            const dirLabel = sig.direction === 'LONG' ? '▲ LONG' : '▼ SHORT';

            const isStock = sig.asset_class === 'STOCK';
            const displayName = sig.stock_ticker || sig.symbol.replace('USDT', '');
            const assetBadgeClass = isStock ? 'badge-stock' : 'badge-crypto';
            const assetBadgeText = isStock ? 'US STOCK' : 'CRYPTO';
            const companyName = sig.company_name && sig.company_name !== displayName ? sig.company_name : '';

            // MTF Bias Badge
            let mtfClass = 'neutral';
            let mtfIcon = '⚪';
            if (sig.htf_bias === 'BULL') {
                mtfClass = sig.htf_aligned ? 'aligned' : 'neutral';
                mtfIcon = '🟢';
            } else if (sig.htf_bias === 'BEAR') {
                mtfClass = sig.htf_aligned ? 'aligned' : 'conflicted';
                mtfIcon = '🔴';
            }
            const mtfBadge = `<span class="mtf-badge ${mtfClass}" title="Higher Timeframe (${sig.htf_interval || '4h'}) Trend: ${sig.htf_bias || 'NEUTRAL'}">${mtfIcon} 4h: ${sig.htf_bias || 'NEUTRAL'}</span>`;

            // Strategy Tier Badge
            const tier = sig.tier || 'B';
            let tierCssClass = 'tier-b';
            if (tier === 'A+') tierCssClass = 'tier-a-plus';
            else if (tier === 'A') tierCssClass = 'tier-a';
            else if (tier === 'B+') tierCssClass = 'tier-b-plus';
            else if (tier === 'C') tierCssClass = 'tier-c';
            const pfText = sig.historical_pf ? `PF ${sig.historical_pf.toFixed(2)}` : 'PF 1.00';
            const tierBadge = `<span class="tier-badge ${tierCssClass}" title="Strategy Tier ${tier} (Backtested PF: ${pfText})">★ Tier ${tier} · ${pfText}</span>`;

            // Freshness
            let freshnessClass, freshnessLabel;
            if (sig.bars_ago === 0) {
                freshnessClass = 'fresh';
                freshnessLabel = 'Current bar';
            } else if (sig.bars_ago === 1) {
                freshnessClass = 'recent';
                freshnessLabel = '1 bar ago';
            } else {
                freshnessClass = 'aging';
                freshnessLabel = `${sig.bars_ago} bars ago`;
            }

            // Confidence class
            let confClass = 'low';
            if (sig.confidence >= 70) confClass = 'high';
            else if (sig.confidence >= 40) confClass = 'medium';

            // Price formatting
            const fmt = (p) => {
                if (p >= 1000) return p.toLocaleString(undefined, { maximumFractionDigits: 2 });
                if (p >= 1) return p.toFixed(4);
                return p.toFixed(6);
            };

            const slLabel = sig.direction === 'LONG' ? `−${sig.sl_distance_pct}%` : `+${sig.sl_distance_pct}%`;
            const tpLabel = sig.direction === 'LONG' ? `+${sig.tp_distance_pct}%` : `−${sig.tp_distance_pct}%`;

            return `
                <div class="signal-card">
                    <div class="signal-card-header">
                        <div class="signal-symbol-group">
                            <div>
                                <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                                    <span class="signal-symbol">${displayName}</span>
                                    <span class="badge-asset ${assetBadgeClass}">${assetBadgeText}</span>
                                    ${tierBadge}
                                </div>
                                ${companyName ? `<div style="font-size:11px; color:var(--text-muted); margin-top:2px;">${companyName}</div>` : ''}
                            </div>
                            <div style="display:flex; flex-direction:column; align-items:flex-end; gap:4px;">
                                <span class="direction-badge ${dirClass}">${dirLabel}</span>
                                ${mtfBadge}
                            </div>
                        </div>
                        <div class="signal-freshness">
                            <span class="freshness-dot ${freshnessClass}"></span>
                            ${freshnessLabel}
                        </div>
                    </div>

                    <div class="signal-card-body">
                        <div class="price-levels">
                            <div class="price-level sl">
                                <span class="price-level-label">🛑 Stop Loss</span>
                                <span class="price-level-value">$${fmt(sig.stop_loss)}</span>
                                <span class="price-level-pct">${slLabel}</span>
                            </div>
                            <div class="price-level entry">
                                <span class="price-level-label">📍 Entry</span>
                                <span class="price-level-value">$${fmt(sig.entry_price)}</span>
                                <span class="price-level-pct">R:R ${sig.rr_ratio}x</span>
                            </div>
                            <div class="price-level tp">
                                <span class="price-level-label">🎯 Take Profit</span>
                                <span class="price-level-value">$${fmt(sig.take_profit)}</span>
                                <span class="price-level-pct">${tpLabel}</span>
                            </div>
                        </div>

                        <div class="confidence-section">
                            <span style="font-size:11px; color:var(--text-muted);">Confidence</span>
                            <div class="confidence-bar-track">
                                <div class="confidence-bar-fill ${confClass}" style="width:${sig.confidence}%"></div>
                            </div>
                            <span class="confidence-label">${sig.confidence}%</span>
                        </div>
                    </div>

                    <div class="signal-card-footer">
                        <div style="display:flex; flex-direction:column; gap:4px;">
                            <span class="signal-strategy-name">${sig.strategy}</span>
                            <div style="display:flex; align-items:center; gap:6px; font-size:10px; color:var(--text-muted);">
                                <span>Macro: <strong style="color:var(--text-secondary);">${sig.macro_regime || 'NEUTRAL'}</strong></span>
                                <span>•</span>
                                <span>RS: <strong style="color:${sig.rs_status === 'ALPHA_LEADER' ? 'var(--green-bull)' : 'var(--text-secondary)'};">${sig.rs_ratio || 1.0}x</strong></span>
                            </div>
                        </div>
                        <div class="signal-meta-row">
                            <span class="signal-meta-item">RSI: ${sig.rsi || '—'}</span>
                            <span class="signal-meta-item">RVOL: ${sig.rvol || '—'}x</span>
                            ${sig.historical_wr ? `<span class="signal-meta-item" style="color:var(--accent-cyan); font-weight:600;">WR: ${sig.historical_wr}%</span>` : ''}
                        </div>
                    </div>

                    <div class="signal-actions-row">
                        <button class="btn-view-signal-chart" data-symbol="${sig.symbol}" data-strategy="${sig.strategy}" data-direction="${sig.direction}" data-entry="${sig.entry_price}" data-sl="${sig.stop_loss}" data-tp="${sig.take_profit}" data-asset="${sig.asset_class}" data-company="${companyName}">
                            📈 Chart
                        </button>
                        <button class="btn-execute-trade" data-symbol="${sig.symbol}" data-strategy="${sig.strategy}" data-direction="${sig.direction}" data-entry="${sig.entry_price}" data-sl="${sig.stop_loss}" data-tp="${sig.take_profit}" data-sl-pct="${sig.sl_distance_pct}" data-tp-pct="${sig.tp_distance_pct}" data-rr="${sig.rr_ratio}">
                            ⚡ Execute Trade
                        </button>
                    </div>
                </div>
            `;
        }).join('');

        // Attach View Chart click listeners
        document.querySelectorAll('.btn-view-signal-chart').forEach(btn => {
            btn.addEventListener('click', () => {
                const setup = {
                    symbol: btn.dataset.symbol,
                    strategy: btn.dataset.strategy,
                    direction: btn.dataset.direction,
                    entry: parseFloat(btn.dataset.entry),
                    sl: parseFloat(btn.dataset.sl),
                    tp: parseFloat(btn.dataset.tp),
                    company: btn.dataset.company,
                    asset: btn.dataset.asset
                };
                openChartForSetup(setup);
            });
        });

        // Attach Trade Execute click listeners
        document.querySelectorAll('.btn-execute-trade').forEach(btn => {
            btn.addEventListener('click', () => {
                const sigData = {
                    symbol: btn.dataset.symbol,
                    strategy: btn.dataset.strategy,
                    direction: btn.dataset.direction,
                    entry: parseFloat(btn.dataset.entry),
                    sl: parseFloat(btn.dataset.sl),
                    tp: parseFloat(btn.dataset.tp),
                    slPct: parseFloat(btn.dataset.slPct),
                    tpPct: parseFloat(btn.dataset.tpPct),
                    rr: btn.dataset.rr,
                };
                openTradeModal(sigData);
            });
        });
    }

    // Filter change listeners for dynamic real-time filtering
    if (directionFilter) directionFilter.addEventListener('change', renderSignalCards);
    if (signalSearchInput) signalSearchInput.addEventListener('input', renderSignalCards);
    if (signalMtfFilter) signalMtfFilter.addEventListener('change', renderSignalCards);
    if (signalTierFilter) signalTierFilter.addEventListener('change', renderSignalCards);

    // ================================================
    // 5m High Delta Futures Terminal Logic
    // ================================================
    const deltaSearchInput = document.getElementById('delta-search-input');
    const deltaMinNatrSelect = document.getElementById('delta-min-natr-select');
    const deltaVolumeSelect = document.getElementById('delta-volume-select');
    const deltaMomentumSelect = document.getElementById('delta-momentum-select');
    const deltaTierSelect = document.getElementById('delta-tier-select');
    const btnScanDelta = document.getElementById('btn-scan-delta');
    const deltaAutoRefreshSelect = document.getElementById('delta-auto-refresh-select');
    const deltaRecordsCount = document.getElementById('delta-records-count');
    const deltaTopLeader = document.getElementById('delta-top-leader');
    const deltaTopLeaderSub = document.getElementById('delta-top-leader-sub');
    const deltaAvgRange = document.getElementById('delta-avg-range');
    const deltaSetupsCount = document.getElementById('delta-setups-count');
    const deltaCardsGrid = document.getElementById('delta-cards-grid');

    let currentDeltaData = [];
    let deltaScanDone = false;
    let deltaAutoRefreshTimer = null;

    if (btnScanDelta) {
        btnScanDelta.addEventListener('click', () => scanHighDelta(true));
    }
    if (deltaMinNatrSelect) deltaMinNatrSelect.addEventListener('change', () => scanHighDelta(true));
    if (deltaVolumeSelect) deltaVolumeSelect.addEventListener('change', () => scanHighDelta(true));
    if (deltaSearchInput) deltaSearchInput.addEventListener('input', renderDeltaCards);
    if (deltaMomentumSelect) deltaMomentumSelect.addEventListener('change', renderDeltaCards);
    if (deltaTierSelect) deltaTierSelect.addEventListener('change', renderDeltaCards);

    if (deltaAutoRefreshSelect) {
        deltaAutoRefreshSelect.addEventListener('change', setupDeltaAutoRefresh);
    }

    function setupDeltaAutoRefresh() {
        if (deltaAutoRefreshTimer) {
            clearInterval(deltaAutoRefreshTimer);
            deltaAutoRefreshTimer = null;
        }
        const val = deltaAutoRefreshSelect ? deltaAutoRefreshSelect.value : "off";
        if (val === "off") return;
        const ms = parseInt(val, 10) || 30000;
        deltaAutoRefreshTimer = setInterval(() => {
            const currentTab = document.querySelector('.tab-btn.active')?.dataset.tab;
            if (currentTab === 'high-delta') {
                scanHighDelta(true);
            }
        }, ms);
    }

    async function scanHighDelta(forceRefresh = false) {
        if (!deltaCardsGrid) return;
        const minVol = parseFloat(deltaVolumeSelect ? deltaVolumeSelect.value : 5000000);
        const minNatr = parseFloat(deltaMinNatrSelect ? deltaMinNatrSelect.value : 0.8);

        deltaCardsGrid.innerHTML = `
            <div class="signal-loading glass-card">
                <div class="spinner"></div>
                <p>Scanning Binance Futures for contracts with high 5-minute range velocity...</p>
            </div>
        `;
        if (btnScanDelta) {
            btnScanDelta.disabled = true;
            btnScanDelta.innerHTML = '<span class="scan-icon">⏳</span> Scanning...';
        }

        try {
            const res = await window.cryptoAPI.getHighDeltaFutures(minVol, minNatr, 40, 12, forceRefresh);
            currentDeltaData = res.results || [];
            deltaScanDone = true;
            renderDeltaCards();
            updateDeltaStats();
        } catch (err) {
            console.error("Delta scan error:", err);
            deltaCardsGrid.innerHTML = `
                <div class="signal-loading glass-card">
                    <p style="color: var(--red-bear);">❌ Failed to scan High Delta Futures. Is backend running?</p>
                </div>
            `;
        }

        if (btnScanDelta) {
            btnScanDelta.disabled = false;
            btnScanDelta.innerHTML = '<span class="scan-icon">⚡</span> Scan 5m Futures';
        }
    }

    function updateDeltaStats() {
        if (!currentDeltaData || currentDeltaData.length === 0) {
            if (deltaTopLeader) deltaTopLeader.textContent = '--';
            if (deltaAvgRange) deltaAvgRange.textContent = '--';
            if (deltaSetupsCount) deltaSetupsCount.textContent = '0';
            return;
        }

        const topLeader = currentDeltaData[0];
        if (deltaTopLeader && topLeader) {
            deltaTopLeader.textContent = `${topLeader.symbol} (+${topLeader.natr_5m_pct}%)`;
            if (deltaTopLeaderSub) {
                deltaTopLeaderSub.textContent = `Avg 5m swing: ${topLeader.avg_5m_range_pct}%`;
            }
        }

        const avgRange = (currentDeltaData.reduce((acc, c) => acc + (c.avg_5m_range_pct || 0), 0) / currentDeltaData.length).toFixed(2);
        if (deltaAvgRange) {
            deltaAvgRange.textContent = `${avgRange}% / 5m`;
        }

        const setups = currentDeltaData.filter(c => c.scalp_setup).length;
        if (deltaSetupsCount) {
            deltaSetupsCount.textContent = setups.toString();
        }
    }

    function renderDeltaCards() {
        if (!deltaCardsGrid) return;
        let filtered = [...currentDeltaData];

        // Search text
        const query = deltaSearchInput ? deltaSearchInput.value.trim().toLowerCase() : '';
        if (query) {
            filtered = filtered.filter(c => c.symbol.toLowerCase().includes(query) || (c.category || '').toLowerCase().includes(query));
        }

        // Momentum filter
        const momFilter = deltaMomentumSelect ? deltaMomentumSelect.value : 'ALL';
        if (momFilter !== 'ALL') {
            filtered = filtered.filter(c => (c.momentum || '').includes(momFilter));
        }

        // Tier filter
        const tierFilter = deltaTierSelect ? deltaTierSelect.value : 'ALL';
        if (tierFilter === 'EXTREME') {
            filtered = filtered.filter(c => c.tier === 'EXTREME');
        } else if (tierFilter === 'HIGH') {
            filtered = filtered.filter(c => c.tier === 'EXTREME' || c.tier === 'HIGH');
        }

        if (deltaRecordsCount) {
            deltaRecordsCount.textContent = `${filtered.length} High Delta Contracts`;
        }

        if (filtered.length === 0) {
            deltaCardsGrid.innerHTML = `
                <div class="signal-loading glass-card">
                    <p>No futures contracts found matching criteria. Try lowering the Min 5m Range or Volume filter.</p>
                </div>
            `;
            return;
        }

        const fmtPrice = p => p >= 1000 ? p.toLocaleString(undefined, { maximumFractionDigits: 2 }) : p >= 1 ? p.toFixed(4) : p.toFixed(6);
        const fmtVol = v => v >= 1e9 ? `$${(v / 1e9).toFixed(2)}B` : v >= 1e6 ? `$${(v / 1e6).toFixed(1)}M` : `$${(v / 1e3).toFixed(0)}K`;

        deltaCardsGrid.innerHTML = filtered.map(item => {
            const setup = item.scalp_setup || {};
            const isLong = setup.direction === 'LONG';
            const tierClass = (item.tier || 'low').toLowerCase();

            return `
                <div class="delta-card">
                    <div class="delta-card-header">
                        <div class="delta-card-symbol-wrap">
                            <span class="delta-card-symbol">
                                ${item.symbol}
                                <span class="delta-futures-tag">FUTURES</span>
                            </span>
                            <span class="delta-card-category">${item.category || 'Crypto'} • 24h Vol: ${fmtVol(item.volume_24h_usdt)}</span>
                        </div>
                        <span class="delta-tier-pill ${tierClass}">${item.tier_badge || item.tier}</span>
                    </div>

                    <div class="delta-metrics-strip">
                        <div class="delta-metric-item">
                            <span class="delta-metric-lbl">5m NATR</span>
                            <span class="delta-metric-val hot">${item.natr_5m_pct}%</span>
                        </div>
                        <div class="delta-metric-item">
                            <span class="delta-metric-lbl">Avg 5m Range</span>
                            <span class="delta-metric-val cyan">${item.avg_5m_range_pct}%</span>
                        </div>
                        <div class="delta-metric-item">
                            <span class="delta-metric-lbl">Bars &gt;1%</span>
                            <span class="delta-metric-val">${item.pct_bars_over_1pct}%</span>
                        </div>
                    </div>

                    <div class="delta-scalp-box ${isLong ? 'long' : 'short'}">
                        <div class="delta-scalp-header">
                            <span class="delta-scalp-tag ${isLong ? 'long' : 'short'}">
                                ${isLong ? '▲ 2:1 LONG SCALP' : '▼ 2:1 SHORT SCALP'}
                            </span>
                            <span class="delta-scalp-rr">2:1 R:R (+${setup.reward_pct}% / -${setup.risk_pct}%)</span>
                        </div>
                        <div class="delta-scalp-levels">
                            <span>Entry: <strong>$${fmtPrice(setup.entry)}</strong></span>
                            <span style="color:var(--red-bear)">SL: <strong>$${fmtPrice(setup.stop_loss)}</strong></span>
                            <span style="color:var(--green-bull)">TP: <strong>$${fmtPrice(setup.take_profit)}</strong></span>
                        </div>
                    </div>

                    <div class="delta-card-actions">
                        <button class="btn-delta-chart" data-symbol="${item.symbol}">
                            📈 5m Chart
                        </button>
                        <button class="btn-delta-trade"
                            data-symbol="${item.symbol}"
                            data-direction="${setup.direction}"
                            data-entry="${setup.entry}"
                            data-sl="${setup.stop_loss}"
                            data-tp="${setup.take_profit}"
                            data-risk-pct="${setup.risk_pct}"
                            data-reward-pct="${setup.reward_pct}"
                            data-rr="${setup.rr_ratio}">
                            ⚡ Quick Scalp (2:1)
                        </button>
                    </div>
                </div>
            `;
        }).join('');

        // Attach Chart button handlers
        document.querySelectorAll('.btn-delta-chart').forEach(btn => {
            btn.addEventListener('click', () => {
                const sym = btn.dataset.symbol;
                openChartForSetup({
                    symbol: sym,
                    strategy: "5m High Delta Scalp",
                    direction: "LONG",
                    entry: 0,
                    sl: 0,
                    tp: 0,
                    asset: "CRYPTO",
                    company: sym
                });
            });
        });

        // Attach Quick Scalp button handlers
        document.querySelectorAll('.btn-delta-trade').forEach(btn => {
            btn.addEventListener('click', () => {
                const sigData = {
                    symbol: btn.dataset.symbol,
                    strategy: "5m High Delta 2:1 Scalp",
                    direction: btn.dataset.direction,
                    entry: parseFloat(btn.dataset.entry),
                    sl: parseFloat(btn.dataset.sl),
                    tp: parseFloat(btn.dataset.tp),
                    slPct: parseFloat(btn.dataset.riskPct),
                    tpPct: parseFloat(btn.dataset.rewardPct),
                    rr: btn.dataset.rr,
                };
                openTradeModal(sigData);
            });
        });
    }

    // ================================================
    // Wallet Tab Logic
    // ================================================
    const portfolioTotalValue = document.getElementById('portfolio-total-value');
    const portfolioAssetCount = document.getElementById('portfolio-asset-count');
    const portfolioTradeStatus = document.getElementById('portfolio-trade-status');
    const walletAssetsGrid = document.getElementById('wallet-assets-grid');
    const btnRefreshWallet = document.getElementById('btn-refresh-wallet');

    let walletLoadedOnce = false;

    btnRefreshWallet.addEventListener('click', loadWallet);

    async function loadWallet() {
        walletAssetsGrid.innerHTML = `
            <div class="signal-loading glass-card">
                <div class="spinner"></div>
                <p>Fetching account balances & market values...</p>
            </div>
        `;

        const res = await window.cryptoAPI.getWallet();

        if (res.error) {
            portfolioTotalValue.textContent = '$0.00';
            portfolioAssetCount.textContent = 'API Error';
            portfolioTradeStatus.className = 'portfolio-status-label no-trade';
            portfolioTradeStatus.textContent = '⚠️ API Key Error';

            walletAssetsGrid.innerHTML = `
                <div class="wallet-error glass-card">
                    <p style="color: var(--red-bear); font-weight: 600; margin-bottom: 8px;">❌ ${res.error}</p>
                    <p style="font-size: 12px; color: var(--text-muted);">Please check your API_KEY and SECRET_KEY in <code>.env</code> and ensure Spot trading permissions are enabled.</p>
                </div>
            `;
            return;
        }

        walletLoadedOnce = true;
        portfolioTotalValue.textContent = `$${res.total_usd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        portfolioAssetCount.textContent = `${res.asset_count} Assets`;

        if (res.can_trade) {
            portfolioTradeStatus.className = 'portfolio-status-label can-trade';
            portfolioTradeStatus.textContent = '🟢 Spot Trading Enabled';
        } else {
            portfolioTradeStatus.className = 'portfolio-status-label no-trade';
            portfolioTradeStatus.textContent = '🟡 Read-Only API';
        }

        if (!res.balances || res.balances.length === 0) {
            walletAssetsGrid.innerHTML = `
                <div class="wallet-error glass-card">
                    <p>No non-zero balances found in Binance Spot account.</p>
                </div>
            `;
            return;
        }

        walletAssetsGrid.innerHTML = res.balances.map(b => {
            let changeClass = 'neutral';
            let changeSign = '';
            if (b.change_24h > 0) { changeClass = 'positive'; changeSign = '+'; }
            else if (b.change_24h < 0) { changeClass = 'negative'; }

            return `
                <div class="asset-card">
                    <div class="asset-card-left">
                        <span class="asset-symbol">${b.asset}</span>
                        <span class="asset-balance">Balance: ${b.total.toLocaleString()} ${b.asset}</span>
                        ${b.locked > 0 ? `<span style="font-size:10px; color:var(--amber-warning);">In Orders: ${b.locked}</span>` : ''}
                    </div>
                    <div class="asset-card-right">
                        <span class="asset-usd-value">$${b.usd_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                        ${b.asset !== 'USDT' && b.asset !== 'BUSD' ? `<span class="asset-change-badge ${changeClass}">${changeSign}${b.change_24h}%</span>` : ''}
                    </div>
                </div>
            `;
        }).join('');
    }

    // ================================================
    // Trade Confirmation Modal Logic
    // ================================================
    const tradeModal = document.getElementById('trade-modal');
    const btnCloseTradeModal = document.getElementById('btn-close-trade-modal');
    const btnCancelTrade = document.getElementById('btn-cancel-trade');
    const btnConfirmTrade = document.getElementById('btn-confirm-trade');

    const tradePairSymbol = document.getElementById('trade-pair-symbol');
    const tradeDirectionBadge = document.getElementById('trade-direction-badge');
    const tradeEntryPrice = document.getElementById('trade-entry-price');
    const tradeSlPrice = document.getElementById('trade-sl-price');
    const tradeSlPct = document.getElementById('trade-sl-pct');
    const tradeTpPrice = document.getElementById('trade-tp-price');
    const tradeTpPct = document.getElementById('trade-tp-pct');

    const tradeAmountInput = document.getElementById('trade-amount');
    const tradeQuantityDisplay = document.getElementById('trade-quantity-display');
    const tradeRrDisplay = document.getElementById('trade-rr-display');

    const tradeResult = document.getElementById('trade-result');
    const tradeResultContent = document.getElementById('trade-result-content');

    let activeTradeData = null;
    let holdTimer = null;
    let holdStartTime = 0;

    btnCloseTradeModal.addEventListener('click', closeTradeModal);
    btnCancelTrade.addEventListener('click', closeTradeModal);

    tradeAmountInput.addEventListener('input', recalculateTradeSizing);

    function openTradeModal(sigData) {
        activeTradeData = sigData;

        tradePairSymbol.textContent = sigData.symbol;
        tradeDirectionBadge.className = `direction-badge ${sigData.direction === 'LONG' ? 'long' : 'short'}`;
        tradeDirectionBadge.textContent = sigData.direction === 'LONG' ? '▲ LONG' : '▼ SHORT';

        const fmt = (p) => p >= 1000 ? p.toLocaleString(undefined, { maximumFractionDigits: 2 }) : p >= 1 ? p.toFixed(4) : p.toFixed(6);

        tradeEntryPrice.textContent = `$${fmt(sigData.entry)}`;
        tradeSlPrice.textContent = `$${fmt(sigData.sl)}`;
        tradeSlPct.textContent = sigData.direction === 'LONG' ? `−${sigData.slPct}%` : `+${sigData.slPct}%`;
        tradeTpPrice.textContent = `$${fmt(sigData.tp)}`;
        tradeTpPct.textContent = sigData.direction === 'LONG' ? `+${sigData.tpPct}%` : `−${sigData.tpPct}%`;
        tradeRrDisplay.textContent = `1:${sigData.rr}`;

        tradeResult.style.display = 'none';
        resetHoldButton();

        recalculateTradeSizing();

        tradeModal.classList.add('active');
    }

    function closeTradeModal() {
        tradeModal.classList.remove('active');
        resetHoldButton();
    }

    function recalculateTradeSizing() {
        if (!activeTradeData) return;

        const amount = parseFloat(tradeAmountInput.value) || 0;
        const qty = activeTradeData.entry > 0 ? (amount / activeTradeData.entry) : 0;

        const baseName = activeTradeData.symbol.replace('USDT', '');
        tradeQuantityDisplay.textContent = `${qty.toFixed(6)} ${baseName}`;
    }

    // 3-Second Hold to Execute Button Interaction
    const holdProgress = btnConfirmTrade.querySelector('.hold-progress');
    const holdText = btnConfirmTrade.querySelector('.hold-text');

    function resetHoldButton() {
        if (holdTimer) clearInterval(holdTimer);
        holdTimer = null;
        btnConfirmTrade.classList.remove('holding', 'confirmed');
        holdProgress.style.width = '0%';
        holdText.textContent = 'Hold 3s to Execute';
        btnConfirmTrade.disabled = false;
    }

    function startHold(e) {
        e.preventDefault();
        if (btnConfirmTrade.disabled) return;

        btnConfirmTrade.classList.add('holding');
        holdStartTime = Date.now();

        holdTimer = setInterval(() => {
            const elapsed = Date.now() - holdStartTime;
            const pct = Math.min(100, (elapsed / 3000) * 100);
            holdProgress.style.width = `${pct}%`;

            if (elapsed >= 3000) {
                clearInterval(holdTimer);
                holdTimer = null;
                btnConfirmTrade.classList.remove('holding');
                btnConfirmTrade.classList.add('confirmed');
                holdText.textContent = '⏳ Placing Order...';
                btnConfirmTrade.disabled = true;

                executeLiveTrade();
            }
        }, 50);
    }

    function cancelHold() {
        if (btnConfirmTrade.classList.contains('confirmed')) return;
        resetHoldButton();
    }

    btnConfirmTrade.addEventListener('mousedown', startHold);
    btnConfirmTrade.addEventListener('mouseup', cancelHold);
    btnConfirmTrade.addEventListener('mouseleave', cancelHold);
    btnConfirmTrade.addEventListener('touchstart', startHold);
    btnConfirmTrade.addEventListener('touchend', cancelHold);

    async function executeLiveTrade() {
        if (!activeTradeData) return;

        const amount = parseFloat(tradeAmountInput.value) || 0;
        if (amount <= 0) {
            tradeResult.style.display = 'block';
            tradeResult.className = 'trade-result error';
            tradeResultContent.innerHTML = `<strong>❌ Enter a valid amount</strong>`;
            resetHoldButton();
            return;
        }

        const side = activeTradeData.direction === 'LONG' ? 'BUY' : 'SELL';

        const orderData = {
            symbol: activeTradeData.symbol,
            side: side,
            amount: amount,
            stop_loss: activeTradeData.sl,
            take_profit: activeTradeData.tp,
        };

        tradeResult.style.display = 'block';
        tradeResult.className = 'trade-result';
        tradeResultContent.innerHTML = `<div class="spinner"></div> Sending order to Binance API...`;

        const res = await window.cryptoAPI.placeOrder(orderData);

        if (res.error) {
            tradeResult.className = 'trade-result error';
            tradeResultContent.innerHTML = `
                <strong>❌ Order Execution Failed</strong><br>
                <span>${res.error}</span>
            `;
            resetHoldButton();
        } else {
            tradeResult.className = 'trade-result success';
            let msg = `<strong>✅ ${res.message}</strong><br>`;
            if (res.entry_order) {
                msg += `Entry Order ID: <code>${res.entry_order.orderId || 'Filled'}</code><br>`;
            }
            if (res.sl_tp_order) {
                msg += `OCO SL/TP Order List ID: <code>${res.sl_tp_order.orderListId || 'Active'}</code><br>`;
            }
            tradeResultContent.innerHTML = msg;

            btnConfirmTrade.disabled = true;
            holdText.textContent = '✓ Executed';

            // Refresh wallet if opened
            walletLoadedOnce = false;
        }
    }

    // ================================================
    // ================================================
    // Autonomous Trading Terminal Logic
    // ================================================
    const btnBotToggle = document.getElementById('btn-bot-toggle');
    const botToggleLabel = document.getElementById('bot-toggle-label');
    const botToggleSwitch = document.getElementById('bot-toggle-switch');
    const botModeBadge = document.getElementById('bot-mode-badge');
    const botStrategyBadge = document.getElementById('bot-strategy-badge');
    const botSubtitle = document.getElementById('bot-subtitle');
    const botStatusDot = document.getElementById('bot-status-dot');

    // Action Buttons
    const btnBotScanNow = document.getElementById('btn-bot-scan-now');
    const scanNowLabel = document.getElementById('scan-now-label');
    const btnBotSquareOffAll = document.getElementById('btn-bot-square-off-all');
    const btnBotPanic = document.getElementById('btn-bot-panic');

    // Square Off Modal
    const squareOffModal = document.getElementById('square-off-modal');
    const squareOffPosCount = document.getElementById('square-off-pos-count');
    const squareOffPreviewList = document.getElementById('square-off-preview-list');
    const btnCancelSquareOff = document.getElementById('btn-cancel-square-off');
    const btnCloseSquareOffModal = document.getElementById('btn-close-square-off-modal');
    const btnConfirmSquareOffAll = document.getElementById('btn-confirm-square-off-all');

    // Capital & Health Stats
    const botStatTotalCapInput = document.getElementById('bot-stat-total-cap-input');
    const botStatDeployedCap = document.getElementById('bot-stat-deployed-cap');
    const botStatDeployedPct = document.getElementById('bot-stat-deployed-pct');
    const botStatFreeCap = document.getElementById('bot-stat-free-cap');
    const botStatPnl = document.getElementById('bot-stat-pnl');
    const botStatPnlSub = document.getElementById('bot-stat-pnl-sub');
    const botStatWinrate = document.getElementById('bot-stat-winrate');
    const botStatTradesSub = document.getElementById('bot-stat-trades-sub');
    const capitalBarRatio = document.getElementById('capital-bar-ratio');
    const capitalProgressFill = document.getElementById('capital-progress-fill');

    // Config Subtabs & Fields
    const botConfigSubtabs = document.getElementById('bot-config-subtabs');
    const botCfgSizingMode = document.getElementById('bot-cfg-sizing-mode');
    const botCfgAmountGroup = document.getElementById('bot-cfg-amount-group');
    const botCfgAmountLabel = document.getElementById('bot-cfg-amount-label');
    const botCfgAmount = document.getElementById('bot-cfg-amount');
    const botCfgTradePctGroup = document.getElementById('bot-cfg-trade-pct-group');
    const botCfgTradePct = document.getElementById('bot-cfg-trade-pct');
    const botCfgRiskPctGroup = document.getElementById('bot-cfg-risk-pct-group');
    const botCfgRiskPct = document.getElementById('bot-cfg-risk-pct');
    const botCfgLeverage = document.getElementById('bot-cfg-leverage');
    const botCfgMarket = document.getElementById('bot-cfg-market');

    const botCfgMaxPos = document.getElementById('bot-cfg-max-pos');
    const botCfgMaxLoss = document.getElementById('bot-cfg-max-loss');
    const botCfgDailyProfitTarget = document.getElementById('bot-cfg-daily-profit-target');
    const botCfgMaxExposure = document.getElementById('bot-cfg-max-exposure');
    const botCfgCooldown = document.getElementById('bot-cfg-cooldown');
    const botCfgConfidence = document.getElementById('bot-cfg-confidence');

    const botCfgAsset = document.getElementById('bot-cfg-asset');
    const botCfgStrategy = document.getElementById('bot-cfg-strategy');
    const botCfgTimeframe = document.getElementById('bot-cfg-timeframe');
    const botCfgInterval = document.getElementById('bot-cfg-interval');

    const botCfgTrailingEnabled = document.getElementById('bot-cfg-trailing-enabled');
    const botCfgTrailingCallback = document.getElementById('bot-cfg-trailing-callback');
    const botCfgMtfEnabled = document.getElementById('bot-cfg-mtf-enabled');
    const botCfgBreakevenEnabled = document.getElementById('bot-cfg-breakeven-enabled');

    const botCfgPaper = document.getElementById('bot-cfg-paper');
    const btnSaveBotConfig = document.getElementById('btn-save-bot-config');

    // Positions & Journal
    const botPositionsList = document.getElementById('bot-positions-list');
    const botPositionsCount = document.getElementById('bot-positions-count');
    const botPositionsLimit = document.getElementById('bot-positions-limit');
    const botLogEntries = document.getElementById('bot-log-entries');
    const botLogCount = document.getElementById('bot-log-count');
    const btnClearJournal = document.getElementById('btn-clear-journal');
    const logFilterPills = document.getElementById('log-filter-pills');

    let botIsRunning = false;
    let botPollTimer = null;
    let currentLogFilter = 'ALL';
    let cachedLogEntries = [];
    let cachedOpenPositions = [];

    // ================================================
    // Subtab Switching Logic
    // ================================================
    if (botConfigSubtabs) {
        botConfigSubtabs.addEventListener('click', (e) => {
            const btn = e.target.closest('.subtab-btn');
            if (!btn) return;
            const subtab = btn.dataset.subtab;

            botConfigSubtabs.querySelectorAll('.subtab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            const panes = ['sizing', 'risk', 'strategy', 'trailing'];
            panes.forEach(p => {
                const pane = document.getElementById(`subtab-${p}`);
                if (pane) pane.style.display = (p === subtab) ? 'block' : 'none';
            });
        });
    }

    // Dynamic Sizing Mode adjustments
    if (botCfgSizingMode) {
        botCfgSizingMode.addEventListener('change', () => {
            updateSizingModeVisibility(botCfgSizingMode.value);
        });
    }

    function updateSizingModeVisibility(mode) {
        if (!botCfgAmountGroup || !botCfgTradePctGroup || !botCfgRiskPctGroup) return;
        if (mode === 'percent_capital') {
            botCfgAmountGroup.style.opacity = '0.5';
            botCfgTradePctGroup.style.opacity = '1';
            botCfgRiskPctGroup.style.opacity = '0.5';
            if (botCfgAmountLabel) botCfgAmountLabel.textContent = 'Fixed Fallback Amount ($)';
        } else if (mode === 'risk_pct') {
            botCfgAmountGroup.style.opacity = '0.5';
            botCfgTradePctGroup.style.opacity = '0.5';
            botCfgRiskPctGroup.style.opacity = '1';
            if (botCfgAmountLabel) botCfgAmountLabel.textContent = 'Fixed Fallback Amount ($)';
        } else {
            botCfgAmountGroup.style.opacity = '1';
            botCfgTradePctGroup.style.opacity = '0.5';
            botCfgRiskPctGroup.style.opacity = '0.5';
            if (botCfgAmountLabel) botCfgAmountLabel.textContent = 'Fixed Amount per Trade (USDT)';
        }
    }

    // ================================================
    // Action Buttons Wiring
    // ================================================

    // Toggle bot ON/OFF
    if (btnBotToggle) {
        btnBotToggle.addEventListener('click', async () => {
            btnBotToggle.disabled = true;
            if (botIsRunning) {
                await window.cryptoAPI.stopBot();
            } else {
                await saveBotConfig();
                await window.cryptoAPI.startBot();
            }
            setTimeout(async () => {
                await loadBotStatus();
                btnBotToggle.disabled = false;
            }, 600);
        });
    }

    // Save configuration
    if (btnSaveBotConfig) {
        btnSaveBotConfig.addEventListener('click', async () => {
            btnSaveBotConfig.disabled = true;
            btnSaveBotConfig.textContent = '⏳ Saving...';
            await saveBotConfig();
            btnSaveBotConfig.textContent = '✅ Saved!';
            setTimeout(() => {
                btnSaveBotConfig.textContent = '💾 Save Configuration';
                btnSaveBotConfig.disabled = false;
            }, 1500);
            await loadBotStatus();
        });
    }

    // Total Capital Input direct change
    if (botStatTotalCapInput) {
        botStatTotalCapInput.addEventListener('change', async () => {
            await saveBotConfig();
            await loadBotStatus();
        });
    }

    // Run Scan Now (Instant Manual Cycle)
    if (btnBotScanNow) {
        btnBotScanNow.addEventListener('click', async () => {
            btnBotScanNow.disabled = true;
            const originalText = scanNowLabel ? scanNowLabel.textContent : 'Run Scan Now';
            if (scanNowLabel) scanNowLabel.textContent = 'Scanning...';

            try {
                await saveBotConfig();
                const res = await window.cryptoAPI.scanBotNow();
                if (scanNowLabel) scanNowLabel.textContent = '✅ Done!';
                setTimeout(() => {
                    if (scanNowLabel) scanNowLabel.textContent = originalText;
                    btnBotScanNow.disabled = false;
                }, 1500);
                await loadBotStatus();
            } catch (err) {
                console.error("Manual scan failed:", err);
                if (scanNowLabel) scanNowLabel.textContent = 'Error';
                setTimeout(() => {
                    if (scanNowLabel) scanNowLabel.textContent = originalText;
                    btnBotScanNow.disabled = false;
                }, 2000);
            }
        });
    }

    // Square Off All Modal Open
    if (btnBotSquareOffAll) {
        btnBotSquareOffAll.addEventListener('click', () => {
            openSquareOffModal();
        });
    }

    function openSquareOffModal() {
        if (!squareOffModal) return;
        const count = cachedOpenPositions.length;
        if (squareOffPosCount) squareOffPosCount.textContent = count;

        if (squareOffPreviewList) {
            if (count === 0) {
                squareOffPreviewList.innerHTML = '<div style="text-align:center; padding:16px; color:var(--text-muted); font-size:13px;">No open positions to liquidate.</div>';
            } else {
                squareOffPreviewList.innerHTML = cachedOpenPositions.map(pos => {
                    const isLong = pos.side === 'BUY';
                    const pnl = pos.unrealized_pnl || 0;
                    const pnlClass = pnl >= 0 ? 'profit' : 'loss';
                    return `
                        <div class="square-off-item">
                            <span style="font-weight:700;">${pos.symbol} <span style="font-size:10px; color:${isLong ? 'var(--green-bull)' : 'var(--red-bear)'};">${isLong ? '▲ LONG' : '▼ SHORT'}</span></span>
                            <span>Qty: ${pos.quantity.toFixed(4)} · Margin: $${pos.amount_usdt}</span>
                            <span class="bot-pos-pnl ${pnlClass}" style="font-weight:700;">${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}</span>
                        </div>
                    `;
                }).join('');
            }
        }

        squareOffModal.style.display = 'flex';
    }

    function closeSquareOffModal() {
        if (squareOffModal) squareOffModal.style.display = 'none';
    }

    if (btnCancelSquareOff) btnCancelSquareOff.addEventListener('click', closeSquareOffModal);
    if (btnCloseSquareOffModal) btnCloseSquareOffModal.addEventListener('click', closeSquareOffModal);

    // Confirm Square Off All
    if (btnConfirmSquareOffAll) {
        btnConfirmSquareOffAll.addEventListener('click', async () => {
            btnConfirmSquareOffAll.disabled = true;
            btnConfirmSquareOffAll.textContent = '⏳ Liquidating...';

            try {
                const res = await window.cryptoAPI.squareOffAll();
                closeSquareOffModal();
                btnConfirmSquareOffAll.disabled = false;
                btnConfirmSquareOffAll.textContent = '⚡ Liquidate All Positions';
                await loadBotStatus();
            } catch (err) {
                console.error("Square off all failed:", err);
                btnConfirmSquareOffAll.disabled = false;
                btnConfirmSquareOffAll.textContent = 'Error';
            }
        });
    }

    // Emergency Panic Stop (Stop Bot + Square Off All)
    if (btnBotPanic) {
        btnBotPanic.addEventListener('click', async () => {
            if (confirm("🚨 EMERGENCY PANIC STOP: Are you sure you want to stop the Auto-Trader and liquidate ALL open positions immediately at market mark price?")) {
                btnBotPanic.disabled = true;
                btnBotPanic.textContent = '⏳ Panic Stopping...';
                await window.cryptoAPI.emergencyStopBot();
                setTimeout(async () => {
                    btnBotPanic.innerHTML = '<span class="btn-action-icon">🛑</span> Panic Stop';
                    btnBotPanic.disabled = false;
                    await loadBotStatus();
                }, 1000);
            }
        });
    }

    // Clear Journal Log
    if (btnClearJournal) {
        btnClearJournal.addEventListener('click', async () => {
            if (confirm("Are you sure you want to clear the trade activity log?")) {
                await window.cryptoAPI.clearBotJournal();
                await loadBotStatus();
            }
        });
    }

    // Log Filter Pills
    if (logFilterPills) {
        logFilterPills.addEventListener('click', (e) => {
            const pill = e.target.closest('.log-pill');
            if (!pill) return;
            logFilterPills.querySelectorAll('.log-pill').forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
            currentLogFilter = pill.dataset.filter || 'ALL';
            renderFilteredLog();
        });
    }

    // ================================================
    // Save & Load Functions
    // ================================================

    async function saveBotConfig() {
        const config = {
            paper_mode: botCfgPaper ? botCfgPaper.checked : true,
            market_type: botCfgMarket ? botCfgMarket.value : 'futures',
            asset_filter: botCfgAsset ? botCfgAsset.value : 'all',
            total_capital: parseFloat(botStatTotalCapInput ? botStatTotalCapInput.value : 1000) || 1000,
            sizing_mode: botCfgSizingMode ? botCfgSizingMode.value : 'fixed',
            amount_per_trade: parseFloat(botCfgAmount ? botCfgAmount.value : 50) || 50,
            trade_size_pct: parseFloat(botCfgTradePct ? botCfgTradePct.value : 5.0) || 5.0,
            risk_per_trade_pct: parseFloat(botCfgRiskPct ? botCfgRiskPct.value : 2.0) || 2.0,
            daily_profit_target: parseFloat(botCfgDailyProfitTarget ? botCfgDailyProfitTarget.value : 100) || 100,
            trailing_stop_enabled: botCfgTrailingEnabled ? botCfgTrailingEnabled.checked : false,
            trailing_stop_callback_pct: parseFloat(botCfgTrailingCallback ? botCfgTrailingCallback.value : 1.5) || 1.5,
            mtf_filter_enabled: botCfgMtfEnabled ? botCfgMtfEnabled.checked : true,
            breakeven_stop_enabled: botCfgBreakevenEnabled ? botCfgBreakevenEnabled.checked : true,
            strategy_filter: botCfgStrategy ? botCfgStrategy.value : 'ALL',
            leverage: parseInt(botCfgLeverage ? botCfgLeverage.value : 5) || 5,
            min_confidence: parseInt(botCfgConfidence ? botCfgConfidence.value : 60) || 60,
            max_positions: parseInt(botCfgMaxPos ? botCfgMaxPos.value : 3) || 3,
            max_daily_loss: parseFloat(botCfgMaxLoss ? botCfgMaxLoss.value : 50) || 50,
            max_total_exposure: parseFloat(botCfgMaxExposure ? botCfgMaxExposure.value : 500) || 500,
            scan_interval_minutes: parseInt(botCfgInterval ? botCfgInterval.value : 60) || 60,
            cooldown_hours: parseInt(botCfgCooldown ? botCfgCooldown.value : 4) || 4,
            candle_interval: botCfgTimeframe ? botCfgTimeframe.value : '1h',
        };
        await window.cryptoAPI.updateBotConfig(config);
    }

    async function loadBotStatus() {
        const data = await window.cryptoAPI.getBotStatus();
        if (!data || data.error) return;

        botIsRunning = data.running;
        const config = data.config || {};
        const stats = data.stats || {};
        cachedOpenPositions = data.open_positions || [];
        cachedLogEntries = data.recent_log || [];

        // Toggle button & header state
        if (btnBotToggle) {
            if (botIsRunning) {
                btnBotToggle.classList.add('active');
                if (botToggleLabel) botToggleLabel.textContent = 'Stop Bot';
                if (botStatusDot) botStatusDot.classList.add('active');
                if (botSubtitle) botSubtitle.textContent = `Running since ${stats.started_at || 'now'} · Last cycle: ${stats.last_cycle || 'pending'}`;
            } else {
                btnBotToggle.classList.remove('active');
                if (botToggleLabel) botToggleLabel.textContent = 'Start Bot';
                if (botStatusDot) botStatusDot.classList.remove('active');
                if (botSubtitle) botSubtitle.textContent = 'Autonomous scanning, risk-gated execution, dynamic capital allocation, and live position management';
            }
        }

        // Mode and Strategy badges
        if (botModeBadge) {
            const isPaper = config.paper_mode !== false;
            const isFutures = config.market_type === 'futures';
            botModeBadge.textContent = isPaper ? 'PAPER MODE' : (isFutures ? 'LIVE FUTURES' : 'LIVE SPOT');
            botModeBadge.className = `bot-mode-badge ${isPaper ? 'paper' : 'live'}`;
        }

        if (botStrategyBadge) {
            const strat = config.strategy_filter || 'ALL';
            botStrategyBadge.textContent = strat === 'ALL' ? 'ALL STRATEGIES' : `${strat.toUpperCase()} ONLY`;
        }

        // Capital & Portfolio Health metrics
        const totalCap = data.total_capital || config.total_capital || 1000;
        const deployedCap = data.deployed_capital || 0;
        const freeCap = data.free_capital !== undefined ? data.free_capital : Math.max(0, totalCap - deployedCap);
        const utilPct = data.capital_utilization_pct || (totalCap > 0 ? (deployedCap / totalCap * 100) : 0);

        if (botStatTotalCapInput && document.activeElement !== botStatTotalCapInput) {
            botStatTotalCapInput.value = totalCap;
        }
        if (botStatDeployedCap) botStatDeployedCap.textContent = `$${deployedCap.toFixed(2)}`;
        if (botStatDeployedPct) botStatDeployedPct.textContent = `${utilPct.toFixed(1)}% of Total`;
        if (botStatFreeCap) botStatFreeCap.textContent = `$${freeCap.toFixed(2)}`;

        const dailyPnl = data.daily_pnl || 0;
        if (botStatPnl) {
            botStatPnl.textContent = `${dailyPnl >= 0 ? '+' : ''}$${dailyPnl.toFixed(2)}`;
            botStatPnl.style.color = dailyPnl >= 0 ? 'var(--green-bull)' : 'var(--red-bear)';
        }
        if (botStatPnlSub) {
            const target = config.daily_profit_target || 100;
            botStatPnlSub.textContent = `Goal: $${target.toFixed(2)} (${dailyPnl >= target ? '🎯 HIT!' : `${Math.round(Math.max(0, dailyPnl)/target*100)}%`})`;
        }

        if (capitalBarRatio) {
            capitalBarRatio.textContent = `Deployed: $${deployedCap.toFixed(2)} / $${totalCap.toFixed(2)} (${utilPct.toFixed(1)}%)`;
        }
        if (capitalProgressFill) {
            capitalProgressFill.style.width = `${Math.min(100, utilPct)}%`;
            capitalProgressFill.style.background = utilPct > 80 ? 'var(--red-bear)' : (utilPct > 50 ? 'var(--amber-warning)' : 'var(--accent-cyan)');
        }

        // Fetch Analytics for Win Rate
        try {
            const analytics = await window.cryptoAPI.getBotAnalytics();
            if (analytics && !analytics.error) {
                if (botStatWinrate) botStatWinrate.textContent = `${analytics.win_rate_pct || 0}%`;
                if (botStatTradesSub) botStatTradesSub.textContent = `${analytics.total_closed_trades || 0} closed (${analytics.winning_trades || 0}W / ${analytics.losing_trades || 0}L)`;
            }
        } catch (e) {
            // fallback
        }

        // Sync inputs
        if (botCfgAmount && document.activeElement !== botCfgAmount) botCfgAmount.value = config.amount_per_trade || 50;
        if (botCfgTradePct && document.activeElement !== botCfgTradePct) botCfgTradePct.value = config.trade_size_pct || 5.0;
        if (botCfgRiskPct && document.activeElement !== botCfgRiskPct) botCfgRiskPct.value = config.risk_per_trade_pct || 2.0;
        if (botCfgLeverage && document.activeElement !== botCfgLeverage) botCfgLeverage.value = config.leverage || 5;
        if (botCfgSizingMode) {
            botCfgSizingMode.value = config.sizing_mode || 'fixed';
            updateSizingModeVisibility(botCfgSizingMode.value);
        }
        if (botCfgMaxPos) botCfgMaxPos.value = config.max_positions || 3;
        if (botCfgMaxLoss) botCfgMaxLoss.value = config.max_daily_loss || 50;
        if (botCfgDailyProfitTarget) botCfgDailyProfitTarget.value = config.daily_profit_target || 100;
        if (botCfgMaxExposure) botCfgMaxExposure.value = config.max_total_exposure || 500;
        if (botCfgInterval) botCfgInterval.value = config.scan_interval_minutes || 60;
        if (botCfgCooldown) botCfgCooldown.value = config.cooldown_hours || 4;
        if (botCfgConfidence) botCfgConfidence.value = config.min_confidence || 60;
        if (botCfgPaper) botCfgPaper.checked = config.paper_mode !== false;
        if (botCfgMarket) botCfgMarket.value = config.market_type || 'futures';
        if (botCfgAsset) botCfgAsset.value = config.asset_filter || 'all';
        if (botCfgStrategy) botCfgStrategy.value = config.strategy_filter || 'ALL';
        if (botCfgTimeframe) botCfgTimeframe.value = config.candle_interval || '1h';
        if (botCfgTrailingEnabled) botCfgTrailingEnabled.checked = config.trailing_stop_enabled === true;
        if (botCfgTrailingCallback) botCfgTrailingCallback.value = config.trailing_stop_callback_pct || 1.5;
        if (botCfgMtfEnabled) botCfgMtfEnabled.checked = config.mtf_filter_enabled !== false;
        if (botCfgBreakevenEnabled) botCfgBreakevenEnabled.checked = config.breakeven_stop_enabled !== false;

        // Position count & limit labels
        const maxPos = config.max_positions || 3;
        if (botPositionsCount) botPositionsCount.textContent = cachedOpenPositions.length;
        if (botPositionsLimit) botPositionsLimit.textContent = `Max ${maxPos} allowed (${cachedOpenPositions.length}/${maxPos})`;

        // Render Open Positions
        renderBotPositions(cachedOpenPositions);

        // Render Activity Log
        renderFilteredLog();

        // Auto-polling when active
        if (botPollTimer) clearInterval(botPollTimer);
        if (botIsRunning) {
            botPollTimer = setInterval(loadBotStatus, 10000);
        }
    }

    // ================================================
    // Render Open Positions with Individual Square-Off
    // ================================================
    function renderBotPositions(positions) {
        if (!botPositionsList) return;

        if (!positions || positions.length === 0) {
            botPositionsList.innerHTML = '<div class="bot-empty-state">No open positions. Start the bot or click "Run Scan Now" to begin.</div>';
            return;
        }

        const fmt = (p) => p >= 1000 ? p.toLocaleString(undefined, { maximumFractionDigits: 2 }) : p >= 1 ? p.toFixed(4) : p.toFixed(6);

        botPositionsList.innerHTML = positions.map(pos => {
            const isLong = pos.side === 'BUY';
            const dirClass = isLong ? 'long' : 'short';
            const dirLabel = isLong ? '▲ LONG' : '▼ SHORT';
            const pnl = pos.unrealized_pnl || 0;
            const pnlClass = pnl >= 0 ? 'profit' : 'loss';
            const roiPct = pos.amount_usdt > 0 ? (pnl / pos.amount_usdt * 100) : 0;
            const paperTag = pos.paper ? '<span class="paper-tag">PAPER</span>' : '<span class="live-tag">LIVE</span>';
            const levTag = pos.leverage > 1 ? `<span class="lev-tag">${pos.leverage}x</span>` : '';
            const trailingTag = pos.trailing_sl ? `<span class="trailing-tag" title="Trailing SL active at $${fmt(pos.trailing_sl)}">🚀 TSL: $${fmt(pos.trailing_sl)}</span>` : '';
            const stratTag = pos.strategy ? `<span class="strat-tag">${pos.strategy}</span>` : '';

            return `
                <div class="bot-position-card ${dirClass}" data-symbol="${pos.symbol}">
                    <div class="bot-pos-header">
                        <div class="bot-pos-symbol-wrap">
                            <span class="bot-pos-symbol">${pos.symbol.replace('USDT', '')}</span>
                            ${paperTag}
                            ${levTag}
                            ${stratTag}
                        </div>
                        <div class="bot-pos-header-right" style="display:flex; align-items:center; gap:6px;">
                            <span class="direction-badge ${dirClass}">${dirLabel}</span>
                            <button class="btn-pos-chart" data-symbol="${pos.symbol}" data-entry="${pos.entry_price}" data-sl="${pos.trailing_sl || pos.stop_loss}" data-tp="${pos.take_profit}" data-strategy="${pos.strategy || ''}" data-direction="${isLong ? 'LONG' : 'SHORT'}" title="View Position Chart">
                                📈 Chart
                            </button>
                            <button class="btn-pos-square-off" data-symbol="${pos.symbol}" title="Liquidate this position now">
                                ⚡ Close
                            </button>
                        </div>
                    </div>
                    <div class="bot-pos-details">
                        <span>Entry: $${fmt(pos.entry_price)}</span>
                        <span>Mark: $${fmt(pos.current_price || pos.entry_price)}</span>
                        <span>Margin: $${pos.amount_usdt.toFixed(1)}</span>
                        <div class="bot-pos-pnl-wrap">
                            <span class="bot-pos-pnl ${pnlClass}">${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}</span>
                            <span class="bot-pos-roi ${pnlClass}">(${roiPct >= 0 ? '+' : ''}${roiPct.toFixed(2)}%)</span>
                        </div>
                    </div>
                    <div class="bot-pos-levels">
                        <span class="sl-label">SL: $${fmt(pos.trailing_sl || pos.stop_loss)}</span>
                        ${trailingTag}
                        <span class="tp-label">TP: $${fmt(pos.take_profit)}</span>
                    </div>
                </div>
            `;
        }).join('');

        // Wire up position chart buttons
        botPositionsList.querySelectorAll('.btn-pos-chart').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const sym = btn.dataset.symbol;
                const isStock = sym && sym.endsWith('BUSDT') && sym !== 'BNBUSDT';
                const setup = {
                    symbol: sym,
                    entry: parseFloat(btn.dataset.entry),
                    sl: parseFloat(btn.dataset.sl),
                    tp: parseFloat(btn.dataset.tp),
                    strategy: btn.dataset.strategy || 'Bot Position',
                    direction: btn.dataset.direction,
                    asset: isStock ? 'STOCK' : 'CRYPTO'
                };
                openChartForSetup(setup);
            });
        });

        // Wire up individual position Square-Off buttons
        botPositionsList.querySelectorAll('.btn-pos-square-off').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const sym = btn.dataset.symbol;
                if (!sym) return;
                btn.disabled = true;
                btn.textContent = '⏳';
                try {
                    await window.cryptoAPI.squareOffPosition(sym);
                    await loadBotStatus();
                } catch (err) {
                    console.error("Individual square off failed:", err);
                    btn.disabled = false;
                    btn.textContent = '⚡ Close';
                }
            });
        });
    }

    // ================================================
    // Render Filterable Activity Log
    // ================================================
    function renderFilteredLog() {
        if (!botLogEntries) return;

        let filtered = cachedLogEntries;
        if (currentLogFilter !== 'ALL') {
            if (currentLogFilter === 'CLOSED') {
                filtered = cachedLogEntries.filter(e => e.type === 'CLOSED' || e.type === 'SQUARE_OFF' || e.type === 'SQUARE_OFF_ALL');
            } else {
                filtered = cachedLogEntries.filter(e => e.type === currentLogFilter);
            }
        }

        if (botLogCount) botLogCount.textContent = `${filtered.length} entries`;

        if (filtered.length === 0) {
            botLogEntries.innerHTML = '<div class="bot-empty-state">No matching log entries.</div>';
            return;
        }

        const typeIcons = {
            'SIGNAL': '🎯',
            'EXECUTE': '⚡',
            'OCO_PLACED': '🛡️',
            'CLOSED': '✅',
            'SQUARE_OFF': '⚡',
            'SQUARE_OFF_ALL': '⚠️',
            'TRAILING_SL': '🚀',
            'FILTERED': '🔽',
            'RISK_BLOCKED': '🚫',
            'CYCLE': '🔄',
            'BOT': '🤖',
            'START': '▶️',
            'STOP': '⏹️',
            'EMERGENCY_STOP': '🚨',
            'THROTTLE': '📉',
        };

        const typeColors = {
            'SIGNAL': 'var(--accent-cyan)',
            'EXECUTE': 'var(--green-bull)',
            'OCO_PLACED': 'var(--amber-warning)',
            'CLOSED': 'var(--green-bull)',
            'SQUARE_OFF': 'var(--amber-warning)',
            'SQUARE_OFF_ALL': 'var(--red-bear)',
            'TRAILING_SL': 'var(--accent-purple)',
            'FILTERED': 'var(--text-muted)',
            'RISK_BLOCKED': 'var(--red-bear)',
            'CYCLE': 'var(--text-secondary)',
            'BOT': 'var(--accent-purple)',
            'START': 'var(--green-bull)',
            'STOP': 'var(--text-muted)',
            'EMERGENCY_STOP': 'var(--red-bear)',
            'THROTTLE': 'var(--amber-warning)',
        };

        botLogEntries.innerHTML = filtered.map(entry => {
            const icon = typeIcons[entry.type] || '📋';
            const color = typeColors[entry.type] || 'var(--text-secondary)';
            const time = entry.timestamp ? entry.timestamp.split(' ')[1] : '';

            let detail = '';
            if (entry.type === 'SIGNAL') {
                detail = `${entry.symbol} ${entry.direction} · ${entry.strategy} · conf=${entry.confidence}%`;
            } else if (entry.type === 'EXECUTE') {
                const tag = entry.paper_trade ? ' [PAPER]' : ' [LIVE]';
                detail = `${entry.side} ${entry.symbol} · $${entry.amount_usdt} · qty=${entry.quantity}${tag}`;
            } else if (entry.type === 'CLOSED') {
                const pnlSign = entry.pnl_usdt >= 0 ? '+' : '';
                detail = `${entry.symbol} ${entry.exit_type} · Realized P&L: ${pnlSign}$${(entry.pnl_usdt || 0).toFixed(2)}`;
            } else if (entry.type === 'FILTERED' || entry.type === 'RISK_BLOCKED') {
                detail = `${entry.symbol} · ${entry.reason}`;
            } else if (entry.type === 'CYCLE') {
                detail = `Found: ${entry.signals_found} · Executed: ${entry.executed} · Filtered: ${entry.filtered} · Blocked: ${entry.risk_blocked}`;
            } else if (entry.type === 'BOT') {
                detail = `${entry.action} ${entry.details || ''}`;
            } else if (entry.type === 'TRAILING_SL') {
                detail = `${entry.details || ''}`;
            } else {
                detail = entry.details || JSON.stringify(entry).substring(0, 100);
            }

            return `
                <div class="bot-log-entry">
                    <span class="bot-log-time">${time}</span>
                    <span class="bot-log-icon">${icon}</span>
                    <span class="bot-log-type" style="color:${color}">${entry.type}</span>
                    <span class="bot-log-detail">${detail}</span>
                </div>
            `;
        }).join('');
    }

});


