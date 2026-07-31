document.addEventListener("DOMContentLoaded", () => {
    let currentScreenerData = [];
    let currentSortColumn = "score";
    let currentSortAscending = false;
    let selectedSymbolData = null;

    const chartRenderer = new CanvasCandleChart('candle-chart');

    // DOM Elements
    const searchInput = document.getElementById("search-input");
    const categorySelect = document.getElementById("category-select");
    const timeframeSelect = document.getElementById("timeframe-select");
    const signalFilterSelect = document.getElementById("signal-filter-select");
    const tableBody = document.getElementById("table-body");
    const recordsCount = document.getElementById("records-count");
    const btnRefresh = document.getElementById("btn-refresh");

    // Ticker & Stats
    const liveTickerStrip = document.getElementById("live-ticker-strip");
    const topVolSymbol = document.getElementById("top-vol-symbol");
    const topVolVal = document.getElementById("top-vol-val");
    const topGainerSymbol = document.getElementById("top-gainer-symbol");
    const topGainerVal = document.getElementById("top-gainer-val");
    const strongBuyCount = document.getElementById("strong-buy-count");
    const sentimentVal = document.getElementById("sentiment-val");
    const sentimentSub = document.getElementById("sentiment-sub");

    // Modal Elements
    const chartModal = document.getElementById("chart-modal");
    const modalSymbol = document.getElementById("modal-symbol");
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

    // Event Listeners
    btnRefresh.addEventListener("click", refreshData);
    categorySelect.addEventListener("change", refreshData);
    timeframeSelect.addEventListener("change", refreshData);
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
    refreshData();

    // Auto Refresh every 30 seconds
    setInterval(() => {
        fetchMarketSummary();
        refreshData();
    }, 30000);

    async function fetchMarketSummary() {
        const summary = await window.cryptoAPI.getMarketSummary();
        if (!summary) return;

        // Render Live Ticker Pills
        if (summary.top_volume && summary.top_volume.length > 0) {
            liveTickerStrip.innerHTML = summary.top_volume.slice(0, 6).map(t => {
                const change = parseFloat(t.priceChangePercent);
                const colorClass = change >= 0 ? 'positive' : 'negative';
                const sign = change >= 0 ? '+' : '';
                return `
                    <div class="ticker-pill">
                        <span class="symbol">${t.symbol.replace('USDT', '')}</span>
                        <span class="price">$${parseFloat(t.lastPrice).toLocaleString()}</span>
                        <span class="${colorClass}">${sign}${change.toFixed(2)}%</span>
                    </div>
                `;
            }).join('');
        }

        // Stats Cards
        if (summary.top_volume && summary.top_volume[0]) {
            const topVol = summary.top_volume[0];
            topVolSymbol.textContent = topVol.symbol;
            topVolVal.textContent = `24h Vol: $${(parseFloat(topVol.quoteVolume) / 1e6).toFixed(1)}M`;
        }

        if (summary.top_gainers && summary.top_gainers[0]) {
            const topG = summary.top_gainers[0];
            topGainerSymbol.textContent = topG.symbol;
            topGainerVal.textContent = `+${parseFloat(topG.priceChangePercent).toFixed(2)}%`;
        }
    }

    async function refreshData() {
        tableBody.innerHTML = `
            <tr>
                <td colspan="11" class="loading-cell">
                    <div class="spinner"></div> Scanning Binance pairs & calculating technical indicators...
                </td>
            </tr>
        `;

        const timeframe = timeframeSelect.value;
        const category = categorySelect.value;
        const res = await window.cryptoAPI.getScreenerData(timeframe, category);

        currentScreenerData = res.data || [];
        updateSentimentStats();
        renderTable();
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
            tableBody.innerHTML = `<tr><td colspan="11" style="text-align:center;">No crypto pairs matched the filter criteria.</td></tr>`;
            recordsCount.textContent = "0 Pairs";
            return;
        }

        let filtered = [...currentScreenerData];

        // Search Filter
        const query = searchInput.value.trim().toUpperCase();
        if (query) {
            filtered = filtered.filter(item => item.symbol.toUpperCase().includes(query));
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

            return `
                <tr>
                    <td><strong>${item.symbol}</strong></td>
                    <td><span class="badge badge-neutral">${item.category}</span></td>
                    <td style="font-family: monospace;">$${item.price < 1 ? item.price : item.price.toLocaleString()}</td>
                    <td class="${priceChangeClass}">${priceChangeSign}${item.price_change_24h}%</td>
                    <td class="${rsiClass}">${item.rsi}</td>
                    <td style="font-family: monospace;" class="${item.macd_hist >= 0 ? 'positive' : 'negative'}">${item.macd_hist}</td>
                    <td>${item.rvol}x</td>
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
        modalSymbol.textContent = data.symbol;
        modalCategory.textContent = data.category;
        modalRecommendation.textContent = data.recommendation;

        modalSignalsList.innerHTML = data.signals.map(sig => `
            <div class="signal-tag" style="background:rgba(255,255,255,0.05); padding:6px 10px; border-radius:6px; font-size:12px; border:1px solid var(--border-color);">
                ⚡ ${sig}
            </div>
        `).join('') || '<div style="font-size:12px; color:var(--text-muted);">No major alert flags active</div>';

        updateRiskCalculator();
        chartModal.classList.add("active");

        // Fetch & Draw Chart
        const timeframe = timeframeSelect.value;
        const klineRes = await window.cryptoAPI.getSymbolKlines(data.symbol, timeframe, 100);
        if (klineRes && klineRes.klines) {
            chartRenderer.render(klineRes.klines, data.symbol);
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
    // Tab Navigation: Screener ↔ Trade Signals
    // ================================================
    const tabBtns = document.querySelectorAll('.tab-btn');
    const screenerPanel = document.getElementById('screener-panel');
    const screenerTableSection = document.getElementById('screener-table-section');
    const signalsPanel = document.getElementById('signals-panel');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            const tab = btn.dataset.tab;
            if (tab === 'screener') {
                screenerPanel.style.display = '';
                screenerTableSection.style.display = '';
                signalsPanel.style.display = 'none';
            } else {
                screenerPanel.style.display = 'none';
                screenerTableSection.style.display = 'none';
                signalsPanel.style.display = '';
                // Auto-scan on first tab switch
                if (!signalsScanDone) {
                    scanTradeSignals();
                }
            }
        });
    });

    // ================================================
    // Trade Signals Panel Logic
    // ================================================
    const btnScanSignals = document.getElementById('btn-scan-signals');
    const rrSelect = document.getElementById('rr-select');
    const signalTimeframeSelect = document.getElementById('signal-timeframe-select');
    const confidenceSelect = document.getElementById('confidence-select');
    const directionFilter = document.getElementById('direction-filter');
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

        // Show loading state
        signalCardsGrid.innerHTML = `
            <div class="signal-loading glass-card">
                <div class="spinner"></div>
                <p>Scanning 24 pairs for active entry signals on <strong>${interval}</strong> timeframe...</p>
            </div>
        `;
        btnScanSignals.disabled = true;
        btnScanSignals.textContent = '⏳ Scanning...';

        try {
            const res = await window.cryptoAPI.getTradeSignals(interval, rr, 3, minConfidence);
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

        // Direction filter
        const dirFilter = directionFilter.value;
        if (dirFilter !== 'ALL') {
            filtered = filtered.filter(s => s.direction === dirFilter);
        }

        signalRecordsCount.textContent = `${filtered.length} Active Signal${filtered.length !== 1 ? 's' : ''}`;
        signalCountBadge.textContent = filtered.length;

        if (filtered.length === 0) {
            signalCardsGrid.innerHTML = `
                <div class="signal-loading glass-card">
                    <p>No active trade signals found. Try lowering the confidence filter or changing the timeframe.</p>
                </div>
            `;
            return;
        }

        signalCardsGrid.innerHTML = filtered.map(sig => {
            const dirClass = sig.direction === 'LONG' ? 'long' : 'short';
            const dirLabel = sig.direction === 'LONG' ? '▲ LONG' : '▼ SHORT';

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
                            <span class="signal-symbol">${sig.symbol.replace('USDT', '')}</span>
                            <span class="direction-badge ${dirClass}">${dirLabel}</span>
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
                        <span class="signal-strategy-name">${sig.strategy}</span>
                        <div class="signal-meta-row">
                            <span class="signal-meta-item">RSI: ${sig.rsi || '—'}</span>
                            <span class="signal-meta-item">RVOL: ${sig.rvol || '—'}x</span>
                        </div>
                    </div>

                    <div style="padding: 0 20px 16px 20px;">
                        <button class="btn-execute-trade" data-symbol="${sig.symbol}" data-strategy="${sig.strategy}" data-direction="${sig.direction}" data-entry="${sig.entry_price}" data-sl="${sig.stop_loss}" data-tp="${sig.take_profit}" data-sl-pct="${sig.sl_distance_pct}" data-tp-pct="${sig.tp_distance_pct}" data-rr="${sig.rr_ratio}">
                            ⚡ Execute Trade (Entry + SL/TP)
                        </button>
                    </div>
                </div>
            `;
        }).join('');

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

    // Re-render signal cards when direction filter changes
    directionFilter.addEventListener('change', renderSignalCards);

    // ================================================
    // Wallet Tab Logic
    // ================================================
    const walletPanel = document.getElementById('wallet-panel');
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

    // Update Tab Nav for Wallet + Bot
    const botPanel = document.getElementById('bot-panel');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            if (tab === 'wallet') {
                screenerPanel.style.display = 'none';
                screenerTableSection.style.display = 'none';
                signalsPanel.style.display = 'none';
                walletPanel.style.display = '';
                botPanel.style.display = 'none';
                if (!walletLoadedOnce) {
                    loadWallet();
                }
            } else if (tab === 'bot') {
                screenerPanel.style.display = 'none';
                screenerTableSection.style.display = 'none';
                signalsPanel.style.display = 'none';
                walletPanel.style.display = 'none';
                botPanel.style.display = '';
                loadBotStatus();
            } else if (tab === 'screener') {
                walletPanel.style.display = 'none';
                botPanel.style.display = 'none';
            } else if (tab === 'signals') {
                walletPanel.style.display = 'none';
                botPanel.style.display = 'none';
            }
        });
    });

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
    // Bot Auto-Trader Panel Logic
    // ================================================
    const btnBotToggle = document.getElementById('btn-bot-toggle');
    const botToggleLabel = document.getElementById('bot-toggle-label');
    const botToggleSwitch = document.getElementById('bot-toggle-switch');
    const botModeBadge = document.getElementById('bot-mode-badge');
    const botSubtitle = document.getElementById('bot-subtitle');
    const botStatusDot = document.getElementById('bot-status-dot');

    // Stats
    const botStatStatus = document.getElementById('bot-stat-status');
    const botStatPositions = document.getElementById('bot-stat-positions');
    const botStatPnl = document.getElementById('bot-stat-pnl');
    const botStatTrades = document.getElementById('bot-stat-trades');

    // Config fields
    const botCfgAmount = document.getElementById('bot-cfg-amount');
    const botCfgLeverage = document.getElementById('bot-cfg-leverage');
    const botCfgConfidence = document.getElementById('bot-cfg-confidence');
    const botCfgMaxPos = document.getElementById('bot-cfg-max-pos');
    const botCfgMaxLoss = document.getElementById('bot-cfg-max-loss');
    const botCfgInterval = document.getElementById('bot-cfg-interval');
    const botCfgCooldown = document.getElementById('bot-cfg-cooldown');
    const botCfgPaper = document.getElementById('bot-cfg-paper');
    const botCfgMarket = document.getElementById('bot-cfg-market');
    const btnSaveBotConfig = document.getElementById('btn-save-bot-config');

    // Positions & Log
    const botPositionsList = document.getElementById('bot-positions-list');
    const botLogEntries = document.getElementById('bot-log-entries');
    const botLogCount = document.getElementById('bot-log-count');

    let botIsRunning = false;
    let botPollTimer = null;

    // Toggle bot ON/OFF
    btnBotToggle.addEventListener('click', async () => {
        btnBotToggle.disabled = true;
        if (botIsRunning) {
            await window.cryptoAPI.stopBot();
        } else {
            // Save config first, then start
            await saveBotConfig();
            await window.cryptoAPI.startBot();
        }
        setTimeout(() => {
            loadBotStatus();
            btnBotToggle.disabled = false;
        }, 500);
    });

    // Save config
    btnSaveBotConfig.addEventListener('click', async () => {
        await saveBotConfig();
        btnSaveBotConfig.textContent = '✅ Saved!';
        setTimeout(() => { btnSaveBotConfig.textContent = '💾 Save Config'; }, 1500);
    });

    async function saveBotConfig() {
        const config = {
            paper_mode: botCfgPaper.checked,
            market_type: botCfgMarket.value,
            amount_per_trade: parseFloat(botCfgAmount.value) || 50,
            leverage: parseInt(botCfgLeverage.value) || 5,
            min_confidence: parseInt(botCfgConfidence.value) || 60,
            max_positions: parseInt(botCfgMaxPos.value) || 3,
            max_daily_loss: parseFloat(botCfgMaxLoss.value) || 50,
            scan_interval_minutes: parseInt(botCfgInterval.value) || 60,
            cooldown_hours: parseInt(botCfgCooldown.value) || 4,
        };
        await window.cryptoAPI.updateBotConfig(config);
    }

    async function loadBotStatus() {
        const data = await window.cryptoAPI.getBotStatus();
        if (data.error) return;

        botIsRunning = data.running;
        const config = data.config || {};
        const stats = data.stats || {};

        // Toggle button state
        if (botIsRunning) {
            btnBotToggle.classList.add('active');
            botToggleLabel.textContent = 'Stop Bot';
            botStatusDot.classList.add('active');
            botStatStatus.textContent = '▶ Running';
            botStatStatus.style.color = 'var(--green-bull)';
            botSubtitle.textContent = `Running since ${stats.started_at || 'now'} · Last cycle: ${stats.last_cycle || 'pending'}`;
        } else {
            btnBotToggle.classList.remove('active');
            botToggleLabel.textContent = 'Start Bot';
            botStatusDot.classList.remove('active');
            botStatStatus.textContent = '⏹ Stopped';
            botStatStatus.style.color = 'var(--text-muted)';
            botSubtitle.textContent = 'Configure and start the autonomous trading bot';
        }

        // Mode badge
        const isPaper = config.paper_mode;
        const isFutures = config.market_type === 'futures';
        botModeBadge.textContent = isPaper ? 'PAPER MODE' : (isFutures ? 'LIVE FUTURES' : 'LIVE SPOT');
        botModeBadge.className = `bot-mode-badge ${isPaper ? 'paper' : 'live'}`;

        // Stats
        const maxPos = config.max_positions || 3;
        botStatPositions.textContent = `${data.position_count} / ${maxPos}`;
        botStatPnl.textContent = `$${(data.daily_pnl || 0).toFixed(2)}`;
        botStatPnl.style.color = data.daily_pnl >= 0 ? 'var(--green-bull)' : 'var(--red-bear)';
        botStatTrades.textContent = stats.total_trades_executed || 0;

        // Sync config fields
        botCfgAmount.value = config.amount_per_trade || 50;
        botCfgLeverage.value = config.leverage || 5;
        botCfgConfidence.value = config.min_confidence || 60;
        botCfgMaxPos.value = config.max_positions || 3;
        botCfgMaxLoss.value = config.max_daily_loss || 50;
        botCfgInterval.value = config.scan_interval_minutes || 60;
        botCfgCooldown.value = config.cooldown_hours || 4;
        botCfgPaper.checked = config.paper_mode !== false;
        botCfgMarket.value = config.market_type || 'futures';

        // Render positions
        renderBotPositions(data.open_positions || []);

        // Render log
        renderBotLog(data.recent_log || []);

        // Auto-poll if running
        if (botPollTimer) clearInterval(botPollTimer);
        if (botIsRunning) {
            botPollTimer = setInterval(loadBotStatus, 10000);
        }
    }

    function renderBotPositions(positions) {
        if (positions.length === 0) {
            botPositionsList.innerHTML = '<div class="bot-empty-state">No open positions</div>';
            return;
        }

        const fmt = (p) => p >= 1000 ? p.toLocaleString(undefined, { maximumFractionDigits: 2 }) : p >= 1 ? p.toFixed(4) : p.toFixed(6);

        botPositionsList.innerHTML = positions.map(pos => {
            const isLong = pos.side === 'BUY';
            const dirClass = isLong ? 'long' : 'short';
            const dirLabel = isLong ? '▲ LONG' : '▼ SHORT';
            const pnl = pos.unrealized_pnl || 0;
            const pnlClass = pnl >= 0 ? 'profit' : 'loss';
            const paperTag = pos.paper ? '<span class="paper-tag">PAPER</span>' : '';

            return `
                <div class="bot-position-card ${dirClass}">
                    <div class="bot-pos-header">
                        <span class="bot-pos-symbol">${pos.symbol.replace('USDT', '')} ${paperTag}</span>
                        <span class="direction-badge ${dirClass}">${dirLabel}</span>
                    </div>
                    <div class="bot-pos-details">
                        <span>Entry: $${fmt(pos.entry_price)}</span>
                        <span>Qty: ${pos.quantity.toFixed(4)}</span>
                        <span class="bot-pos-pnl ${pnlClass}">${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}</span>
                    </div>
                    <div class="bot-pos-levels">
                        <span class="sl-label">SL: $${fmt(pos.stop_loss)}</span>
                        <span class="tp-label">TP: $${fmt(pos.take_profit)}</span>
                    </div>
                </div>
            `;
        }).join('');
    }

    function renderBotLog(entries) {
        if (entries.length === 0) {
            botLogEntries.innerHTML = '<div class="bot-empty-state">No activity yet. Start the bot to begin scanning.</div>';
            botLogCount.textContent = '0 entries';
            return;
        }

        botLogCount.textContent = `${entries.length} entries`;

        const typeIcons = {
            'SIGNAL': '🎯',
            'EXECUTE': '⚡',
            'OCO_PLACED': '🛡️',
            'CLOSED': '✅',
            'FILTERED': '🔽',
            'RISK_BLOCKED': '🚫',
            'CYCLE': '🔄',
            'BOT': '🤖',
        };

        const typeColors = {
            'SIGNAL': 'var(--accent-cyan)',
            'EXECUTE': 'var(--green-bull)',
            'OCO_PLACED': 'var(--amber-warning)',
            'CLOSED': 'var(--green-bull)',
            'FILTERED': 'var(--text-muted)',
            'RISK_BLOCKED': 'var(--red-bear)',
            'CYCLE': 'var(--text-secondary)',
            'BOT': 'var(--accent-purple)',
        };

        botLogEntries.innerHTML = entries.map(entry => {
            const icon = typeIcons[entry.type] || '📋';
            const color = typeColors[entry.type] || 'var(--text-secondary)';
            const time = entry.timestamp ? entry.timestamp.split(' ')[1] : '';

            let detail = '';
            if (entry.type === 'SIGNAL') {
                detail = `${entry.symbol} ${entry.direction} · ${entry.strategy} · conf=${entry.confidence}`;
            } else if (entry.type === 'EXECUTE') {
                const tag = entry.paper_trade ? ' [PAPER]' : '';
                detail = `${entry.side} ${entry.symbol} · $${entry.amount_usdt} · qty=${entry.quantity}${tag}`;
            } else if (entry.type === 'CLOSED') {
                const pnlSign = entry.pnl_usdt >= 0 ? '+' : '';
                detail = `${entry.symbol} ${entry.exit_type} · P&L: ${pnlSign}$${(entry.pnl_usdt || 0).toFixed(2)}`;
            } else if (entry.type === 'FILTERED') {
                detail = `${entry.symbol} · ${entry.reason}`;
            } else if (entry.type === 'RISK_BLOCKED') {
                detail = `${entry.symbol} · ${entry.reason}`;
            } else if (entry.type === 'CYCLE') {
                detail = `Found: ${entry.signals_found} · Executed: ${entry.executed} · Filtered: ${entry.filtered} · Blocked: ${entry.risk_blocked}`;
            } else if (entry.type === 'BOT') {
                detail = `${entry.action} ${entry.details || ''}`;
            } else {
                detail = JSON.stringify(entry).substring(0, 80);
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

