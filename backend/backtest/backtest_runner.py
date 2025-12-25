"""
OIE MVP - Backtest Runner
==========================

Motor de backtesting pentru strategia OIE.

Funcționalități:
- Walk-forward backtesting
- Simulare semnale pe date istorice
- Calculare metrici performanță (Sharpe, Sortino, Max Drawdown)
- Generare raport detaliat

Utilizare:
    python -m backend.backtest.backtest_runner --data data/historical/binance_BTCUSDT_1m.csv
"""

import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
import math

# Adaugă path-ul pentru importuri
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.data.models import Bar
from backend.topology.engine import TopologyEngine
from backend.predictive.engine import PredictiveEngine
from backend.signals.engine import SignalsEngine
from backend.backtest.data_fetcher import DataManager, OHLCVBar


class TradeDirection(Enum):
    LONG = "long"
    SHORT = "short"


@dataclass
class Trade:
    """Reprezentarea unei tranzacții"""
    entry_time: datetime
    entry_price: float
    direction: TradeDirection
    signal_type: str
    signal_confidence: float
    
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    
    pnl: float = 0.0
    pnl_percent: float = 0.0
    bars_held: int = 0
    max_favorable: float = 0.0  # Max profit în timpul trade-ului
    max_adverse: float = 0.0   # Max pierdere în timpul trade-ului
    
    def close(self, exit_time: datetime, exit_price: float, reason: str):
        """Închide trade-ul"""
        self.exit_time = exit_time
        self.exit_price = exit_price
        self.exit_reason = reason
        
        if self.direction == TradeDirection.LONG:
            self.pnl = exit_price - self.entry_price
        else:
            self.pnl = self.entry_price - exit_price
        
        self.pnl_percent = (self.pnl / self.entry_price) * 100
    
    def update(self, current_price: float):
        """Actualizează metrici în timpul trade-ului"""
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
            'pnl': self.pnl,
            'pnl_percent': self.pnl_percent,
            'bars_held': self.bars_held,
            'exit_reason': self.exit_reason,
            'max_favorable': self.max_favorable,
            'max_adverse': self.max_adverse
        }


@dataclass
class BacktestConfig:
    """Configurație backtest"""
    # Dimensiune fereastră pentru motoare
    topology_window: int = 100
    predictive_window: int = 200
    
    # Parametri trading
    min_confidence: float = 0.5  # Confidence minim pentru semnal
    max_hold_bars: int = 60     # Max bare de ținut poziție
    
    # Stop loss / Take profit (în procente)
    stop_loss_pct: float = 1.0   # 1% stop loss
    take_profit_pct: float = 2.0  # 2% take profit
    
    # Capital
    initial_capital: float = 10000.0
    position_size_pct: float = 100.0  # % din capital per trade
    
    # Filtre
    min_IFI: float = 0.0  # IFI minim pentru a lua semnal
    require_vortex: bool = False  # Necesită vortex pentru confirmare


