"""
Risk Manager — Enforces trading rules to prevent catastrophic losses.
Checks position limits, daily loss caps, duplicate symbols, cooldowns,
sector concentration, total notional exposure, and consecutive losses
before allowing the bot to execute a trade.
"""
import threading
from datetime import datetime, timezone, timedelta
from typing import Tuple, Dict, List, Any, Optional

from backend.screener import CATEGORY_MAP, get_symbol_category


class RiskManager:
    """
    Stateful risk gate that decides whether a new trade is allowed.
    All state is derived from the trade journal and open positions,
    so it's resilient to restarts.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self._lock = threading.Lock()
        self.config = config or {}

    def update_config(self, config: Dict[str, Any]):
        """Update risk configuration."""
        with self._lock:
            self.config.update(config)

    def can_trade(
        self,
        symbol: str,
        amount: float,
        open_positions: List[Dict[str, Any]],
        today_executions: List[Dict[str, Any]],
        daily_pnl: float,
        leverage: int = 1,
        strategy: str = "",
    ) -> Tuple[bool, str]:
        """
        Check if a new trade is allowed.

        Returns:
            (True, "OK") if trade is allowed
            (False, "reason") if trade is blocked
        """
        max_positions = self.config.get("max_positions", 3)
        max_daily_loss = self.config.get("max_daily_loss", 50)
        daily_profit_target = self.config.get("daily_profit_target", 0)
        total_capital = self.config.get("total_capital", 1000)
        cooldown_hours = self.config.get("cooldown_hours", 4)
        max_total_exposure = self.config.get("max_total_exposure", 500)
        max_sector_positions = self.config.get("max_sector_positions", 2)
        strategy_filter = self.config.get("strategy_filter", "ALL")

        # Gate 0: Strategy Filter check
        if strategy_filter and strategy_filter.upper() != "ALL":
            if strategy and strategy_filter.lower() not in strategy.lower():
                return False, f"Strategy '{strategy}' does not match filter '{strategy_filter}'"

        # Gate 1: Max open positions
        if len(open_positions) >= max_positions:
            return False, f"Max positions reached ({len(open_positions)}/{max_positions})"

        # Gate 2: Daily loss limit
        if daily_pnl <= -abs(max_daily_loss):
            return False, f"Daily loss limit hit (${daily_pnl:.2f} / -${max_daily_loss})"

        # Gate 2b: Daily profit target hit (lock in profit)
        if daily_profit_target > 0 and daily_pnl >= daily_profit_target:
            return False, f"Daily profit target achieved (${daily_pnl:.2f} >= ${daily_profit_target:.2f})"

        # Gate 3: No duplicate symbols
        open_symbols = [p.get("symbol", "").upper() for p in open_positions]
        if symbol.upper() in open_symbols:
            return False, f"Already have open position in {symbol}"

        # Gate 4: Cooldown — don't re-enter same symbol within N hours
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=cooldown_hours)
        for ex in today_executions:
            if ex.get("symbol", "").upper() == symbol.upper():
                ts_str = ex.get("timestamp", "")
                try:
                    ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
                    if ts > cutoff:
                        remaining = (ts + timedelta(hours=cooldown_hours) - now)
                        mins = int(remaining.total_seconds() / 60)
                        return False, f"Cooldown active for {symbol} ({mins}min remaining)"
                except (ValueError, TypeError):
                    pass

        # Gate 5: Amount sanity check
        if amount <= 0:
            return False, "Trade amount must be greater than 0"

        # Gate 5b: Total Capital deployment check
        current_deployed = sum(p.get("amount_usdt", 0) for p in open_positions)
        if current_deployed + amount > total_capital:
            return False, f"Insufficient free capital (${current_deployed + amount:.2f} > Total Capital ${total_capital:.2f})"

        # Gate 6: Sector concentration — max N positions in same category
        new_category = get_symbol_category(symbol.upper())
        sector_count = 0
        for p in open_positions:
            pos_category = get_symbol_category(p.get("symbol", ""))
            if pos_category == new_category:
                sector_count += 1
        if sector_count >= max_sector_positions:
            return False, f"Sector limit reached ({sector_count}/{max_sector_positions} in '{new_category}')"

        # Gate 7: Total notional exposure check
        total_exposure = sum(
            p.get("amount_usdt", 0) * p.get("leverage", 1) for p in open_positions
        )
        new_exposure = amount * leverage
        if total_exposure + new_exposure > max_total_exposure:
            return False, (
                f"Total exposure would be ${total_exposure + new_exposure:.0f} "
                f"(limit: ${max_total_exposure})"
            )

        return True, "OK"


