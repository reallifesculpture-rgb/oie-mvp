"""
Trade Logger Service - Persistent trade logging with JSONL storage
"""
import asyncio
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pathlib import Path


@dataclass
class TradeEvent:
    """Represents a single trade event"""
    id: str                          # Unique trade ID
    ts: str                          # ISO timestamp
    symbol: str                      # e.g., BTCUSDT
    timeframe: str                   # e.g., 1m, 5m
    side: str                        # BUY or SELL
    action: str                      # OPEN, CLOSE, STOP_LOSS, TAKE_PROFIT
    qty: float                       # Quantity traded
    entry_price: float               # Entry price
    exit_price: Optional[float] = None  # Exit price (for closes)
    pnl: float = 0.0                 # Realized PnL
    fees: float = 0.0                # Trading fees
    reason: str = ""                 # Signal reason (e.g., "momentum_breakout")
    signal_id: Optional[str] = None  # Linked signal ID
    meta: Dict[str, Any] = field(default_factory=dict)  # Additional metadata

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradeEvent":
        return cls(**data)


class TradeLogger:
    """Thread-safe trade logger with JSONL persistence"""

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.trades_file = self.data_dir / "trades.jsonl"
        self._lock = asyncio.Lock()
        self._trades: List[TradeEvent] = []
        self._ensure_data_dir()

    def _ensure_data_dir(self):
        """Ensure data directory exists"""
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def load_from_disk(self) -> int:
        """Load trades from JSONL file. Returns count of loaded trades."""
        self._trades = []
        if not self.trades_file.exists():
            return 0

        try:
            with open(self.trades_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            self._trades.append(TradeEvent.from_dict(data))
                        except (json.JSONDecodeError, TypeError) as e:
                            print(f"[TradeLogger] Skip invalid line: {e}")
            print(f"[TradeLogger] Loaded {len(self._trades)} trades from disk")
            return len(self._trades)
        except Exception as e:
            print(f"[TradeLogger] Error loading trades: {e}")
            return 0

    async def log_event(self, event: TradeEvent) -> bool:
        """Log a trade event to memory and disk"""
        async with self._lock:
            try:
                # Add to memory
                self._trades.append(event)

                # Append to JSONL file
                with open(self.trades_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event.to_dict()) + "\n")

                print(f"[TradeLogger] Logged: {event.action} {event.side} {event.qty} {event.symbol} @ {event.entry_price}")
                return True
            except Exception as e:
                print(f"[TradeLogger] Error logging event: {e}")
                return False

    def get_trades(
        self,
        symbol: Optional[str] = None,
        limit: int = 200,
        today_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Get trades, optionally filtered by symbol"""
        trades = self._trades

        # Filter by symbol
        if symbol:
            trades = [t for t in trades if t.symbol == symbol]

        # Filter by today
        if today_only:
            today = date.today().isoformat()
            trades = [t for t in trades if t.ts.startswith(today)]

        # Sort by timestamp descending (newest first)
        trades = sorted(trades, key=lambda t: t.ts, reverse=True)

        # Apply limit
        trades = trades[:limit]

        return [t.to_dict() for t in trades]

    def get_stats(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Calculate trading statistics"""
        trades = self._trades
        if symbol:
            trades = [t for t in trades if t.symbol == symbol]

        today = date.today().isoformat()
        today_trades = [t for t in trades if t.ts.startswith(today)]

        # All-time stats
        all_time = self._calculate_stats(trades)

        # Today's stats
        today_stats = self._calculate_stats(today_trades)

        # Per-symbol breakdown
        symbols = set(t.symbol for t in trades)
        by_symbol = {}
        for sym in symbols:
            sym_trades = [t for t in trades if t.symbol == sym]
            by_symbol[sym] = self._calculate_stats(sym_trades)

        return {
            "all_time": all_time,
            "today": today_stats,
            "by_symbol": by_symbol
        }

    def _calculate_stats(self, trades: List[TradeEvent]) -> Dict[str, Any]:
        """Calculate stats for a list of trades"""
        if not trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "total_fees": 0.0,
                "net_pnl": 0.0,
                "avg_pnl": 0.0,
                "best_trade": 0.0,
                "worst_trade": 0.0
            }

        # Only count closed trades for PnL stats
        closed_trades = [t for t in trades if t.action in ("CLOSE", "STOP_LOSS", "TAKE_PROFIT")]

        total_pnl = sum(t.pnl for t in closed_trades)
        total_fees = sum(t.fees for t in trades)
        winning = [t for t in closed_trades if t.pnl > 0]
        losing = [t for t in closed_trades if t.pnl < 0]

        pnls = [t.pnl for t in closed_trades] if closed_trades else [0]

        return {
            "total_trades": len(trades),
            "closed_trades": len(closed_trades),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": len(winning) / len(closed_trades) * 100 if closed_trades else 0.0,
            "total_pnl": round(total_pnl, 4),
            "total_fees": round(total_fees, 4),
            "net_pnl": round(total_pnl - total_fees, 4),
            "avg_pnl": round(total_pnl / len(closed_trades), 4) if closed_trades else 0.0,
            "best_trade": round(max(pnls), 4),
            "worst_trade": round(min(pnls), 4)
        }

    async def reset(self, symbol: Optional[str] = None) -> bool:
        """Reset trades - either all or for a specific symbol"""
        async with self._lock:
            try:
                if symbol:
                    # Keep only trades that don't match the symbol
                    self._trades = [t for t in self._trades if t.symbol != symbol]
                else:
                    # Clear all
                    self._trades = []

                # Rewrite file
                with open(self.trades_file, "w", encoding="utf-8") as f:
                    for trade in self._trades:
                        f.write(json.dumps(trade.to_dict()) + "\n")

                print(f"[TradeLogger] Reset trades" + (f" for {symbol}" if symbol else ""))
                return True
            except Exception as e:
                print(f"[TradeLogger] Error resetting: {e}")
                return False


# Singleton instance
_logger: Optional[TradeLogger] = None


def get_trade_logger() -> TradeLogger:
    """Get or create the singleton TradeLogger instance"""
    global _logger
    if _logger is None:
        _logger = TradeLogger()
        _logger.load_from_disk()
    return _logger
