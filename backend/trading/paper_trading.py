"""
OIE MVP - Paper Trading Manager
================================

Gestionează trading-ul automat bazat pe semnalele OIE.
- Convertește semnale în ordine
- Risk management
- Position sizing
- Trade logging
"""

import os
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path

logger = logging.getLogger(__name__)

from dotenv import load_dotenv

from backend.trading.binance_connector import (
    BinanceTestnetConnector,
    get_connector,
    TradeResult,
    Position
)
from backend.services.trade_logger import get_trade_logger, TradeEvent

load_dotenv()


@dataclass
class TradingConfig:
    """Configurație trading - OPTIMIZAT pe baza backtest-ului
    
    Backtest Results (14 zile, delta trend):
    - Win Rate: 63.41%
    - Profit Factor: 2.42
    - LONG Win Rate: 70.6%
    - SHORT Win Rate: 58.3%
    """
    symbol: str = "BTCUSDT"
    leverage: int = 1

    # Risk Management
    max_position_value: float = 1000.0  # Max USD value per trade
    risk_per_trade: float = 0.01        # 1% of balance per trade

    # Stop Loss / Take Profit (1:1 R:R - validat de backtest, funcționează bine)
    stop_loss_pct: float = 1.0       # 1% stop loss
    take_profit_pct: float = 1.0     # 1% take profit

    # Signal Filters - OPTIMIZAT
    min_confidence: float = 0.62     # Minimum signal confidence (62% - mărită de la 60%)

    # Reversal Protection - prevent premature position closures
    min_reversal_confidence: float = 0.70   # Need 70%+ confidence to reverse (was 62%)
    reversal_cooldown_minutes: float = 25.0  # Don't reverse within 25 min of opening (was 10)
    protect_profitable_positions: bool = True  # Don't reverse if position is profitable
    never_reverse_in_profit: bool = True  # NEVER reverse if position is profitable (strict mode)
    min_loss_before_reversal: float = 0.3  # Minimum loss % before allowing reversal (new)

    # Trading Hours (optional)
    trading_enabled: bool = True


@dataclass 
class TradeLog:
    """Log entry pentru un trade"""
    timestamp: datetime
    signal_type: str
    confidence: float
    direction: str
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    order_id: str
    status: str = "OPEN"
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'signal_type': self.signal_type,
            'confidence': self.confidence,
            'direction': self.direction,
            'entry_price': self.entry_price,
            'quantity': self.quantity,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'order_id': self.order_id,
            'status': self.status,
            'exit_price': self.exit_price,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'pnl': self.pnl
        }


