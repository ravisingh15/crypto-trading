"""
Auto Trader Engine — The brain of the agentic trading system.
Runs a scan-filter-execute loop on a schedule using a background thread.
Supports paper trading mode for safe testing.
Uses Binance Futures for both LONG and SHORT trades, with Spot fallback.

Key improvements:
- Stores SL/TP order IDs for cancel-other logic on Futures
- Paper mode correctly applies leverage to quantity calculation
- Passes strategy name to journal for per-strategy performance tracking
- Passes leverage and category info to risk manager
"""
import math
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from backend.binance_client import binance_client
from backend.trade_signals import scan_all_signals
from backend.trade_journal import trade_journal
from backend.risk_manager import RiskManager
from backend.position_tracker import position_tracker


def format_quantity(raw_qty: float, step_size: float) -> float:
    """Format quantity to match step_size precision safely."""
    if step_size <= 0:
        return raw_qty
    step_str = f"{step_size:.8f}".rstrip('0')
    precision = len(step_str.split('.')[1]) if '.' in step_str else 0
    steps = math.floor(round(raw_qty / step_size, 8))
    return round(steps * step_size, precision)


def format_price(price: float, tick_size: float) -> float:
    """Format price to match tick_size precision safely."""
    if tick_size <= 0:
        return price
    tick_str = f"{tick_size:.8f}".rstrip('0')
    precision = len(tick_str.split('.')[1]) if '.' in tick_str else 0
    ticks = round(price / tick_size)
    return round(ticks * tick_size, precision)


