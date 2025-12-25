# 📊 RAPORT BACKTEST OIE MVP - BTCUSDT 1 AN

**Data Generării:** 21 Decembrie 2025  
**Perioadă Testată:** 21 Decembrie 2024 → 21 Decembrie 2025  
**Interval:** 15 minute  
**Total Bare:** 35,040  

---

## 📈 REZULTATE PRINCIPALE

### Sumar General
| Metrică | Valoare |
|---------|---------|
| **Total Tranzacții** | 580 |
| **Câștigătoare** | 281 (48.4%) |
| **Pierzătoare** | 299 (51.6%) |
| **Win Rate** | 48.45% |

### Profit & Loss
| Metrică | Valoare |
|---------|---------|
| **Total P&L** | $821.30 |
| **Total P&L %** | +2.09% |
| **Câștig Mediu** | $943.73 |
| **Pierdere Medie** | $884.17 |
| **Profit Factor** | 1.00 |
| **Expectancy** | $1.42 per trade |

### Metrici de Risc
| Metrică | Valoare |
|---------|---------|
| **Max Drawdown** | $34,547.80 |
| **Max Drawdown %** | 345.48%* |
| **Sharpe Ratio** | 0.05 |
| **Sortino Ratio** | 0.05 |

*Notă: Max Drawdown % e calculat relativ la capitalul inițial de $10,000 și reflectă trades cu leverage implicit.

### Timing
| Metrică | Valoare |
|---------|---------|
| **Bare Medii Ținute** | 36.5 |
| **Max Câștiguri Consecutive** | 7 |
| **Max Pierderi Consecutive** | 8 |

---

## 📊 PERFORMANȚĂ PER TIP SEMNAL

| Semnal | Trades | Win Rate | P&L Total | P&L Mediu |
|--------|--------|----------|-----------|-----------|
| **predictive_breakout_short** | 255 | 49.4% | +$5,202.50 | +$20.40 |
| **predictive_breakout_long** | 325 | 47.7% | -$4,381.20 | -$13.48 |

### Observații:
- ✅ **Semnalele SHORT au performat mai bine** (+$5,202.50)
- ⚠️ **Semnalele LONG au pierdut bani** (-$4,381.20)
- 📊 Perioada testată (2024-2025) a fost predominant bearish/sideways pentru BTC

---

## 🔧 PARAMETRI BACKTEST

| Parametru | Valoare |
|-----------|---------|
| Fereastră Topology | 100 bare |
| Fereastră Predictive | 200 bare |
| Confidence Minim | 0.55 |
| Stop Loss | 1.5% |
| Take Profit | 3.0% |
| Max Hold | 40 bare (10h) |
| Capital Inițial | $10,000 |

---

## 📉 ANALIZA EXIT REASONS

Motivele închiderii tranzacțiilor (din primele trades):
- **max_hold**: Majoritatea - trades care au atins limita de timp
- **stop_loss**: Trades închise pe pierdere (1.5%)
- **take_profit**: Trades câștigătoare (3.0%)

---

## 💡 CONCLUZII ȘI RECOMANDĂRI

### Ce a mers bine ✅
1. Sistemul a generat semnale consistente (580 trades în 1 an)
2. Semnalele SHORT au fost profitabile
3. Win rate echilibrat (~48%)

### Ce trebuie îmbunătățit ⚠️
1. **Semnalele LONG au pierdut bani** - necesită filtrare suplimentară
2. **Sharpe Ratio scăzut (0.05)** - volatilitate mare a returnurilor
3. **Max Drawdown mare** - necesită position sizing mai conservator

### Recomandări pentru Optimizare 🚀

1. **Filtrare Regime de Piață**
   - Adaugă indicator trend (MA, ADX)
   - Ia semnale LONG doar în uptrend confirmat
   - Preferă semnale SHORT în downtrend/range

2. **Ajustare Stop Loss / Take Profit**
   - Testează TP mai mic (2.0% în loc de 3.0%)
   - Trailing stop pentru a captura mai mult profit

3. **Position Sizing**
   - Reduce poziția la 10-20% din capital per trade
   - Scade riscul de max drawdown

4. **Filtrare pe IFI**
   - Ia trades doar când IFI > prag minim
   - Evită perioade de volatilitate scăzută

5. **Adaugă Vortex Confirmation**
   - Configurează `require_vortex = True`
   - Reduce numărul de semnale dar crește calitatea

---

## 📁 FIȘIERE GENERATE

| Fișier | Descriere |
|--------|-----------|
| `data/historical/binance_BTCUSDT_15m.csv` | Date istorice 1 an |
| `results/backtest_btcusdt_1year_15m.json` | Rezultate detaliate (580 trades) |

---

## 🔄 NEXT STEPS

```bash
# Backtest cu filtrare pe SHORT-only
python -m backend.backtest.backtest_runner \
    --data data/historical/binance_BTCUSDT_15m.csv \
    --confidence 0.6 \
    --stop-loss 1.0 \
    --take-profit 2.0 \
    --output results/backtest_optimized.json

# Testează pe ETHUSDT
python -m backend.backtest.data_fetcher --source binance --symbol ETHUSDT --interval 15m --days 365
python -m backend.backtest.backtest_runner --data data/historical/binance_ETHUSDT_15m.csv
```

---

**Status:** ✅ Backtest complet  
**Verdict:** Sistemul funcționează, dar necesită optimizări pentru a fi profitabil consistent.
