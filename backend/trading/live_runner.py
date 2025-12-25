"""
OIE MVP - Live Trading Runner
==============================

Integrare completă în timp real:
- Date live de la Binance WebSocket
- Engine-uri OIE (Topology, Predictive, Signals)
- Execuție automată trades pe Binance Testnet
- Broadcast la frontend via WebSocket
"""

import os
import asyncio
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from collections import deque

import aiohttp
from dotenv import load_dotenv

from backend.data.models import Bar
from backend.topology.engine import engine as topology_engine
from backend.predictive.engine import engine as predictive_engine
from backend.signals.engine import engine as signals_engine
from backend.trading.binance_connector import BinanceTestnetConnector
from backend.trading.paper_trading import PaperTradingManager, TradingConfig

load_dotenv()


@dataclass
class LiveBar:
    """Bară live de la Binance"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    
    @property
    def delta(self) -> float:
        return self.buy_volume - self.sell_volume
    
    def to_bar(self) -> Bar:
        """Convertește la Bar model"""
        return Bar(
            timestamp=self.timestamp.isoformat(),
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
            buy_volume=self.buy_volume,
            sell_volume=self.sell_volume
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'delta': self.delta
        }


class BinanceLiveDataFeed:
    """
    Feed de date live de la Binance WebSocket
    Agregrează tick data în bare de 1 minut
    """
    
    WS_URL = "wss://fstream.binance.com/ws"
    
    def __init__(self, symbol: str = "btcusdt", interval: str = "1m"):
        self.symbol = symbol.lower()
        self.interval = interval
        self.ws = None
        self.session = None
        
        self.current_bar: Optional[LiveBar] = None
        self.bars: deque = deque(maxlen=200)  # Keep last 200 bars
        
        self.callbacks: List[callable] = []
        self.running = False
    
    def on_bar(self, callback: callable):
        """Înregistrează callback pentru bare noi"""
        self.callbacks.append(callback)
    
    async def start(self):
        """Pornește feed-ul de date"""
        print(f"[DATA] Starting live data feed for {self.symbol.upper()}...")
        print(f"[DATA] WebSocket URL: {self.WS_URL}/{self.symbol}@kline_{self.interval}")

        try:
            self.session = aiohttp.ClientSession()
        except Exception as e:
            print(f"[ERROR] Failed to create session: {e}")
            return

        self.running = True

        # Subscribe la kline stream
        stream = f"{self.symbol}@kline_{self.interval}"
        url = f"{self.WS_URL}/{stream}"

        try:
            print(f"[DATA] Connecting to WebSocket...")
            async with self.session.ws_connect(url, timeout=10) as ws:
                self.ws = ws
                print(f"[OK] Connected to Binance {self.symbol.upper()} {self.interval} stream")
                
                async for msg in ws:
                    if not self.running:
                        break
                    
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await self._handle_message(json.loads(msg.data))
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        print(f"WebSocket error: {msg.data}")
                        break
        
        except Exception as e:
            print(f"[ERROR] Data feed error: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Oprește feed-ul"""
        self.running = False
        if self.session:
            await self.session.close()
        print("[DATA] Data feed stopped")
    
    async def _handle_message(self, data: Dict):
        """Procesează mesaj de la WebSocket"""
        if 'k' not in data:
            return
        
        kline = data['k']
        
        bar = LiveBar(
            timestamp=datetime.fromtimestamp(kline['t'] / 1000),
            open=float(kline['o']),
            high=float(kline['h']),
            low=float(kline['l']),
            close=float(kline['c']),
            volume=float(kline['v']),
            buy_volume=float(kline['V']),  # Taker buy volume
            sell_volume=float(kline['v']) - float(kline['V'])  # Estimated sell
        )
        
        is_closed = kline['x']  # Bar is closed
        
        self.current_bar = bar
        
        if is_closed:
            self.bars.append(bar)
            
            # Notify callbacks
            for callback in self.callbacks:
                try:
                    await callback(bar)
                except Exception as e:
                    print(f"Callback error: {e}")
    
    def get_bars(self, count: int = 50) -> List[Bar]:
        """Returnează ultimele N bare ca obiecte Bar"""
        bars_list = list(self.bars)[-count:]
        return [b.to_bar() for b in bars_list]


