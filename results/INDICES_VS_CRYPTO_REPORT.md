# 📊 RAPORT BACKTEST - INDICI US vs CRYPTO

**Data:** 21 Decembrie 2025

---

## 🎯 SUMAR

Am testat strategia OIE MVP pe multiple piețe:

### CRYPTO (1 an de date)
| Simbol | Interval | Trades | Win Rate | P&L | Sharpe |
|--------|----------|--------|----------|-----|--------|
| **BTCUSDT** | 15m | 612 | 47.9% | **+$42,328** | 1.02 ✅ |
| **ETHUSDT** | 15m | 334 | 49.1% | **+$1,306** | 1.44 ✅ |

### INDICI US (60 zile de date - limitare yfinance)
| Simbol | Interval | Trades | Win Rate | P&L | Sharpe |
|--------|----------|--------|----------|-----|--------|
| **SPY** | 15m | 29 | 51.7% | -$8.32 | -1.16 ❌ |
| **QQQ** | 15m | 30 | 33.3% | -$39.51 | -5.37 ❌ |

---

## 🔍 ANALIZĂ

### De ce strategia funcționează PE CRYPTO dar NU pe INDICI US?

1. **Volatilitatea diferită**
   - Crypto: 2-5% mișcări zilnice normale
   - Indici US: 0.5-1% mișcări zilnice normale
   - Pragurile noastre (1% SL, 2% TP) sunt calibrate pentru crypto

2. **Order Flow (Delta) diferit**
   - Crypto: Delta real disponibil din buy/sell volume
   - Indici: Delta estimat din direcția candelei (mai puțin precis)

3. **Perioade de tranzacționare**
   - Crypto: 24/7
   - Indici: Doar în orele de market (9:30-16:00 EST)

4. **Lichiditate și microstructură**
   - Crypto: Multe retail traders, semnale orderflow mai clare
   - Indici: Dominate de instituționali, semnale mai noise

---

## ✅ CE FUNCȚIONEAZĂ

### CRYPTO
- ✅ BTCUSDT: +$42,328 profit (Sharpe 1.02)
- ✅ ETHUSDT: +$1,306 profit (Sharpe 1.44)
- ✅ Semnale SHORT performează mai bine în bear market

**Parametri Optimali pentru Crypto:**
```
Confidence: 0.60
Stop Loss: 1.0%
Take Profit: 2.0%
Max Hold: 30 bare
```

---

## 🔧 RECOMANDĂRI PENTRU INDICI US

Dacă vrei să adaptezi strategia pentru indici, ai nevoie de:

### 1. Parametri Ajustați pentru Volatilitate Mai Mică
```
Confidence: 0.55 (mai permisiv)
Stop Loss: 0.2-0.3%
Take Profit: 0.4-0.6%
Max Hold: 10-15 bare
```

### 2. Date cu Delta Real
- **Tardis.dev** - date cu order book și delta real (~$50/lună)
- **Polygon.io** - date intraday cu volume (gratuit tier)
- **Interactive Brokers API** - dacă ai cont IB

### 3. Indici CFD în loc de ETF-uri
- Multe platforme forex oferă CFD-uri pe indici cu:
  - US500 (S&P 500)
  - US100 (Nasdaq 100)
  - US30 (Dow Jones)
- Acestea pot avea date mai bune pentru orderflow

### 4. Timeframe Mai Mare
- Pentru indici, încearcă 1h sau 4h în loc de 15m
- Semnalele sunt mai clare pe timeframe mai mare

---

## 📁 DATE DISPONIBILE

Am descărcat și salvat:

### Crypto (Binance):
- `binance_BTCUSDT_15m.csv` - 35,040 bare (1 an)
- `binance_BTCUSDT_5m.csv` - 51,852 bare (6 luni)
- `binance_ETHUSDT_15m.csv` - 35,040 bare (1 an)

### Indici (Yahoo Finance):
- `yahoo_SPY_15m.csv` - 1,070 bare (60 zile) - S&P 500 ETF
- `yahoo_QQQ_15m.csv` - 1,070 bare (60 zile) - Nasdaq 100 ETF
- `yahoo_US30_15m.csv` - 1,070 bare (60 zile) - Dow Jones
- `yahoo_SPY_1d.csv` - 249 bare (1 an) - Daily data
- `yahoo_QQQ_1d.csv` - 249 bare (1 an) - Daily data

---

## 🚀 NEXT STEPS

### Pentru Crypto:
1. ✅ Strategia este GATA pentru paper trading
2. Implementează în aplicația principală
3. Monitorizează performanța live

### Pentru Indici US:
1. Găsește sursă de date cu delta real
2. Recalibrează pragurile pentru volatilitate mai mică
3. Testează pe timeframe mai mare (1h, 4h)
4. Consideră alte indicatori (RSI, MACD) pentru confirmare

---

## 📋 CONCLUZIE FINALĂ

| Piață | Status | Recomandare |
|-------|--------|-------------|
| **BTCUSDT** | ✅ PROFITABIL | Continuă cu paper trading |
| **ETHUSDT** | ✅ PROFITABIL | Continuă cu paper trading |
| **SPY/US500** | ❌ NEPROFITABIL | Necesită recalibrare |
| **QQQ/US100** | ❌ NEPROFITABIL | Necesită recalibrare |

**Strategia OIE MVP este optimizată pentru piețele CRYPTO!**

Pentru indici US, ar trebui creată o variantă separată cu:
- Praguri mai mici
- Date cu delta real
- Timeframe mai mare
- Posibil indicatori adiționali
