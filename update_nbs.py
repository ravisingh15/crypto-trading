import json
import nbformat
from pathlib import Path

def update_notebook_06():
    path = Path("notebooks/06_atr_risk_management_backtest.ipynb")
    if not path.exists():
        return
        
    with open(path, "r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)
        
    # Replace cell index 6 and 7 (Simulator Engine and Execution Engine)
    # Actually, we can just find the cells by scanning for text
    
    for idx, cell in enumerate(nb.cells):
        if cell.cell_type == "code" and "Institutional Trade Simulator Engine" in cell.source:
            cell.source = """from backend.backtester import generate_trades, simulate_portfolio, get_performance_metrics
print('Institutional Trade Simulator Engine imported from backend.backtester.')"""
        
        elif cell.cell_type == "code" and "RISK_MODES = ['static', 'breakeven', 'trailing']" in cell.source:
            # We replace the execution cell with the new logic
            cell.source = """RR_CONFIGS = [
    {'label': '1:1.5 R:R', 'sl_mult': 1.5, 'tp_mult': 2.25},
    {'label': '1:2.0 R:R', 'sl_mult': 1.5, 'tp_mult': 3.00},
    {'label': '1:3.0 R:R', 'sl_mult': 1.0, 'tp_mult': 3.00},
]

backtest_results = []

for tf in TIMEFRAMES:
    sym_dict = datasets.get(tf, {})
    for strat_name, strat_info in STRATEGIES.items():
        fn = strat_info['fn']
        direction = strat_info['direction']
        
        for rr in RR_CONFIGS:
            # Generate all trades across all symbols
            all_trades = generate_trades(
                sym_dict, 
                fn, 
                direction, 
                sl_mult=rr['sl_mult'], 
                tp_mult=rr['tp_mult'],
                max_bars=40
            )
            
            # Simulate Portfolio with Chronological fractional risk sizing
            if len(all_trades) >= 5:
                df_history = simulate_portfolio(all_trades, initial_capital=10000.0, risk_per_trade_pct=0.01)
                
                if not df_history.empty:
                    metrics = get_performance_metrics(all_trades, df_history)
                    
                    backtest_results.append({
                        'Strategy': strat_name,
                        'Timeframe': tf,
                        'R:R Target': rr['label'],
                        'Stop Mode': 'Static',
                        'Signals': metrics.get('Trades', 0),
                        'Hit TP': int(metrics.get('TP Hit (%)', 0) / 100 * metrics.get('Trades', 0)),
                        'Hit SL': int(metrics.get('SL Hit (%)', 0) / 100 * metrics.get('Trades', 0)),
                        'Win Rate (%)': metrics.get('Win Rate (%)', 0.0),
                        'Avg Net Ret (%)': metrics.get('Avg Trade (%)', 0.0),
                        'Net Profit Factor': metrics.get('Net Profit Factor', 0.0),
                        'Portfolio Return (%)': metrics.get('Portfolio Return (%)', 0.0),
                        'Max Drawdown (%)': metrics.get('Max Drawdown (%)', 0.0)
                    })

df_results = pd.DataFrame(backtest_results)
print(f'Institutional Backtesting Complete! Evaluated {len(df_results)} strategy-timeframe-RR scenarios.')
df_results.sort_values('Net Profit Factor', ascending=False).head(10)"""

    with open(path, "w", encoding="utf-8") as f:
        nbformat.write(nb, f)
    print("Updated 06_atr_risk_management_backtest.ipynb")

def update_notebook_07():
    path = Path("notebooks/07_profitable_strategies_backtest.ipynb")
    if not path.exists():
        return
        
    with open(path, "r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)
        
    # Inject SHORT strategies to 07
    for cell in nb.cells:
        if cell.cell_type == "code" and "def strat_macro_trend_pullback" in cell.source:
            cell.source += """\n
def strat_macro_trend_short(df):
    \"\"\"Macro 200 EMA Downtrend + Overbought Bounce (> 60)\"\"\"
    macro_downtrend = df['close'] < df['ema_200']
    rsi_pullback = (df['rsi'].shift(1) > 60) & (df['rsi'] <= 60)
    ema_bearish = df['ema_8'] < df['ema_21']
    return macro_downtrend & rsi_pullback & ema_bearish

STRATEGIES['Macro Regime Short'] = strat_macro_trend_short
"""
        
        elif cell.cell_type == "code" and "def backtest_engine" in cell.source:
            cell.source = """from backend.backtester import generate_trades, simulate_portfolio, get_performance_metrics

results = []
equity_curves = {}

for name, fn in STRATEGIES.items():
    direction = 'SHORT' if 'Short' in name or 'Bear' in name else 'LONG'
    
    all_trades = generate_trades(datasets, fn, direction, sl_mult=1.5, tp_mult=2.0)
    
    if len(all_trades) >= 5:
        df_history = simulate_portfolio(all_trades, initial_capital=10000.0, risk_per_trade_pct=0.01)
        if not df_history.empty:
            metrics = get_performance_metrics(all_trades, df_history)
            metrics['Strategy'] = name
            results.append(metrics)
            
            # Save equity curve for plotting
            equity_curves[name] = df_history['equity']

df_results = pd.DataFrame(results).sort_values('Net Profit Factor', ascending=False)
df_results"""

    with open(path, "w", encoding="utf-8") as f:
        nbformat.write(nb, f)
    print("Updated 07_profitable_strategies_backtest.ipynb")

if __name__ == "__main__":
    update_notebook_06()
    update_notebook_07()