class PaperTradingManager:
    """
    Manager pentru paper trading automat
    
    Primește semnale de la OIE și execută trades pe Binance Testnet.
    """
    
    def __init__(self, config: TradingConfig = None):
        self.config = config or TradingConfig()
        self.connector: Optional[BinanceTestnetConnector] = None

        self.current_trade: Optional[TradeLog] = None
        self.trade_history: List[TradeLog] = []

        self.is_running: bool = False
        self.last_signal_time: Optional[datetime] = None

        # Stats
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.total_pnl: float = 0.0

        # Trade logger for persistent logging
        self.trade_logger = get_trade_logger()

        # Log file
        self.log_dir = Path(__file__).parent.parent.parent / "results" / "paper_trading"
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    async def start(self):
        """Porneste trading manager"""
        print("\n" + "=" * 60)
        print("[PAPER] OIE Paper Trading Manager")
        print("=" * 60)

        self.connector = get_connector()

        if not await self.connector.connect():
            print("[ERROR] Failed to connect to Binance Testnet")
            return False

        # Set leverage
        await self.connector.set_leverage(self.config.symbol, self.config.leverage)

        # Sync existing position from Binance
        await self._sync_existing_position()

        self.is_running = True
        print(f"\n[OK] Trading Manager Started")
        print(f"   Symbol: {self.config.symbol}")
        print(f"   Leverage: {self.config.leverage}x")
        print(f"   Max Position Value: ${self.config.max_position_value}")
        print(f"   SL: {self.config.stop_loss_pct}% | TP: {self.config.take_profit_pct}%")
        print(f"   Min Confidence: {self.config.min_confidence:.0%}")
        print(f"   Reversal Protection:")
        print(f"      - Min confidence for reversal: {self.config.min_reversal_confidence:.0%}")
        print(f"      - Cooldown after open: {self.config.reversal_cooldown_minutes} min")
        print(f"      - Never reverse in profit: {self.config.never_reverse_in_profit}")
        print(f"      - Min loss before reversal: {self.config.min_loss_before_reversal}%")
        if self.current_trade:
            print(f"   [SYNC] Existing position: {self.current_trade.direction} @ ${self.current_trade.entry_price:,.2f}")

        return True

    async def _check_reversal_allowed(self, current_position: Position, new_confidence: float) -> tuple:
        """
        Verifică dacă putem face reversal pe poziția curentă.

        Returns:
            (bool, str): (can_reverse, reason_if_blocked)
        """
        # 1. Check confidence threshold for reversal
        if new_confidence < self.config.min_reversal_confidence:
            return False, f"confidence {new_confidence:.0%} < {self.config.min_reversal_confidence:.0%} required for reversal"

        # 2. Check cooldown period
        if self.current_trade and self.current_trade.timestamp:
            time_since_open = (datetime.now() - self.current_trade.timestamp).total_seconds() / 60
            if time_since_open < self.config.reversal_cooldown_minutes:
                return False, f"cooldown active ({time_since_open:.1f}min < {self.config.reversal_cooldown_minutes}min)"

        # 3. Check position PnL
        entry = current_position.entry_price
        current = await self.connector.get_price(self.config.symbol)

        if current_position.side == 'LONG':
            pnl_pct = ((current - entry) / entry) * 100
        else:
            pnl_pct = ((entry - current) / entry) * 100

        # STRICT MODE: Never reverse if in profit - let TP/SL handle it
        if pnl_pct > 0 and self.config.never_reverse_in_profit:
            return False, f"in profit ({pnl_pct:.2f}%) - waiting for TP/SL"

        # SOFT MODE: Allow reversal only if very close to entry (< 0.5% profit)
        if pnl_pct > 0 and self.config.protect_profitable_positions and pnl_pct > 0.5:
            return False, f"profitable ({pnl_pct:.2f}%) - waiting for TP/SL"

        # 4. Check minimum loss threshold before allowing reversal
        # Don't reverse if position is in small loss - wait for clearer signal
        if pnl_pct < 0 and abs(pnl_pct) < self.config.min_loss_before_reversal:
            return False, f"small loss ({pnl_pct:.2f}%) - need {self.config.min_loss_before_reversal}% loss or wait for SL"

        return True, ""

    async def _sync_existing_position(self):
        """Sincronizează poziția existentă de pe Binance și setează SL/TP dacă lipsesc"""
        logger.warning(f"[SYNC] Checking for existing position on {self.config.symbol}...")

        position = await self.connector.get_position(self.config.symbol)

        if position:
            logger.warning(f"[SYNC] Found existing {position.side} position on {self.config.symbol}")
            print(f"   Entry: ${position.entry_price:,.2f}")
            print(f"   Quantity: {position.quantity}")
            print(f"   Unrealized PnL: ${position.unrealized_pnl:,.2f}")

            # Calculate expected SL/TP based on config
            entry_price = position.entry_price
            if position.side == 'LONG':
                expected_sl = entry_price * (1 - self.config.stop_loss_pct / 100)
                expected_tp = entry_price * (1 + self.config.take_profit_pct / 100)
            else:  # SHORT
                expected_sl = entry_price * (1 + self.config.stop_loss_pct / 100)
                expected_tp = entry_price * (1 - self.config.take_profit_pct / 100)

            # Create TradeLog for existing position
            self.current_trade = TradeLog(
                timestamp=datetime.now(),
                signal_type="synced_position",
                confidence=1.0,
                direction=position.side,
                entry_price=position.entry_price,
                quantity=position.quantity,
                stop_loss=expected_sl,  # Calculate from config
                take_profit=expected_tp,  # Calculate from config
                order_id="synced",
                status="OPEN"
            )

            # Try to get SL/TP from open orders (override calculated values if found)
            orders = await self.connector.get_open_orders(self.config.symbol)
            has_sl_order = False
            has_tp_order = False
            for order in orders:
                order_type = order.get('type', '')
                stop_price = float(order.get('stopPrice', 0))
                if 'STOP' in order_type and stop_price > 0:
                    self.current_trade.stop_loss = stop_price
                    has_sl_order = True
                    print(f"   SL found: ${stop_price:,.2f}")
                elif 'PROFIT' in order_type and stop_price > 0:
                    self.current_trade.take_profit = stop_price
                    has_tp_order = True
                    print(f"   TP found: ${stop_price:,.2f}")

            # Log calculated SL/TP if not found on exchange
            if not has_sl_order:
                print(f"   SL calculated: ${expected_sl:,.4f} (will be checked manually)")
            if not has_tp_order:
                print(f"   TP calculated: ${expected_tp:,.4f} (will be checked manually)")
        else:
            print(f"[SYNC] No existing position on {self.config.symbol}")
    
    async def stop(self, close_positions: bool = False):
        """Opreste trading manager

        Args:
            close_positions: Dacă True, închide pozițiile deschise.
                           Default False - lasă pozițiile pe Binance pentru re-sync la restart.
        """
        print("\n[STOP] Stopping Trading Manager...")

        # Only close positions if explicitly requested
        if close_positions and self.current_trade:
            await self.close_current_position("manager_stopped")
        elif self.current_trade:
            print(f"[INFO] Leaving position open on Binance: {self.current_trade.direction} @ ${self.current_trade.entry_price:,.2f}")
            print(f"       Position will be re-synced on next restart")

        if self.connector:
            await self.connector.disconnect()

        self.is_running = False

        # Save final stats
        self._save_stats()

        print("[OK] Trading Manager Stopped")
    
    async def process_signal(self, signal: Dict[str, Any]) -> Optional[TradeResult]:
        """
        Procesează un semnal de la OIE

        Args:
            signal: Dict cu 'type', 'confidence', 'timestamp', 'signal_id' (optional)

        Returns:
            TradeResult dacă s-a executat un trade
        """
        if not self.is_running or not self.config.trading_enabled:
            print(f"[SKIP] Trading not enabled: is_running={self.is_running}, trading_enabled={self.config.trading_enabled}")
            return None

        signal_type = signal.get('type', '')
        confidence = signal.get('confidence', 0)
        signal_id = signal.get('signal_id')  # For linking trade to signal

        print(f"[SIGNAL] Processing: {signal_type} with confidence {confidence:.2f} (min: {self.config.min_confidence})")

        # Ignoră semnale neutrale
        if 'watch' in signal_type or 'neutral' in signal_type:
            print(f"[SKIP] Neutral signal ignored: {signal_type}")
            return None

        # Verifica confidence minim
        if confidence < self.config.min_confidence:
            print(f"[SKIP] Signal ignored: confidence {confidence:.2f} < {self.config.min_confidence}")
            return None

        print(f"[OK] Signal passed filters, executing trade...")
        
        # Determină direcția
        is_long = 'long' in signal_type.lower()
        is_short = 'short' in signal_type.lower()
        
        if not is_long and not is_short:
            return None
        
        # Verifică dacă avem deja poziție deschisă
        current_position = await self.connector.get_position(self.config.symbol)

        # Sync check: if no position on Binance but we have local trade, clean up
        if not current_position and self.current_trade:
            print(f"[SYNC] Position closed externally - cleaning up local state")
            await self.connector.cancel_all_orders(self.config.symbol)
            self.current_trade = None

        # Clean orphan orders if no position exists
        if not current_position:
            orders = await self.connector.get_open_orders(self.config.symbol)
            if orders:
                print(f"[CLEANUP] Found {len(orders)} orphan orders before new trade - cancelling...")
                await self.connector.cancel_all_orders(self.config.symbol)

        if current_position:
            # Dacă semnalul e în direcția opusă, verifică dacă putem face reversal
            current_is_long = current_position.side == 'LONG'

            if (is_long and not current_is_long) or (is_short and current_is_long):
                # Check reversal protection conditions
                can_reverse, block_reason = await self._check_reversal_allowed(
                    current_position, confidence
                )

                if not can_reverse:
                    print(f"[PROTECT] Reversal blocked: {block_reason}")
                    return None

                print(f"[REVERSE] Signal reversal allowed - closing current position")
                await self.close_current_position("signal_reversal")
            else:
                # Same direction, skip
                print(f"[SKIP] Already in {current_position.side} position")
                return None
        
        # Calculează position size
        balance = await self.connector.get_balance()
        price = await self.connector.get_price(self.config.symbol)

        # Get symbol info for proper precision
        symbol_info = await self.connector.get_symbol_info(self.config.symbol)
        min_qty = symbol_info.get('min_qty', 0.001)

        # Position size bazat pe risk (in USD)
        risk_amount = balance * self.config.risk_per_trade
        sl_distance = price * (self.config.stop_loss_pct / 100)
        risk_based_qty = risk_amount / sl_distance

        # Max position size in base asset (from USD value)
        max_qty = self.config.max_position_value / price

        # Use smaller of risk-based or max
        quantity = min(risk_based_qty, max_qty)

        # Round to symbol's precision
        quantity = self.connector.round_quantity(self.config.symbol, quantity)

        if quantity < min_qty:
            print(f"[SKIP] Position size {quantity} < min {min_qty} for {self.config.symbol}")
            return None
        
        # Calculează SL și TP
        if is_long:
            stop_loss = price * (1 - self.config.stop_loss_pct / 100)
            take_profit = price * (1 + self.config.take_profit_pct / 100)
        else:
            stop_loss = price * (1 + self.config.stop_loss_pct / 100)
            take_profit = price * (1 - self.config.take_profit_pct / 100)
        
        # Executa trade
        symbol_base = self.config.symbol.replace('USDT', '')
        print(f"\n[TRADE] Executing {'LONG' if is_long else 'SHORT'} Trade on {self.config.symbol}")
        print(f"   Confidence: {confidence:.2f}")
        print(f"   Quantity: {quantity} {symbol_base}")
        print(f"   Price: ${price:,.4f}")
        
        if is_long:
            result = await self.connector.open_long(
                self.config.symbol, 
                quantity,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
        else:
            result = await self.connector.open_short(
                self.config.symbol,
                quantity,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
        
        if result.success:
            # Use actual execution price from result
            actual_entry_price = result.price
            print(f"   [OK] Trade executed @ ${actual_entry_price:,.2f}")

            # Log trade with actual execution price
            self.current_trade = TradeLog(
                timestamp=datetime.now(),
                signal_type=signal_type,
                confidence=confidence,
                direction='LONG' if is_long else 'SHORT',
                entry_price=actual_entry_price,
                quantity=quantity,
                stop_loss=stop_loss,
                take_profit=take_profit,
                order_id=result.order_id
            )

            self._log_trade(self.current_trade, "OPENED")

            # Log to persistent trade logger
            trade_event = TradeEvent(
                id=str(uuid.uuid4()),
                ts=datetime.now().isoformat(),
                symbol=self.config.symbol,
                timeframe="1m",  # Default, could be passed in
                side='BUY' if is_long else 'SELL',
                action='OPEN',
                qty=quantity,
                entry_price=actual_entry_price,
                reason=signal_type,
                signal_id=signal_id,  # Link to triggering signal
                meta={'confidence': confidence, 'order_id': result.order_id}
            )
            asyncio.create_task(self.trade_logger.log_event(trade_event))

        return result
    
    async def close_current_position(self, reason: str = "manual") -> Optional[TradeResult]:
        """Închide poziția curentă"""
        if not self.current_trade:
            return None

        result = await self.connector.close_position(self.config.symbol)

        if result.success:
            # Use actual exit price from result
            actual_exit_price = result.price
            entry_price = self.current_trade.entry_price

            # Calculate PnL using actual prices
            if self.current_trade.direction == 'LONG':
                pnl = (actual_exit_price - entry_price) * self.current_trade.quantity
            else:
                pnl = (entry_price - actual_exit_price) * self.current_trade.quantity

            print(f"   [CLOSE] Entry: ${entry_price:,.2f} -> Exit: ${actual_exit_price:,.2f} | PnL: ${pnl:,.2f}")

            # Update trade log
            self.current_trade.status = "CLOSED"
            self.current_trade.exit_price = actual_exit_price
            self.current_trade.exit_time = datetime.now()
            self.current_trade.pnl = pnl

            # Update stats
            self.total_trades += 1
            self.total_pnl += pnl
            if pnl > 0:
                self.winning_trades += 1

            self.trade_history.append(self.current_trade)
            self._log_trade(self.current_trade, f"CLOSED ({reason})")

            # Log to persistent trade logger
            close_event = TradeEvent(
                id=str(uuid.uuid4()),
                ts=datetime.now().isoformat(),
                symbol=self.config.symbol,
                timeframe="1m",
                side='SELL' if self.current_trade.direction == 'LONG' else 'BUY',
                action='CLOSE',
                qty=self.current_trade.quantity,
                entry_price=entry_price,
                exit_price=actual_exit_price,
                pnl=pnl,
                reason=reason,
                meta={'order_id': self.current_trade.order_id}
            )
            asyncio.create_task(self.trade_logger.log_event(close_event))

            self.current_trade = None

        return result
    
    async def check_position_status(self):
        """Verifică statusul poziției (SL/TP hit) - atât pe Binance cât și manual"""
        if not self.current_trade:
            # No trade tracked - check for orphan orders and clean them
            orders = await self.connector.get_open_orders(self.config.symbol)
            if orders:
                print(f"[CLEANUP] Found {len(orders)} orphan orders - cancelling...")
                await self.connector.cancel_all_orders(self.config.symbol)
            return

        position = await self.connector.get_position(self.config.symbol)
        current_price = await self.connector.get_price(self.config.symbol)

        if not position:
            # Position closed (SL or TP hit on Binance)
            if self.current_trade.direction == 'LONG':
                pnl = (current_price - self.current_trade.entry_price) * self.current_trade.quantity
            else:
                pnl = (self.current_trade.entry_price - current_price) * self.current_trade.quantity

            reason = "take_profit" if pnl > 0 else "stop_loss"

            self.current_trade.status = "CLOSED"
            self.current_trade.exit_price = current_price
            self.current_trade.exit_time = datetime.now()
            self.current_trade.pnl = pnl

            self.total_trades += 1
            self.total_pnl += pnl
            if pnl > 0:
                self.winning_trades += 1

            self.trade_history.append(self.current_trade)
            self._log_trade(self.current_trade, f"CLOSED ({reason})")

            # Log to persistent trade logger
            action = "TAKE_PROFIT" if reason == "take_profit" else "STOP_LOSS"
            close_event = TradeEvent(
                id=str(uuid.uuid4()),
                ts=datetime.now().isoformat(),
                symbol=self.config.symbol,
                timeframe="1m",
                side='SELL' if self.current_trade.direction == 'LONG' else 'BUY',
                action=action,
                qty=self.current_trade.quantity,
                entry_price=self.current_trade.entry_price,
                exit_price=current_price,
                pnl=pnl,
                reason=reason,
                meta={'order_id': self.current_trade.order_id}
            )
            asyncio.create_task(self.trade_logger.log_event(close_event))

            # IMPORTANT: Cancel remaining orders (SL or TP that didn't trigger)
            print(f"[CLEANUP] Position closed by {reason} - cancelling remaining orders...")
            await self.connector.cancel_all_orders(self.config.symbol)

            self.current_trade = None
            return

        # Position still exists - check manual TP/SL (for synced positions without orders)
        entry_price = self.current_trade.entry_price
        is_long = self.current_trade.direction == 'LONG'

        # Calculate current PnL percentage
        if is_long:
            pnl_pct = (current_price - entry_price) / entry_price * 100
        else:
            pnl_pct = (entry_price - current_price) / entry_price * 100

        # Check if TP/SL orders exist on exchange
        has_tp_order = self.current_trade.take_profit > 0
        has_sl_order = self.current_trade.stop_loss > 0

        # Manual TP check (if no TP order exists)
        if not has_tp_order and pnl_pct >= self.config.take_profit_pct:
            print(f"[TP HIT] Manual TP triggered at {pnl_pct:.2f}% profit!")
            await self._close_position_with_reason("take_profit_manual", current_price)
            return

        # Manual SL check (if no SL order exists)
        if not has_sl_order and pnl_pct <= -self.config.stop_loss_pct:
            print(f"[SL HIT] Manual SL triggered at {pnl_pct:.2f}% loss!")
            await self._close_position_with_reason("stop_loss_manual", current_price)
            return

    async def _close_position_with_reason(self, reason: str, exit_price: float):
        """Închide poziția curentă cu un motiv specificat"""
        if not self.current_trade:
            return

        result = await self.connector.close_position(self.config.symbol)

        if result.success:
            actual_exit_price = result.price if result.price else exit_price
            entry_price = self.current_trade.entry_price

            if self.current_trade.direction == 'LONG':
                pnl = (actual_exit_price - entry_price) * self.current_trade.quantity
            else:
                pnl = (entry_price - actual_exit_price) * self.current_trade.quantity

            print(f"   [CLOSE] Entry: ${entry_price:,.2f} -> Exit: ${actual_exit_price:,.2f} | PnL: ${pnl:,.2f}")

            self.current_trade.status = "CLOSED"
            self.current_trade.exit_price = actual_exit_price
            self.current_trade.exit_time = datetime.now()
            self.current_trade.pnl = pnl

            self.total_trades += 1
            self.total_pnl += pnl
            if pnl > 0:
                self.winning_trades += 1

            self.trade_history.append(self.current_trade)
            self._log_trade(self.current_trade, f"CLOSED ({reason})")

            # Log to persistent trade logger
            action = "TAKE_PROFIT" if "take_profit" in reason else "STOP_LOSS" if "stop_loss" in reason else "CLOSE"
            close_event = TradeEvent(
                id=str(uuid.uuid4()),
                ts=datetime.now().isoformat(),
                symbol=self.config.symbol,
                timeframe="1m",
                side='SELL' if self.current_trade.direction == 'LONG' else 'BUY',
                action=action,
                qty=self.current_trade.quantity,
                entry_price=entry_price,
                exit_price=actual_exit_price,
                pnl=pnl,
                reason=reason,
                meta={'order_id': self.current_trade.order_id}
            )
            asyncio.create_task(self.trade_logger.log_event(close_event))

            # Cancel any remaining orders
            await self.connector.cancel_all_orders(self.config.symbol)

            self.current_trade = None

    def get_stats(self) -> Dict[str, Any]:
        """Returnează statistici trading"""
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        
        return {
            'is_running': self.is_running,
            'symbol': self.config.symbol,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.total_trades - self.winning_trades,
            'win_rate': round(win_rate, 2),
            'total_pnl': round(self.total_pnl, 2),
            'current_position': self.current_trade.to_dict() if self.current_trade else None
        }
    
    def _log_trade(self, trade: TradeLog, action: str):
        """Loghează trade în fișier"""
        log_file = self.log_dir / f"trades_{datetime.now().strftime('%Y%m%d')}.json"
        
        log_entry = {
            'action': action,
            'timestamp': datetime.now().isoformat(),
            'trade': trade.to_dict()
        }
        
        # Append to log file
        logs = []
        if log_file.exists():
            try:
                with open(log_file, 'r') as f:
                    logs = json.load(f)
            except:
                logs = []
        
        logs.append(log_entry)
        
        with open(log_file, 'w') as f:
            json.dump(logs, f, indent=2)
        
        print(f"[LOG] Trade logged: {action}")
    
    def _save_stats(self):
        """Salvează statistici finale"""
        stats_file = self.log_dir / "stats.json"
        
        stats = self.get_stats()
        stats['last_updated'] = datetime.now().isoformat()
        stats['trade_history'] = [t.to_dict() for t in self.trade_history]
        
        with open(stats_file, 'w') as f:
            json.dump(stats, f, indent=2)
        
        print(f"[STATS] Stats saved to: {stats_file}")


# Singleton
_manager: Optional[PaperTradingManager] = None


def get_trading_manager() -> PaperTradingManager:
    """Returnează instanța singleton"""
    global _manager
    if _manager is None:
        _manager = PaperTradingManager()
    return _manager


async def test_trading():
    """Test trading manager"""
    manager = PaperTradingManager()
    
    if not await manager.start():
        return
    
    # Simulate a signal
    test_signal = {
        'type': 'predictive_breakout_long',
        'confidence': 0.75,
        'timestamp': datetime.now().isoformat()
    }
    
    print("\n[SIM] Simulating LONG signal...")
    result = await manager.process_signal(test_signal)
    
    if result and result.success:
        print("\n[WAIT] Waiting 10 seconds...")
        await asyncio.sleep(10)

        print("\n[SIM] Closing position...")
        await manager.close_current_position("test_complete")
    
    await manager.stop()

    print("\n[STATS] Final Stats:")
    print(json.dumps(manager.get_stats(), indent=2))


if __name__ == '__main__':
    asyncio.run(test_trading())
