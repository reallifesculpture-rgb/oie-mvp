"""
OIE MVP - Indices Backtest Runner
==================================

Motor de backtesting adaptat pentru indici bursieri.

Diferențe față de versiunea crypto:
- Folosește motoare adaptate pentru volatilitate scăzută
- Include indicatori tehnici (RSI, MA, ATR)
- Opțional: ATR-based stops
- Filtrare pe trend

Utilizare:
    python -m backend.backtest.indices_backtest --data data/historical/yahoo_SPY_15m.csv
"""

import os
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.data.models import Bar
from backend.predictive.engine import PredictiveEngine
from backend.backtest.data_fetcher import DataManager, OHLCVBar
from backend.backtest.indices_engines import (
    IndicesTopologyEngine,
    IndicesSignalsEngine,
    IndicesSignal,
    IndicesBacktestConfig,
    calculate_atr,
    calculate_rsi,
    detect_trend
)


class TradeDirection(Enum):
    LONG = "long"
    SHORT = "short"


@dataclass
class IndicesTrade:
    """Trade pentru indici cu metrici extinse"""
    entry_time: datetime
    entry_price: float
    direction: TradeDirection
    signal_type: str
    signal_confidence: float
    
    # Indicatori la intrare
    entry_rsi: float = 0.0
    entry_trend: str = "sideways"
    entry_atr: float = 0.0
    
    # Exit
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    
    # P&L
    pnl: float = 0.0
    pnl_percent: float = 0.0
    bars_held: int = 0
    max_favorable: float = 0.0
    max_adverse: float = 0.0
    
    # Stop levels
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0
    
    def close(self, exit_time: datetime, exit_price: float, reason: str):
        self.exit_time = exit_time
        self.exit_price = exit_price
        self.exit_reason = reason
        
        if self.direction == TradeDirection.LONG:
            self.pnl = exit_price - self.entry_price
        else:
            self.pnl = self.entry_price - exit_price
        
        self.pnl_percent = (self.pnl / self.entry_price) * 100
    
    def update(self, current_price: float):
        self.bars_held += 1
        
        if self.direction == TradeDirection.LONG:
            unrealized = current_price - self.entry_price
        else:
            unrealized = self.entry_price - current_price
        
        self.max_favorable = max(self.max_favorable, unrealized)
        self.max_adverse = min(self.max_adverse, unrealized)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'entry_time': self.entry_time.isoformat(),
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'direction': self.direction.value,
            'signal_type': self.signal_type,
            'signal_confidence': self.signal_confidence,
            'entry_rsi': self.entry_rsi,
            'entry_trend': self.entry_trend,
            'entry_atr': self.entry_atr,
            'pnl': self.pnl,
            'pnl_percent': self.pnl_percent,
            'bars_held': self.bars_held,
            'exit_reason': self.exit_reason,
            'max_favorable': self.max_favorable,
            'max_adverse': self.max_adverse
        }


