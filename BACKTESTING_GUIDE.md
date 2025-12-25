# 📊 GHID BACKTESTING OIE MVP

## 🎯 Obiectiv

Acest document explică cum să obții date corecte și curate pentru backtesting și cum să rulezi simulări pe strategia OIE MVP.

---

## 📥 SURSE DE DATE

### 1. **Binance** (RECOMANDAT) ⭐

**Ce oferă:**
- Date OHLCV gratuite (fără limită)
- Istoric complet din 2017+
- Intervale: 1m, 3m, 5m, 15m, 30m, 1h, 4h, 1d
- Aggregate trades pentru calcul delta real

**Cum să folosești:**
```bash
# Descarcă 7 zile de date BTCUSDT la 1 minut
python -m backend.backtest.data_fetcher --source binance --symbol BTCUSDT --interval 1m --days 7

# Descarcă 30 zile la 5 minute (fără delta real - prea lent)
python -m backend.backtest.data_fetcher --source binance --symbol BTCUSDT --interval 5m --days 30 --no-delta

# Descarcă de pe market spot în loc de futures
python -m backend.backtest.data_fetcher --source binance --symbol BTCUSDT --interval 1h --days 90 --spot
```

**API Endpoint:**
- Futures: `https://fapi.binance.com/fapi/v1/klines`
- Spot: `https://api.binance.com/api/v3/klines`

**Limite:**
- 1500 bare per request
- Fără API key: 1200 requests/min
- Cu API key: 2400 requests/min

---

### 2. **Bybit**

**Ce oferă:**
- Date OHLCV gratuite
- USDT Perpetual, Inverse Perpetual
- Intervale similare cu Binance

**Cum să folosești:**
```bash
python -m backend.backtest.data_fetcher --source bybit --symbol BTCUSDT --interval 1m --days 7
```

**API Endpoint:**
- `https://api.bybit.com/v5/market/kline`

---

### 3. **Tardis.dev** (Date Profesionale)

**Ce oferă:**
- Date tick-level (fiecare tranzacție)
- Order book historical
- Delta real calculat
- Foarte precise dar PLĂTITE

**Website:** https://tardis.dev

---

### 4. **CryptoDataDownload** (Gratuit, fără cod)

**Ce oferă:**
- Fișiere CSV pre-descărcate
- Multiple exchange-uri
- Foarte ușor de folosit

**Website:** https://www.cryptodatadownload.com/data/

**Cum să folosești:**
1. Descarcă CSV-ul dorit (ex: Binance BTCUSDT hourly)
2. Pune-l în `oie_mvp/data/historical/`
3. Convertește la formatul OIE (vezi mai jos)

---

### 5. **Kaggle Datasets** (Gratuit)

**Datasets utile:**
- "Bitcoin Historical Data" - Minute-level back to 2012
- "Cryptocurrency Market Data" - Multiple coins
- "Binance Full History" - OHLCV complet

**Website:** https://www.kaggle.com/datasets

---

## 📋 FORMATUL DATELOR OIE MVP

Sistemul OIE MVP așteaptă CSV cu următoarele coloane:

```csv
timestamp,open,high,low,close,volume,buy_volume,sell_volume
2025-01-01T09:30:00,100.00,100.10,99.90,100.05,1000.0,600.0,400.0
2025-01-01T09:31:00,100.05,100.15,99.95,100.10,1050.0,640.0,410.0
```

| Coloană | Tip | Obligatoriu | Descriere |
|---------|-----|-------------|-----------|
| timestamp | ISO datetime | ✅ Da | Format: YYYY-MM-DDTHH:MM:SS |
| open | float | ✅ Da | Preț deschidere |
| high | float | ✅ Da | Preț maxim |
| low | float | ✅ Da | Preț minim |
| close | float | ✅ Da | Preț închidere |
| volume | float | ✅ Da | Volum total |
| buy_volume | float | ❌ Opțional | Volum cumpărare |
| sell_volume | float | ❌ Opțional | Volum vânzare |

**Notă:** Dacă `buy_volume` și `sell_volume` nu sunt disponibile, sistemul le va estima din direcția candelei.

---

## 🔧 CONVERTOR CSV GENERIC

Dacă ai date în alt format, poți folosi acest script:

```python
# convert_csv.py
import csv
from datetime import datetime

def convert_generic_csv(input_path, output_path, 
                        timestamp_col='timestamp',
                        timestamp_format='%Y-%m-%d %H:%M:%S',
                        columns_map=None):
    """
    Convertește orice CSV la formatul OIE MVP.
    
    columns_map exemplu:
    {
        'timestamp': 'date',
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close',
        'volume': 'Volume'
    }
    """
    if columns_map is None:
        columns_map = {
            'timestamp': 'timestamp',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume'
        }
    
    with open(input_path, 'r') as inf, open(output_path, 'w', newline='') as outf:
        reader = csv.DictReader(inf)
        writer = csv.DictWriter(outf, fieldnames=[
            'timestamp', 'open', 'high', 'low', 'close', 
            'volume', 'buy_volume', 'sell_volume'
        ])
        writer.writeheader()
        
        for row in reader:
            # Parse timestamp
            ts_raw = row[columns_map['timestamp']]
            try:
                ts = datetime.strptime(ts_raw, timestamp_format)
            except:
                ts = datetime.fromisoformat(ts_raw.replace('Z', '+00:00'))
            
            # Get OHLCV
            o = float(row[columns_map['open']])
            h = float(row[columns_map['high']])
            l = float(row[columns_map['low']])
            c = float(row[columns_map['close']])
            v = float(row[columns_map['volume']])
            
            # Estimate buy/sell volume from candle direction
            if c > o:
                ratio = 0.6  # Green candle = more buying
            elif c < o:
                ratio = 0.4  # Red candle = more selling
            else:
                ratio = 0.5
            
            writer.writerow({
                'timestamp': ts.isoformat(),
                'open': o,
                'high': h,
                'low': l,
                'close': c,
                'volume': v,
                'buy_volume': v * ratio,
                'sell_volume': v * (1 - ratio)
            })
    
    print(f"Convertit: {input_path} -> {output_path}")


# Exemplu utilizare:
# convert_generic_csv('raw_data.csv', 'oie_data.csv',
#                     timestamp_format='%Y-%m-%d %H:%M:%S',
#                     columns_map={'timestamp': 'Date', 'open': 'Open', ...})
```

