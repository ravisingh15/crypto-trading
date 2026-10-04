"""
Run Backtest — Fixed Edition.

This script fetches 6 months of historical data, classifies market regimes,
and runs all confluence strategies through the fixed backtesting engine.

Key fixes from original:
- Uses paginated data fetcher (6+ months instead of 41 days)
- Proper friction model (no double-counting)
- Regime-filtered strategies
- Correct position sizing
"""
import sys
from pathlib import Path

# Ensure project root is in path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
from backend.binance_client import binance_client
from backend.indicators import enrich_klines_dataframe
from backend.data_fetcher import fetch_multi_symbol
from backend.regime import classify_regime, get_regime_summary
from backend.strategies import STRATEGIES
from backend.backtester import generate_trades, simulate_portfolio, get_performance_metrics

# ============================================================================
# CONFIGURATION
# ============================================================================

SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'AVAXUSDT', 'NEARUSDT', 'DOGEUSDT']
INTERVAL = '1h'
MONTHS = 6  # Fetch 6 months of data

# Friction parameters
FEE_PCT = 0.00075       # 0.075% Binance taker fee per side
SLIPPAGE_PCT = 0.0003   # 0.03% slippage per side (market orders only)

# Risk management (Optimized with empirical 2.0x ATR SL for noise immunity)
SL_MULT = 2.0   # Stop-loss at 2.0x ATR (noise-immune breathing room)
TP_MULT = 3.5   # Take-profit at 3.5x ATR (1:1.75 true reward-to-risk)
MAX_BARS = 48   # Max hold time in candles
ALLOW_OVERLAP = False  # Realistic non-overlapping entries matching live bot mutex

# ============================================================================
# FETCH DATA
# ============================================================================

print("=" * 90)
print(f"CRYPTO STRATEGY BACKTEST — {MONTHS} MONTHS | {INTERVAL} CANDLES | {len(SYMBOLS)} PAIRS")
print("=" * 90)

datasets = fetch_multi_symbol(
    binance_client, SYMBOLS, INTERVAL,
    months=MONTHS,
    enrich_fn=enrich_klines_dataframe,
    use_cache=True,
)

# ============================================================================
# CLASSIFY MARKET REGIMES
# ============================================================================

print("=" * 90)
print("MARKET REGIME ANALYSIS")
print("=" * 90)

for sym, df in datasets.items():
    datasets[sym] = classify_regime(df)
    summary = get_regime_summary(df)
    regime_str = " | ".join([f"{k}: {v['pct']}%" for k, v in summary.items()])
    date_range = f"{df['open_time'].iloc[0].strftime('%Y-%m-%d')} to {df['open_time'].iloc[-1].strftime('%Y-%m-%d')}"
    print(f"  {sym:10s} [{date_range}] -> {regime_str}")

# ============================================================================
# RUN BACKTESTS
# ============================================================================

print("\n" + "=" * 90)
print(f"BACKTESTING {len(STRATEGIES)} STRATEGIES (SL={SL_MULT}x ATR, TP={TP_MULT}x ATR, Overlap={ALLOW_OVERLAP}, Friction={2*(FEE_PCT+SLIPPAGE_PCT)*100:.3f}%)")
print("=" * 90)

results = []

for strat_name, strat_info in STRATEGIES.items():
    fn = strat_info['fn']
    direction = strat_info['direction']
    
    all_trades = generate_trades(
        datasets, fn, direction,
        sl_mult=SL_MULT, tp_mult=TP_MULT,
        max_bars=MAX_BARS,
        fee_pct=FEE_PCT, slippage_pct=SLIPPAGE_PCT,
        allow_overlap=ALLOW_OVERLAP,
    )
    
    if len(all_trades) >= 5:
        df_history = simulate_portfolio(all_trades, initial_capital=10000.0, risk_per_trade_pct=0.01, sl_mult=SL_MULT)
        if not df_history.empty:
            metrics = get_performance_metrics(all_trades, df_history)
            metrics['Strategy'] = strat_name
            metrics['Direction'] = direction
            results.append(metrics)
    else:
        print(f"  {strat_name}: Only {len(all_trades)} trades (need >= 5, skipping)")

# ============================================================================
# DISPLAY RESULTS
# ============================================================================

print("\n" + "=" * 90)
print("STRATEGY COMPARISON TABLE (Sorted by Profit Factor)")
print("=" * 90)

if results:
    df_res = pd.DataFrame(results)
    
    # Reorder columns for readability
    col_order = ['Strategy', 'Direction', 'Trades', 'Win Rate (%)', 'Avg Trade (%)',
                 'Net Profit Factor', 'Portfolio Return (%)', 'Max Drawdown (%)',
                 'Sharpe Ratio', 'Sortino Ratio', 'TP Hit (%)', 'SL Hit (%)', 'Timeout (%)']
    col_order = [c for c in col_order if c in df_res.columns]
    df_res = df_res[col_order].sort_values('Net Profit Factor', ascending=False)
    
    pd.set_option('display.max_columns', 20)
    pd.set_option('display.width', 240)
    print(f"\n{df_res.to_string(index=False)}")
    
    # Highlight winners
    profitable = df_res[df_res['Net Profit Factor'] > 1.0]
    if not profitable.empty:
        print(f"\n[OK] {len(profitable)} PROFITABLE STRATEGIES (Profit Factor > 1.0):")
        for _, row in profitable.iterrows():
            print(f"   -> {row['Strategy']}: PF={row['Net Profit Factor']:.2f}, WR={row['Win Rate (%)']:.1f}%, Return={row['Portfolio Return (%)']:.1f}%")
    else:
        print("\n[!!] No strategies achieved Profit Factor > 1.0 in this period.")
        print("    This may indicate the test period was predominantly ranging/choppy.")
        print("    Check regime distribution above — if BULL_RANGE/BEAR_RANGE dominate,")
        print("    trend-following strategies will struggle (as expected).")
else:
    print("\n[FAIL] No strategies generated enough signals for evaluation.")
    print("   This may mean the market was ranging with low ADX (< 25) throughout the test period.")

print("\n" + "=" * 90)