@dataclass
class IndicesBacktestResults:
    """Rezultatele backtestului pentru indici"""
    config: IndicesBacktestConfig
    trades: List[IndicesTrade] = field(default_factory=list)
    
    # Metrici
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    total_pnl: float = 0.0
    total_pnl_percent: float = 0.0
    
    max_drawdown: float = 0.0
    max_drawdown_percent: float = 0.0
    
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    
    avg_bars_held: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    
    # Per signal type și trend
    signal_performance: Dict[str, Dict] = field(default_factory=dict)
    trend_performance: Dict[str, Dict] = field(default_factory=dict)
    
    def calculate_metrics(self):
        if not self.trades:
            return
        
        closed_trades = [t for t in self.trades if t.exit_time is not None]
        
        if not closed_trades:
            return
        
        self.total_trades = len(closed_trades)
        self.winning_trades = len([t for t in closed_trades if t.pnl > 0])
        self.losing_trades = len([t for t in closed_trades if t.pnl <= 0])
        
        self.total_pnl = sum(t.pnl for t in closed_trades)
        self.total_pnl_percent = sum(t.pnl_percent for t in closed_trades)
        
        self.win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0
        
        wins = [t.pnl for t in closed_trades if t.pnl > 0]
        losses = [t.pnl for t in closed_trades if t.pnl <= 0]
        
        self.avg_win = sum(wins) / len(wins) if wins else 0
        self.avg_loss = abs(sum(losses) / len(losses)) if losses else 0
        
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 1
        self.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        self.expectancy = (self.win_rate * self.avg_win) - ((1 - self.win_rate) * self.avg_loss)
        
        self.avg_bars_held = sum(t.bars_held for t in closed_trades) / len(closed_trades)
        
        # Drawdown
        equity_curve = []
        running_equity = self.config.initial_capital
        peak = running_equity
        max_dd = 0
        
        for trade in closed_trades:
            running_equity += trade.pnl * (self.config.position_size_pct / 100)
            equity_curve.append(running_equity)
            peak = max(peak, running_equity)
            drawdown = peak - running_equity
            max_dd = max(max_dd, drawdown)
        
        self.max_drawdown = max_dd
        self.max_drawdown_percent = (max_dd / self.config.initial_capital) * 100
        
        # Sharpe/Sortino
        returns = [t.pnl_percent for t in closed_trades]
        if len(returns) > 1:
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
            std_dev = math.sqrt(variance) if variance > 0 else 1
            self.sharpe_ratio = (mean_return / std_dev) * math.sqrt(252) if std_dev > 0 else 0
        
        negative_returns = [r for r in returns if r < 0]
        if negative_returns:
            downside_variance = sum(r ** 2 for r in negative_returns) / len(negative_returns)
            downside_dev = math.sqrt(downside_variance)
            mean_return = sum(returns) / len(returns)
            self.sortino_ratio = (mean_return / downside_dev) * math.sqrt(252) if downside_dev > 0 else 0
        
        # Consecutive
        current_wins = 0
        current_losses = 0
        
        for trade in closed_trades:
            if trade.pnl > 0:
                current_wins += 1
                current_losses = 0
                self.max_consecutive_wins = max(self.max_consecutive_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                self.max_consecutive_losses = max(self.max_consecutive_losses, current_losses)
        
        # Per signal type
        signal_trades = {}
        for trade in closed_trades:
            st = trade.signal_type
            if st not in signal_trades:
                signal_trades[st] = []
            signal_trades[st].append(trade)
        
        for signal_type, trades in signal_trades.items():
            wins = [t for t in trades if t.pnl > 0]
            self.signal_performance[signal_type] = {
                'total': len(trades),
                'wins': len(wins),
                'win_rate': len(wins) / len(trades) if trades else 0,
                'total_pnl': sum(t.pnl for t in trades),
                'avg_pnl': sum(t.pnl for t in trades) / len(trades) if trades else 0
            }
        
        # Per trend
        trend_trades = {}
        for trade in closed_trades:
            tr = trade.entry_trend
            if tr not in trend_trades:
                trend_trades[tr] = []
            trend_trades[tr].append(trade)
        
        for trend, trades in trend_trades.items():
            wins = [t for t in trades if t.pnl > 0]
            self.trend_performance[trend] = {
                'total': len(trades),
                'wins': len(wins),
                'win_rate': len(wins) / len(trades) if trades else 0,
                'total_pnl': sum(t.pnl for t in trades),
                'avg_pnl': sum(t.pnl for t in trades) / len(trades) if trades else 0
            }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': round(self.win_rate * 100, 2),
            'total_pnl': round(self.total_pnl, 2),
            'total_pnl_percent': round(self.total_pnl_percent, 2),
            'max_drawdown': round(self.max_drawdown, 2),
            'max_drawdown_percent': round(self.max_drawdown_percent, 2),
            'avg_win': round(self.avg_win, 2),
            'avg_loss': round(self.avg_loss, 2),
            'profit_factor': round(self.profit_factor, 2),
            'expectancy': round(self.expectancy, 4),
            'sharpe_ratio': round(self.sharpe_ratio, 2),
            'sortino_ratio': round(self.sortino_ratio, 2),
            'avg_bars_held': round(self.avg_bars_held, 1),
            'max_consecutive_wins': self.max_consecutive_wins,
            'max_consecutive_losses': self.max_consecutive_losses,
            'signal_performance': self.signal_performance,
            'trend_performance': self.trend_performance
        }
    
    def print_report(self):
        print("\n" + "=" * 70)
        print("📊 RAPORT BACKTEST OIE MVP - INDICI")
        print("=" * 70)
        
        print(f"\n📈 SUMAR GENERAL")
        print(f"   Total Tranzacții: {self.total_trades}")
        print(f"   Câștigătoare: {self.winning_trades} | Pierzătoare: {self.losing_trades}")
        print(f"   Win Rate: {self.win_rate * 100:.1f}%")
        
        print(f"\n💰 PROFIT & LOSS")
        print(f"   Total P&L: ${self.total_pnl:,.2f} ({self.total_pnl_percent:+.2f}%)")
        print(f"   Câștig Mediu: ${self.avg_win:.2f}")
        print(f"   Pierdere Medie: ${self.avg_loss:.2f}")
        print(f"   Profit Factor: {self.profit_factor:.2f}")
        print(f"   Expectancy: ${self.expectancy:.4f}")
        
        print(f"\n📉 RISC")
        print(f"   Max Drawdown: ${self.max_drawdown:.2f} ({self.max_drawdown_percent:.2f}%)")
        print(f"   Sharpe Ratio: {self.sharpe_ratio:.2f}")
        print(f"   Sortino Ratio: {self.sortino_ratio:.2f}")
        
        print(f"\n⏱️ TIMING")
        print(f"   Bare Medii Ținute: {self.avg_bars_held:.1f}")
        print(f"   Max Câștiguri Consecutive: {self.max_consecutive_wins}")
        print(f"   Max Pierderi Consecutive: {self.max_consecutive_losses}")
        
        if self.signal_performance:
            print(f"\n📊 PERFORMANȚĂ PER TIP SEMNAL")
            for signal_type, perf in self.signal_performance.items():
                print(f"   {signal_type}:")
                print(f"      Trades: {perf['total']} | Win Rate: {perf['win_rate']*100:.1f}% | P&L: ${perf['total_pnl']:.2f}")
        
        if self.trend_performance:
            print(f"\n📈 PERFORMANȚĂ PER TREND")
            for trend, perf in self.trend_performance.items():
                print(f"   {trend}:")
                print(f"      Trades: {perf['total']} | Win Rate: {perf['win_rate']*100:.1f}% | P&L: ${perf['total_pnl']:.2f}")
        
        print("\n" + "=" * 70)


