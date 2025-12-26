"""
Signal Logger Service - Persistent signal logging with JSONL storage
"""
import asyncio
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pathlib import Path


@dataclass
class SignalEvent:
    """Represents a single signal event"""
    id: str                              # Unique signal ID (uuid)
    ts: str                              # ISO timestamp
    symbol: str                          # e.g., BTCUSDT
    timeframe: str                       # e.g., 1m, 5m
    signal_type: str                     # LONG, SHORT, EXIT, NONE
    strength: float                      # Signal confidence/strength 0-1
    delta: float                         # Current delta value
    ifi: float                           # Institutional Flow Index
    vortex: float                        # Vortex indicator (bp_up or bp_down)
    regime: str                          # Market regime (BULLISH, BEARISH, NEUTRAL)
    decision: str                        # EXECUTED, IGNORED, BLOCKED
    reason: str                          # Human-readable reason
    linked_trade_id: Optional[str] = None  # Trade ID if executed
    meta: Dict[str, Any] = field(default_factory=dict)  # Additional metadata

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SignalEvent":
        return cls(**data)


class SignalLogger:
    """Thread-safe signal logger with JSONL persistence"""

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.signals_file = self.data_dir / "signals.jsonl"
        self._lock = asyncio.Lock()
        self._signals: List[SignalEvent] = []
        self._last_signal_by_symbol: Dict[str, SignalEvent] = {}
        self._ensure_data_dir()

    def _ensure_data_dir(self):
        """Ensure data directory exists"""
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def load_from_disk(self, limit: int = 1000) -> int:
        """Load last N signals from JSONL file. Returns count of loaded signals."""
        self._signals = []
        if not self.signals_file.exists():
            return 0

        try:
            # Read all lines first
            all_lines = []
            with open(self.signals_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        all_lines.append(line)

            # Take only last N
            recent_lines = all_lines[-limit:] if len(all_lines) > limit else all_lines

            for line in recent_lines:
                try:
                    data = json.loads(line)
                    signal = SignalEvent.from_dict(data)
                    self._signals.append(signal)
                    self._last_signal_by_symbol[signal.symbol] = signal
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"[SignalLogger] Skip invalid line: {e}")

            print(f"[SignalLogger] Loaded {len(self._signals)} signals from disk")
            return len(self._signals)
        except Exception as e:
            print(f"[SignalLogger] Error loading signals: {e}")
            return 0

    async def log_signal(self, event: SignalEvent) -> bool:
        """Log a signal event to memory and disk"""
        async with self._lock:
            try:
                # Add to memory
                self._signals.append(event)
                self._last_signal_by_symbol[event.symbol] = event

                # Keep memory bounded
                if len(self._signals) > 5000:
                    self._signals = self._signals[-3000:]

                # Append to JSONL file
                with open(self.signals_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event.to_dict()) + "\n")

                print(f"[SignalLogger] {event.signal_type} {event.symbol} | {event.decision} | {event.reason[:50]}")
                return True
            except Exception as e:
                print(f"[SignalLogger] Error logging signal: {e}")
                return False

    def get_signals(
        self,
        symbol: Optional[str] = None,
        limit: int = 200,
        today_only: bool = False,
        decision: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get signals, optionally filtered"""
        signals = self._signals

        # Filter by symbol
        if symbol:
            signals = [s for s in signals if s.symbol == symbol]

        # Filter by decision
        if decision:
            signals = [s for s in signals if s.decision == decision]

        # Filter by today
        if today_only:
            today = date.today().isoformat()
            signals = [s for s in signals if s.ts.startswith(today)]

        # Sort by timestamp descending (newest first)
        signals = sorted(signals, key=lambda s: s.ts, reverse=True)

        # Apply limit
        signals = signals[:limit]

        return [s.to_dict() for s in signals]

    def get_last_signal(self, symbol: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get the most recent signal, optionally for a specific symbol"""
        if symbol:
            signal = self._last_signal_by_symbol.get(symbol)
            return signal.to_dict() if signal else None

        # Get most recent across all symbols
        if not self._signals:
            return None
        return self._signals[-1].to_dict()

    def get_stats(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Calculate signal statistics"""
        signals = self._signals
        if symbol:
            signals = [s for s in signals if s.symbol == symbol]

        today = date.today().isoformat()
        today_signals = [s for s in signals if s.ts.startswith(today)]

        return {
            "all_time": self._calculate_stats(signals),
            "today": self._calculate_stats(today_signals),
            "by_symbol": self._get_per_symbol_stats(signals)
        }

    def _calculate_stats(self, signals: List[SignalEvent]) -> Dict[str, Any]:
        """Calculate stats for a list of signals"""
        if not signals:
            return {
                "total_signals": 0,
                "executed": 0,
                "ignored": 0,
                "blocked": 0,
                "long_signals": 0,
                "short_signals": 0,
                "execution_rate": 0.0
            }

        executed = len([s for s in signals if s.decision == "EXECUTED"])
        ignored = len([s for s in signals if s.decision == "IGNORED"])
        blocked = len([s for s in signals if s.decision == "BLOCKED"])
        long_signals = len([s for s in signals if s.signal_type == "LONG"])
        short_signals = len([s for s in signals if s.signal_type == "SHORT"])

        return {
            "total_signals": len(signals),
            "executed": executed,
            "ignored": ignored,
            "blocked": blocked,
            "long_signals": long_signals,
            "short_signals": short_signals,
            "execution_rate": round(executed / len(signals) * 100, 2) if signals else 0.0
        }

    def _get_per_symbol_stats(self, signals: List[SignalEvent]) -> Dict[str, Dict[str, Any]]:
        """Get stats per symbol"""
        symbols = set(s.symbol for s in signals)
        result = {}
        for sym in symbols:
            sym_signals = [s for s in signals if s.symbol == sym]
            result[sym] = self._calculate_stats(sym_signals)
        return result

    async def reset(self, symbol: Optional[str] = None) -> bool:
        """Reset signals - either all or for a specific symbol"""
        async with self._lock:
            try:
                if symbol:
                    self._signals = [s for s in self._signals if s.symbol != symbol]
                    if symbol in self._last_signal_by_symbol:
                        del self._last_signal_by_symbol[symbol]
                else:
                    self._signals = []
                    self._last_signal_by_symbol = {}

                # Rewrite file
                with open(self.signals_file, "w", encoding="utf-8") as f:
                    for signal in self._signals:
                        f.write(json.dumps(signal.to_dict()) + "\n")

                print(f"[SignalLogger] Reset signals" + (f" for {symbol}" if symbol else ""))
                return True
            except Exception as e:
                print(f"[SignalLogger] Error resetting: {e}")
                return False


# Singleton instance
_logger: Optional[SignalLogger] = None


def get_signal_logger() -> SignalLogger:
    """Get or create the singleton SignalLogger instance"""
    global _logger
    if _logger is None:
        _logger = SignalLogger()
        _logger.load_from_disk()
    return _logger
