# 📊 GHID COMPLET - TICK DATA IMPORT

**Data:** 21 Decembrie 2025

---

## 🎯 CE ESTE TICK DATA?

**Tick data** = fiecare tranzacție individuală pe bursă, conținând:
- Timestamp exact (millisecunde)
- Preț
- Cantitate
- Direcție (buy sau sell)

### De ce e important?
- ✅ **Delta REAL** - știi exact cât s-a cumpărat vs vândut
- ✅ **Orderflow precis** - vezi presiunea reală din piață
- ✅ **Backtesting mai precis** - nu mai estimezi delta

---

## 📥 SURSE DE TICK DATA

### 1. **BINANCE** (Gratuit, recomandat!) ⭐

**Ce oferă:**
- Toate tranzacțiile în format ZIP
- Istoric din 2021+
- Format: CSV în ZIP
- Delta REAL din `is_buyer_maker`

**Link:** https://data.binance.vision/

**Cum descarci:**
```bash
# O zi de date (BTCUSDT, 5 minute)
python -m backend.backtest.tick_importer \
    --source binance \
    --symbol BTCUSDT \
    --date 2025-12-15 \
    --interval 300

# 7 zile de date
python -m backend.backtest.tick_importer \
    --source binance \
    --symbol BTCUSDT \
    --date 2025-12-10 \
    --days 7 \
    --interval 300
```

**Structura fișier descărcat:**
```
agg_trade_id,price,quantity,first_trade_id,last_trade_id,timestamp,is_buyer_maker
1234567,98500.50,0.015,1234567,1234567,1734278400000,True
```

---

### 2. **DUKASCOPY** (Gratuit - Forex)

**Ce oferă:**
- Tick-by-tick pentru Forex
- Istoric 10+ ani
- Format bi5 (binar)

**Link:** https://www.dukascopy.com/swiss/english/marketwatch/historical/

**Perechi disponibile:**
- EUR/USD, GBP/USD, USD/JPY
- XAU/USD (Gold), XAG/USD (Silver)

---

### 3. **TARDIS.DEV** (Plătit dar profesional)

**Ce oferă:**
- Order book level 2
- Toate trades
- Funding rates
- Multe exchange-uri

**Preț:** ~$50-100/lună
**Link:** https://tardis.dev

---

### 4. **CSV GENERIC**

Dacă ai tick data în format CSV, poți importa:

```bash
python -m backend.backtest.tick_importer \
    --source csv \
    --csv-file path/to/ticks.csv \
    --interval 60 \
    --output data/ticks/aggregated.csv
```

**Format necesar:**
```csv
timestamp,price,quantity,side
2025-12-15T10:00:00.123,98500.50,0.015,buy
2025-12-15T10:00:00.456,98501.00,0.020,sell
```

---

## 🔧 INTERVALURI DE AGREGARE

| Interval | Secunde | Comenză |
|----------|---------|---------|
| 1 minut | 60 | `--interval 60` |
| 5 minute | 300 | `--interval 300` |
| 15 minute | 900 | `--interval 900` |
| 1 oră | 3600 | `--interval 3600` |

---

## 📊 OUTPUT - BARE CU DELTA REAL

Fișierul CSV generat conține:

| Coloană | Descriere |
|---------|-----------|
| timestamp | Începutul barei |
| open | Preț deschidere |
| high | Preț maxim |
| low | Preț minim |
| close | Preț închidere |
| volume | Volum total |
| **buy_volume** | Volum cumpărare REAL |
| **sell_volume** | Volum vânzare REAL |
| **delta** | buy_volume - sell_volume (REAL!) |
| trades_count | Număr de trades în bară |
| vwap | Preț mediu ponderat cu volum |

---

## 🚀 UTILIZARE ÎN BACKTEST

### Metodă 1: Direct în backtest runner

