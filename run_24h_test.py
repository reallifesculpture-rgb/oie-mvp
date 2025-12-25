"""
OIE MVP - 24H Test Runner
=========================

Rulează trading pe 5m și 15m pentru 24 ore.
"""

import asyncio
import sys
from datetime import datetime

# Add parent to path
sys.path.insert(0, '.')

from backend.trading.live_runner import LiveTradingRunner


async def run_24h_test():
    """Rulează test 24h pe 5m și 15m"""
    print("\n" + "=" * 60)
    print("🔴 OIE MVP - 24H LIVE TRADING TEST")
    print("=" * 60)
    print(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Timeframes: 5m, 15m")
    print(f"   Symbol: BTCUSDT")
    print(f"   Duration: 24 hours")
    print("=" * 60 + "\n")
    
    # Create runners
    runner_5m = LiveTradingRunner(symbol="BTCUSDT", interval="5m")
    runner_15m = LiveTradingRunner(symbol="BTCUSDT", interval="15m")
    
    # Start 5m
    print("📊 Starting 5m timeframe...")
    if not await runner_5m.start():
        print("❌ Failed to start 5m runner")
        return
    
    await asyncio.sleep(5)
    
    # Start 15m
    print("\n📊 Starting 15m timeframe...")
    if not await runner_15m.start():
        print("❌ Failed to start 15m runner")
        await runner_5m.stop()
        return
    
    print("\n" + "=" * 60)
    print("✅ BOTH TIMEFRAMES RUNNING!")
    print("=" * 60)
    print("   5m:  ✅ Active")
    print("   15m: ✅ Active")
    print("\n⏰ Running for 24 hours...")
    print("   Press Ctrl+C to stop early\n")
    
    try:
        # Run for 24 hours
        await asyncio.sleep(24 * 60 * 60)
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
    finally:
        print("\n" + "=" * 60)
        print("⏹️ STOPPING ALL TRADING")
        print("=" * 60)
        
        await runner_5m.stop()
        await runner_15m.stop()
        
        # Print final stats
        print("\n" + "=" * 60)
        print("📊 FINAL RESULTS")
        print("=" * 60)
        
        stats_5m = runner_5m.get_status()
        stats_15m = runner_15m.get_status()
        
        print("\n5m Timeframe:")
        print(f"   Bars processed: {stats_5m.get('bars_processed', 0)}")
        print(f"   Signals: {stats_5m.get('signals_generated', 0)}")
        print(f"   Trades: {stats_5m.get('trades_executed', 0)}")
        
        print("\n15m Timeframe:")
        print(f"   Bars processed: {stats_15m.get('bars_processed', 0)}")
        print(f"   Signals: {stats_15m.get('signals_generated', 0)}")
        print(f"   Trades: {stats_15m.get('trades_executed', 0)}")
        
        print("\n" + "=" * 60)
        print(f"   Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_24h_test())