@dataclass
class BacktestResults:
    """Rezultatele backtestului"""
    config: BacktestConfig
    
    # Trades
    trades: List[Trade] = field(default_factory=list)
    
    # Metrici generale
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    total_pnl: float = 0.0
    total_pnl_percent: float = 0.0
    
    max_drawdown: float = 0.0
    max_drawdown_percent: float = 0.0
    
    # Metrici avansate
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    
    # Time-based
    avg_bars_held: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    
    # Per signal type
    signal_performance: Dict[str, Dict] = field(default_factory=dict)
    
    def calculate_metrics(self):
        """Calculează toate metricile"""
        if not self.trades:
            return
        
        closed_trades = [t for t in self.trades if t.exit_time is not None]
        
        if not closed_trades:
            return
        
        self.total_trades = len(closed_trades)
        self.winning_trades = len([t for t in closed_trades if t.pnl > 0])
        self.losing_trades = len([t for t in closed_trades if t.pnl <= 0])
        
        # P&L
        self.total_pnl = sum(t.pnl for t in closed_trades)
        self.total_pnl_percent = sum(t.pnl_percent for t in closed_trades)
        
        # Win rate
        self.win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0
        
        # Average win/loss
        wins = [t.pnl for t in closed_trades if t.pnl > 0]
        losses = [t.pnl for t in closed_trades if t.pnl <= 0]
        
        self.avg_win = sum(wins) / len(wins) if wins else 0
        self.avg_loss = abs(sum(losses) / len(losses)) if losses else 0
        
        # Profit factor
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 1
        self.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Expectancy
        self.expectancy = (self.win_rate * self.avg_win) - ((1 - self.win_rate) * self.avg_loss)
        
        # Average bars held
        self.avg_bars_held = sum(t.bars_held for t in closed_trades) / len(closed_trades)
        
        # Max drawdown (simplu)
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
        
        # Sharpe Ratio (simplificat)
        returns = [t.pnl_percent for t in closed_trades]
        if len(returns) > 1:
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
            std_dev = math.sqrt(variance) if variance > 0 else 1
            self.sharpe_ratio = (mean_return / std_dev) * math.sqrt(252) if std_dev > 0 else 0
        
        # Sortino Ratio (doar downside deviation)
        negative_returns = [r for r in returns if r < 0]
        if negative_returns:
            downside_variance = sum(r ** 2 for r in negative_returns) / len(negative_returns)
            downside_dev = math.sqrt(downside_variance)
            mean_return = sum(returns) / len(returns)
            self.sortino_ratio = (mean_return / downside_dev) * math.sqrt(252) if downside_dev > 0 else 0
        
        # Consecutive wins/losses
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
        
        # Performance per signal type
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
            'signal_performance': self.signal_performance
        }
    
    def print_report(self):
        """Afișează raportul"""
        print("\n" + "=" * 70)
        print("[REPORT] RAPORT BACKTEST OIE MVP")
        print("=" * 70)
        
        print(f"\n[SUMMARY] SUMAR GENERAL")
        print(f"   Total Tranzactii: {self.total_trades}")
        print(f"   Castigatoare: {self.winning_trades} | Pierzatoare: {self.losing_trades}")
        print(f"   Win Rate: {self.win_rate * 100:.1f}%")

        print(f"\n[PNL] PROFIT & LOSS")
        print(f"   Total P&L: ${self.total_pnl:,.2f} ({self.total_pnl_percent:+.2f}%)")
        print(f"   Castig Mediu: ${self.avg_win:.2f}")
        print(f"   Pierdere Medie: ${self.avg_loss:.2f}")
        print(f"   Profit Factor: {self.profit_factor:.2f}")
        print(f"   Expectancy: ${self.expectancy:.4f}")

        print(f"\n[RISK] RISC")
        print(f"   Max Drawdown: ${self.max_drawdown:.2f} ({self.max_drawdown_percent:.2f}%)")
        print(f"   Sharpe Ratio: {self.sharpe_ratio:.2f}")
        print(f"   Sortino Ratio: {self.sortino_ratio:.2f}")

        print(f"\n[TIMING] TIMING")
        print(f"   Bare Medii Tinute: {self.avg_bars_held:.1f}")
        print(f"   Max Castiguri Consecutive: {self.max_consecutive_wins}")
        print(f"   Max Pierderi Consecutive: {self.max_consecutive_losses}")

        if self.signal_performance:
            print(f"\n[SIGNALS] PERFORMANTA PER TIP SEMNAL")
            for signal_type, perf in self.signal_performance.items():
                print(f"   {signal_type}:")
                print(f"      Trades: {perf['total']} | Win Rate: {perf['win_rate']*100:.1f}% | P&L: ${perf['total_pnl']:.2f}")
        
        print("\n" + "=" * 70)


