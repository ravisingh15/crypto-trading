"""
Trade Journal — Persistent log of all bot actions and trade history.
Uses append-only JSONL format (one JSON object per line) for:
- O(1) writes instead of O(n) full-file rewrites
- Crash safety (partial writes only affect last line)
- Easy streaming and grep-ability

Migrates automatically from legacy trade_journal.json on first load.
"""
import json
import os
import threading
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path


JOURNAL_DIR = Path(__file__).resolve().parent.parent / "data_cache"
JOURNAL_FILE = JOURNAL_DIR / "trade_journal.jsonl"
LEGACY_JOURNAL_FILE = JOURNAL_DIR / "trade_journal.json"


class TradeJournal:
    """Thread-safe trade journal that persists to a JSONL file (append-only)."""

    def __init__(self, filepath: Path = JOURNAL_FILE):
        self.filepath = filepath
        self._lock = threading.Lock()
        self._entries: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        """Load existing journal from disk. Auto-migrate from legacy JSON if needed."""
        # Migrate legacy JSON format to JSONL
        if LEGACY_JOURNAL_FILE.exists() and not self.filepath.exists():
            try:
                with open(LEGACY_JOURNAL_FILE, "r") as f:
                    legacy_entries = json.load(f)
                if isinstance(legacy_entries, list) and legacy_entries:
                    self.filepath.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.filepath, "w") as f:
                        for entry in legacy_entries:
                            f.write(json.dumps(entry, default=str) + "\n")
                    self._entries = legacy_entries
                    # Rename old file so we don't re-migrate
                    LEGACY_JOURNAL_FILE.rename(LEGACY_JOURNAL_FILE.with_suffix(".json.bak"))
                    print(f"  [TradeJournal] Migrated {len(legacy_entries)} entries from JSON to JSONL")
                    return
            except (json.JSONDecodeError, IOError) as e:
                print(f"  [TradeJournal] Warning: Legacy migration failed: {e}")

        # Load JSONL file
        try:
            if self.filepath.exists():
                entries = []
                with open(self.filepath, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                entries.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue  # Skip corrupted lines
                self._entries = entries
        except IOError:
            self._entries = []

    def _append(self, entry: Dict[str, Any]):
        """Append a single entry to the JSONL file (O(1) write)."""
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filepath, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except IOError as e:
            print(f"  [TradeJournal] Warning: Could not append to journal: {e}")

    def _now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    def log(self, event_type: str, data: Dict[str, Any]):
        """Log a generic event."""
        entry = {
            "timestamp": self._now(),
            "type": event_type,
            **data,
        }
        with self._lock:
            self._entries.append(entry)
            self._append(entry)

    def log_signal_seen(self, symbol: str, direction: str, strategy: str,
                        confidence: int, entry_price: float):
        """Log a signal that was detected."""
        self.log("SIGNAL", {
            "symbol": symbol,
            "direction": direction,
            "strategy": strategy,
            "confidence": confidence,
            "entry_price": entry_price,
        })

    def log_signal_filtered(self, symbol: str, reason: str):
        """Log a signal that was filtered out."""
        self.log("FILTERED", {
            "symbol": symbol,
            "reason": reason,
        })

    def log_risk_blocked(self, symbol: str, reason: str):
        """Log a signal blocked by risk manager."""
        self.log("RISK_BLOCKED", {
            "symbol": symbol,
            "reason": reason,
        })

    def log_execution(self, symbol: str, side: str, amount: float,
                      quantity: float, order_id: Any = None,
                      sl: float = 0, tp: float = 0,
                      paper: bool = False, strategy: str = ""):
        """Log a trade execution."""
        self.log("EXECUTE", {
            "symbol": symbol,
            "side": side,
            "amount_usdt": amount,
            "quantity": quantity,
            "order_id": order_id,
            "stop_loss": sl,
            "take_profit": tp,
            "paper_trade": paper,
            "strategy": strategy,
        })

    def log_oco_placed(self, symbol: str, sl: float, tp: float,
                       oco_id: Any = None, paper: bool = False):
        """Log OCO order placement."""
        self.log("OCO_PLACED", {
            "symbol": symbol,
            "stop_loss": sl,
            "take_profit": tp,
            "oco_id": oco_id,
            "paper_trade": paper,
        })

    def log_position_closed(self, symbol: str, exit_type: str,
                            pnl: float, paper: bool = False,
                            strategy: str = ""):
        """Log a position closure (SL/TP hit or manual close)."""
        self.log("CLOSED", {
            "symbol": symbol,
            "exit_type": exit_type,
            "pnl_usdt": pnl,
            "paper_trade": paper,
            "strategy": strategy,
        })

    def log_bot_event(self, action: str, details: str = ""):
        """Log bot start/stop/error events."""
        self.log("BOT", {
            "action": action,
            "details": details,
        })

    def log_cycle(self, signals_found: int, signals_executed: int,
                  signals_filtered: int, signals_risk_blocked: int):
        """Log a scan cycle summary."""
        self.log("CYCLE", {
            "signals_found": signals_found,
            "executed": signals_executed,
            "filtered": signals_filtered,
            "risk_blocked": signals_risk_blocked,
        })

    def get_recent(self, limit: int = 50, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent journal entries, newest first."""
        with self._lock:
            entries = self._entries
            if event_type:
                entries = [e for e in entries if e.get("type") == event_type]
            return list(reversed(entries[-limit:]))

    def get_today_executions(self) -> List[Dict[str, Any]]:
        """Get all executions from today (UTC)."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._lock:
            return [
                e for e in self._entries
                if e.get("type") == "EXECUTE" and e.get("timestamp", "").startswith(today)
            ]

    def get_today_closures(self) -> List[Dict[str, Any]]:
        """Get all closures from today for P&L calculation."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._lock:
            return [
                e for e in self._entries
                if e.get("type") == "CLOSED" and e.get("timestamp", "").startswith(today)
            ]

    def get_daily_pnl(self) -> float:
        """Calculate today's realized P&L."""
        closures = self.get_today_closures()
        return sum(c.get("pnl_usdt", 0) for c in closures)

    def get_total_trades(self) -> int:
        """Total number of executions ever."""
        with self._lock:
            return len([e for e in self._entries if e.get("type") == "EXECUTE"])

    def get_strategy_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Compute per-strategy performance stats from closed trades.
        Returns dict of {strategy_name: {trades, wins, win_rate, total_pnl, avg_pnl}}.
        """
        with self._lock:
            closures = [e for e in self._entries if e.get("type") == "CLOSED" and e.get("strategy")]

        stats: Dict[str, Dict[str, Any]] = {}
        for c in closures:
            strat = c.get("strategy", "Unknown")
            if strat not in stats:
                stats[strat] = {"trades": 0, "wins": 0, "total_pnl": 0.0, "pnl_list": []}
            stats[strat]["trades"] += 1
            pnl = c.get("pnl_usdt", 0)
            stats[strat]["total_pnl"] += pnl
            stats[strat]["pnl_list"].append(pnl)
            if pnl > 0:
                stats[strat]["wins"] += 1

        # Calculate derived metrics
        for strat, s in stats.items():
            s["win_rate"] = round(s["wins"] / s["trades"] * 100, 1) if s["trades"] > 0 else 0
            s["avg_pnl"] = round(s["total_pnl"] / s["trades"], 2) if s["trades"] > 0 else 0
            s["total_pnl"] = round(s["total_pnl"], 2)
            del s["pnl_list"]  # Don't expose raw list in API

        return stats

    def get_consecutive_losses(self) -> int:
        """Count consecutive SL/loss closures from the most recent trade backward."""
        with self._lock:
            closures = [e for e in self._entries if e.get("type") == "CLOSED"]

        count = 0
        for c in reversed(closures):
            if c.get("pnl_usdt", 0) < 0:
                count += 1
            else:
                break
        return count

    def clear(self):
        """Clear all journal entries (uses atomic write)."""
        with self._lock:
            self._entries = []
            try:
                self.filepath.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = self.filepath.with_suffix(".tmp")
                with open(tmp_path, "w") as f:
                    pass  # Empty file
                os.replace(str(tmp_path), str(self.filepath))
            except IOError:
                pass


# Global instance
trade_journal = TradeJournal()
