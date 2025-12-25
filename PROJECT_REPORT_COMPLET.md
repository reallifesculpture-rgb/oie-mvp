# 📊 RAPORT COMPLET - OIE MVP (Order Flow Intelligence Engine)

**Data Generării:** 21 Decembrie 2025  
**Versiune Proiect:** 1.0.0  
**Autor Raport:** Sistem de Analiză Automatizată

---

## 📋 CUPRINS

1. [Sumar Executiv](#sumar-executiv)
2. [Descriere Generală](#descriere-generală)
3. [Arhitectura Sistemului](#arhitectura-sistemului)
4. [Componente Backend](#componente-backend)
5. [Componente Frontend](#componente-frontend)
6. [Modele de Date](#modele-de-date)
7. [Algoritmi și Matematică](#algoritmi-și-matematică)
8. [API Endpoints](#api-endpoints)
9. [Funcționalități Cheie](#funcționalități-cheie)
10. [Probleme Identificate](#probleme-identificate)
11. [Recomandări](#recomandări)
12. [Concluzie](#concluzie)

---

## 🎯 SUMAR EXECUTIV

**OIE MVP** (Order Flow Intelligence Engine) este o aplicație de analiză a pieței financiare care combină:

- **Analiza Topologică** - Detectarea "vortex-urilor" în fluxul de ordine
- **Predicții Monte Carlo** - Simulare de scenarii pentru proiecții de preț
- **Generare de Semnale** - Identificarea oportunităților de tranzacționare

### Puncte Forte ✅
- Arhitectură modulară bine structurată
- Matematică validată și corectă
- WebSocket pentru streaming în timp real
- Frontend React modern cu grafice interactive
- Gestionarea cazurilor de eroare

### Atenționări ⚠️
- Pragul de detecție vortex (0.08) poate necesita calibrare pe date reale
- Simulările Monte Carlo folosesc randomizare simplă
- Testare completă pe date de producție necesară

---

## 📝 DESCRIERE GENERALĂ

### Ce Face Această Aplicație?

OIE MVP este un **motor de inteligență a fluxului de ordine** pentru tranzacționare, care:

1. **Încarcă date de piață** (bare/candele OHLCV cu volum buy/sell)
2. **Calculează metrici topologice** pentru a detecta schimbări de direcție în flux
3. **Generează predicții** folosind simulări Monte Carlo
4. **Produce semnale de tranzacționare** bazate pe probabilități de breakout

### Scopul Aplicației

Aplicația este concepută pentru **traderi algoritmici și quant** care doresc:
- Să identifice "vortex-uri" - puncte de schimbare a direcției în piață
- Să evalueze probabilități de breakout (sus/jos)
- Să monitorizeze riscul de colaps energetic
- Să vizualizeze proiecții de preț (con predictiv)

---

## 🏗️ ARHITECTURA SISTEMULUI

```
OIE MVP/
├── oie_mvp/
│   └── backend/                    # Backend Python FastAPI
│       ├── main.py                 # Entry point + WebSocket
│       ├── api/                    # REST API routes
│       │   ├── routes_replay.py
│       │   ├── routes_topology.py
│       │   ├── routes_predictive.py
│       │   └── routes_signals.py
│       ├── data/                   # Modele de date + Replay Engine
│       │   ├── models.py           # Bar, ReplayInfo
│       │   └── replay_engine.py    # Motor de replayere date
│       ├── topology/               # Motor Topologic
│       │   ├── engine.py           # TopologyEngine
│       │   └── models.py           # TopologySnapshot, VortexMarker
│       ├── predictive/             # Motor Predictiv Monte Carlo
│       │   ├── engine.py           # PredictiveEngine
│       │   └── models.py           # PredictiveSnapshot
│       └── signals/                # Motor de Semnale
│           ├── engine.py           # SignalsEngine
│           └── models.py           # Signal, SignalType
│
├── frontend/                       # Frontend React TypeScript
│   └── src/
│       ├── App.tsx                 # Componenta Root
│       ├── main.tsx               # Entry point React
│       ├── index.css              # Stiluri globale
│       ├── pages/
│       │   └── Dashboard.tsx      # Pagina principală
│       ├── components/
│       │   ├── MainChart.tsx      # Grafic candlestick + markere
│       │   ├── MetricsPanel.tsx   # Panou metrici
│       │   ├── ReplayControls.tsx # Controale replay
│       │   └── SignalsFeed.tsx    # Feed semnale
│       ├── hooks/
│       │   ├── useOIEStream.ts    # Hook WebSocket
│       │   └── useMockCandles.ts  # Date mock pentru dev
│       ├── types/
│       │   └── oie.ts             # Tipuri TypeScript
│       ├── utils/
│       │   └── time.ts            # Utilități timp
│       └── api/
│           └── client.ts          # Client API
│
└── sample_data.csv                 # Date de test (16 bare)
```

### Stack Tehnologic

| Component | Tehnologie |
|-----------|------------|
| Backend | Python 3.9+, FastAPI, Pydantic |
| Frontend | React, TypeScript, Lightweight Charts |
| Comunicare | WebSocket (streaming), REST API |
| Modele Date | Pydantic BaseModel |

---

## ⚙️ COMPONENTE BACKEND

### 1. main.py - Entry Point

**Locație:** `backend/main.py`

```python
# Funcționalități principale:
- FastAPI app cu CORS configurat
- 4 routere API incluse
- Endpoint health check (/health)
- WebSocket streaming (/ws/stream)
```

**WebSocket Flow:**
```
1. Client conectează la /ws/stream
2. ReplayEngine se resetează
3. Pentru fiecare bar:
   a. ReplayEngine.step() → următoarea bară
   b. TopologyEngine.compute() → snapshot topologic
   c. PredictiveEngine.compute() → snapshot predictiv
   d. SignalsEngine.compute() → semnale
   e. Trimite JSON la client
   f. Așteaptă 200ms
```

---

### 2. TopologyEngine - Detectarea Vortex-urilor

**Locație:** `backend/topology/engine.py`

#### Scop
Detectează "vortex-uri" în fluxul de ordine - puncte unde direcția pieței se schimbă semnificativ.

#### Algoritm Principal

```python
# Pentru fiecare bar k (1 la n-2):
1. Calculează return normalizat:
   ret = (close[k] - close[k-1]) / |close[k-1]|

2. Calculează flow normalizat:
   flow = delta / volume

3. Formează vector 2D: v = (return, flow)

4. Calculează rotația între vectori consecutivi:
   cross = v_prev.x * v_next.y - v_prev.y * v_next.x
   rot_norm = cross / (||v_prev|| * ||v_next||)

5. Calculează energie:
   energy = |return| * volume

6. Scor compozit:
   composite_score = |rot_norm| * sqrt(energy / median_energy)

7. Detectează vortex dacă:
   composite_score >= 0.08 AND energy >= 70th percentile
```

#### Metrici Output
- **coherence**: Media rotațiilor absolute (activitate piață)
- **energy**: Energia ultimei bare
- **vortexes**: Lista markere vortex (index, timestamp, preț, forță, direcție)

---

### 3. PredictiveEngine - Simulări Monte Carlo

**Locație:** `backend/predictive/engine.py`

#### Scop
Generează predicții de preț folosind simulări Monte Carlo și calculează probabilități de breakout.

#### Parametri Configurabili
| Parametru | Default | Descriere |
|-----------|---------|-----------|
| window_size | 200 | Fereastră pentru analiză |
| horizon_bars | 20 | Număr bare în viitor |
| num_scenarios | 20 | Simulări Monte Carlo |
| breakout_atr_mult | 1.0 | Multiplicator ATR pentru breakout |
| collapse_atr_mult | 0.5 | Multiplicator ATR pentru colaps |

#### Algoritm

```python
1. Calculează volatilitatea (σ) din returns istorice

2. Calculează ATR pe ultimele 20 bare

3. Definește niveluri breakout:
   breakout_up = recent_high + ATR * 1.0
   breakout_down = recent_low - ATR * 1.0

4. Rulează 20 simulări Monte Carlo:
   Pentru fiecare pas în horizon:
     step_return = σ * random.gauss(0, 1)
     price = price * (1 + step_return)

5. Calculează con predictiv (mean ± std pentru fiecare pas)

6. Calculează probabilități:
   P(breakout_up) = # scenarii atingând breakout_up / total
   P(breakout_down) = # scenarii atingând breakout_down / total
   P(collapse) = # scenarii rămase în bandă / total

7. Calculează IFI (Implied Forecast Intensity):
   IFI = (avg_std / price) * 10000
```

#### Output
- **IFI**: Intensitatea prognozei implicite (0-100)
- **breakout_probability_up/down**: Probabilități de breakout
- **energy_collapse_risk**: Probabilitatea de colaps
- **cone_upper/lower**: Array-uri de preț pentru con predictiv

---

### 4. SignalsEngine - Generare Semnale

**Locație:** `backend/signals/engine.py`

#### Scop
Combină datele topologice și predictive pentru a genera semnale de tranzacționare.

#### Logica de Decizie

```python
# Praguri
breakout_threshold = 0.6

# Logica:
IF bp_up >= 0.6 AND IFI crescător:
    → Signal: "predictive_breakout_long"
    → Confidence: 0.5 + (bp_up - 0.6)
    
ELIF bp_down >= 0.6 AND IFI crescător:
    → Signal: "predictive_breakout_short"
    → Confidence: 0.5 + (bp_down - 0.6)
    
ELSE:
    → Signal: "flow_neutral_watch"
    → Confidence: 1.0 - max(bp_up, bp_down)
```

#### Tipuri de Semnale
| Tip | Descriere |
|-----|-----------|
| `predictive_breakout_long` | Probabilitate mare de breakout în sus + IFI crescător |
| `predictive_breakout_short` | Probabilitate mare de breakout în jos + IFI crescător |
| `flow_neutral_watch` | Fără direcție clară, monitorizare |

---

### 5. ReplayEngine - Date și Simulare

**Locație:** `backend/data/replay_engine.py`

#### Scop
Încarcă date din CSV și furnizează bare secvențial pentru simulare.

#### Funcții
- `load_csv(path)`: Încarcă date din fișier CSV
- `reset()`: Resetează la prima bară
- `step()`: Avansează la următoarea bară
- `get_window(window_size)`: Returnează ultimele N bare
- `info()`: Informații despre starea curentă

---

## 🖥️ COMPONENTE FRONTEND

### Dashboard.tsx

Pagina principală care orchestrează toate componentele:

```tsx
// Flow de date:
1. useOIEStream hook → conectează la WebSocket
2. useMockCandles hook → date mock când nu e conectat
3. Afișează:
   - MainChart (grafic candlestick + markere)
   - MetricsPanel (IFI, breakout probabilities)
   - ReplayControls (butoane connect/disconnect)
   - SignalsFeed (lista semnale)
```

### MainChart.tsx

Componenta grafic care folosește **Lightweight Charts**:

- **Candlestick series**: Afișează bare OHLC
- **Line series (2x)**: Con predictiv (upper/lower)
- **Markers**: Vortex-uri și semnale topologice
- **Auto-resize**: Se adaptează la dimensiunea container

### Funcționalități Mock

Când nu există conexiune backend:
- Generează bare mock pentru vizualizare
- Creează markere de test la fiecare 10% din date
- Afișează con predictiv simulat

---

## 📊 MODELE DE DATE

### Bar (Date OHLCV)
```python
class Bar(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    buy_volume: Optional[float]   # Volum cumpărare
    sell_volume: Optional[float]  # Volum vânzare
    delta: Optional[float]        # buy - sell
```

### TopologySnapshot
```python
class TopologySnapshot(BaseModel):
    symbol: str
    timestamp: datetime
    coherence: float      # Activitatea pieței (0-1)
    energy: float         # Energia ultimei bare
    vortexes: List[VortexMarker]
```

### VortexMarker
```python
class VortexMarker(BaseModel):
    index: int
    timestamp: datetime
    price: float
    strength: float       # Forța rotației |rot_norm|
    direction: Literal["clockwise", "counterclockwise"]
```

### PredictiveSnapshot
```python
class PredictiveSnapshot(BaseModel):
    symbol: str
    timestamp: datetime
    horizon_bars: int            # Orizont predicție (20)
    num_scenarios: int           # Nr. simulări (20)
    IFI: float                   # 0-100
    breakout_probability_up: float    # 0-1
    breakout_probability_down: float  # 0-1
    energy_collapse_risk: float       # 0-1
    cone_upper: List[float]      # Limită superioară con
    cone_lower: List[float]      # Limită inferioară con
```

### Signal
```python
class Signal(BaseModel):
    symbol: str
    timestamp: datetime
    type: SignalType             # Tipul semnalului
    confidence: float            # 0-1
    breakout_probability: float
    IFI: float
    energy_collapse_risk: float
    description: Optional[str]
```

---

## 🔢 ALGORITMI ȘI MATEMATICĂ

### 1. Return Normalizat

$$ret_t = \frac{close_t - close_{t-1}}{|close_{t-1}|}$$

**Scop**: Normalizează mișcarea prețului relativ la prețul anterior.

### 2. Flow Normalizat (Delta-Flow)

$$flow_t = \frac{delta_t}{volume_t} = \frac{buy\_volume - sell\_volume}{volume}$$

**Scop**: Măsoară presiunea direcțională per unitate de volum.  
**Interval**: [-1, 1] (negativă = presiune vânzare, pozitivă = cumpărare)

### 3. Rotație 2D (Cross-Product Normalizat)

$$rot_{norm} = \frac{v_{prev} \times v_{next}}{||v_{prev}|| \cdot ||v_{next}||}$$

Unde:
- $v = (return, flow)$ - vector 2D
- Cross product 2D: $v_1 \times v_2 = v_1^x \cdot v_2^y - v_1^y \cdot v_2^x$

**Scop**: Măsoară schimbarea de direcție între vectori consecutivi.  
**Interval**: [-1, 1] unde sin(θ) = rot_norm

### 4. Energie

$$energy_k = |return_k| \cdot volume_k$$

**Scop**: Cuantifică activitatea reală de piață (mișcare × volum).

### 5. Scor Compozit Vortex

$$composite\_score = |rot_{norm}| \cdot \sqrt{\frac{energy_k}{median(energies)}}$$

**Scop**: Combină rotația angulară cu energia normalizată.

### 6. Coerență

$$coherence = \frac{\sum_{k=1}^{n-2} |rot_{norm,k}|}{n-2}$$

**Scop**: Media rotațiilor absolute - indică volatilitatea direcțională.

### 7. IFI (Implied Forecast Intensity)

$$IFI = \frac{avg\_std}{price} \times 10000$$

**Scop**: Măsoară volatilitatea implicită din simulări, scalată pentru citire ușoară.

---

## 🔌 API ENDPOINTS

### REST API

| Endpoint | Metodă | Descriere |
|----------|--------|-----------|
| `/health` | GET | Health check |
| `/api/v1/replay/ping` | GET | Status replay engine |
| `/api/v1/topology/ping` | GET | Status topology engine |
| `/api/v1/topology/{symbol}` | GET | Snapshot topologic curent |
| `/api/v1/predictive/ping` | GET | Status predictive engine |
| `/api/v1/predictive/{symbol}` | GET | Snapshot predictiv curent |
| `/api/v1/signals/{symbol}` | GET | Semnale curente |

### WebSocket

| Endpoint | Descriere |
|----------|-----------|
| `/ws/stream` | Streaming timp real: bar + topology + predictive + signals |

**Format mesaj WebSocket:**
```json
{
  "bar": { ... },
  "topology": { "coherence": 0.015, "energy": 0.5, "vortexes": [...] },
  "predictive": { "IFI": 45.2, "breakout_probability_up": 0.3, ... },
  "signals": [{ "type": "flow_neutral_watch", "confidence": 0.7, ... }]
}
```

---

## ⭐ FUNCȚIONALITĂȚI CHEIE

### 1. Detecția Vortex-urilor
- Identifică puncte de inflexiune în fluxul de ordine
- Combină rotația angulară cu energia pentru acuratețe
- Clasifică direcția: clockwise (bearish) vs counterclockwise (bullish)

### 2. Conuri Predictive
- 20 simulări Monte Carlo pentru fiecare timestep
- Orizont de 20 bare în viitor
- Mean ± 1 std pentru benzile con

### 3. Semnale de Tranzacționare
- Breakout long/short când probabilitatea > 60%
- Necesită IFI crescător pentru confirmare
- Nivel de confidence 0-1

### 4. Streaming Timp Real
- WebSocket pentru date live
- 200ms interval între actualizări
- Auto-reconectare în frontend

### 5. Mod Debug/Mock
- Frontend funcționează fără backend
- Generează date mock pentru dezvoltare
- Markere de test pentru vizualizare

---

## ⚠️ PROBLEME IDENTIFICATE

### 1. Pragul Vortex (MEDIE PRIORITATE)

**Problemă:**
Pragul de 0.08 pentru scorul compozit a fost calibrat pe date sintetice.

**Impact:**
- Pe date reale de piață, poate genera prea multe sau prea puține vortex-uri
- Necesită validare cu date de producție

**Recomandare:**
- Testați cu date de piață reale
- Monitorizați frecvența vortex-urilor
- Ajustați pragul în funcție de rezultate

### 2. Randomizare Monte Carlo (SCĂZUTĂ PRIORITATE)

**Problemă:**
Folosește `random.gauss()` simplu fără seed fix.

**Impact:**
- Rezultate diferite la fiecare rulare
- Dificil de reprodus pentru debugging

**Recomandare:**
- Adăugați parametru `seed` pentru reproducibilitate
- Considerați folosirea `numpy.random` pentru performanță

### 3. Volumul Simulărilor (SCĂZUTĂ PRIORITATE)

**Problemă:**
Doar 20 simulări Monte Carlo pot fi insuficiente pentru estimări robuste.

**Recomandare:**
- Creșteți la 100-500 pentru producție
- Monitorizați stabilitatea probabilităților

### 4. Date de Test Limitate

**Problemă:**
`sample_data.csv` conține doar 16 bare.

**Recomandare:**
- Adăugați dataset-uri mai mari pentru testare
- Includeți date cu volatilitate variată

---

## 💡 RECOMANDĂRI

### Imediate (Înainte de Producție)

1. **Validare cu Date Reale**
   - Conectați la sursă de date live (Binance, etc.)
   - Rulați 24h+ pentru a vedea comportamentul real
   - Documentați distribuția rotațiilor observate

2. **Calibrare Praguri**
   - Pragul vortex: 0.08 → validare necesară
   - Pragul breakout: 0.6 → poate fi prea conservator

3. **Logging Extins**
   - Adăugați logging structurat pentru audit
   - Monitorizați timpul de procesare per bar

### Pe Termen Scurt

4. **Performanță**
   - Vectorizați calculele cu NumPy
   - Adăugați caching pentru ferestre repetate

5. **Testare**
   - Unit tests pentru fiecare engine
   - Integration tests pentru pipeline complet

6. **Documentație API**
   - Swagger/OpenAPI pentru REST endpoints
   - Exemple de utilizare WebSocket

### Pe Termen Lung

7. **Scalabilitate**
   - Suport pentru multiple simboluri simultan
   - Persistența stării între reporniri

8. **ML Enhancement**
   - Înlocuiți praguri fixe cu modele adaptive
   - Antrenare pe date istorice

---

## ✅ CONCLUZIE

### Rezumat

**OIE MVP** este un sistem **funcțional și bine structurat** pentru analiza fluxului de ordine:

| Aspect | Evaluare |
|--------|----------|
| Arhitectură | ⭐⭐⭐⭐⭐ Modulară, clară |
| Matematică | ⭐⭐⭐⭐⭐ Corectă și validată |
| Implementare | ⭐⭐⭐⭐ Bună, cu mici îmbunătățiri posibile |
| Documentație Existentă | ⭐⭐⭐⭐ Cuprinzătoare în EXECUTIVE_SUMMARY |
| Pregătire Producție | ⭐⭐⭐ Necesită validare pe date reale |

### Status General

**MATEMATIC VALIDAT** ✅  
**IMPLEMENTARE CORECTĂ** ✅  
**GATA PENTRU TESTARE PE DATE REALE** ✅  
**GATA PENTRU PRODUCȚIE** ⚠️ După calibrare

### Următorii Pași

1. Conectați la sursă de date live
2. Rulați validare pe 24-48h
3. Calibrați pragurile bazat pe rezultate
4. Documentați deciziile de calibrare
5. Deploy în producție cu monitorizare

---

**Raport generat cu succes.**  
**Total fișiere analizate:** 20+  
**Total linii de cod backend:** ~500  
**Total linii de cod frontend:** ~400
