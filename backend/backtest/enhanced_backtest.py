"""
OIE MVP - Enhanced Backtest Runner cu Delta Filters
=====================================================

Versiune îmbunătățită care folosește delta REAL din tick data
pentru a ajusta confidence, NU pentru a bloca trades.

Filtre propuse:
1. Delta Confirmation - boost/reduce confidence bazat pe delta bară curentă
2. Cumulative Delta Bias - ajustează bazat pe delta rolling
3. Volume Imbalance - ajustează bazat pe buy/sell ratio
4. Momentum Alignment - verifică dacă semnalul e în direcția momentum-ului

IMPORTANT: Toate filtrele AJUSTEAZĂ confidence, nu BLOCHEAZĂ trades!
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
from backend.topology.engine import TopologyEngine
from backend.predictive.engine import PredictiveEngine
from backend.signals.engine import SignalsEngine
from backend.backtest.data_fetcher import DataManager, OHLCVBar


class TradeDirection(Enum):
    LONG = "long"
    SHORT = "short"


@dataclass
class EnhancedTrade:
    """Trade cu metrici extinse"""
    entry_time: datetime
    entry_price: float
    direction: TradeDirection
    signal_type: str
    original_confidence: float
    adjusted_confidence: float
    
    # Delta metrics la intrare
    bar_delta: float = 0.0
    cumulative_delta: float = 0.0
    buy_ratio: float = 0.5
    confidence_adjustments: Dict[str, float] = field(default_factory=dict)
    
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    
    pnl: float = 0.0
    pnl_percent: float = 0.0
    bars_held: int = 0
    
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
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'entry_time': self.entry_time.isoformat(),
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'direction': self.direction.value,
            'signal_type': self.signal_type,
            'original_confidence': self.original_confidence,
            'adjusted_confidence': self.adjusted_confidence,
            'bar_delta': self.bar_delta,
            'cumulative_delta': self.cumulative_delta,
            'buy_ratio': self.buy_ratio,
            'confidence_adjustments': self.confidence_adjustments,
            'pnl': self.pnl,
            'pnl_percent': self.pnl_percent,
            'bars_held': self.bars_held,
            'exit_reason': self.exit_reason
        }


@dataclass
class EnhancedBacktestConfig:
    """Configurație cu filtre delta"""
    # Ferestre
    topology_window: int = 100
    predictive_window: int = 200
    
    # Bazice
    min_confidence: float = 0.50
    max_hold_bars: int = 30
    stop_loss_pct: float = 1.0
    take_profit_pct: float = 2.0
    initial_capital: float = 10000.0
    
    # ===== FILTRE DELTA (toate sunt SOFT - ajustează confidence) =====
    
    # 1. Delta Bar Confirmation
    # Dacă delta barei curente e în aceeași direcție cu semnalul → boost
    use_delta_confirmation: bool = True
    delta_confirm_boost: float = 0.10      # +10% confidence dacă delta confirmă
    delta_against_penalty: float = -0.05   # -5% dacă delta e contra (mic, să nu excludem)
    
    # 2. Cumulative Delta Bias
    # Dacă ultimele N bare au delta cumulat în direcția semnalului → boost
    use_cumulative_delta: bool = True
    cumulative_delta_bars: int = 10        # Ultimele 10 bare
    cumulative_delta_boost: float = 0.08   # +8% dacă cumulative delta confirmă
    cumulative_delta_penalty: float = -0.03  # -3% dacă e contra
    
    # 3. Volume Imbalance
    # Dacă buy_volume/volume > 0.52 pentru LONG sau < 0.48 pentru SHORT → boost
    use_volume_imbalance: bool = True
    volume_imbalance_threshold: float = 0.52  # 52% = ușor imbalance
    volume_imbalance_boost: float = 0.07   # +7% dacă imbalance confirmă
    
    # 4. Momentum Alignment (din direcția ultimelor bare)
    use_momentum_filter: bool = True
    momentum_bars: int = 5                 # Ultimele 5 bare
    momentum_boost: float = 0.06           # +6% dacă momentum confirmă


class DeltaAnalyzer:
    """Analizează delta din bare cu delta real"""
    
    @staticmethod
    def get_bar_delta(bar: Bar) -> float:
        """Returnează delta barei (buy_vol - sell_vol)"""
        if bar.delta is not None:
            return bar.delta
        
        # Fallback la estimare dacă nu avem delta
        if bar.buy_volume is not None and bar.sell_volume is not None:
            return bar.buy_volume - bar.sell_volume
        
        # Ultima estimare - din direcția candelei
        if bar.close > bar.open:
            return bar.volume * 0.1
        elif bar.close < bar.open:
            return -bar.volume * 0.1
        return 0
    
    @staticmethod
    def get_cumulative_delta(bars: List[Bar], n: int = 10) -> float:
        """Returnează suma delta pe ultimele N bare"""
        recent = bars[-n:] if len(bars) >= n else bars
        return sum(DeltaAnalyzer.get_bar_delta(b) for b in recent)
    
    @staticmethod
    def get_buy_ratio(bar: Bar) -> float:
        """Returnează raportul buy_volume / total_volume"""
        if bar.buy_volume is not None and bar.volume and bar.volume > 0:
            return bar.buy_volume / bar.volume
        
        # Estimare din direcția candelei
        if bar.close > bar.open:
            return 0.55
        elif bar.close < bar.open:
            return 0.45
        return 0.5
    
    @staticmethod
    def get_momentum(bars: List[Bar], n: int = 5) -> float:
        """Returnează momentum (1 = bullish, -1 = bearish)"""
        recent = bars[-n:] if len(bars) >= n else bars
        if len(recent) < 2:
            return 0
        
        up_bars = sum(1 for b in recent if b.close > b.open)
        down_bars = len(recent) - up_bars
        
        return (up_bars - down_bars) / len(recent)  # Range: -1 to 1


class EnhancedBacktestRunner:
    """Motor de backtesting cu filtre delta soft"""
    
    def __init__(self, config: EnhancedBacktestConfig = None):
        self.config = config or EnhancedBacktestConfig()
        
        self.topology_engine = TopologyEngine(window_size=self.config.topology_window)
        self.predictive_engine = PredictiveEngine(window_size=self.config.predictive_window)
        self.signals_engine = SignalsEngine()
        
        self.current_trade: Optional[EnhancedTrade] = None
        self.trades: List[EnhancedTrade] = []
    
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
    
    def calculate_confidence_adjustments(
        self,
        signal_type: str,
        current_bar: Bar,
        window: List[Bar]
    ) -> Dict[str, float]:
        """
        Calculează ajustările de confidence bazate pe filtre.
        
        IMPORTANT: Returnează dicționar cu ajustări, nu blochează niciun trade!
        """
        adjustments = {}
        
        is_long = "long" in signal_type.lower()
        
        # 1. Delta Bar Confirmation
        if self.config.use_delta_confirmation:
            bar_delta = DeltaAnalyzer.get_bar_delta(current_bar)
            
            if is_long:
                if bar_delta > 0:
                    adjustments['delta_confirm'] = self.config.delta_confirm_boost
                elif bar_delta < 0:
                    adjustments['delta_confirm'] = self.config.delta_against_penalty
            else:  # SHORT
                if bar_delta < 0:
                    adjustments['delta_confirm'] = self.config.delta_confirm_boost
                elif bar_delta > 0:
                    adjustments['delta_confirm'] = self.config.delta_against_penalty
        
        # 2. Cumulative Delta Bias
        if self.config.use_cumulative_delta:
            cum_delta = DeltaAnalyzer.get_cumulative_delta(
                window, 
                self.config.cumulative_delta_bars
            )
            
            if is_long:
                if cum_delta > 0:
                    adjustments['cumulative_delta'] = self.config.cumulative_delta_boost
                elif cum_delta < 0:
                    adjustments['cumulative_delta'] = self.config.cumulative_delta_penalty
            else:  # SHORT
                if cum_delta < 0:
                    adjustments['cumulative_delta'] = self.config.cumulative_delta_boost
                elif cum_delta > 0:
                    adjustments['cumulative_delta'] = self.config.cumulative_delta_penalty
        
        # 3. Volume Imbalance
        if self.config.use_volume_imbalance:
            buy_ratio = DeltaAnalyzer.get_buy_ratio(current_bar)
            
            if is_long and buy_ratio > self.config.volume_imbalance_threshold:
                adjustments['volume_imbalance'] = self.config.volume_imbalance_boost
            elif not is_long and buy_ratio < (1 - self.config.volume_imbalance_threshold):
                adjustments['volume_imbalance'] = self.config.volume_imbalance_boost
        
        # 4. Momentum Alignment
        if self.config.use_momentum_filter:
            momentum = DeltaAnalyzer.get_momentum(window, self.config.momentum_bars)
            
            if is_long and momentum > 0:
                adjustments['momentum'] = self.config.momentum_boost * momentum
            elif not is_long and momentum < 0:
                adjustments['momentum'] = self.config.momentum_boost * abs(momentum)
        
        return adjustments
    
    def run(self, ohlcv_bars: List[OHLCVBar], symbol: str = "TEST") -> Dict:
        bars = self.convert_to_bars(ohlcv_bars)
        
        print(f"\n🚀 Enhanced Backtest cu Delta Filters")
        print(f"   Perioadă: {bars[0].timestamp} → {bars[-1].timestamp}")
        print(f"   Total bare: {len(bars)}")
        print(f"\n📊 Filtre active:")
        print(f"   Delta Confirmation: {self.config.use_delta_confirmation}")
        print(f"   Cumulative Delta: {self.config.use_cumulative_delta}")
        print(f"   Volume Imbalance: {self.config.use_volume_imbalance}")  
        print(f"   Momentum Filter: {self.config.use_momentum_filter}")
        
        self.trades = []
        self.current_trade = None
        
        min_window = max(self.config.topology_window, self.config.predictive_window)
        
        filter_stats = {
            'total_signals': 0,
            'confidence_boosts': 0,
            'confidence_reductions': 0,
            'avg_adjustment': 0.0
        }
        adjustments_sum = 0
        
        for i in range(min_window, len(bars)):
            window = bars[max(0, i - min_window):i + 1]
            current_bar = bars[i]
            
            topology = self.topology_engine.compute(symbol, window)
            predictive = self.predictive_engine.compute(symbol, window)
            signals = self.signals_engine.compute(symbol, topology, predictive)
            
            # Gestionează trade curent
            if self.current_trade:
                self._manage_open_trade(current_bar)
            
            # Evaluează semnale noi
            if not self.current_trade:
                for signal in signals:
                    if signal.type == "flow_neutral_watch":
                        continue
                    
                    original_confidence = signal.confidence
                    
                    if original_confidence < self.config.min_confidence:
                        continue
                    
                    filter_stats['total_signals'] += 1
                    
                    # Calculează ajustări
                    adjustments = self.calculate_confidence_adjustments(
                        signal.type,
                        current_bar,
                        window
                    )
                    
                    # Aplică ajustări
                    total_adjustment = sum(adjustments.values())
                    adjusted_confidence = min(1.0, max(0.0, original_confidence + total_adjustment))
                    
                    adjustments_sum += total_adjustment
                    
                    if total_adjustment > 0:
                        filter_stats['confidence_boosts'] += 1
                    elif total_adjustment < 0:
                        filter_stats['confidence_reductions'] += 1
                    
                    # Verifică din nou confidence după ajustare
                    if adjusted_confidence < self.config.min_confidence:
                        continue
                    
                    # Determină direcția
                    if signal.type == "predictive_breakout_long":
                        direction = TradeDirection.LONG
                    elif signal.type == "predictive_breakout_short":
                        direction = TradeDirection.SHORT
                    else:
                        continue
                    
                    self.current_trade = EnhancedTrade(
                        entry_time=current_bar.timestamp,
                        entry_price=current_bar.close,
                        direction=direction,
                        signal_type=signal.type,
                        original_confidence=original_confidence,
                        adjusted_confidence=adjusted_confidence,
                        bar_delta=DeltaAnalyzer.get_bar_delta(current_bar),
                        cumulative_delta=DeltaAnalyzer.get_cumulative_delta(window),
                        buy_ratio=DeltaAnalyzer.get_buy_ratio(current_bar),
                        confidence_adjustments=adjustments
                    )
                    break
            
            if i % 500 == 0:
                print(f"   Procesat {i}/{len(bars)} bare...")
        
        # Închide trade la final
        if self.current_trade:
            self.current_trade.close(bars[-1].timestamp, bars[-1].close, "backtest_end")
            self.trades.append(self.current_trade)
        
        if filter_stats['total_signals'] > 0:
            filter_stats['avg_adjustment'] = adjustments_sum / filter_stats['total_signals']
        
        # Calculează metrici
        results = self._calculate_results(filter_stats)
        
        return results
    
    def _manage_open_trade(self, current_bar: Bar):
        trade = self.current_trade
        trade.update(current_bar.close)
        
        if trade.direction == TradeDirection.LONG:
            current_pnl_pct = ((current_bar.close - trade.entry_price) / trade.entry_price) * 100
        else:
            current_pnl_pct = ((trade.entry_price - current_bar.close) / trade.entry_price) * 100
        
        if current_pnl_pct <= -self.config.stop_loss_pct:
            trade.close(current_bar.timestamp, current_bar.close, "stop_loss")
            self.trades.append(trade)
            self.current_trade = None
            return
        
        if current_pnl_pct >= self.config.take_profit_pct:
            trade.close(current_bar.timestamp, current_bar.close, "take_profit")
            self.trades.append(trade)
            self.current_trade = None
            return
        
        if trade.bars_held >= self.config.max_hold_bars:
            trade.close(current_bar.timestamp, current_bar.close, "max_hold")
            self.trades.append(trade)
            self.current_trade = None
            return
    
    def _calculate_results(self, filter_stats: Dict) -> Dict:
        closed_trades = [t for t in self.trades if t.exit_time is not None]
        
        if not closed_trades:
            return {'trades': [], 'summary': {}, 'filter_stats': filter_stats}
        
        total = len(closed_trades)
        winners = [t for t in closed_trades if t.pnl > 0]
        losers = [t for t in closed_trades if t.pnl <= 0]
        
        win_rate = len(winners) / total
        total_pnl = sum(t.pnl for t in closed_trades)
        avg_win = sum(t.pnl for t in winners) / len(winners) if winners else 0
        avg_loss = abs(sum(t.pnl for t in losers) / len(losers)) if losers else 0
        
        gross_profit = sum(t.pnl for t in winners) if winners else 0
        gross_loss = abs(sum(t.pnl for t in losers)) if losers else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        
        # Sharpe
        returns = [t.pnl_percent for t in closed_trades]
        if len(returns) > 1:
            mean_ret = sum(returns) / len(returns)
            var = sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)
            std = math.sqrt(var) if var > 0 else 1
            sharpe = (mean_ret / std) * math.sqrt(252) if std > 0 else 0
        else:
            sharpe = 0
        
        # Per signal type
        signal_perf = {}
        for trade in closed_trades:
            st = trade.signal_type
            if st not in signal_perf:
                signal_perf[st] = {'total': 0, 'wins': 0, 'pnl': 0}
            signal_perf[st]['total'] += 1
            if trade.pnl > 0:
                signal_perf[st]['wins'] += 1
            signal_perf[st]['pnl'] += trade.pnl
        
        for st in signal_perf:
            signal_perf[st]['win_rate'] = signal_perf[st]['wins'] / signal_perf[st]['total']
        
        # Eficiență filtre - compară trades boosted vs reduced
        boosted_trades = [t for t in closed_trades if sum(t.confidence_adjustments.values()) > 0]
        reduced_trades = [t for t in closed_trades if sum(t.confidence_adjustments.values()) < 0]
        
        filter_effectiveness = {
            'boosted_trades': len(boosted_trades),
            'boosted_winrate': len([t for t in boosted_trades if t.pnl > 0]) / len(boosted_trades) if boosted_trades else 0,
            'boosted_pnl': sum(t.pnl for t in boosted_trades),
            'reduced_trades': len(reduced_trades),
            'reduced_winrate': len([t for t in reduced_trades if t.pnl > 0]) / len(reduced_trades) if reduced_trades else 0,
            'reduced_pnl': sum(t.pnl for t in reduced_trades)
        }
        
        summary = {
            'total_trades': total,
            'winning_trades': len(winners),
            'losing_trades': len(losers),
            'win_rate': round(win_rate * 100, 2),
            'total_pnl': round(total_pnl, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'profit_factor': round(profit_factor, 2),
            'expectancy': round(expectancy, 4),
            'sharpe_ratio': round(sharpe, 2),
            'signal_performance': signal_perf,
            'filter_stats': filter_stats,
            'filter_effectiveness': filter_effectiveness
        }
        
        # Print report
        print("\n" + "=" * 70)
        print("📊 RAPORT ENHANCED BACKTEST (cu Delta Filters)")
        print("=" * 70)
        
        print(f"\n📈 SUMAR GENERAL")
        print(f"   Total Tranzacții: {total}")
        print(f"   Câștigătoare: {len(winners)} | Pierzătoare: {len(losers)}")
        print(f"   Win Rate: {win_rate * 100:.1f}%")
        
        print(f"\n💰 PROFIT & LOSS")
        print(f"   Total P&L: ${total_pnl:,.2f}")
        print(f"   Avg Win: ${avg_win:.2f} | Avg Loss: ${avg_loss:.2f}")
        print(f"   Profit Factor: {profit_factor:.2f}")
        print(f"   Expectancy: ${expectancy:.4f}")
        print(f"   Sharpe Ratio: {sharpe:.2f}")
        
        print(f"\n📊 PERFORMANȚĂ PER SEMNAL")
        for st, perf in signal_perf.items():
            print(f"   {st}: {perf['total']} trades | WR: {perf['win_rate']*100:.1f}% | P&L: ${perf['pnl']:.2f}")
        
        print(f"\n🔧 EFICIENȚA FILTRELOR")
        print(f"   Semnale evaluate: {filter_stats['total_signals']}")
        print(f"   Confidence boosted: {filter_stats['confidence_boosts']}")
        print(f"   Confidence reduced: {filter_stats['confidence_reductions']}")
        print(f"   Avg adjustment: {filter_stats['avg_adjustment']:+.3f}")
        
        print(f"\n📈 TRADES BOOSTED vs REDUCED")
        print(f"   Boosted: {filter_effectiveness['boosted_trades']} trades | WR: {filter_effectiveness['boosted_winrate']*100:.1f}% | P&L: ${filter_effectiveness['boosted_pnl']:.2f}")
        print(f"   Reduced: {filter_effectiveness['reduced_trades']} trades | WR: {filter_effectiveness['reduced_winrate']*100:.1f}% | P&L: ${filter_effectiveness['reduced_pnl']:.2f}")
        
        print("\n" + "=" * 70)
        
        return {
            'trades': [t.to_dict() for t in self.trades],
            'summary': summary
        }
    
    def save_results(self, results: Dict, path: str):
        with open(path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Rezultate salvate în: {path}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced Backtest cu Delta Filters")
    parser.add_argument('--data', required=True, help='Calea CSV')
    parser.add_argument('--confidence', type=float, default=0.50, help='Confidence minim')
    parser.add_argument('--stop-loss', type=float, default=1.0, help='Stop loss %')
    parser.add_argument('--take-profit', type=float, default=2.0, help='Take profit %')
    parser.add_argument('--max-hold', type=int, default=30, help='Max hold bars')
    parser.add_argument('--no-delta-confirm', action='store_true', help='Dezactivează delta confirm')
    parser.add_argument('--no-cumulative', action='store_true', help='Dezactivează cumulative delta')
    parser.add_argument('--no-volume', action='store_true', help='Dezactivează volume imbalance')
    parser.add_argument('--no-momentum', action='store_true', help='Dezactivează momentum')
    parser.add_argument('--output', help='Output JSON')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("OIE MVP - Enhanced Backtest cu Delta Filters")
    print("=" * 60)
    
    manager = DataManager()
    bars = manager.load_from_csv(Path(args.data))
    print(f"\n📂 Încărcat {len(bars)} bare din {args.data}")
    
    config = EnhancedBacktestConfig(
        min_confidence=args.confidence,
        stop_loss_pct=args.stop_loss,
        take_profit_pct=args.take_profit,
        max_hold_bars=args.max_hold,
        use_delta_confirmation=not args.no_delta_confirm,
        use_cumulative_delta=not args.no_cumulative,
        use_volume_imbalance=not args.no_volume,
        use_momentum_filter=not args.no_momentum
    )
    
    runner = EnhancedBacktestRunner(config)
    results = runner.run(bars)
    
    if args.output:
        runner.save_results(results, args.output)


if __name__ == '__main__':
    main()
