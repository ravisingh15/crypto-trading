"""
Position Tracker — Monitors open positions and detects closures.
Tracks entries placed by the bot (both paper and live) and polls
Binance for order status to detect SL/TP fills.

Key capabilities:
- Persists positions to disk (JSON) — survives server restarts
- Tracks SL/TP order IDs for Futures cancel-other logic
- Detects live closures via actual order status queries (not guessing)
- Supports trailing stop loss fields for future use
"""
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from backend.binance_client import binance_client


# Persistence file path
POSITIONS_DIR = Path(__file__).resolve().parent.parent / "data_cache"
POSITIONS_FILE = POSITIONS_DIR / "positions.json"


class PositionTracker:
    """
    Tracks open positions placed by the auto-trader.
    Paper trades are tracked internally. Live trades are cross-referenced
    with Binance order status to detect SL/TP fills.

    All positions are persisted to disk as JSON — state survives restarts.
    """

    def __init__(self, filepath: Path = POSITIONS_FILE):
        self._lock = threading.Lock()
        self.filepath = filepath
        # Active positions keyed by symbol
        self._positions: Dict[str, Dict[str, Any]] = {}
        self._load()

    # ==========================================================================
    # PERSISTENCE
    # ==========================================================================

    def _load(self):
        """Load positions from disk on startup."""
        try:
            if self.filepath.exists():
                with open(self.filepath, "r") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._positions = data
                elif isinstance(data, list):
                    # Legacy format: list of positions → convert to dict keyed by symbol
                    self._positions = {p["symbol"]: p for p in data if "symbol" in p}
                print(f"  [PositionTracker] Restored {len(self._positions)} positions from disk")
        except (json.JSONDecodeError, IOError, KeyError) as e:
            print(f"  [PositionTracker] Warning: Could not load positions: {e}")
            self._positions = {}

    def _save(self):
        """Persist positions to disk using atomic write (temp file + rename)."""
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.filepath.with_suffix(".tmp")
            with open(tmp_path, "w") as f:
                json.dump(self._positions, f, indent=2, default=str)
            # Atomic rename — safe against crashes mid-write
            os.replace(str(tmp_path), str(self.filepath))
        except (IOError, OSError) as e:
            print(f"  [PositionTracker] Warning: Could not save positions: {e}")

    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================

    def add_position(self, symbol: str, side: str, quantity: float,
                     entry_price: float, amount_usdt: float,
                     sl: float, tp: float,
                     order_id: Any = None, oco_id: Any = None,
                     sl_order_id: Any = None, tp_order_id: Any = None,
                     paper: bool = False, market_type: str = "futures",
                     strategy: str = "", leverage: int = 1):
        """Record a new open position and persist to disk."""
        with self._lock:
            self._positions[symbol.upper()] = {
                "symbol": symbol.upper(),
                "side": side,
                "quantity": quantity,
                "entry_price": entry_price,
                "amount_usdt": amount_usdt,
                "stop_loss": sl,
                "take_profit": tp,
                "order_id": order_id,
                "oco_id": oco_id,
                "sl_order_id": sl_order_id,
                "tp_order_id": tp_order_id,
                "paper": paper,
                "market_type": market_type,
                "strategy": strategy,
                "leverage": leverage,
                # Trailing SL fields (Phase 3)
                "trailing_sl": None,
                "highest_price": entry_price if side == "BUY" else None,
                "lowest_price": entry_price if side == "SELL" else None,
                "opened_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            }
            self._save()

    def remove_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Remove and return a closed position, persist to disk."""
        with self._lock:
            removed = self._positions.pop(symbol.upper(), None)
            if removed is not None:
                self._save()
            return removed

    def update_position(self, symbol: str, updates: Dict[str, Any]):
        """Update fields on an existing position and persist."""
        with self._lock:
            pos = self._positions.get(symbol.upper())
            if pos:
                pos.update(updates)
                self._save()

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all currently tracked positions."""
        with self._lock:
            return list(self._positions.values())

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get a specific position by symbol."""
        with self._lock:
            return self._positions.get(symbol.upper())

    def has_position(self, symbol: str) -> bool:
        """Check if we have an open position for a symbol."""
        with self._lock:
            return symbol.upper() in self._positions

    def count(self) -> int:
        """Number of open positions."""
        with self._lock:
            return len(self._positions)

    def _get_price(self, symbol: str, market_type: str = "futures") -> float:
        """Helper to get current price based on market_type with fallback."""
        if market_type == "futures":
            try:
                return binance_client.futures_get_symbol_price(symbol)
            except Exception:
                return binance_client.get_symbol_price(symbol)
        else:
            try:
                return binance_client.get_symbol_price(symbol)
            except Exception:
                return binance_client.futures_get_symbol_price(symbol)

    # ==========================================================================
    # PAPER POSITION CLOSURES
    # ==========================================================================

    def check_paper_closures(self) -> List[Dict[str, Any]]:
        """
        Check paper positions against current prices to detect SL/TP hits.
        Returns list of closed positions with P&L.
        """
        closed = []
        positions_to_check = self.get_open_positions()

        for pos in positions_to_check:
            if not pos.get("paper"):
                continue

            symbol = pos["symbol"]
            m_type = pos.get("market_type", "futures")
            try:
                current_price = self._get_price(symbol, m_type)
            except Exception:
                continue

            entry = pos["entry_price"]
            sl = pos.get("trailing_sl") or pos["stop_loss"]  # Use trailing SL if set
            tp = pos["take_profit"]
            qty = pos["quantity"]
            side = pos["side"]

            # Update high/low watermarks for trailing SL (Phase 3)
            if side == "BUY" and (pos.get("highest_price") is None or current_price > pos["highest_price"]):
                self.update_position(symbol, {"highest_price": current_price})
            elif side == "SELL" and (pos.get("lowest_price") is None or current_price < pos["lowest_price"]):
                self.update_position(symbol, {"lowest_price": current_price})

            hit = None
            if side == "BUY":  # LONG position
                if current_price <= sl:
                    hit = "SL"
                    pnl = (sl - entry) * qty
                elif current_price >= tp:
                    hit = "TP"
                    pnl = (tp - entry) * qty
            else:  # SHORT position
                if current_price >= sl:
                    hit = "SL"
                    pnl = (entry - sl) * qty
                elif current_price <= tp:
                    hit = "TP"
                    pnl = (entry - tp) * qty

            if hit:
                removed = self.remove_position(symbol)
                if removed:
                    removed["exit_type"] = hit
                    removed["pnl"] = round(pnl, 4)
                    removed["exit_price"] = current_price
                    closed.append(removed)

        return closed

    # ==========================================================================
    # LIVE POSITION CLOSURES (via order status queries)
    # ==========================================================================

    def check_live_closures(self) -> List[Dict[str, Any]]:
        """
        Check live positions by querying actual order status from Binance.

        For Futures: queries individual SL/TP order status to determine
        which one filled, then cancels the other.

        For Spot: queries open orders; if none remain, checks OCO status.
        """
        closed = []
        positions_to_check = self.get_open_positions()

        for pos in positions_to_check:
            if pos.get("paper"):
                continue

            symbol = pos["symbol"]
            m_type = pos.get("market_type", "futures")

            try:
                if m_type == "futures":
                    result = self._check_futures_closure(pos)
                else:
                    result = self._check_spot_closure(pos)

                if result:
                    closed.append(result)
            except Exception:
                continue

        return closed

    def _check_futures_closure(self, pos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Check Futures position closure by querying SL/TP order status directly.
        If one filled, cancel the other and record the closure.
        """
        symbol = pos["symbol"]
        sl_order_id = pos.get("sl_order_id")
        tp_order_id = pos.get("tp_order_id")
        entry = pos["entry_price"]
        qty = pos["quantity"]

        # If we don't have order IDs, fall back to open-orders check
        if not sl_order_id and not tp_order_id:
            return self._check_closure_by_open_orders(pos)

        sl_filled = False
        tp_filled = False
        sl_fill_price = None
        tp_fill_price = None

        # Check SL order status
        if sl_order_id:
            try:
                sl_status = binance_client.futures_get_order_status(symbol, sl_order_id)
                if sl_status.get("status") == "FILLED":
                    sl_filled = True
                    sl_fill_price = float(sl_status.get("avgPrice", 0))
                    if sl_fill_price <= 0:
                        sl_fill_price = pos["stop_loss"]
            except Exception:
                pass

        # Check TP order status
        if tp_order_id:
            try:
                tp_status = binance_client.futures_get_order_status(symbol, tp_order_id)
                if tp_status.get("status") == "FILLED":
                    tp_filled = True
                    tp_fill_price = float(tp_status.get("avgPrice", 0))
                    if tp_fill_price <= 0:
                        tp_fill_price = pos["take_profit"]
            except Exception:
                pass

        if not sl_filled and not tp_filled:
            # Neither filled yet — check if position was liquidated
            try:
                futures_positions = binance_client.futures_get_positions(symbol)
                if not futures_positions:
                    # Position gone but no SL/TP filled → liquidation
                    removed = self.remove_position(symbol)
                    if removed:
                        removed["exit_type"] = "LIQUIDATION"
                        removed["pnl"] = round(-pos["amount_usdt"], 4)  # Assume full loss
                        removed["exit_price"] = 0
                        # Cancel any remaining orders
                        self._cancel_remaining_orders(symbol, sl_order_id, tp_order_id)
                        return removed
            except Exception:
                pass
            return None

        # Determine which filled and cancel the other
        if sl_filled:
            exit_type = "SL"
            exit_price = sl_fill_price
            # Cancel the TP order
            if tp_order_id:
                try:
                    binance_client.futures_cancel_order(symbol, tp_order_id)
                except Exception:
                    pass
        else:  # tp_filled
            exit_type = "TP"
            exit_price = tp_fill_price
            # Cancel the SL order
            if sl_order_id:
                try:
                    binance_client.futures_cancel_order(symbol, sl_order_id)
                except Exception:
                    pass

        # Calculate PnL from actual fill price
        if pos["side"] == "BUY":
            pnl = (exit_price - entry) * qty
        else:
            pnl = (entry - exit_price) * qty

        removed = self.remove_position(symbol)
        if removed:
            removed["exit_type"] = exit_type
            removed["pnl"] = round(pnl, 4)
            removed["exit_price"] = exit_price
            return removed

        return None

    def _check_spot_closure(self, pos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check Spot position closure by querying open orders."""
        return self._check_closure_by_open_orders(pos)

    def _check_closure_by_open_orders(self, pos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fallback closure detection: if no open orders remain, position was closed.
        Queries actual order history when possible for accurate fill price.
        """
        symbol = pos["symbol"]
        m_type = pos.get("market_type", "futures")

        try:
            if m_type == "futures":
                open_orders = binance_client.futures_get_open_orders(symbol)
            else:
                open_orders = binance_client.get_open_orders(symbol)

            if len(open_orders) > 0:
                return None  # Still has open orders — not closed

            # No open orders remain — position was closed
            removed = self.remove_position(symbol)
            if removed:
                try:
                    current_price = self._get_price(symbol, m_type)
                except Exception:
                    current_price = removed["entry_price"]

                entry = removed["entry_price"]
                qty = removed["quantity"]

                # Try to determine exit type from order IDs
                exit_type, fill_price = self._query_fill_info(removed, m_type)

                if fill_price and fill_price > 0:
                    actual_exit = fill_price
                else:
                    actual_exit = current_price

                if pos["side"] == "BUY":
                    pnl = (actual_exit - entry) * qty
                else:
                    pnl = (entry - actual_exit) * qty

                removed["exit_type"] = exit_type
                removed["pnl"] = round(pnl, 4)
                removed["exit_price"] = actual_exit
                return removed
        except Exception:
            pass

        return None

    def _query_fill_info(self, pos: Dict[str, Any], m_type: str) -> tuple:
        """Try to determine exit type and fill price from order history."""
        sl_order_id = pos.get("sl_order_id")
        tp_order_id = pos.get("tp_order_id")

        if m_type == "futures":
            # Check SL order
            if sl_order_id:
                try:
                    status = binance_client.futures_get_order_status(pos["symbol"], sl_order_id)
                    if status.get("status") == "FILLED":
                        price = float(status.get("avgPrice", 0))
                        return "SL", price if price > 0 else None
                except Exception:
                    pass
            # Check TP order
            if tp_order_id:
                try:
                    status = binance_client.futures_get_order_status(pos["symbol"], tp_order_id)
                    if status.get("status") == "FILLED":
                        price = float(status.get("avgPrice", 0))
                        return "TP", price if price > 0 else None
                except Exception:
                    pass

        return "UNKNOWN", None

    def _cancel_remaining_orders(self, symbol: str, sl_order_id: Any, tp_order_id: Any):
        """Cancel any remaining unfilled orders for a symbol."""
        for oid in [sl_order_id, tp_order_id]:
            if oid:
                try:
                    binance_client.futures_cancel_order(symbol, oid)
                except Exception:
                    pass

    # ==========================================================================
    # SERIALIZATION
    # ==========================================================================

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Serialize all positions for API response."""
        positions = self.get_open_positions()
        for pos in positions:
            symbol = pos["symbol"]
            m_type = pos.get("market_type", "futures")
            try:
                pos["current_price"] = self._get_price(symbol, m_type)
                entry = pos["entry_price"]
                current = pos["current_price"]
                qty = pos["quantity"]
                if pos["side"] == "BUY":
                    pos["unrealized_pnl"] = round((current - entry) * qty, 4)
                else:
                    pos["unrealized_pnl"] = round((entry - current) * qty, 4)
            except Exception:
                pos["current_price"] = None
                pos["unrealized_pnl"] = None
        return positions


# Global instance
position_tracker = PositionTracker()