class IndicesBacktestRunner:
    """Motor de backtesting pentru indici"""
    
    def __init__(self, config: IndicesBacktestConfig = None):
        self.config = config or IndicesBacktestConfig()
        
        # Motoare adaptate pentru indici
        self.topology_engine = IndicesTopologyEngine(window_size=self.config.topology_window)
        self.predictive_engine = PredictiveEngine(window_size=self.config.predictive_window)
        self.signals_engine = IndicesSignalsEngine(
            breakout_threshold=0.45,
            rsi_overbought=self.config.rsi_overbought,
            rsi_oversold=self.config.rsi_oversold,
            require_trend_confirmation=self.config.require_trend_confirmation
        )
        
        self.current_trade: Optional[IndicesTrade] = None
        self.results: IndicesBacktestResults = None
    
    def convert_to_bars(self, ohlcv_bars: List[OHLCVBar]) -> List[Bar]:
        bars = []
        for ob in ohlcv_bars:
            bar = Bar(
                timestamp=ob.timestamp,
                open=ob.open,
                high=ob.high,
                low=ob.low,
                close=ob.close,
                volume=ob.volume,
                buy_volume=ob.buy_volume,
                sell_volume=ob.sell_volume,
                delta=ob.delta
            )
            bars.append(bar)
        return bars
    
    def run(self, ohlcv_bars: List[OHLCVBar], symbol: str = "INDEX") -> IndicesBacktestResults:
        bars = self.convert_to_bars(ohlcv_bars)
        
        print(f"\n🚀 Rulare backtest INDICI pe {len(bars)} bare...")
        print(f"   Perioadă: {bars[0].timestamp} → {bars[-1].timestamp}")
        print(f"   Config: SL={self.config.stop_loss_pct}%, TP={self.config.take_profit_pct}%")
        
        self.results = IndicesBacktestResults(config=self.config)
        self.current_trade = None
        
        min_window = max(self.config.topology_window, self.config.predictive_window)
        
        for i in range(min_window, len(bars)):
            window = bars[max(0, i - min_window):i + 1]
            current_bar = bars[i]
            
            # Calculează snapshot-uri
            topology = self.topology_engine.compute(symbol, window)
            predictive = self.predictive_engine.compute(symbol, window)
            signals = self.signals_engine.compute(symbol, window, topology, predictive)
            
            # Calculează indicatori pentru trade
            closes = [b.close for b in window]
            current_rsi = calculate_rsi(closes, 14)
            current_trend = detect_trend(closes, 10, 30)
            current_atr = calculate_atr(window, 14)
            
            # Gestionează trade curent
            if self.current_trade:
                self._manage_open_trade(current_bar, current_atr)
            
            # Evaluează semnale noi
            if not self.current_trade:
                self._evaluate_signals(signals, current_bar, current_rsi, current_trend.value, current_atr)
            
            if i % 200 == 0:
                print(f"   Procesat {i}/{len(bars)} bare...")
        
        # Închide trade la final
        if self.current_trade:
            self.current_trade.close(bars[-1].timestamp, bars[-1].close, "backtest_end")
            self.results.trades.append(self.current_trade)
        
        self.results.calculate_metrics()
        
        return self.results
    
    def _evaluate_signals(self, signals: List[IndicesSignal], current_bar: Bar, 
                          rsi: float, trend: str, atr: float):
        for signal in signals:
            if signal.type == "indices_neutral_watch":
                continue
            
            if signal.confidence < self.config.min_confidence:
                continue
            
            # Determină direcția
            if signal.type == "indices_breakout_long":
                direction = TradeDirection.LONG
            elif signal.type == "indices_breakout_short":
                direction = TradeDirection.SHORT
            else:
                continue
            
            # Calculează stop levels
            if self.config.use_atr_stops and atr > 0:
                stop_dist = atr * self.config.atr_stop_mult
                tp_dist = atr * self.config.atr_tp_mult
            else:
                stop_dist = current_bar.close * (self.config.stop_loss_pct / 100)
                tp_dist = current_bar.close * (self.config.take_profit_pct / 100)
            
            if direction == TradeDirection.LONG:
                sl_price = current_bar.close - stop_dist
                tp_price = current_bar.close + tp_dist
            else:
                sl_price = current_bar.close + stop_dist
                tp_price = current_bar.close - tp_dist
            
            self.current_trade = IndicesTrade(
                entry_time=current_bar.timestamp,
                entry_price=current_bar.close,
                direction=direction,
                signal_type=signal.type,
                signal_confidence=signal.confidence,
                entry_rsi=rsi,
                entry_trend=trend,
                entry_atr=atr,
                stop_loss_price=sl_price,
                take_profit_price=tp_price
            )
            break
    
    def _manage_open_trade(self, current_bar: Bar, current_atr: float):
        trade = self.current_trade
        trade.update(current_bar.close)
        
        # Check folosind prețuri stop
        if trade.direction == TradeDirection.LONG:
            if current_bar.low <= trade.stop_loss_price:
                trade.close(current_bar.timestamp, trade.stop_loss_price, "stop_loss")
                self.results.trades.append(trade)
                self.current_trade = None
                return
            
            if current_bar.high >= trade.take_profit_price:
                trade.close(current_bar.timestamp, trade.take_profit_price, "take_profit")
                self.results.trades.append(trade)
                self.current_trade = None
                return
        else:  # SHORT
            if current_bar.high >= trade.stop_loss_price:
                trade.close(current_bar.timestamp, trade.stop_loss_price, "stop_loss")
                self.results.trades.append(trade)
                self.current_trade = None
                return
            
            if current_bar.low <= trade.take_profit_price:
                trade.close(current_bar.timestamp, trade.take_profit_price, "take_profit")
                self.results.trades.append(trade)
                self.current_trade = None
                return
        
        # Max hold
        if trade.bars_held >= self.config.max_hold_bars:
            trade.close(current_bar.timestamp, current_bar.close, "max_hold")
            self.results.trades.append(trade)
            self.current_trade = None
            return
    
    def save_results(self, path: str):
        if not self.results:
            return
        
        output = {
            'summary': self.results.to_dict(),
            'trades': [t.to_dict() for t in self.results.trades],
            'config': {
                'topology_window': self.config.topology_window,
                'predictive_window': self.config.predictive_window,
                'min_confidence': self.config.min_confidence,
                'stop_loss_pct': self.config.stop_loss_pct,
                'take_profit_pct': self.config.take_profit_pct,
                'use_atr_stops': self.config.use_atr_stops,
                'atr_stop_mult': self.config.atr_stop_mult,
                'atr_tp_mult': self.config.atr_tp_mult,
                'initial_capital': self.config.initial_capital
            }
        }
        
        with open(path, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"\n💾 Rezultate salvate în: {path}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Rulează backtest adaptat pentru indici"
    )
    parser.add_argument('--data', required=True,
                        help='Calea către fișierul CSV')
    parser.add_argument('--confidence', type=float, default=0.45,
                        help='Confidence minim (default: 0.45)')
    parser.add_argument('--stop-loss', type=float, default=0.3,
                        help='Stop loss % (default: 0.3)')
    parser.add_argument('--take-profit', type=float, default=0.6,
                        help='Take profit % (default: 0.6)')
    parser.add_argument('--max-hold', type=int, default=20,
                        help='Max bare (default: 20)')
    parser.add_argument('--use-atr', action='store_true',
                        help='Folosește ATR pentru stops')
    parser.add_argument('--atr-stop', type=float, default=1.5,
                        help='ATR multiplier pentru SL (default: 1.5)')
    parser.add_argument('--atr-tp', type=float, default=2.5,
                        help='ATR multiplier pentru TP (default: 2.5)')
    parser.add_argument('--output',
                        help='Calea pentru salvare rezultate')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("OIE MVP - Indices Backtest Runner")
    print("=" * 60)
    
    manager = DataManager()
    bars = manager.load_from_csv(Path(args.data))
    print(f"\n📂 Încărcat {len(bars)} bare din {args.data}")
    
    config = IndicesBacktestConfig(
        min_confidence=args.confidence,
        stop_loss_pct=args.stop_loss,
        take_profit_pct=args.take_profit,
        max_hold_bars=args.max_hold,
        use_atr_stops=args.use_atr,
        atr_stop_mult=args.atr_stop,
        atr_tp_mult=args.atr_tp
    )
    
    runner = IndicesBacktestRunner(config)
    results = runner.run(bars)
    
    results.print_report()
    
    if args.output:
        runner.save_results(args.output)


if __name__ == '__main__':
    main()
