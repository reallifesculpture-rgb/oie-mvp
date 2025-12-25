"""
OIE MVP - Indices Trend-Following Strategy
============================================

Strategie simplificată pentru indici care:
1. Tranzacționează DOAR în direcția trend-ului
2. Folosește ATR pentru dimensionare stops
3. Evită sideways markets

Aceasta ar trebui să funcționeze mai bine pe indici.
"""

import os
import sys
from datetime import datetime
from typing import List, Optional
from pathlib import Path
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.data.models import Bar
from backend.backtest.data_fetcher import DataManager, OHLCVBar
from backend.backtest.indices_engines import (
    calculate_atr,
    calculate_rsi,
    calculate_sma,
    calculate_ema,
    detect_trend,
    TrendDirection
)


def run_trend_following_backtest(
    bars: List[Bar],
    # Parametri strategie
    trend_short_ma: int = 10,
    trend_long_ma: int = 30,
    rsi_period: int = 14,
    atr_period: int = 14,
    
    # Entry conditions
    min_trend_strength: float = 0.15,  # % diferență între MAs
    rsi_oversold: float = 35,
    rsi_overbought: float = 65,
    
    # Exit conditions
    atr_stop_mult: float = 2.0,
    atr_trail_mult: float = 1.5,  # Trailing stop
    max_hold_bars: int = 40,
    
    # Risk management
    initial_capital: float = 10000.0,
) -> dict:
    """
    Strategie trend-following simplificată.
    
    REGULI:
    1. Intrăm LONG doar când:
       - Trend UP (short MA > long MA cu > min_trend_strength%)
       - RSI < rsi_overbought (nu e overbought)
       - Preț face pullback spre short MA
    
    2. Intrăm SHORT doar când:
       - Trend DOWN (short MA < long MA cu > min_trend_strength%)
       - RSI > rsi_oversold (nu e oversold)
       - Preț face rally spre short MA
    
    3. Exit:
       - ATR-based stop loss
       - Trailing stop după ce suntem în profit
       - Max hold time
    """
    
    # Rezultate
    trades = []
    current_position = None  # {'direction': 'long'/'short', 'entry_price', 'entry_time', 'stop_loss', 'highest'/'lowest'}
    
    min_lookback = max(trend_long_ma, rsi_period, atr_period) + 5
    
    print(f"\n🚀 Trend-Following Strategy Backtest")
    print(f"   Perioadă: {bars[0].timestamp} → {bars[-1].timestamp}")
    print(f"   Total bare: {len(bars)}")
    print(f"   Trend MAs: {trend_short_ma}/{trend_long_ma}")
    print(f"   ATR Stop: {atr_stop_mult}x, Trail: {atr_trail_mult}x")
    
    for i in range(min_lookback, len(bars)):
        window = bars[max(0, i - 100):i + 1]
        current_bar = bars[i]
        
        closes = [b.close for b in window]
        
        # Calculează indicatori
        short_ma = calculate_sma(closes, trend_short_ma)
        long_ma = calculate_sma(closes, trend_long_ma)
        rsi = calculate_rsi(closes, rsi_period)
        atr = calculate_atr(window, atr_period)
        
        # Determină trend
        if long_ma > 0:
            trend_strength = ((short_ma - long_ma) / long_ma) * 100
        else:
            trend_strength = 0
        
        if trend_strength > min_trend_strength:
            trend = 'up'
        elif trend_strength < -min_trend_strength:
            trend = 'down'
        else:
            trend = 'sideways'
        
        # ===== GESTIONARE POZIȚIE DESCHISĂ =====
        if current_position:
            pos = current_position
            
            if pos['direction'] == 'long':
                # Update highest pentru trailing
                pos['highest'] = max(pos['highest'], current_bar.high)
                
                # Calculează trailing stop
                trail_stop = pos['highest'] - atr * atr_trail_mult
                effective_stop = max(pos['stop_loss'], trail_stop)
                
                # Check stop
                if current_bar.low <= effective_stop:
                    exit_price = effective_stop
                    pnl = exit_price - pos['entry_price']
                    pnl_pct = (pnl / pos['entry_price']) * 100
                    
                    trades.append({
                        'entry_time': pos['entry_time'],
                        'exit_time': current_bar.timestamp,
                        'direction': 'long',
                        'entry_price': pos['entry_price'],
                        'exit_price': exit_price,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'bars_held': pos['bars_held'],
                        'exit_reason': 'trailing_stop' if trail_stop > pos['stop_loss'] else 'stop_loss',
                        'trend_at_entry': pos['trend']
                    })
                    current_position = None
                    continue
                
                # Check max hold
                pos['bars_held'] += 1
                if pos['bars_held'] >= max_hold_bars:
                    pnl = current_bar.close - pos['entry_price']
                    pnl_pct = (pnl / pos['entry_price']) * 100
                    
                    trades.append({
                        'entry_time': pos['entry_time'],
                        'exit_time': current_bar.timestamp,
                        'direction': 'long',
                        'entry_price': pos['entry_price'],
                        'exit_price': current_bar.close,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'bars_held': pos['bars_held'],
                        'exit_reason': 'max_hold',
                        'trend_at_entry': pos['trend']
                    })
                    current_position = None
                    continue
                
                # Check trend change (exit if trend reverses)
                if trend == 'down':
                    pnl = current_bar.close - pos['entry_price']
                    pnl_pct = (pnl / pos['entry_price']) * 100
                    
                    trades.append({
                        'entry_time': pos['entry_time'],
                        'exit_time': current_bar.timestamp,
                        'direction': 'long',
                        'entry_price': pos['entry_price'],
                        'exit_price': current_bar.close,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'bars_held': pos['bars_held'],
                        'exit_reason': 'trend_reversal',
                        'trend_at_entry': pos['trend']
                    })
                    current_position = None
                    continue
            
            else:  # SHORT
                pos['lowest'] = min(pos['lowest'], current_bar.low)
                
                trail_stop = pos['lowest'] + atr * atr_trail_mult
                effective_stop = min(pos['stop_loss'], trail_stop)
                
                if current_bar.high >= effective_stop:
                    exit_price = effective_stop
                    pnl = pos['entry_price'] - exit_price
                    pnl_pct = (pnl / pos['entry_price']) * 100
                    
                    trades.append({
                        'entry_time': pos['entry_time'],
                        'exit_time': current_bar.timestamp,
                        'direction': 'short',
                        'entry_price': pos['entry_price'],
                        'exit_price': exit_price,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'bars_held': pos['bars_held'],
                        'exit_reason': 'trailing_stop' if trail_stop < pos['stop_loss'] else 'stop_loss',
                        'trend_at_entry': pos['trend']
                    })
                    current_position = None
                    continue
                
                pos['bars_held'] += 1
                if pos['bars_held'] >= max_hold_bars:
                    pnl = pos['entry_price'] - current_bar.close
                    pnl_pct = (pnl / pos['entry_price']) * 100
                    
                    trades.append({
                        'entry_time': pos['entry_time'],
                        'exit_time': current_bar.timestamp,
                        'direction': 'short',
                        'entry_price': pos['entry_price'],
                        'exit_price': current_bar.close,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'bars_held': pos['bars_held'],
                        'exit_reason': 'max_hold',
                        'trend_at_entry': pos['trend']
                    })
                    current_position = None
                    continue
                
                if trend == 'up':
                    pnl = pos['entry_price'] - current_bar.close
                    pnl_pct = (pnl / pos['entry_price']) * 100
                    
                    trades.append({
                        'entry_time': pos['entry_time'],
                        'exit_time': current_bar.timestamp,
                        'direction': 'short',
                        'entry_price': pos['entry_price'],
                        'exit_price': current_bar.close,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'bars_held': pos['bars_held'],
                        'exit_reason': 'trend_reversal',
                        'trend_at_entry': pos['trend']
                    })
                    current_position = None
                    continue
        
        # ===== CĂUTARE INTRARE NOUĂ =====
        if current_position is None:
            # LONG: Trend UP + RSI nu overbought + pullback la MA
            if trend == 'up' and rsi < rsi_overbought:
                # Pullback: preț aproape de short MA sau a atins-o recent
                pullback_threshold = atr * 0.5
                near_ma = abs(current_bar.close - short_ma) < pullback_threshold
                
                if near_ma:
                    stop_loss = current_bar.close - atr * atr_stop_mult
                    
                    current_position = {
                        'direction': 'long',
                        'entry_price': current_bar.close,
                        'entry_time': current_bar.timestamp,
                        'stop_loss': stop_loss,
                        'highest': current_bar.high,
                        'bars_held': 0,
                        'trend': trend
                    }
            
            # SHORT: Trend DOWN + RSI nu oversold + rally la MA
            elif trend == 'down' and rsi > rsi_oversold:
                pullback_threshold = atr * 0.5
                near_ma = abs(current_bar.close - short_ma) < pullback_threshold
                
                if near_ma:
                    stop_loss = current_bar.close + atr * atr_stop_mult
                    
                    current_position = {
                        'direction': 'short',
                        'entry_price': current_bar.close,
                        'entry_time': current_bar.timestamp,
                        'stop_loss': stop_loss,
                        'lowest': current_bar.low,
                        'bars_held': 0,
                        'trend': trend
                    }
    
    # Închide poziție rămasă
    if current_position:
        pos = current_position
        last_bar = bars[-1]
        
        if pos['direction'] == 'long':
            pnl = last_bar.close - pos['entry_price']
        else:
            pnl = pos['entry_price'] - last_bar.close
        pnl_pct = (pnl / pos['entry_price']) * 100
        
        trades.append({
            'entry_time': pos['entry_time'],
            'exit_time': last_bar.timestamp,
            'direction': pos['direction'],
            'entry_price': pos['entry_price'],
            'exit_price': last_bar.close,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'bars_held': pos['bars_held'],
            'exit_reason': 'backtest_end',
            'trend_at_entry': pos['trend']
        })
    
    # ===== CALCULARE METRICI =====
    if not trades:
        print("\n❌ Niciun trade generat!")
        return {'trades': [], 'summary': {}}
    
    total_trades = len(trades)
    winning_trades = [t for t in trades if t['pnl'] > 0]
    losing_trades = [t for t in trades if t['pnl'] <= 0]
    
    win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
    total_pnl = sum(t['pnl'] for t in trades)
    total_pnl_pct = sum(t['pnl_pct'] for t in trades)
    
    avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
    avg_loss = abs(sum(t['pnl'] for t in losing_trades) / len(losing_trades)) if losing_trades else 0
    
    gross_profit = sum(t['pnl'] for t in winning_trades) if winning_trades else 0
    gross_loss = abs(sum(t['pnl'] for t in losing_trades)) if losing_trades else 1
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
    
    # Per direction
    long_trades = [t for t in trades if t['direction'] == 'long']
    short_trades = [t for t in trades if t['direction'] == 'short']
    
    summary = {
        'total_trades': total_trades,
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'win_rate': round(win_rate * 100, 2),
        'total_pnl': round(total_pnl, 2),
        'total_pnl_pct': round(total_pnl_pct, 2),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'profit_factor': round(profit_factor, 2),
        'expectancy': round(expectancy, 4),
        'long_trades': {
            'total': len(long_trades),
            'wins': len([t for t in long_trades if t['pnl'] > 0]),
            'pnl': round(sum(t['pnl'] for t in long_trades), 2)
        },
        'short_trades': {
            'total': len(short_trades),
            'wins': len([t for t in short_trades if t['pnl'] > 0]),
            'pnl': round(sum(t['pnl'] for t in short_trades), 2)
        }
    }
    
    # PRINT REPORT
    print("\n" + "=" * 70)
    print("📊 RAPORT BACKTEST - TREND FOLLOWING STRATEGY")
    print("=" * 70)
    
    print(f"\n📈 SUMAR GENERAL")
    print(f"   Total Tranzacții: {total_trades}")
    print(f"   Câștigătoare: {len(winning_trades)} | Pierzătoare: {len(losing_trades)}")
    print(f"   Win Rate: {win_rate * 100:.1f}%")
    
    print(f"\n💰 PROFIT & LOSS")
    print(f"   Total P&L: ${total_pnl:,.2f} ({total_pnl_pct:+.2f}%)")
    print(f"   Câștig Mediu: ${avg_win:.2f}")
    print(f"   Pierdere Medie: ${avg_loss:.2f}")
    print(f"   Profit Factor: {profit_factor:.2f}")
    print(f"   Expectancy: ${expectancy:.4f}")
    
    print(f"\n📊 PER DIRECȚIE")
    print(f"   LONG:  {len(long_trades)} trades | {len([t for t in long_trades if t['pnl'] > 0])} wins | P&L: ${sum(t['pnl'] for t in long_trades):.2f}")
    print(f"   SHORT: {len(short_trades)} trades | {len([t for t in short_trades if t['pnl'] > 0])} wins | P&L: ${sum(t['pnl'] for t in short_trades):.2f}")
    
    # Per exit reason
    exit_reasons = {}
    for t in trades:
        r = t['exit_reason']
        if r not in exit_reasons:
            exit_reasons[r] = {'count': 0, 'pnl': 0}
        exit_reasons[r]['count'] += 1
        exit_reasons[r]['pnl'] += t['pnl']
    
    print(f"\n🚪 EXIT REASONS")
    for reason, data in exit_reasons.items():
        print(f"   {reason}: {data['count']} trades | P&L: ${data['pnl']:.2f}")
    
    print("\n" + "=" * 70)
    
    return {'trades': trades, 'summary': summary}


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Trend-Following Strategy pentru Indici")
    parser.add_argument('--data', required=True, help='Calea CSV')
    parser.add_argument('--short-ma', type=int, default=10, help='Short MA period')
    parser.add_argument('--long-ma', type=int, default=30, help='Long MA period')
    parser.add_argument('--atr-stop', type=float, default=2.0, help='ATR stop multiplier')
    parser.add_argument('--atr-trail', type=float, default=1.5, help='ATR trail multiplier')
    parser.add_argument('--max-hold', type=int, default=40, help='Max hold bars')
    parser.add_argument('--output', help='Output JSON')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("OIE MVP - Trend Following Strategy")
    print("=" * 60)
    
    manager = DataManager()
    ohlcv_bars = manager.load_from_csv(Path(args.data))
    
    # Convert to Bar objects
    bars = []
    for ob in ohlcv_bars:
        from backend.data.models import Bar
        bar = Bar(
            timestamp=ob.timestamp,
            open=ob.open,
            high=ob.high,
            low=ob.low,
            close=ob.close,
            volume=ob.volume,
            delta=ob.delta
        )
        bars.append(bar)
    
    print(f"\n📂 Încărcat {len(bars)} bare din {args.data}")
    
    results = run_trend_following_backtest(
        bars,
        trend_short_ma=args.short_ma,
        trend_long_ma=args.long_ma,
        atr_stop_mult=args.atr_stop,
        atr_trail_mult=args.atr_trail,
        max_hold_bars=args.max_hold
    )
    
    if args.output:
        # Convert datetime to string for JSON
        for t in results['trades']:
            t['entry_time'] = t['entry_time'].isoformat()
            t['exit_time'] = t['exit_time'].isoformat()
        
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Rezultate salvate în: {args.output}")


if __name__ == '__main__':
    main()
