"""
OIE MVP - Backtest cu Delta Trend
=================================

Ruleaza backtest pe datele disponibile cu setarile curente:
- min_confidence: 60%
- min_reversal_confidence: 62%
- SL: 1%, TP: 2%
- Delta trend pentru filtrarea semnalelor contratrend
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
from datetime import datetime
from backend.backtest.backtest_runner import BacktestRunner, BacktestConfig
from backend.backtest.data_fetcher import OHLCVBar


def load_data_with_delta(csv_path: str):
    """Incarca date cu delta din CSV"""
    df = pd.read_csv(csv_path)

    bars = []
    for _, row in df.iterrows():
        bar = OHLCVBar(
            timestamp=pd.to_datetime(row['timestamp']),
            open=float(row['open']),
            high=float(row['high']),
            low=float(row['low']),
            close=float(row['close']),
            volume=float(row['volume']),
        )
        # Adauga delta info daca exista
        if 'buy_volume' in row:
            bar.buy_volume = float(row['buy_volume'])
        if 'sell_volume' in row:
            bar.sell_volume = float(row['sell_volume'])
        if 'delta' in row:
            bar.delta = float(row['delta'])

        bars.append(bar)

    return bars


def main():
    print("=" * 60)
    print("OIE MVP - BACKTEST CU DELTA TREND")
    print("=" * 60)

    # Calea catre date
    data_path = os.path.join(
        os.path.dirname(__file__),
        "data", "ticks", "btcusdt_5m_14days_delta_real.csv"
    )

    if not os.path.exists(data_path):
        print(f"[ERROR] Fisierul nu exista: {data_path}")
        return

    print(f"\n[DATA] Date: {data_path}")

    # Incarca datele
    print("[LOAD] Incarcare date...")
    bars = load_data_with_delta(data_path)
    print(f"   Incarcate {len(bars)} bare")
    print(f"   Perioada: {bars[0].timestamp} -> {bars[-1].timestamp}")

    # Verifica daca avem delta
    has_delta = hasattr(bars[0], 'delta') and bars[0].delta is not None
    print(f"   Delta disponibil: {'DA' if has_delta else 'NU'}")

    # Configurare backtest cu setarile curente
    config = BacktestConfig(
        min_confidence=0.60,      # 60% minim pentru intrare
        stop_loss_pct=1.0,        # 1% SL
        take_profit_pct=1.0,      # 1% TP (1:1 risk/reward)
        initial_capital=10000,    # $10,000 capital initial
        position_size_pct=0.10,   # 10% din capital per trade
        max_hold_bars=120,        # Max 120 bare (10h pentru 5m timeframe)
        min_IFI=0,                # Nu filtram pe IFI
        require_vortex=False,     # Nu cerem vortex
    )

    print(f"\n[CONFIG] Configurare:")
    print(f"   Min Confidence: {config.min_confidence:.0%}")
    print(f"   Stop Loss: {config.stop_loss_pct}%")
    print(f"   Take Profit: {config.take_profit_pct}%")
    print(f"   Capital Initial: ${config.initial_capital:,.0f}")
    print(f"   Position Size: {config.position_size_pct:.0%}")

    # Ruleaza backtest
    runner = BacktestRunner(config)
    results = runner.run(bars, symbol="BTCUSDT")

    # Afiseaza rezultate
    print("\n" + "=" * 60)
    print("[RESULTS] REZULTATE BACKTEST")
    print("=" * 60)

    summary = results.to_dict()

    print(f"\n[PERF] Performanta Generala:")
    print(f"   Total Trade-uri: {summary['total_trades']}")
    print(f"   Win Rate: {summary['win_rate']:.1f}%")
    print(f"   Profit Factor: {summary['profit_factor']:.2f}")
    print(f"   Total P&L: ${summary['total_pnl']:,.2f}")
    print(f"   Total P&L %: {summary['total_pnl_percent']:.2f}%")

    print(f"\n[RISK] Risk Metrics:")
    print(f"   Max Drawdown: {summary['max_drawdown']:.2f}%")
    print(f"   Sharpe Ratio: {summary['sharpe_ratio']:.2f}")
    print(f"   Sortino Ratio: {summary['sortino_ratio']:.2f}")

    print(f"\n[STATS] Trade Stats:")
    print(f"   Avg Win: ${summary['avg_win']:.2f}")
    print(f"   Avg Loss: ${summary['avg_loss']:.2f}")
    avg_bars = summary.get('avg_bars_held', 0)
    print(f"   Avg Hold Time: {avg_bars:.0f} bare (~{avg_bars * 5:.0f} min)")

    # Trade-uri pe directie
    long_trades = [t for t in results.trades if t.direction.value == 'long']
    short_trades = [t for t in results.trades if t.direction.value == 'short']

    long_wins = len([t for t in long_trades if t.pnl > 0])
    short_wins = len([t for t in short_trades if t.pnl > 0])

    print(f"\n[LONG] LONG Trades:")
    print(f"   Total: {len(long_trades)}")
    print(f"   Win Rate: {(long_wins / len(long_trades) * 100) if long_trades else 0:.1f}%")

    print(f"\n[SHORT] SHORT Trades:")
    print(f"   Total: {len(short_trades)}")
    print(f"   Win Rate: {(short_wins / len(short_trades) * 100) if short_trades else 0:.1f}%")

    # Distributie exit reasons
    exit_reasons = {}
    for t in results.trades:
        reason = t.exit_reason or 'unknown'
        exit_reasons[reason] = exit_reasons.get(reason, 0) + 1

    print(f"\n[EXIT] Exit Reasons:")
    for reason, count in sorted(exit_reasons.items(), key=lambda x: -x[1]):
        pct = count / len(results.trades) * 100 if results.trades else 0
        print(f"   {reason}: {count} ({pct:.1f}%)")

    # Salveaza rezultatele
    output_path = os.path.join(
        os.path.dirname(__file__),
        "results", "backtest_delta_trend.json"
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    runner.save_results(output_path)

    print("\n" + "=" * 60)
    print("[OK] Backtest completat!")
    print("=" * 60)


if __name__ == '__main__':
    main()
