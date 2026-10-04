"""
Fixed Backtesting Engine.

Key fixes from the original:
1. TP exits use limit-order fills (no slippage penalty on winning trades)
2. When both SL/TP hit same candle, uses candle-open proximity logic
3. Portfolio sizing properly calculates position size from risk % and SL distance
4. Friction accounting is correct (fee per leg, slippage only on market orders)
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Callable, Optional


def calculate_trade_exit(
    df: pd.DataFrame,
    entry_idx: int,
    direction: str,
    sl_mult: float,
    tp_mult: float,
    fee_pct: float = 0.00075,
    slippage_pct: float = 0.0003,
    max_bars: int = 48,
):
    """
    Simulates a single trade from entry to exit with realistic friction.
    
    Friction model:
    - Entry: market order → fee + slippage
    - SL exit: market order → fee + slippage
    - TP exit: limit order → fee only (no slippage)
    - Timeout: market order at close → fee + slippage
    
    When both SL and TP hit on the same candle:
    - Check if candle opened closer to SL or TP level
    - If equidistant, assume SL hit first (conservative)
    """
    n = len(df)
    entry_row = df.iloc[entry_idx]
    raw_entry = entry_row['close']
    atr = entry_row['atr']
    if np.isnan(atr) or atr <= 0:
        atr = raw_entry * 0.01

    # Entry with slippage (market order)
    if direction == 'LONG':
        entry_price = raw_entry * (1 + slippage_pct)
        sl_price = entry_price - (sl_mult * atr)
        tp_price = entry_price + (tp_mult * atr)
    else:
        entry_price = raw_entry * (1 - slippage_pct)
        sl_price = entry_price + (sl_mult * atr)
        tp_price = entry_price - (tp_mult * atr)

    exit_bound = min(n - 1, entry_idx + max_bars)
    exit_price = None
    exit_idx = exit_bound
    reason = 'TIMEOUT'

    future_start = entry_idx + 1
    future_end = exit_bound + 1
    
    if future_start >= n:
        # No future candles available
        exit_price = raw_entry
        exit_idx = entry_idx
        reason = 'TIMEOUT'
    else:
        future_highs = df['high'].values[future_start:future_end]
        future_lows = df['low'].values[future_start:future_end]
        future_opens = df['open'].values[future_start:future_end]

        for i in range(len(future_highs)):
            h = future_highs[i]
            l = future_lows[i]
            o = future_opens[i]

            if direction == 'LONG':
                hit_sl = l <= sl_price
                hit_tp = h >= tp_price

                if hit_sl and hit_tp:
                    # Both hit same candle — check which is more likely first
                    # If open is closer to SL, SL probably hit first
                    dist_to_sl = abs(o - sl_price)
                    dist_to_tp = abs(o - tp_price)
                    
                    if dist_to_sl <= dist_to_tp:
                        # SL hit first (market order: fee + slippage)
                        exit_price = sl_price * (1 - slippage_pct)
                        reason = 'STOP_LOSS'
                    else:
                        # TP hit first (limit order: fee only, no slippage)
                        exit_price = tp_price
                        reason = 'TAKE_PROFIT'
                    exit_idx = future_start + i
                    break
                elif hit_sl:
                    # SL is market order: fee + slippage
                    exit_price = sl_price * (1 - slippage_pct)
                    exit_idx = future_start + i
                    reason = 'STOP_LOSS'
                    break
                elif hit_tp:
                    # TP is limit order: fee only, no slippage penalty
                    exit_price = tp_price
                    exit_idx = future_start + i
                    reason = 'TAKE_PROFIT'
                    break
            else:  # SHORT
                hit_sl = h >= sl_price
                hit_tp = l <= tp_price

                if hit_sl and hit_tp:
                    dist_to_sl = abs(o - sl_price)
                    dist_to_tp = abs(o - tp_price)
                    
                    if dist_to_sl <= dist_to_tp:
                        exit_price = sl_price * (1 + slippage_pct)
                        reason = 'STOP_LOSS'
                    else:
                        exit_price = tp_price
                        reason = 'TAKE_PROFIT'
                    exit_idx = future_start + i
                    break
                elif hit_sl:
                    exit_price = sl_price * (1 + slippage_pct)
                    exit_idx = future_start + i
                    reason = 'STOP_LOSS'
                    break
                elif hit_tp:
                    exit_price = tp_price
                    exit_idx = future_start + i
                    reason = 'TAKE_PROFIT'
                    break

    # Timeout exit (market order at close)
    if exit_price is None:
        last_close = df['close'].values[min(exit_idx, n - 1)]
        if direction == 'LONG':
            exit_price = last_close * (1 - slippage_pct)
        else:
            exit_price = last_close * (1 + slippage_pct)

    # Calculate return
    if direction == 'LONG':
        gross_ret = (exit_price - entry_price) / entry_price
    else:
        gross_ret = (entry_price - exit_price) / entry_price

    # Fee: charged once on entry, once on exit = 2 * fee_pct
    net_ret = gross_ret - (2 * fee_pct)
    
    return exit_idx, exit_price, net_ret, reason


def generate_trades(
    datasets: Dict[str, pd.DataFrame],
    strategy_fn: Callable,
    direction: str,
    sl_mult: float = 2.0,
    tp_mult: float = 3.5,
    max_bars: int = 48,
    fee_pct: float = 0.00075,
    slippage_pct: float = 0.0003,
    allow_overlap: bool = False,
) -> List[Dict[str, Any]]:
    """
    Generates all trades for a given strategy across multiple datasets.
    
    Args:
        allow_overlap: If False (default), prevents opening new trades on the same
                       symbol while a trade is already active (matches live bot mutex).
    """
    all_trades = []

    for sym, df in datasets.items():
        try:
            signal_mask = strategy_fn(df)
            if not isinstance(signal_mask, pd.Series):
                continue
        except Exception:
            continue

        entry_indices = np.where(signal_mask)[0]
        last_exit_idx = -1

        for idx in entry_indices:
            if not allow_overlap and idx <= last_exit_idx:
                continue
            if idx >= len(df) - 1:
                continue

            exit_idx, exit_price, net_ret, reason = calculate_trade_exit(
                df, idx, direction, sl_mult, tp_mult, fee_pct, slippage_pct, max_bars
            )
            last_exit_idx = exit_idx

            all_trades.append({
                'symbol': sym,
                'entry_time': df['open_time'].iloc[idx],
                'exit_time': df['open_time'].iloc[exit_idx],
                'entry_price': df['close'].iloc[idx],
                'exit_price': exit_price,
                'atr_at_entry': df['atr'].iloc[idx],
                'net_return': net_ret,
                'reason': reason,
                'bars_held': exit_idx - idx,
                'direction': direction,
            })

    return all_trades


def simulate_portfolio(
    trades: List[Dict[str, Any]],
    initial_capital: float = 10000.0,
    risk_per_trade_pct: float = 0.01,
    sl_mult: float = 1.5,
) -> pd.DataFrame:
    """
    Simulates portfolio equity curve with proper position sizing.
    
    Position sizing logic (fixed fractional risk):
    - Risk amount = risk_per_trade_pct * current_equity
    - SL distance = sl_mult * ATR (as fraction of entry price)
    - Position size = risk_amount / SL_distance_fraction
    - PnL = position_size * net_return
    
    Example: 1% risk, $10,000 equity, SL distance = 2% of entry
    → Risk = $100, Position size = $100 / 0.02 = $5,000
    → If trade returns +3%, PnL = $5,000 * 0.03 = $150 (+1.5% of equity)
    → If trade returns -2%, PnL = $5,000 * -0.02 = -$100 (-1% of equity, as designed)
    """
    if not trades:
        return pd.DataFrame()

    # Sort trades by entry time
    trades_sorted = sorted(trades, key=lambda x: x['entry_time'])

    current_equity = initial_capital
    portfolio_history = []

    for trade in trades_sorted:
        # Calculate SL distance as a fraction of entry price
        atr = trade.get('atr_at_entry', trade['entry_price'] * 0.01)
        if np.isnan(atr) or atr <= 0:
            atr = trade['entry_price'] * 0.01
        
        sl_distance_frac = (sl_mult * atr) / trade['entry_price']
        
        # Position size from fixed fractional risk
        risk_amount = current_equity * risk_per_trade_pct
        position_size = risk_amount / sl_distance_frac if sl_distance_frac > 0 else 0
        
        # Cap position size at current equity (no leverage by default)
        position_size = min(position_size, current_equity)
        
        # Calculate PnL
        pnl = position_size * trade['net_return']
        current_equity += pnl

        portfolio_history.append({
            'time': trade['entry_time'],
            'equity': current_equity,
            'symbol': trade['symbol'],
            'net_return': trade['net_return'],
            'reason': trade['reason'],
            'pnl': pnl,
            'position_size': position_size,
        })

    df_history = pd.DataFrame(portfolio_history).sort_values('time').reset_index(drop=True)
    return df_history


def get_performance_metrics(
    trades: List[Dict[str, Any]],
    df_history: pd.DataFrame,
    initial_capital: float = 10000.0,
) -> Dict[str, Any]:
    """Calculate comprehensive performance metrics."""
    if not trades or df_history.empty:
        return {}

    returns = [t['net_return'] for t in trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]

    win_rate = len(wins) / len(returns) * 100
    avg_net_ret = np.mean(returns) * 100
    avg_win = np.mean(wins) * 100 if wins else 0
    avg_loss = np.mean(losses) * 100 if losses else 0

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    final_cap = df_history['equity'].iloc[-1]
    portfolio_ret = ((final_cap - initial_capital) / initial_capital) * 100

    equity_curve = df_history['equity']
    rolling_max = equity_curve.cummax()
    drawdown = ((equity_curve - rolling_max) / rolling_max) * 100
    max_drawdown = drawdown.min()

    # Sharpe & Sortino (annualized for crypto 365 days)
    ret_series = pd.Series(returns)
    trade_std = ret_series.std()
    downside_std = ret_series[ret_series < 0].std()
    
    # Approximate trades per year based on average bars held
    avg_bars = np.mean([t['bars_held'] for t in trades])
    trades_per_year = 8760 / max(avg_bars, 1)  # 8760 hours in a year
    
    sharpe = (ret_series.mean() / trade_std) * np.sqrt(trades_per_year) if trade_std > 0 else 0
    sortino = (ret_series.mean() / downside_std) * np.sqrt(trades_per_year) if downside_std > 0 else 0

    tp_hit = sum(1 for t in trades if t['reason'] == 'TAKE_PROFIT') / len(trades) * 100
    sl_hit = sum(1 for t in trades if t['reason'] == 'STOP_LOSS') / len(trades) * 100
    timeout = sum(1 for t in trades if t['reason'] == 'TIMEOUT') / len(trades) * 100

    # Expectancy
    expectancy = (win_rate / 100 * (avg_win / 100)) - ((100 - win_rate) / 100 * abs(avg_loss / 100))

    return {
        'Trades': len(trades),
        'Win Rate (%)': round(win_rate, 2),
        'Avg Trade (%)': round(avg_net_ret, 3),
        'Avg Win (%)': round(avg_win, 3),
        'Avg Loss (%)': round(avg_loss, 3),
        'Expectancy': round(expectancy, 5),
        'Net Profit Factor': round(profit_factor, 3),
        'Portfolio Return (%)': round(portfolio_ret, 2),
        'Max Drawdown (%)': round(max_drawdown, 2),
        'Sharpe Ratio': round(sharpe, 2),
        'Sortino Ratio': round(sortino, 2),
        'TP Hit (%)': round(tp_hit, 1),
        'SL Hit (%)': round(sl_hit, 1),
        'Timeout (%)': round(timeout, 1),
    }