---

## 🚀 RULARE BACKTEST

### Pasul 1: Descarcă Date

```bash
cd oie_mvp

# Opțiunea A: Folosește data fetcher-ul nostru
python -m backend.backtest.data_fetcher --source binance --symbol BTCUSDT --interval 5m --days 30

# Opțiunea B: Pune CSV-ul propriu în data/historical/
```

### Pasul 2: Rulează Backtest

```bash
# Backtest de bază
python -m backend.backtest.backtest_runner --data data/historical/binance_BTCUSDT_5m.csv

# Cu parametri personalizați
python -m backend.backtest.backtest_runner \
    --data data/historical/binance_BTCUSDT_5m.csv \
    --confidence 0.6 \
    --stop-loss 1.5 \
    --take-profit 3.0 \
    --max-hold 120 \
    --capital 50000 \
    --output results/backtest_btc_5m.json
```

### Pasul 3: Analizează Rezultatele

Raportul va include:
- Win Rate
- Profit Factor
- Sharpe Ratio
- Sortino Ratio
- Max Drawdown
- Performanță per tip semnal

---

## 📊 RECOMANDĂRI PENTRU DATE CURATE

### 1. **Verifică Continuitatea**
- Asigură-te că nu lipsesc bare
- Găurile în date pot afecta calculele

```python
def check_continuity(bars, expected_interval_seconds):
    gaps = []
    for i in range(1, len(bars)):
        diff = (bars[i].timestamp - bars[i-1].timestamp).total_seconds()
        if diff > expected_interval_seconds * 1.5:
            gaps.append((bars[i-1].timestamp, bars[i].timestamp, diff))
    return gaps
```

### 2. **Filtrează Outliers**
- Elimină bare cu volum 0 sau anormal de mare
- Elimină price spikes nerealiste

### 3. **Folosește Perioada Corectă**
- Evită perioade de maintenance exchange
- Evită "flash crashes" dacă nu sunt relevante

### 4. **Testează pe Multiple Perioade**
- In-sample: 70% date (training)
- Out-of-sample: 30% date (validare)

---

## 🔄 WORKFLOW COMPLET BACKTEST

```
1. DESCARCĂ DATE
   └── python -m backend.backtest.data_fetcher ...

2. VERIFICĂ DATE
   └── Check continuitate, outliers, format

3. SPLIT DATE
   └── 70% training / 30% validation

4. OPTIMIZARE PARAMETRI (pe training)
   └── Grid search pe confidence, SL, TP

5. VALIDARE (pe out-of-sample)
   └── Rulează cu parametri optimi

6. WALK-FORWARD (opțional)
   └── Re-optimizează periodic pe ferestre rolling

7. ANALIZĂ REZULTATE
   └── Sharpe > 1.5, Profit Factor > 1.5, Max DD < 20%
```

---

## ⚠️ ATENȚIONĂRI

1. **Delta estimat vs real**
   - Pentru intervale > 7 zile, delta este ESTIMAT din direcția candelei
   - Pentru delta REAL, folosește intervale <= 7 zile sau surse premium

2. **Slippage și comisioane**
   - Backtestul curent NU include slippage
   - Adaugă 0.1% per trade pentru estimări realiste

3. **Survivorship bias**
   - Testează pe coins care au eșuat, nu doar pe BTC/ETH

4. **Overfitting**
   - Nu optimiza prea mult pe aceleași date
   - Folosește always out-of-sample validation

---

## 📁 STRUCTURA FIȘIERE

După instalare, structura va arăta astfel:

```
oie_mvp/
├── backend/
│   └── backtest/
│       ├── __init__.py
│       ├── data_fetcher.py      # Descărcare date
│       └── backtest_runner.py   # Motor backtest
│
├── data/
│   └── historical/              # Date cache-uite
│       ├── binance_BTCUSDT_1m.csv
│       ├── binance_ETHUSDT_5m.csv
│       └── ...
│
└── results/                     # Rezultate backtest
    ├── backtest_btc_1m.json
    └── ...
```

---

## 🎯 NEXT STEPS

1. **Descarcă date inițiale:**
   ```bash
   python -m backend.backtest.data_fetcher --source binance --symbol BTCUSDT --interval 5m --days 14
   ```

2. **Rulează primul backtest:**
   ```bash
   python -m backend.backtest.backtest_runner --data data/historical/binance_BTCUSDT_5m.csv
   ```

3. **Analizează și iterează pe parametri**

---

**Întrebări frecvente?** Deschide un issue sau contactează maintainerul proiectului.
