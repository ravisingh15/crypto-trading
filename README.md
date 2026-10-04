# Binance Live Crypto Analysis & Screener

> A high-performance, real-time Cryptocurrency Market Screener and Technical Analysis platform powered by the Binance REST API. Features parallel multi-factor pair screening, vectorized technical indicators, signal scoring, an interactive web dashboard, and dedicated Jupyter notebooks for exploratory data analysis.

---

## Key Features

1. **Secure Credential Management**:
   - Strictly git-ignored `.env` file for private `API_KEY` and `SECRET_KEY`.
   - `.env.example` template for public repository deployment without secret leaks.

2. **Real-Time Technical Analysis Engine**:
   - **RSI (14)**: Relative Strength Index oversold (<30) and overbought (>70) detection.
   - **MACD (12, 26, 9)**: Bullish & Bearish signal line crossover tracking.
   - **EMA Stack (9, 21, 50, 200)**: Trend direction stack & Golden Cross identification.
   - **Bollinger Bands (20, 2)**: Bandwidth percentage calculation and volatility compression.
   - **RVOL (Relative Volume)**: Volume spike detection vs 20-period moving average.
   - **ATR (14)**: Average True Range calculation for dynamic Stop Loss & Take Profit targets.

3. **Multi-Factor Crypto Screener**:
   - Parallel multi-threaded scanning across Binance USDT pairs.
   - Composite Signal Scoring model (-100 to +100) categorizing pairs into **STRONG BUY**, **BUY**, **NEUTRAL**, **SELL**, or **STRONG SELL**.
   - Sector/Category filters (Layer 1, AI / Data, DeFi, Meme, Layer 2).

4. **Multi-Timeframe (MTF) Trend Confluence & Strategy Alpha Tiers**:
   - **Higher-Timeframe Alignment**: Live signal generation cross-references higher timeframes (15m → 1h, 1h → 4h, 4h → 1d) via EMA 21/50 slope and price structure.
   - **Empirical Alpha Tiers**: Strategy registry enriched with 6-month empirical backtest ratings (**Tier A+**, **A**, **B+**, **B**, **C**) and historical Profit Factors (e.g. RSI Divergence 1.17 PF, Trend Pullback 1.15 PF).
   - **Confluence Scoring**: +12 confidence points awarded for trend-aligned signals; counter-trend setups receive confidence penalties.

5. **Autonomous Trading Bot & Advanced Risk Guardrails**:
   - **Dynamic Breakeven Stop Ratchet**: When an open position reaches $\ge 1.0R$ profit, the bot automatically moves the Stop-Loss to entry + fee buffer to lock in a risk-free trade.
   - **MTF Trend Filter**: Autonomous cycle skips counter-trend entries against higher-timeframe biases, preventing chop bleed.
   - **Dynamic Position Sizing**: Supports Fixed USDT, Percent of Capital, and Kelly/Risk % sizing models with leverage and emergency square-off.

6. **Interactive Web Dashboard & Pro High-Definition Chart Engine**:
   - Glassmorphic dark trading UI built with vanilla HTML/CSS/JS.
   - **Pro HD Multi-Pane Charting**: DPI-aware canvas chart with Price Candlesticks, Volume, and an integrated RSI (14) sub-pane (70/50/30 zones).
   - **Dynamic Overlays**: EMA 9, 21, 50, Bollinger Bands envelopes/clouds, and trade setup target zones (Entry, SL, TP).
   - **Trade Signals Terminal**: Real-time coin/strategy search, MTF filter, Alpha Tier filter, and 1-click execution or chart visualization.
   - **Live Wallet & Bot Monitor**: Real-time open positions, trailing SL tracker, PnL analytics, and audit journal.
   
   ![Market Screener Dashboard](assets/screenshots/screener_dashboard.png)
   
   ![Trade Signals Terminal](assets/screenshots/trade_signals_dashboard.png)
   
   ![Wallet Dashboard](assets/screenshots/wallet_panel.png)
   
   ![Trade Confirmation Modal](assets/screenshots/trade_modal.png)

7. **Interactive Jupyter Notebooks**:
   - `01_binance_data_exploration.ipynb`: Market summary, 24-hour volume leaders, and candlestick ingestion.
   - `02_indicator_deep_dive.ipynb`: Multi-indicator plotting with Plotly dark themes.
   - `03_screener_backtest.ipynb`: Backtesting technical signal rules against historical klines.
   - `04_strategy_backtest_comparison.ipynb`: 20-strategy comparison with win rate, Sharpe ratio, equity curves, and composite ranking.
   - `05_multi_timeframe_analysis.ipynb`: Multi-timeframe (5m/15m/1h/4h) 20-strategy comparison plus Crypto vs Gold (XAUTUSDT, PAXGUSDT) analysis.
   - `06_atr_risk_management_backtest.ipynb`: Bar-by-bar ATR Stop-Loss & Take-Profit simulator testing 1:1.5, 1:2.0, and 1:3.0 Risk-to-Reward ratios and account equity growth ($1,000 capital, 2% risk/trade).