```bash
# Descarcă tick data
python -m backend.backtest.tick_importer \
    --source binance \
    --symbol BTCUSDT \
    --date 2025-12-01 \
    --days 7 \
    --interval 300

# Rulează backtest pe datele cu delta real
python -m backend.backtest.backtest_runner \
    --data data/ticks/ticks_aggregated_BTCUSDT_5m_2025-12-01.csv \
    --confidence 0.6 \
    --stop-loss 1.0 \
    --take-profit 2.0
```

### Metodă 2: Python script

```python
from backend.backtest.tick_importer import TickDataManager, BinanceTickFetcher
from datetime import date
import asyncio

async def main():
    manager = TickDataManager()
    
    # Descarcă și agregă tick data
    bars = await manager.download_and_aggregate(
        symbol='BTCUSDT',
        start_date=date(2025, 12, 1),
        end_date=date(2025, 12, 7),
        interval_seconds=300,  # 5 minute
        source='binance'
    )
    
    # bars conține delta REAL!
    for bar in bars[:5]:
        print(f"{bar.timestamp}: Delta={bar.delta:+.2f}")

asyncio.run(main())
```

---

## 📈 EXEMPLU OUTPUT

Am descărcat 7 zile de tick data pentru BTCUSDT:

```
📊 Download tick data pentru BTCUSDT
   Perioadă: 2025-12-10 → 2025-12-16
   Interval agregare: 300s

✅ Parsed 1,995,637 ticks din 2025-12-10
✅ Parsed 1,847,523 ticks din 2025-12-11
...
🔄 Agregare 11,393,700 ticks în bare...
✅ Creat 2,016 bare cu delta REAL

📈 STATISTICI:
   Volum Total: 125,847.32 BTC
   Buy Volume:  62,891.45 BTC (50.0%)
   Sell Volume: 62,955.87 BTC (50.0%)
   Delta Net:   -64.42 BTC (ușor bearish)
```

---

## 📁 STRUCTURĂ FIȘIERE

```
oie_mvp/
├── backend/backtest/
│   └── tick_importer.py       # Importator tick data
│
└── data/
    ├── historical/            # Date OHLCV fără delta real
    │   ├── binance_BTCUSDT_15m.csv
    │   └── yahoo_SPY_15m.csv
    │
    └── ticks/                 # Date agregate din ticks (cu delta REAL)
        ├── ticks_aggregated_BTCUSDT_1m_2025-12-15.csv
        └── ticks_aggregated_BTCUSDT_5m_2025-12-10.csv
```

---

## ⚠️ LIMITĂRI

1. **Dimensiune fișiere** - O zi de ticks BTCUSDT = 1-2 milioane de rânduri
2. **Memorie** - Procesarea necesită RAM (4GB+ recomandat)
3. **Timp** - Descărcarea unei zile durează 30-60 secunde
4. **Istoric** - Binance oferă de la 2021+

---

## ✅ RECOMANDĂRI

1. **Pentru crypto** → Folosește Binance ZIP files (gratuit, complet)
2. **Pentru forex** → Dukascopy sau HistData.com
3. **Pentru stocks** → FirstRateData sau Databento (plătit)
4. **Interval optim** → 5 minute pentru backtesting (echilibru între precizie și viteză)

---

## 🔄 WORKFLOW COMPLET

```
1. DESCARCĂ TICK DATA
   └── python -m backend.backtest.tick_importer --source binance --symbol BTCUSDT --date 2025-12-01 --days 7 --interval 300

2. VERIFICĂ DELTA
   └── Deschide CSV și verifică buy_volume, sell_volume, delta

3. RULEAZĂ BACKTEST
   └── python -m backend.backtest.backtest_runner --data data/ticks/ticks_aggregated_*.csv

4. ANALIZEAZĂ REZULTATE
   └── Compară cu rezultatele din date fără delta real
```

---

**Tick data oferă cel mai precis delta pentru orderflow analysis!** 🎯