class AutoTrader:
    """
    Autonomous trading engine that scans for signals and executes trades.

    Flow per cycle:
    1. Scan all symbols for signals
    2. Filter: confidence >= threshold, bars_ago == 0 (fresh)
    3. Risk check: max positions, daily loss, cooldowns, exposure limits
    4. Execute: place Futures/Spot market order + SL/TP
    5. Log everything with strategy attribution
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._risk_manager = RiskManager()

        # Default configuration
        self._config: Dict[str, Any] = {
            "enabled": False,
            "paper_mode": True,
            "market_type": "futures",      # "futures" or "spot"
            "amount_per_trade": 50,        # USDT per trade
            "leverage": 5,                 # Futures leverage (1-125)
            "min_confidence": 60,          # Minimum signal confidence (0-100)
            "max_positions": 3,            # Max concurrent open positions
            "max_daily_loss": 50,          # Stop trading if daily loss exceeds this
            "cooldown_hours": 4,           # Don't re-enter same symbol within N hours
            "scan_interval_minutes": 60,   # How often to scan (match candle timeframe)
            "candle_interval": "1h",       # Candle timeframe for signal scanning
            "max_total_exposure": 500,     # Max total notional exposure in USDT
            "max_sector_positions": 2,     # Max positions in same sector
        }

        # Runtime stats
        self._stats = {
            "last_cycle": None,
            "total_cycles": 0,
            "total_signals_seen": 0,
            "total_trades_executed": 0,
            "started_at": None,
        }

    @property
    def config(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._config)

    @property
    def is_running(self) -> bool:
        return self._running

    def update_config(self, new_config: Dict[str, Any]):
        """Update bot configuration. Can be called while running."""
        with self._lock:
            for key, value in new_config.items():
                if key in self._config:
                    expected_type = type(self._config[key])
                    try:
                        if expected_type is bool:
                            if isinstance(value, str):
                                self._config[key] = value.lower() in ("true", "1", "yes")
                            else:
                                self._config[key] = bool(value)
                        else:
                            self._config[key] = expected_type(value)
                    except (ValueError, TypeError):
                        pass

            # Sync risk manager config
            self._risk_manager.update_config({
                "max_positions": self._config["max_positions"],
                "max_daily_loss": self._config["max_daily_loss"],
                "cooldown_hours": self._config["cooldown_hours"],
                "max_total_exposure": self._config["max_total_exposure"],
                "max_sector_positions": self._config["max_sector_positions"],
            })

    def start(self) -> Dict[str, Any]:
        """Start the auto-trading loop."""
        if self._running:
            return {"status": "already_running"}

        self._running = True
        self._config["enabled"] = True
        self._stats["started_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Sync risk manager
        self._risk_manager.update_config({
            "max_positions": self._config["max_positions"],
            "max_daily_loss": self._config["max_daily_loss"],
            "cooldown_hours": self._config["cooldown_hours"],
            "max_total_exposure": self._config["max_total_exposure"],
            "max_sector_positions": self._config["max_sector_positions"],
        })

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        mode = "PAPER" if self._config["paper_mode"] else "LIVE"
        market = self._config["market_type"].upper()
        trade_journal.log_bot_event("START", f"Bot started in {mode} mode on {market}")

        return {
            "status": "started",
            "mode": mode,
            "market": market,
            "config": dict(self._config),
        }

    def stop(self) -> Dict[str, Any]:
        """Stop the auto-trading loop."""
        if not self._running:
            return {"status": "already_stopped"}

        self._running = False
        self._config["enabled"] = False
        trade_journal.log_bot_event("STOP", "Bot stopped by user")

        return {"status": "stopped", "stats": dict(self._stats)}

    def get_status(self) -> Dict[str, Any]:
        """Get current bot status."""
        open_positions = position_tracker.to_dict_list()
        daily_pnl = trade_journal.get_daily_pnl()

        return {
            "running": self._running,
            "config": dict(self._config),
            "stats": dict(self._stats),
            "open_positions": open_positions,
            "position_count": len(open_positions),
            "daily_pnl": round(daily_pnl, 2),
            "recent_log": trade_journal.get_recent(limit=20),
        }

    def _run_loop(self):
        """Main bot loop — runs in a background thread."""
        # Run first cycle immediately
        self._execute_cycle()

        while self._running:
            interval_seconds = self._config["scan_interval_minutes"] * 60
            for _ in range(int(interval_seconds / 5)):
                if not self._running:
                    return
                time.sleep(5)

            if self._running:
                self._execute_cycle()

    def _execute_cycle(self):
        """Execute one scan-filter-execute cycle."""
        try:
            self._stats["total_cycles"] += 1
            self._stats["last_cycle"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

            paper = self._config["paper_mode"]
            amount = self._config["amount_per_trade"]
            min_conf = self._config["min_confidence"]
            interval = self._config["candle_interval"]
            use_futures = self._config["market_type"] == "futures"
            leverage = self._config["leverage"]

            # Check consecutive losses — reduce size after 3+ consecutive SLs
            consec_losses = trade_journal.get_consecutive_losses()
            if consec_losses >= 3:
                amount = amount * 0.5
                trade_journal.log_bot_event("THROTTLE",
                    f"Reduced trade size to ${amount:.0f} after {consec_losses} consecutive losses")

            # Step 1: Check for closed positions (paper or live)
            self._check_closures()

            # Step 2: Scan for signals
            signals = scan_all_signals(
                interval=interval,
                lookback_bars=1,
                min_confidence=min_conf,
            )

            self._stats["total_signals_seen"] += len(signals)

            # Step 3: Initial filter for freshness & direction
            candidate_signals = []
            signals_filtered = 0

            for sig in signals:
                if not use_futures and sig["direction"] != "LONG":
                    trade_journal.log_signal_filtered(sig["symbol"], "SHORT skipped (Spot mode)")
                    signals_filtered += 1
                    continue

                if sig["bars_ago"] > 0:
                    trade_journal.log_signal_filtered(sig["symbol"], f"Stale (bars_ago={sig['bars_ago']})")
                    signals_filtered += 1
                    continue

                trade_journal.log_signal_seen(
                    symbol=sig["symbol"],
                    direction=sig["direction"],
                    strategy=sig["strategy"],
                    confidence=sig["confidence"],
                    entry_price=sig["entry_price"],
                )
                candidate_signals.append(sig)

            # Step 4: Execute candidate signals with per-trade risk checking
            signals_executed = 0
            signals_risk_blocked = 0

            for sig in candidate_signals:
                open_positions = position_tracker.get_open_positions()
                today_execs = trade_journal.get_today_executions()
                daily_pnl = trade_journal.get_daily_pnl()

                can_trade, reason = self._risk_manager.can_trade(
                    symbol=sig["symbol"],
                    amount=amount,
                    open_positions=open_positions,
                    today_executions=today_execs,
                    daily_pnl=daily_pnl,
                    leverage=leverage,
                )

                if not can_trade:
                    trade_journal.log_risk_blocked(sig["symbol"], reason)
                    signals_risk_blocked += 1
                    continue

                success = self._execute_trade(sig, amount, paper, use_futures, leverage)
                if success:
                    signals_executed += 1
                    self._stats["total_trades_executed"] += 1

            # Log cycle summary
            trade_journal.log_cycle(
                signals_found=len(signals),
                signals_executed=signals_executed,
                signals_filtered=signals_filtered,
                signals_risk_blocked=signals_risk_blocked,
            )

        except Exception as e:
            trade_journal.log_bot_event("ERROR", f"Cycle error: {str(e)}")

    def _execute_trade(self, signal: Dict[str, Any], amount: float,
                       paper: bool, use_futures: bool, leverage: int = 1) -> bool:
        """Execute a single trade (paper or live, spot or futures)."""
        symbol = signal["symbol"]
        direction = signal["direction"]
        entry_price = signal["entry_price"]
        sl = signal["stop_loss"]
        tp = signal["take_profit"]
        strategy = signal.get("strategy", "")
        side = "BUY" if direction == "LONG" else "SELL"
        exit_side = "SELL" if side == "BUY" else "BUY"
        market_type = "futures" if use_futures else "spot"

        try:
            # --- PAPER MODE ---
            if paper:
                try:
                    if use_futures:
                        current_price = binance_client.futures_get_symbol_price(symbol)
                    else:
                        current_price = binance_client.get_symbol_price(symbol)
                except Exception:
                    current_price = entry_price

                # FIX: Apply leverage to quantity for futures paper trades
                if use_futures:
                    qty = (amount * leverage) / current_price
                else:
                    qty = amount / current_price

                trade_journal.log_execution(
                    symbol=symbol, side=side, amount=amount,
                    quantity=round(qty, 6), order_id="PAPER",
                    sl=sl, tp=tp, paper=True, strategy=strategy,
                )
                trade_journal.log_oco_placed(
                    symbol=symbol, sl=sl, tp=tp,
                    oco_id="PAPER", paper=True,
                )

                position_tracker.add_position(
                    symbol=symbol, side=side, quantity=qty,
                    entry_price=current_price, amount_usdt=amount,
                    sl=sl, tp=tp, paper=True, market_type=market_type,
                    strategy=strategy, leverage=leverage,
                )
                return True

            # --- LIVE FUTURES ---
            if use_futures:
                return self._execute_futures_trade(
                    symbol, side, exit_side, amount, sl, tp, leverage, strategy)

            # --- LIVE SPOT ---
            else:
                return self._execute_spot_trade(
                    symbol, side, exit_side, amount, sl, tp, strategy)

        except Exception as e:
            trade_journal.log_bot_event("ERROR", f"Trade failed for {symbol}: {str(e)}")
            return False

    def _execute_futures_trade(self, symbol: str, side: str, exit_side: str,
                                amount: float, sl: float, tp: float,
                                leverage: int = 5, strategy: str = "") -> bool:
        """Execute a live Futures trade with SL/TP and order ID tracking."""
        # Set leverage
        try:
            binance_client.futures_set_leverage(symbol, leverage)
        except Exception as e:
            trade_journal.log_bot_event("WARN", f"Leverage set failed for {symbol}: {str(e)}")

        current_price = binance_client.futures_get_symbol_price(symbol)
        if current_price <= 0:
            trade_journal.log_bot_event("ERROR", f"No price for {symbol}")
            return False

        info = binance_client.futures_get_exchange_info(symbol)
        filters = {f["filterType"]: f for f in info.get("filters", [])}

        lot_size = filters.get("LOT_SIZE", {})
        step_size = float(lot_size.get("stepSize", "0.001"))
        min_qty = float(lot_size.get("minQty", "0.001"))

        price_filter = filters.get("PRICE_FILTER", {})
        tick_size = float(price_filter.get("tickSize", "0.01"))

        notional = amount * leverage
        raw_qty = notional / current_price
        qty = format_quantity(raw_qty, step_size)

        if qty < min_qty:
            trade_journal.log_bot_event("ERROR", f"Qty {qty} < min {min_qty} for {symbol}")
            return False

        entry_result = binance_client.futures_place_market_order(symbol, side, qty)
        order_id = entry_result.get("orderId")

        trade_journal.log_execution(
            symbol=symbol, side=side, amount=amount,
            quantity=qty, order_id=order_id,
            sl=sl, tp=tp, paper=False, strategy=strategy,
        )

        formatted_sl = format_price(sl, tick_size)
        formatted_tp = format_price(tp, tick_size)

        # Place SL order and track its ID
        sl_order_id = None
        try:
            sl_result = binance_client.futures_place_stop_market(
                symbol, exit_side, qty, formatted_sl
            )
            sl_order_id = sl_result.get("orderId")
        except Exception as e:
            trade_journal.log_bot_event("ERROR", f"SL order failed for {symbol}: {str(e)}")

        # Place TP order and track its ID
        tp_order_id = None
        try:
            tp_result = binance_client.futures_place_take_profit_market(
                symbol, exit_side, qty, formatted_tp
            )
            tp_order_id = tp_result.get("orderId")
        except Exception as e:
            trade_journal.log_bot_event("ERROR", f"TP order failed for {symbol}: {str(e)}")

        trade_journal.log_oco_placed(
            symbol=symbol, sl=formatted_sl, tp=formatted_tp,
            oco_id=f"SL:{sl_order_id}/TP:{tp_order_id}", paper=False,
        )

        # Store SL/TP order IDs so we can cancel the other when one fills
        position_tracker.add_position(
            symbol=symbol, side=side, quantity=qty,
            entry_price=current_price, amount_usdt=amount,
            sl=sl, tp=tp, order_id=order_id,
            sl_order_id=sl_order_id, tp_order_id=tp_order_id,
            paper=False, market_type="futures",
            strategy=strategy, leverage=leverage,
        )
        return True

    def _execute_spot_trade(self, symbol: str, side: str, exit_side: str,
                            amount: float, sl: float, tp: float,
                            strategy: str = "") -> bool:
        """Execute a live Spot trade with OCO SL/TP."""
        current_price = binance_client.get_symbol_price(symbol)
        if current_price <= 0:
            trade_journal.log_bot_event("ERROR", f"No price for {symbol}")
            return False

        info = binance_client.get_symbol_exchange_info(symbol)
        filters = {f["filterType"]: f for f in info.get("filters", [])}

        lot_size = filters.get("LOT_SIZE", {})
        step_size = float(lot_size.get("stepSize", "0.001"))
        min_qty = float(lot_size.get("minQty", "0.001"))

        price_filter = filters.get("PRICE_FILTER", {})
        tick_size = float(price_filter.get("tickSize", "0.01"))

        raw_qty = amount / current_price
        qty = format_quantity(raw_qty, step_size)

        if qty < min_qty:
            trade_journal.log_bot_event("ERROR", f"Qty {qty} < min {min_qty} for {symbol}")
            return False

        entry_result = binance_client.place_market_order(symbol, side, qty)
        order_id = entry_result.get("orderId")

        trade_journal.log_execution(
            symbol=symbol, side=side, amount=amount,
            quantity=qty, order_id=order_id,
            sl=sl, tp=tp, paper=False, strategy=strategy,
        )

        formatted_sl = format_price(sl, tick_size)
        formatted_tp = format_price(tp, tick_size)

        if exit_side == "SELL":
            sl_limit = format_price(formatted_sl * 0.999, tick_size)
        else:
            sl_limit = format_price(formatted_sl * 1.001, tick_size)

        oco_id = None
        try:
            oco_result = binance_client.place_oco_order(
                symbol=symbol, side=exit_side, quantity=qty,
                price=formatted_tp, stop_price=formatted_sl,
                stop_limit_price=sl_limit,
            )
            oco_id = oco_result.get("orderListId")
            trade_journal.log_oco_placed(
                symbol=symbol, sl=formatted_sl, tp=formatted_tp,
                oco_id=oco_id, paper=False,
            )
        except Exception as e:
            trade_journal.log_bot_event("ERROR", f"OCO failed for {symbol}: {str(e)}")

        position_tracker.add_position(
            symbol=symbol, side=side, quantity=qty,
            entry_price=current_price, amount_usdt=amount,
            sl=sl, tp=tp, order_id=order_id, oco_id=oco_id,
            paper=False, market_type="spot",
            strategy=strategy, leverage=1,
        )
        return True

    def _check_closures(self):
        """Check if any positions have been closed (SL/TP hit)."""
        paper_closed = position_tracker.check_paper_closures()
        for pos in paper_closed:
            trade_journal.log_position_closed(
                symbol=pos["symbol"],
                exit_type=pos.get("exit_type", "UNKNOWN"),
                pnl=pos.get("pnl", 0),
                paper=True,
                strategy=pos.get("strategy", ""),
            )

        live_closed = position_tracker.check_live_closures()
        for pos in live_closed:
            trade_journal.log_position_closed(
                symbol=pos["symbol"],
                exit_type=pos.get("exit_type", "UNKNOWN"),
                pnl=pos.get("pnl", 0),
                paper=False,
                strategy=pos.get("strategy", ""),
            )


# Global instance
auto_trader = AutoTrader()
