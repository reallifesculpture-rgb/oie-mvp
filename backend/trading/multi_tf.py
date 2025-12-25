"""
OIE MVP - Multi-Timeframe Live Trading
=======================================

Suport pentru multiple timeframe-uri (1m, 5m, 15m).
Fiecare timeframe rulează independent cu propria instanță.
"""

import asyncio
from typing import Dict, Optional
from backend.trading.live_runner import LiveTradingRunner, run_live_trading


class MultiTimeframeRunner:
    """
    Manager pentru trading pe multiple timeframe-uri simultan
    
    Usage:
        runner = MultiTimeframeRunner()
        await runner.start_timeframe("1m")
        await runner.start_timeframe("5m")
    """
    
    SUPPORTED_INTERVALS = ["1m", "3m", "5m", "15m", "30m", "1h"]
    
    def __init__(self):
        self.runners: Dict[str, LiveTradingRunner] = {}
        self.tasks: Dict[str, asyncio.Task] = {}
    
    async def start_timeframe(self, interval: str, symbol: str = "BTCUSDT") -> bool:
        """Pornește trading pe un timeframe specific"""
        if interval not in self.SUPPORTED_INTERVALS:
            print(f"❌ Unsupported interval: {interval}")
            print(f"   Supported: {', '.join(self.SUPPORTED_INTERVALS)}")
            return False
        
        if interval in self.runners and self.runners[interval].running:
            print(f"⚠️ {interval} already running")
            return False
        
        runner = LiveTradingRunner(symbol=symbol, interval=interval)
        self.runners[interval] = runner
        
        # Start in background
        if await runner.start():
            print(f"✅ Started {symbol} {interval} trading")
            return True
        
        return False
    
    async def stop_timeframe(self, interval: str):
        """Oprește trading pe un timeframe"""
        if interval in self.runners:
            await self.runners[interval].stop()
            del self.runners[interval]
            print(f"⏹️ Stopped {interval} trading")
    
    async def stop_all(self):
        """Oprește toate timeframe-urile"""
        for interval in list(self.runners.keys()):
            await self.stop_timeframe(interval)
    
    def get_status(self) -> Dict:
        """Returnează status pentru toate timeframe-urile"""
        return {
            interval: runner.get_status() 
            for interval, runner in self.runners.items()
        }


async def run_5m_trading(duration_minutes: int = 120):
    """Rulează trading pe 5 minute"""
    runner = LiveTradingRunner(
        symbol="BTCUSDT",
        interval="5m"
    )
    
    if not await runner.start():
        return
    
    print(f"\n⏰ Running 5m trading for {duration_minutes} minutes...")
    print("   Press Ctrl+C to stop\n")
    
    try:
        await asyncio.sleep(duration_minutes * 60)
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
    finally:
        await runner.stop()


async def run_multi_timeframe(duration_minutes: int = 120):
    """Rulează trading pe 1m și 5m simultan"""
    print("\n" + "=" * 60)
    print("🔴 MULTI-TIMEFRAME LIVE TRADING")
    print("=" * 60)
    
    runner_1m = LiveTradingRunner(symbol="BTCUSDT", interval="1m")
    runner_5m = LiveTradingRunner(symbol="BTCUSDT", interval="5m")
    
    # Start both
    await runner_1m.start()
    await asyncio.sleep(2)  # Small delay
    await runner_5m.start()
    
    print(f"\n⏰ Running multi-timeframe for {duration_minutes} minutes...")
    print("   Active: 1m, 5m")
    print("   Press Ctrl+C to stop\n")
    
    try:
        await asyncio.sleep(duration_minutes * 60)
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
    finally:
        await runner_1m.stop()
        await runner_5m.stop()


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        interval = sys.argv[1]
        if interval == "5m":
            asyncio.run(run_5m_trading(120))
        elif interval == "multi":
            asyncio.run(run_multi_timeframe(120))
        else:
            print(f"Usage: python -m backend.trading.multi_tf [5m|multi]")
    else:
        # Default to 5m
        asyncio.run(run_5m_trading(120))