---

## Repository Structure

```
crypto-analysis/
├── .env                               # Private API credentials (GIT IGNORED)
├── .env.example                       # Safe environment variable template
├── .gitignore                         # Standard exclusion rules
├── README.md                          # Documentation & project guide
├── requirements.txt                   # Dependencies (FastAPI, Pandas, Jupyter, Plotly)
├── assets/
│   └── screenshots/                   # UI documentation screenshots
├── notebooks/                         # Jupyter Notebooks for analysis
│   ├── 01_binance_data_exploration.ipynb
│   ├── 02_indicator_deep_dive.ipynb
│   ├── 03_screener_backtest.ipynb
│   ├── 04_strategy_backtest_comparison.ipynb
│   ├── 05_multi_timeframe_analysis.ipynb
│   └── 06_atr_risk_management_backtest.ipynb
├── backend/
│   ├── config.py                      # Environment configuration loader
│   ├── binance_client.py              # REST API client with failover endpoints
│   ├── indicators.py                  # Vectorized Technical Indicators Engine
│   ├── screener.py                    # Multi-pair Screener & Signal Scoring
│   └── app.py                         # FastAPI Web Server & Static File Host
└── frontend/
    ├── index.html                     # Web Dashboard layout
    ├── css/
    │   └── styles.css                 # Dark mode glassmorphic CSS theme
    └── js/
        ├── api.js                     # API communications client
        ├── chart.js                   # Canvas candlestick charting renderer
        └── app.js                     # Interactive table UI & position calculator
```

---

## Quick Start Guide

### 🚀 1-Click Launch (Windows)
Simply **double-click** [`start.bat`](file:///c:/Users/rvsdc/crypto-analysis/start.bat) in the project folder!
- It automatically verifies Python, installs missing dependencies if needed, starts the FastAPI server, and opens **`http://127.0.0.1:8000`** in your default web browser.

---

### Manual Launch

#### 1. Prerequisites
- Ensure you have **Python 3.10+** installed.
- A **Binance Account** is required to generate API keys for live data and trading. If you don't have one, you can [sign up here using this referral link](https://www.binance.com/referral/earn-together/refer2earn-usdc/claim?hl=en-IN&ref=GRO_28502_VRJ5Y&utm_source=referral_entrance) to claim a sign-up bonus.

#### 2. Configure Environment Variables
Copy `.env.example` to `.env` and enter your Binance API Key and Secret:
```bash
cp .env.example .env
```
*(Your `.env` file is protected by `.gitignore` and will never be committed to Git.)*

#### 3. Install Dependencies
Install required packages using `pip`:
```bash
pip install -r requirements.txt
```

#### 4. Run the Screener Server & Web Dashboard
Launch the FastAPI server:
```bash
python -m backend.app
# OR
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
```
Open your browser and navigate directly to:
👉 **`http://127.0.0.1:8000`** (or `/index`, `/dashboard`)


---

## Using Jupyter Notebooks

Launch Jupyter Notebook to perform custom research and backtesting:
```bash
jupyter notebook
```
Navigate to the `notebooks/` directory and open any of the notebooks:
- **`01_binance_data_exploration.ipynb`**: Fetch 24-hour market metrics & ticker statistics.
- **`02_indicator_deep_dive.ipynb`**: Plot RSI, MACD, and EMA charts interactively.
- **`03_screener_backtest.ipynb`**: Test technical signal win-rates against historical candles.
- **`04_strategy_backtest_comparison.ipynb`**: Full 20-strategy backtest comparison with performance metrics, heatmaps, and equity curves.
- **`05_multi_timeframe_analysis.ipynb`**: Multi-timeframe (5m/15m/1h/4h) analysis and Crypto vs Gold comparison.
- **`06_atr_risk_management_backtest.ipynb`**: Dynamic ATR Stop-Loss / Take-Profit backtester with account equity growth simulation.

---

## Security Best Practices

- **Never hardcode API Keys**: Always read credentials from `.env` via `backend/config.py`.
- **Binance API Key Permissions**: For read-only screening, enable **only Read Info / Market Data** permissions on Binance. Disable Withdrawal permissions on your API key.
- **Git Verification**: Run `git status` before committing to confirm `.env` is un-tracked.

---

## License
This project is open source and available under the [MIT License](LICENSE).