class LiveTradingRunner:
    """
    Runner principal pentru trading live
    
    Integrează:
    - Date live de la Binance
    - Engine-uri OIE
    - Paper trading pe Testnet
    - Broadcast la frontend
    """
    
    def __init__(self, symbol: str = "BTCUSDT", interval: str = "1m"):
        self.symbol = symbol
        self.interval = interval
        
        # Components
        self.data_feed: Optional[BinanceLiveDataFeed] = None
        self.trading_manager: Optional[PaperTradingManager] = None
        
        # State
        self.running = False
        self.last_signal: Optional[Dict] = None
        self.signal_history: List[Dict] = []
        
        # WebSocket clients for frontend
        self.ws_clients: List = []
        
        # Stats
        self.bars_processed = 0
        self.signals_generated = 0
        self.trades_executed = 0
    
    async def start(self):
        """Porneste live trading"""
        print("\n" + "=" * 60)
        print("[LIVE] LIVE TRADING MODE - OIE MVP")
        print("=" * 60)
        print(f"   Symbol: {self.symbol}")
        print(f"   Interval: {self.interval}")
        print(f"   Mode: Paper Trading (Binance Testnet)")
        print("=" * 60)
        
        # Initialize trading manager - uses defaults from TradingConfig
        config = TradingConfig(
            symbol=self.symbol,
            leverage=1,
            max_position_value=1000.0,  # Max USD per trade
            # SL/TP/confidence uses defaults from TradingConfig:
            # stop_loss_pct=1.0, take_profit_pct=1.0, min_confidence=0.60
        )
        
        self.trading_manager = PaperTradingManager(config)
        if not await self.trading_manager.start():
            print("[ERROR] Failed to start trading manager")
            return False
        
        # Initialize data feed
        self.data_feed = BinanceLiveDataFeed(
            symbol=self.symbol.lower().replace('usdt', '') + 'usdt',
            interval=self.interval
        )
        self.data_feed.on_bar(self._on_new_bar)
        
        self.running = True

        # Start data feed in background with error handling
        async def run_data_feed():
            try:
                await self.data_feed.start()
            except Exception as e:
                print(f"[ERROR] Data feed crashed: {e}")
                import traceback
                traceback.print_exc()

        asyncio.create_task(run_data_feed())

        print("\n[OK] Live trading started!")
        print("   Waiting for signals...\n")
        
        return True
    
    async def stop(self):
        """Opreste live trading"""
        print("\n[STOP] Stopping live trading...")
        
        self.running = False
        
        if self.data_feed:
            await self.data_feed.stop()
        
        if self.trading_manager:
            await self.trading_manager.stop()
        
        print("[OK] Live trading stopped")
        self._print_summary()
    
    async def _on_new_bar(self, bar: LiveBar):
        """Handler pentru bara nouă"""
        self.bars_processed += 1
        
        # Get window of bars
        bars = self.data_feed.get_bars(50)
        
        if len(bars) < 5:
            print(f"[WAIT] Collecting bars... ({len(bars)}/5)")
            return
        
        # Run OIE engines
        try:
            topology_snapshot = topology_engine.compute(symbol=self.symbol, bars=bars)
            predictive_snapshot = predictive_engine.compute(symbol=self.symbol, bars=bars)
            signals = signals_engine.compute(
                symbol=self.symbol,
                topology=topology_snapshot,
                predictive=predictive_snapshot,
                bars=bars  # Pentru delta trend calculation
            )
            
            # Log current state
            current_time = datetime.now().strftime("%H:%M:%S")
            price = bar.close
            delta = bar.delta
            ifi = predictive_snapshot.IFI
            bp_up = predictive_snapshot.breakout_probability_up
            bp_down = predictive_snapshot.breakout_probability_down

            # Log signal status every bar
            for signal in signals:
                sig_type = signal.type
                conf = signal.confidence
                desc = getattr(signal, 'description', '')
                if 'watch' in sig_type or 'neutral' in sig_type:
                    # Log neutral signals periodically
                    if self.bars_processed % 5 == 0:  # Every 5 bars
                        print(f"[{current_time}] {self.symbol} | ${price:,.2f} | bp_up={bp_up:.0%} bp_down={bp_down:.0%} | {desc[:50]}")
                break  # Only log first signal

            # Check for actionable signals
            for signal in signals:
                sig_type = signal.type
                confidence = signal.confidence
                
                # Skip neutral signals
                if 'watch' in sig_type or 'neutral' in sig_type:
                    continue
                
                self.signals_generated += 1
                self.last_signal = {
                    'type': sig_type,
                    'confidence': confidence,
                    'timestamp': datetime.now().isoformat(),
                    'price': price,
                    'ifi': ifi,
                    'delta': delta
                }
                self.signal_history.append(self.last_signal)
                
                # Print signal
                is_long = 'long' in sig_type.lower()
                marker = "[LONG]" if is_long else "[SHORT]"
                direction = "LONG" if is_long else "SHORT"

                print(f"\n{marker} [{current_time}] SIGNAL: {direction}")
                print(f"   Confidence: {confidence:.2%}")
                print(f"   Price: ${price:,.2f}")
                print(f"   Delta: {delta:+.1f}")
                print(f"   IFI: {ifi:.2f}")
                
                # Execute trade
                result = await self.trading_manager.process_signal({
                    'type': sig_type,
                    'confidence': confidence
                })
                
                if result and result.success:
                    self.trades_executed += 1
                    print(f"   [OK] Trade executed @ ${result.price:,.2f}")
                
                # Broadcast to frontend
                await self._broadcast({
                    'type': 'signal',
                    'signal': self.last_signal,
                    'position': self.trading_manager.current_trade.to_dict() if self.trading_manager.current_trade else None
                })
            
            # Periodic status (every 10 bars)
            if self.bars_processed % 10 == 0:
                status = "[INFO]" if not self.trading_manager.current_trade else "[POS]"
                pos_info = ""
                if self.trading_manager.current_trade:
                    pos = self.trading_manager.current_trade
                    pos_info = f" | Position: {pos.direction} @ ${pos.entry_price:,.2f}"
                
                print(f"{status} [{current_time}] ${price:,.2f} | D {delta:+.1f} | IFI {ifi:.2f}{pos_info}")
            
            # Check position status (SL/TP)
            await self.trading_manager.check_position_status()
            
            # Broadcast update to frontend
            await self._broadcast({
                'type': 'update',
                'symbol': self.symbol,
                'interval': self.interval,
                'bar': bar.to_dict(),
                'bars_processed': self.bars_processed,
                'topology': topology_snapshot.model_dump(mode='json'),
                'predictive': predictive_snapshot.model_dump(mode='json'),
                'signals': [s.model_dump(mode='json') for s in signals],
                'stats': self.trading_manager.get_stats(),
                'balance': self.trading_manager.connector.balance if self.trading_manager.connector else 0
            })
            
        except Exception as e:
            print(f"[ERROR] Error processing bar: {e}")
            import traceback
            traceback.print_exc()
    
    async def _broadcast(self, message: Dict):
        """Broadcast mesaj la toate clientele WebSocket"""
        for ws in self.ws_clients:
            try:
                await ws.send_json(message)
            except:
                self.ws_clients.remove(ws)
    
    def add_ws_client(self, ws):
        """Adaugă client WebSocket"""
        self.ws_clients.append(ws)
    
    def remove_ws_client(self, ws):
        """Elimină client WebSocket"""
        if ws in self.ws_clients:
            self.ws_clients.remove(ws)
    
    def get_status(self) -> Dict[str, Any]:
        """Returnează status curent"""
        return {
            'running': self.running,
            'symbol': self.symbol,
            'interval': self.interval,
            'bars_processed': self.bars_processed,
            'signals_generated': self.signals_generated,
            'trades_executed': self.trades_executed,
            'last_signal': self.last_signal,
            'trading_stats': self.trading_manager.get_stats() if self.trading_manager else None,
            'current_bar': self.data_feed.current_bar.to_dict() if self.data_feed and self.data_feed.current_bar else None
        }
    
    def _print_summary(self):
        """Printeaza sumar la final"""
        print("\n" + "=" * 60)
        print("[SUMMARY] LIVE TRADING SUMMARY")
        print("=" * 60)
        print(f"   Bars processed: {self.bars_processed}")
        print(f"   Signals generated: {self.signals_generated}")
        print(f"   Trades executed: {self.trades_executed}")
        
        if self.trading_manager:
            stats = self.trading_manager.get_stats()
            print(f"\n   Total P&L: ${stats['total_pnl']:,.2f}")
            print(f"   Win Rate: {stats['win_rate']}%")
        print("=" * 60)


# Singleton
_runner: Optional[LiveTradingRunner] = None


def get_live_runner() -> LiveTradingRunner:
    """Returnează instanța singleton"""
    global _runner
    if _runner is None:
        _runner = LiveTradingRunner()
    return _runner


async def run_live_trading(duration_minutes: int = 60):
    """Rulează live trading pentru o perioadă specificată"""
    runner = LiveTradingRunner(
        symbol="BTCUSDT",
        interval="1m"
    )
    
    if not await runner.start():
        return
    
    print(f"\n[TIME] Running for {duration_minutes} minutes...")
    print("   Press Ctrl+C to stop\n")
    
    try:
        await asyncio.sleep(duration_minutes * 60)
    except KeyboardInterrupt:
        print("\n\n[WARN] Interrupted by user")
    finally:
        await runner.stop()


if __name__ == '__main__':
    # Run for 60 minutes by default
    asyncio.run(run_live_trading(60))