class BacktestRunner:
    """Motor de backtesting"""
    
    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        
        # Inițializare motoare
        self.topology_engine = TopologyEngine(window_size=self.config.topology_window)
        self.predictive_engine = PredictiveEngine(window_size=self.config.predictive_window)
        self.signals_engine = SignalsEngine()
        
        # State
        self.current_trade: Optional[Trade] = None
        self.results: BacktestResults = None
    
    def convert_to_bars(self, ohlcv_bars: List[OHLCVBar]) -> List[Bar]:
        """Convertește OHLCVBar la Bar (model backend)"""
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
    
    def run(self, ohlcv_bars: List[OHLCVBar], symbol: str = "TEST") -> BacktestResults:
        """
        Rulează backtestul pe date.
        
        Args:
            ohlcv_bars: Lista de bare OHLCV
            symbol: Simbolul pentru procesare
        
        Returns:
            BacktestResults cu toate metricile
        """
        bars = self.convert_to_bars(ohlcv_bars)
        
        print(f"\n[RUN] Rulare backtest pe {len(bars)} bare...")
        print(f"   Perioada: {bars[0].timestamp} -> {bars[-1].timestamp}")
        
        self.results = BacktestResults(config=self.config)
        self.current_trade = None
        
        # Dimensiunea ferestrei minime pentru a începe
        min_window = max(self.config.topology_window, self.config.predictive_window)
        
        for i in range(min_window, len(bars)):
            # Fereastră de date
            window = bars[max(0, i - min_window):i + 1]
            current_bar = bars[i]
            
            # Calculează snapshot-uri
            topology = self.topology_engine.compute(symbol, window)
            predictive = self.predictive_engine.compute(symbol, window)
            signals = self.signals_engine.compute(symbol, topology, predictive, bars=window)
            
            # Gestionează trade curent
            if self.current_trade:
                self._manage_open_trade(current_bar, i)
            
            # Evaluează semnale noi (doar dacă nu avem trade deschis)
            if not self.current_trade:
                self._evaluate_signals(signals, current_bar, topology, predictive)
            
            # Progress
            if i % 1000 == 0:
                print(f"   Procesat {i}/{len(bars)} bare...")
        
        # Închide trade deschis la final
        if self.current_trade:
            self.current_trade.close(bars[-1].timestamp, bars[-1].close, "backtest_end")
            self.results.trades.append(self.current_trade)
        
        # Calculează metrici finale
        self.results.calculate_metrics()
        
        return self.results
    
    def _evaluate_signals(self, signals, current_bar: Bar, topology, predictive):
        """Evaluează semnalele și deschide trade dacă e cazul"""
        for signal in signals:
            # Filtrează semnale neutrale
            if signal.type == "flow_neutral_watch":
                continue
            
            # Verifică confidence minim
            if signal.confidence < self.config.min_confidence:
                continue
            
            # Verifică IFI minim
            if predictive.IFI < self.config.min_IFI:
                continue
            
            # Verifică vortex dacă e cerut
            if self.config.require_vortex and len(topology.vortexes) == 0:
                continue
            
            # Determină direcția
            if signal.type == "predictive_breakout_long":
                direction = TradeDirection.LONG
            elif signal.type == "predictive_breakout_short":
                direction = TradeDirection.SHORT
            else:
                continue
            
            # Deschide trade
            self.current_trade = Trade(
                entry_time=current_bar.timestamp,
                entry_price=current_bar.close,
                direction=direction,
                signal_type=signal.type,
                signal_confidence=signal.confidence
            )
            break  # Un singur trade la un moment dat
    
    def _manage_open_trade(self, current_bar: Bar, bar_index: int):
        """Gestionează un trade deschis"""
        trade = self.current_trade
        trade.update(current_bar.close)
        
        # Calculează profit/pierdere curentă
        if trade.direction == TradeDirection.LONG:
            current_pnl_pct = ((current_bar.close - trade.entry_price) / trade.entry_price) * 100
        else:
            current_pnl_pct = ((trade.entry_price - current_bar.close) / trade.entry_price) * 100
        
        # Check stop loss
        if current_pnl_pct <= -self.config.stop_loss_pct:
            trade.close(current_bar.timestamp, current_bar.close, "stop_loss")
            self.results.trades.append(trade)
            self.current_trade = None
            return
        
        # Check take profit
        if current_pnl_pct >= self.config.take_profit_pct:
            trade.close(current_bar.timestamp, current_bar.close, "take_profit")
            self.results.trades.append(trade)
            self.current_trade = None
            return
        
        # Check max hold time
        if trade.bars_held >= self.config.max_hold_bars:
            trade.close(current_bar.timestamp, current_bar.close, "max_hold")
            self.results.trades.append(trade)
            self.current_trade = None
            return
    
    def save_results(self, path: str):
        """Salvează rezultatele în JSON"""
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
                'initial_capital': self.config.initial_capital
            }
        }
        
        with open(path, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"\n[SAVE] Rezultate salvate in: {path}")


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """CLI pentru rularea backtestului"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Rulează backtest pe date OIE MVP"
    )
    parser.add_argument('--data', required=True,
                        help='Calea către fișierul CSV cu date')
    parser.add_argument('--confidence', type=float, default=0.5,
                        help='Confidence minim pentru semnale (default: 0.5)')
    parser.add_argument('--stop-loss', type=float, default=1.0,
                        help='Stop loss în procente (default: 1.0)')
    parser.add_argument('--take-profit', type=float, default=2.0,
                        help='Take profit în procente (default: 2.0)')
    parser.add_argument('--max-hold', type=int, default=60,
                        help='Max bare de ținut poziție (default: 60)')
    parser.add_argument('--capital', type=float, default=10000,
                        help='Capital inițial (default: 10000)')
    parser.add_argument('--output',
                        help='Calea pentru a salva rezultatele (JSON)')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("OIE MVP - Backtest Runner")
    print("=" * 60)
    
    # Încarcă date
    manager = DataManager()
    bars = manager.load_from_csv(Path(args.data))
    print(f"\n[LOAD] Incarcat {len(bars)} bare din {args.data}")
    
    # Configurație
    config = BacktestConfig(
        min_confidence=args.confidence,
        stop_loss_pct=args.stop_loss,
        take_profit_pct=args.take_profit,
        max_hold_bars=args.max_hold,
        initial_capital=args.capital
    )
    
    # Rulează backtest
    runner = BacktestRunner(config)
    results = runner.run(bars)
    
    # Afișează raport
    results.print_report()
    
    # Salvează dacă e specificat
    if args.output:
        runner.save_results(args.output)


if __name__ == '__main__':
    main()
