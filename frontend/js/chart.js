/**
 * High-Definition Canvas Candlestick & Technical Analysis Chart Engine
 * Features:
 * - High-DPI (Retina / 4K) crisp rendering
 * - Multi-Pane layout: Price Candlesticks + Volume + RSI (14)
 * - Vectorized Technical Overlays: EMA 9, EMA 21, EMA 50, Bollinger Bands
 * - Interactive Crosshair with Hairline coordinate markers and date/price tags
 * - Interactive Top HUD with candle OHLCV, % change, RSI, and MA values
 * - Actionable Trade Setup Overlay: Entry, Stop Loss, and Take Profit levels with shaded R:R zones
 */
class CanvasCandleChart {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');

        // State
        this.klines = [];
        this.symbol = "BTCUSDT";
        this.timeframe = "1h";
        this.tradeSetup = null; // { entry, sl, tp, direction, rr }
        this.hoveredIndex = null;
        this.mousePos = null;

        // Display toggles
        this.toggles = {
            ema: true,
            bb: true,
            volume: true,
            rsi: true,
            tradeSetup: true,
        };

        // Attach event listeners for crosshair
        this._bindEvents();
    }

    _bindEvents() {
        if (!this.canvas) return;

        const onMove = (e) => {
            if (!this.klines || this.klines.length === 0) return;
            const rect = this.canvas.getBoundingClientRect();
            const clientX = e.touches ? e.touches[0].clientX : e.clientX;
            const clientY = e.touches ? e.touches[0].clientY : e.clientY;
            const x = clientX - rect.left;
            const y = clientY - rect.top;

            this.mousePos = { x, y };

            // Determine hovered candle
            const padding = this._getPadding();
            const chartWidth = this.cssWidth - padding.left - padding.right;
            const count = this.klines.length;
            const candleSlot = chartWidth / count;

            if (x >= padding.left && x <= this.cssWidth - padding.right) {
                const idx = Math.floor((x - padding.left) / candleSlot);
                this.hoveredIndex = Math.max(0, Math.min(count - 1, idx));
            } else {
                this.hoveredIndex = null;
            }

            this._draw();
        };

        const onLeave = () => {
            this.mousePos = null;
            this.hoveredIndex = null;
            this._draw();
        };

        this.canvas.addEventListener('mousemove', onMove);
        this.canvas.addEventListener('mouseleave', onLeave);
        this.canvas.addEventListener('touchmove', onMove, { passive: true });
        this.canvas.addEventListener('touchend', onLeave);
    }

    _getPadding() {
        return { top: 34, right: 68, bottom: 26, left: 16 };
    }

    formatPrice(price) {
        if (price === null || price === undefined || isNaN(price)) return "--";
        const val = parseFloat(price);
        if (val >= 1000) return val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        if (val >= 1) return val.toFixed(2);
        if (val >= 0.01) return val.toFixed(4);
        return val.toFixed(6);
    }

    formatVolume(vol) {
        if (!vol || isNaN(vol)) return "0";
        if (vol >= 1e9) return (vol / 1e9).toFixed(2) + "B";
        if (vol >= 1e6) return (vol / 1e6).toFixed(2) + "M";
        if (vol >= 1e3) return (vol / 1e3).toFixed(1) + "K";
        return Math.round(vol).toString();
    }

    formatTime(ts) {
        if (!ts) return "";
        const d = new Date(ts * 1000);
        const m = (d.getMonth() + 1).toString().padStart(2, '0');
        const day = d.getDate().toString().padStart(2, '0');
        const h = d.getHours().toString().padStart(2, '0');
        const min = d.getMinutes().toString().padStart(2, '0');
        return `${m}/${day} ${h}:${min}`;
    }

    setTradeSetup(setup) {
        this.tradeSetup = setup;
        this._draw();
    }

    clearTradeSetup() {
        this.tradeSetup = null;
        this._draw();
    }

    toggleIndicator(key) {
        if (this.toggles[key] !== undefined) {
            this.toggles[key] = !this.toggles[key];
            this._draw();
        }
    }

    render(klines, symbol = "BTCUSDT", tradeSetup = null, timeframe = "1h") {
        if (!this.canvas) return;
        this.klines = klines || [];
        this.symbol = symbol;
        this.timeframe = timeframe;
        if (tradeSetup !== undefined) {
            this.tradeSetup = tradeSetup;
        }

        this._setupDPI();
        this._draw();
    }

    _setupDPI() {
        const dpr = window.devicePixelRatio || 1;
        const rect = this.canvas.getBoundingClientRect();
        const cssWidth = rect.width > 0 ? rect.width : (this.canvas.width || 800);
        const cssHeight = rect.height > 0 ? rect.height : (this.canvas.height || 420);

        this.canvas.width = Math.round(cssWidth * dpr);
        this.canvas.height = Math.round(cssHeight * dpr);

        this.ctx.resetTransform?.();
        this.ctx.scale(dpr, dpr);

        this.cssWidth = cssWidth;
        this.cssHeight = cssHeight;
    }

    _draw() {
        if (!this.canvas || !this.klines || this.klines.length === 0) return;

        const ctx = this.ctx;
        const width = this.cssWidth || 800;
        const height = this.cssHeight || 420;
        const padding = this._getPadding();

        // Pane heights: Price pane 68%, RSI/Volume pane 32%
        const subPaneHeight = this.toggles.rsi ? Math.round(height * 0.26) : 0;
        const pricePaneHeight = height - padding.top - padding.bottom - (subPaneHeight > 0 ? subPaneHeight + 14 : 0);
        const pricePaneBottom = padding.top + pricePaneHeight;
        const subPaneTop = pricePaneBottom + 14;

        const chartWidth = width - padding.left - padding.right;
        const candleCount = this.klines.length;
        const candleSlot = chartWidth / candleCount;
        const candleWidth = Math.max(2, candleSlot * 0.68);

        // 1. Clear Background
        ctx.fillStyle = '#07090e';
        ctx.fillRect(0, 0, width, height);

        // Subtle gradient background
        const grad = ctx.createLinearGradient(0, 0, 0, height);
        grad.addColorStop(0, 'rgba(15, 23, 42, 0.45)');
        grad.addColorStop(1, 'rgba(7, 9, 14, 0.95)');
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, width, height);

        // 2. Compute Price Range
        let highs = this.klines.map(k => k.high);
        let lows = this.klines.map(k => k.low);

        if (this.toggles.bb) {
            this.klines.forEach(k => {
                if (k.bb_upper) highs.push(k.bb_upper);
                if (k.bb_lower) lows.push(k.bb_lower);
            });
        }

        // Include Trade Setup levels if present so they are always visible
        if (this.toggles.tradeSetup && this.tradeSetup) {
            if (this.tradeSetup.entry) { highs.push(this.tradeSetup.entry); lows.push(this.tradeSetup.entry); }
            if (this.tradeSetup.sl) { highs.push(this.tradeSetup.sl); lows.push(this.tradeSetup.sl); }
            if (this.tradeSetup.tp) { highs.push(this.tradeSetup.tp); lows.push(this.tradeSetup.tp); }
        }

        let maxPrice = Math.max(...highs);
        let minPrice = Math.min(...lows);
        let priceSpan = maxPrice - minPrice || 1;
        // 4% margin
        maxPrice += priceSpan * 0.04;
        minPrice -= priceSpan * 0.04;
        priceSpan = maxPrice - minPrice || 1;

        // Coordinate helper functions
        const getX = (i) => padding.left + (i * candleSlot) + (candleSlot / 2);
        const getY = (p) => padding.top + pricePaneHeight - (((p - minPrice) / priceSpan) * pricePaneHeight);

        // 3. Price Grid Lines & Axis
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 4]);

        const gridSteps = 4;
        for (let i = 0; i <= gridSteps; i++) {
            const y = padding.top + (pricePaneHeight * (i / gridSteps));
            const priceVal = maxPrice - (priceSpan * (i / gridSteps));

            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(width - padding.right, y);
            ctx.stroke();

            // Price text
            ctx.fillStyle = '#64748b';
            ctx.font = '10px "Inter", monospace';
            ctx.textAlign = 'left';
            ctx.fillText(this.formatPrice(priceVal), width - padding.right + 6, y + 3);
        }
        ctx.setLineDash([]);

        // 4. Trade Setup Visual Overlay (Risk / Reward boxes and lines)
        if (this.toggles.tradeSetup && this.tradeSetup && this.tradeSetup.entry) {
            const entry = parseFloat(this.tradeSetup.entry);
            const sl = parseFloat(this.tradeSetup.sl);
            const tp = parseFloat(this.tradeSetup.tp);
            const dir = this.tradeSetup.direction || (tp > entry ? 'LONG' : 'SHORT');

            const entryY = getY(entry);
            const slY = getY(sl);
            const tpY = getY(tp);

            // Shaded Risk Box
            ctx.fillStyle = 'rgba(244, 63, 94, 0.12)';
            const riskTop = Math.min(entryY, slY);
            const riskH = Math.abs(entryY - slY);
            ctx.fillRect(padding.left, riskTop, chartWidth, riskH);

            // Shaded Reward Box
            ctx.fillStyle = 'rgba(16, 185, 129, 0.12)';
            const rewardTop = Math.min(entryY, tpY);
            const rewardH = Math.abs(entryY - tpY);
            ctx.fillRect(padding.left, rewardTop, chartWidth, rewardH);

            // Entry Line
            ctx.strokeStyle = '#38bdf8';
            ctx.lineWidth = 1.5;
            ctx.setLineDash([5, 4]);
            ctx.beginPath();
            ctx.moveTo(padding.left, entryY);
            ctx.lineTo(width - padding.right, entryY);
            ctx.stroke();

            // Stop Loss Line
            ctx.strokeStyle = '#f43f5e';
            ctx.lineWidth = 1.5;
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            ctx.moveTo(padding.left, slY);
            ctx.lineTo(width - padding.right, slY);
            ctx.stroke();

            // Take Profit Line
            ctx.strokeStyle = '#10b981';
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.moveTo(padding.left, tpY);
            ctx.lineTo(width - padding.right, tpY);
            ctx.stroke();
            ctx.setLineDash([]);

            // Level Labels
            this._drawLevelBadge(ctx, width - padding.right + 2, entryY, `ENTRY $${this.formatPrice(entry)}`, '#0284c7');
            const slDistPct = Math.abs((entry - sl) / entry * 100).toFixed(1);
            this._drawLevelBadge(ctx, width - padding.right + 2, slY, `SL $${this.formatPrice(sl)} (-${slDistPct}%)`, '#e11d48');
            const tpDistPct = Math.abs((tp - entry) / entry * 100).toFixed(1);
            this._drawLevelBadge(ctx, width - padding.right + 2, tpY, `TP $${this.formatPrice(tp)} (+${tpDistPct}%)`, '#059669');
        }

        // 5. Bollinger Bands (Cloud & Lines)
        if (this.toggles.bb && this.klines.some(k => k.bb_upper && k.bb_lower)) {
            // BB Cloud
            ctx.fillStyle = 'rgba(56, 189, 248, 0.04)';
            ctx.beginPath();
            let first = true;
            for (let i = 0; i < candleCount; i++) {
                const k = this.klines[i];
                if (k.bb_upper) {
                    const x = getX(i);
                    const y = getY(k.bb_upper);
                    if (first) { ctx.moveTo(x, y); first = false; }
                    else ctx.lineTo(x, y);
                }
            }
            for (let i = candleCount - 1; i >= 0; i--) {
                const k = this.klines[i];
                if (k.bb_lower) {
                    ctx.lineTo(getX(i), getY(k.bb_lower));
                }
            }
            ctx.closePath();
            ctx.fill();

            // BB Upper Line
            this._drawPathLine(ctx, this.klines, k => k.bb_upper, getX, getY, 'rgba(56, 189, 248, 0.35)', 1, [2, 2]);
            // BB Lower Line
            this._drawPathLine(ctx, this.klines, k => k.bb_lower, getX, getY, 'rgba(56, 189, 248, 0.35)', 1, [2, 2]);
            // BB Middle Line
            this._drawPathLine(ctx, this.klines, k => k.bb_middle, getX, getY, 'rgba(148, 163, 184, 0.35)', 1, [1, 2]);
        }

        // 6. Volume Histogram in Main Pane Bottom
        if (this.toggles.volume) {
            const vols = this.klines.map(k => k.volume || 0);
            const maxVol = Math.max(...vols) || 1;
            const maxVolH = pricePaneHeight * 0.20;

            this.klines.forEach((k, i) => {
                const x = getX(i);
                const volH = Math.max(1, (k.volume / maxVol) * maxVolH);
                const isBull = k.close >= k.open;
                ctx.fillStyle = isBull ? 'rgba(0, 245, 160, 0.18)' : 'rgba(255, 73, 92, 0.18)';
                ctx.fillRect(x - (candleWidth / 2), pricePaneBottom - volH, candleWidth, volH);
            });
        }

        // 7. Candlesticks
        this.klines.forEach((k, i) => {
            const x = getX(i);
            const openY = getY(k.open);
            const closeY = getY(k.close);
            const highY = getY(k.high);
            const lowY = getY(k.low);

            const isBullish = k.close >= k.open;
            const color = isBullish ? '#00f5a0' : '#ff495c';

            // Wick
            ctx.strokeStyle = color;
            ctx.lineWidth = 1.2;
            ctx.beginPath();
            ctx.moveTo(x, highY);
            ctx.lineTo(x, lowY);
            ctx.stroke();

            // Body
            ctx.fillStyle = color;
            const bodyY = Math.min(openY, closeY);
            const bodyHeight = Math.max(2, Math.abs(closeY - openY));
            ctx.fillRect(x - (candleWidth / 2), bodyY, candleWidth, bodyHeight);
        });

        // 8. EMA Lines Overlay
        if (this.toggles.ema) {
            // EMA 9 (Cyan)
            this._drawPathLine(ctx, this.klines, k => k.ema_9, getX, getY, '#00d2ff', 1.8);
            // EMA 21 (Amber)
            this._drawPathLine(ctx, this.klines, k => k.ema_21, getX, getY, '#ffb703', 1.8);
            // EMA 50 (Purple)
            this._drawPathLine(ctx, this.klines, k => k.ema_50, getX, getY, '#c084fc', 1.4);
        }

        // 9. RSI Sub-Pane
        if (this.toggles.rsi && subPaneHeight > 0) {
            // Separator Line
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(padding.left, subPaneTop - 8);
            ctx.lineTo(width - padding.right, subPaneTop - 8);
            ctx.stroke();

            // RSI Background Area
            ctx.fillStyle = 'rgba(15, 23, 42, 0.5)';
            ctx.fillRect(padding.left, subPaneTop, chartWidth, subPaneHeight);

            const rsiY = (v) => subPaneTop + subPaneHeight - ((v / 100) * subPaneHeight);

            // Overbought zone (70-100)
            ctx.fillStyle = 'rgba(244, 63, 94, 0.05)';
            ctx.fillRect(padding.left, subPaneTop, chartWidth, rsiY(70) - subPaneTop);

            // Oversold zone (0-30)
            ctx.fillStyle = 'rgba(16, 185, 129, 0.05)';
            ctx.fillRect(padding.left, rsiY(30), chartWidth, (subPaneTop + subPaneHeight) - rsiY(30));

            // Reference Lines 70, 50, 30
            ctx.setLineDash([2, 4]);
            // 70 Line (Red)
            ctx.strokeStyle = 'rgba(244, 63, 94, 0.4)';
            ctx.beginPath();
            ctx.moveTo(padding.left, rsiY(70));
            ctx.lineTo(width - padding.right, rsiY(70));
            ctx.stroke();

            // 50 Midline (Gray)
            ctx.strokeStyle = 'rgba(100, 116, 139, 0.3)';
            ctx.beginPath();
            ctx.moveTo(padding.left, rsiY(50));
            ctx.lineTo(width - padding.right, rsiY(50));
            ctx.stroke();

            // 30 Line (Green)
            ctx.strokeStyle = 'rgba(16, 185, 129, 0.4)';
            ctx.beginPath();
            ctx.moveTo(padding.left, rsiY(30));
            ctx.lineTo(width - padding.right, rsiY(30));
            ctx.stroke();
            ctx.setLineDash([]);

            // Axis labels for RSI
            ctx.font = '9px monospace';
            ctx.fillStyle = '#f43f5e';
            ctx.fillText('70', width - padding.right + 6, rsiY(70) + 3);
            ctx.fillStyle = '#64748b';
            ctx.fillText('50', width - padding.right + 6, rsiY(50) + 3);
            ctx.fillStyle = '#10b981';
            ctx.fillText('30', width - padding.right + 6, rsiY(30) + 3);

            // RSI Curve
            ctx.strokeStyle = '#38bdf8';
            ctx.lineWidth = 1.6;
            ctx.beginPath();
            let rsiStarted = false;
            this.klines.forEach((k, i) => {
                if (k.rsi !== null && k.rsi !== undefined && !isNaN(k.rsi)) {
                    const x = getX(i);
                    const y = rsiY(k.rsi);
                    if (!rsiStarted) { ctx.moveTo(x, y); rsiStarted = true; }
                    else ctx.lineTo(x, y);
                }
            });
            ctx.stroke();

            // RSI Sub-Pane Label
            ctx.fillStyle = '#94a3b8';
            ctx.font = '10px "Inter", sans-serif';
            ctx.fillText('RSI (14)', padding.left + 4, subPaneTop + 14);
        }

        // 10. Interactive Crosshair & Cursor Tags
        if (this.mousePos && this.hoveredIndex !== null) {
            const hIdx = this.hoveredIndex;
            const hCandle = this.klines[hIdx];
            const crossX = getX(hIdx);
            const crossY = Math.max(padding.top, Math.min(pricePaneBottom, this.mousePos.y));

            // Hairlines
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
            ctx.lineWidth = 1;
            ctx.setLineDash([3, 3]);

            // Vertical hairline
            ctx.beginPath();
            ctx.moveTo(crossX, padding.top);
            ctx.lineTo(crossX, height - padding.bottom);
            ctx.stroke();

            // Horizontal hairline in price pane
            if (this.mousePos.y <= pricePaneBottom) {
                ctx.beginPath();
                ctx.moveTo(padding.left, crossY);
                ctx.lineTo(width - padding.right, crossY);
                ctx.stroke();

                // Price badge on right axis
                const priceAtCursor = maxPrice - (((crossY - padding.top) / pricePaneHeight) * priceSpan);
                this._drawAxisBadge(ctx, width - padding.right, crossY, this.formatPrice(priceAtCursor), '#334155');
            }
            ctx.setLineDash([]);

            // Time badge on bottom axis
            const timeStr = this.formatTime(hCandle.time);
            this._drawTimeBadge(ctx, crossX, height - padding.bottom + 8, timeStr);
        }

        // 11. Top HUD Header
        this._drawHUD(ctx, width, padding);
    }

    _drawPathLine(ctx, klines, valGetter, getX, getY, color, lineWidth = 1.5, dash = []) {
        ctx.strokeStyle = color;
        ctx.lineWidth = lineWidth;
        if (dash.length > 0) ctx.setLineDash(dash);
        ctx.beginPath();
        let started = false;
        klines.forEach((k, i) => {
            const val = valGetter(k);
            if (val !== null && val !== undefined && !isNaN(val)) {
                const x = getX(i);
                const y = getY(val);
                if (!started) { ctx.moveTo(x, y); started = true; }
                else ctx.lineTo(x, y);
            }
        });
        ctx.stroke();
        if (dash.length > 0) ctx.setLineDash([]);
    }

    _drawLevelBadge(ctx, x, y, text, color) {
        ctx.font = '10px "Inter", sans-serif';
        const txtWidth = ctx.measureText(text).width;
        ctx.fillStyle = color;
        ctx.fillRect(x, y - 8, txtWidth + 8, 16);
        ctx.fillStyle = '#ffffff';
        ctx.fillText(text, x + 4, y + 4);
    }

    _drawAxisBadge(ctx, x, y, text, bgColor) {
        ctx.font = '10px monospace';
        const w = ctx.measureText(text).width + 8;
        ctx.fillStyle = bgColor;
        ctx.fillRect(x + 2, y - 8, w, 16);
        ctx.fillStyle = '#f8fafc';
        ctx.fillText(text, x + 6, y + 4);
    }

    _drawTimeBadge(ctx, x, y, text) {
        ctx.font = '10px monospace';
        const w = ctx.measureText(text).width + 8;
        ctx.fillStyle = '#334155';
        ctx.fillRect(x - (w / 2), y, w, 16);
        ctx.fillStyle = '#f8fafc';
        ctx.textAlign = 'center';
        ctx.fillText(text, x, y + 12);
        ctx.textAlign = 'left';
    }

    _drawHUD(ctx, width, padding) {
        const candle = (this.hoveredIndex !== null && this.klines[this.hoveredIndex])
            ? this.klines[this.hoveredIndex]
            : this.klines[this.klines.length - 1];

        if (!candle) return;

        const isHover = this.hoveredIndex !== null;
        const changePct = candle.open ? (((candle.close - candle.open) / candle.open) * 100) : 0;
        const changeColor = changePct >= 0 ? '#00f5a0' : '#ff495c';

        // Title text
        ctx.fillStyle = '#f8fafc';
        ctx.font = 'bold 12px "Outfit", sans-serif';
        const title = `${this.symbol} · ${this.timeframe.toUpperCase()}`;
        ctx.fillText(title, padding.left, 18);

        let curX = padding.left + ctx.measureText(title).width + 16;

        ctx.font = '11px "Inter", monospace';

        // Time
        ctx.fillStyle = '#94a3b8';
        const tStr = this.formatTime(candle.time);
        ctx.fillText(tStr, curX, 18);
        curX += ctx.measureText(tStr).width + 14;

        // O H L C
        const ohlc = [
            { l: 'O:', v: this.formatPrice(candle.open), c: '#cbd5e1' },
            { l: 'H:', v: this.formatPrice(candle.high), c: '#cbd5e1' },
            { l: 'L:', v: this.formatPrice(candle.low), c: '#cbd5e1' },
            { l: 'C:', v: this.formatPrice(candle.close), c: changeColor },
            { l: '', v: (changePct >= 0 ? '+' : '') + changePct.toFixed(2) + '%', c: changeColor },
        ];

        ohlc.forEach(item => {
            if (curX > width - 240) return;
            if (item.l) {
                ctx.fillStyle = '#64748b';
                ctx.fillText(item.l, curX, 18);
                curX += ctx.measureText(item.l).width + 2;
            }
            ctx.fillStyle = item.c;
            ctx.fillText(item.v, curX, 18);
            curX += ctx.measureText(item.v).width + 8;
        });

        // Indicators in HUD
        if (candle.rsi !== null && candle.rsi !== undefined && curX < width - 160) {
            ctx.fillStyle = '#38bdf8';
            const rsiStr = `RSI: ${candle.rsi.toFixed(1)}`;
            ctx.fillText(rsiStr, curX, 18);
            curX += ctx.measureText(rsiStr).width + 10;
        }

        // Legend Pills in Top Right
        ctx.textAlign = 'right';
        ctx.font = '10px "Inter", sans-serif';
        const legendX = width - padding.right;

        ctx.fillStyle = '#00d2ff';
        ctx.fillText('■ EMA9', legendX - 100, 18);
        ctx.fillStyle = '#ffb703';
        ctx.fillText('■ EMA21', legendX - 50, 18);
        ctx.fillStyle = '#c084fc';
        ctx.fillText('■ EMA50', legendX, 18);

        ctx.textAlign = 'left';
    }
}

window.CanvasCandleChart = CanvasCandleChart;
