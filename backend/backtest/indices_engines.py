"""
OIE MVP - Indices Adapted Engines
==================================

Motoare adaptate pentru tranzacționarea indicilor bursieri (S&P 500, Nasdaq, etc.)

Diferențe față de versiunea crypto:
- Praguri mai mici (volatilitate 5-10x mai mică)
- Indicatori tehnici adiționali (RSI, MA)
- Ferestre de calcul mai scurte
- Filtrare pe ore de market
"""

import math
from typing import List, Optional, Tuple
from datetime import datetime, time
from dataclasses import dataclass
from enum import Enum

# Importă modelele existente
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.data.models import Bar
from backend.topology.models import TopologySnapshot, VortexMarker
from backend.predictive.models import PredictiveSnapshot
from backend.signals.models import Signal


# ============================================================================
# INDICATORI TEHNICI
# ============================================================================

def calculate_rsi(closes: List[float], period: int = 14) -> float:
    """Calculează RSI (Relative Strength Index)"""
    if len(closes) < period + 1:
        return 50.0  # Neutral
    
    changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    recent_changes = changes[-(period):]
    
    gains = [c for c in recent_changes if c > 0]
    losses = [-c for c in recent_changes if c < 0]
    
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0.0001
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_sma(values: List[float], period: int) -> float:
    """Calculează Simple Moving Average"""
    if len(values) < period:
        return values[-1] if values else 0
    return sum(values[-period:]) / period


def calculate_ema(values: List[float], period: int) -> float:
    """Calculează Exponential Moving Average"""
    if len(values) < period:
        return values[-1] if values else 0
    
    multiplier = 2 / (period + 1)
    ema = values[0]
    
    for price in values[1:]:
        ema = (price - ema) * multiplier + ema
    
    return ema


def calculate_atr(bars: List[Bar], period: int = 14) -> float:
    """Calculează Average True Range"""
    if len(bars) < 2:
        return 0
    
    true_ranges = []
    for i in range(1, len(bars)):
        high = bars[i].high
        low = bars[i].low
        prev_close = bars[i-1].close
        
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)
    
    if len(true_ranges) < period:
        return sum(true_ranges) / len(true_ranges) if true_ranges else 0
    
    return sum(true_ranges[-period:]) / period


def calculate_bollinger_bands(closes: List[float], period: int = 20, std_mult: float = 2.0) -> Tuple[float, float, float]:
    """Calculează Bollinger Bands (upper, middle, lower)"""
    if len(closes) < period:
        middle = closes[-1] if closes else 0
        return middle, middle, middle
    
    middle = calculate_sma(closes, period)
    
    variance = sum((c - middle) ** 2 for c in closes[-period:]) / period
    std = math.sqrt(variance)
    
    upper = middle + std_mult * std
    lower = middle - std_mult * std
    
    return upper, middle, lower


class TrendDirection(Enum):
    UP = "up"
    DOWN = "down"
    SIDEWAYS = "sideways"


def detect_trend(closes: List[float], short_period: int = 10, long_period: int = 30) -> TrendDirection:
    """Detectează direcția trendului folosind MA crossover"""
    if len(closes) < long_period:
        return TrendDirection.SIDEWAYS
    
    short_ma = calculate_sma(closes, short_period)
    long_ma = calculate_sma(closes, long_period)
    
    diff_pct = ((short_ma - long_ma) / long_ma) * 100
    
    if diff_pct > 0.1:  # Short MA > Long MA cu > 0.1%
        return TrendDirection.UP
    elif diff_pct < -0.1:
        return TrendDirection.DOWN
    else:
        return TrendDirection.SIDEWAYS


# ============================================================================
# TOPOLOGY ENGINE ADAPTAT PENTRU INDICI
# ============================================================================

class IndicesTopologyEngine:
    """
    Motor topologic adaptat pentru indici.
    
    Diferențe față de crypto:
    - Prag vortex mai mic (0.02 vs 0.08)
    - Fereastră mai scurtă (50 vs 100)
    - Energie threshold mai scăzut
    """
    
    def __init__(self, window_size: int = 50):
        self.window_size = window_size
        # Prag mult mai mic pentru indici (volatilitate scăzută)
        self.composite_threshold = 0.02
        self.energy_percentile = 0.60  # 60th percentile vs 70th
    
    def compute(self, symbol: str, bars: List[Bar]) -> TopologySnapshot:
        if len(bars) < 3:
            return TopologySnapshot(
                symbol=symbol,
                timestamp=bars[-1].timestamp if bars else None,
                coherence=0.0,
                energy=0.0,
                vortexes=[]
            )
        
        returns = []
        flows = []
        
        for i in range(len(bars)):
            if i == 0:
                ret = 0.0
            else:
                prev_close = bars[i - 1].close
                ret = 0.0 if prev_close == 0 else (bars[i].close - prev_close) / abs(prev_close)
            returns.append(ret)
            
            if bars[i].volume and bars[i].volume > 0 and bars[i].delta is not None:
                flow = bars[i].delta / bars[i].volume
            else:
                flow = 0.0
            flows.append(flow)
        
        def norm(v):
            return math.sqrt(v[0] * v[0] + v[1] * v[1])
        
        rotations = []
        energies = []
        composite_scores = []
        
        for k in range(1, len(bars) - 1):
            v_prev = (returns[k - 1], flows[k - 1])
            v_next = (returns[k + 1], flows[k + 1])
            
            cross = v_prev[0] * v_next[1] - v_prev[1] * v_next[0]
            denom = norm(v_prev) * norm(v_next)
            
            if denom < 1e-9:
                rot_norm = 0.0
            else:
                rot_norm = cross / denom
            
            rotations.append(rot_norm)
            
            energy_k = abs(returns[k]) * (bars[k].volume or 0.0)
            energies.append(energy_k)
            
            median_energy = sorted(energies)[len(energies)//2] if energies else 1.0
            if median_energy > 0:
                normalized_energy = math.sqrt(energy_k / median_energy)
            else:
                normalized_energy = 0.0
            composite_score = abs(rot_norm) * normalized_energy
            composite_scores.append(composite_score)
        
        if not rotations:
            return TopologySnapshot(
                symbol=symbol,
                timestamp=bars[-1].timestamp,
                coherence=0.0,
                energy=0.0,
                vortexes=[]
            )
        
        coherence = sum(abs(r) for r in rotations) / len(rotations)
        
        sorted_energies = sorted(energies)
        thr_index = int(self.energy_percentile * len(sorted_energies))
        thr_index = max(0, min(thr_index, len(sorted_energies) - 1))
        energy_threshold = sorted_energies[thr_index]
        
        vortex_markers = []
        for k_idx, k in enumerate(range(1, len(bars) - 1)):
            # Prag mai mic pentru indici
            if composite_scores[k_idx] >= self.composite_threshold and energies[k_idx] >= energy_threshold:
                direction = "clockwise" if rotations[k_idx] < 0 else "counterclockwise"
                marker = VortexMarker(
                    index=k,
                    timestamp=bars[k].timestamp,
                    price=bars[k].close,
                    strength=abs(rotations[k_idx]),
                    direction=direction
                )
                vortex_markers.append(marker)
        
        snapshot_energy = energies[-1] if energies else 0.0
        
        return TopologySnapshot(
            symbol=symbol,
            timestamp=bars[-1].timestamp,
            coherence=coherence,
            energy=snapshot_energy,
            vortexes=vortex_markers
        )


# ============================================================================
# SIGNALS ENGINE ADAPTAT PENTRU INDICI
# ============================================================================

@dataclass
class IndicesSignal:
    """Semnal adaptat pentru indici cu indicatori tehnici"""
    symbol: str
    timestamp: datetime
    type: str
    confidence: float
    breakout_probability: float
    IFI: float
    energy_collapse_risk: float
    description: str
    
    # Indicatori adiționali
    rsi: float
    trend: str
    ma_short: float
    ma_long: float
    atr: float
    
    def to_dict(self):
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'type': self.type,
            'confidence': self.confidence,
            'breakout_probability': self.breakout_probability,
            'IFI': self.IFI,
            'energy_collapse_risk': self.energy_collapse_risk,
            'description': self.description,
            'rsi': self.rsi,
            'trend': self.trend,
            'ma_short': self.ma_short,
            'ma_long': self.ma_long,
            'atr': self.atr
        }


class IndicesSignalsEngine:
    """
    Motor de semnale adaptat pentru indici.
    
    Adaugă:
    - Filtrare RSI (evită overbought/oversold)
    - Confirmare trend
    - Praguri mai mici pentru breakout
    - Orele de market
    """
    
    def __init__(
        self,
        breakout_threshold: float = 0.45,  # Mai mic pentru indici (vs 0.6)
        rsi_overbought: float = 70,
        rsi_oversold: float = 30,
        require_trend_confirmation: bool = True
    ):
        self.breakout_threshold = breakout_threshold
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        self.require_trend_confirmation = require_trend_confirmation
        self._last_IFI = {}
    
    def is_market_hours(self, timestamp: datetime) -> bool:
        """Verifică dacă suntem în orele de market US (9:30 - 16:00 EST)"""
        # Simplificat - presupunem timezone local
        t = timestamp.time()
        market_open = time(9, 30)
        market_close = time(16, 0)
        return market_open <= t <= market_close
    
    def compute(
        self,
        symbol: str,
        bars: List[Bar],
        topology: TopologySnapshot,
        predictive: PredictiveSnapshot
    ) -> List[IndicesSignal]:
        """Generează semnale pentru indici"""
        signals = []
        
        if len(bars) < 30:
            return signals
        
        closes = [b.close for b in bars]
        
        # Calculează indicatori
        rsi = calculate_rsi(closes, 14)
        trend = detect_trend(closes, 10, 30)
        ma_short = calculate_sma(closes, 10)
        ma_long = calculate_sma(closes, 30)
        atr = calculate_atr(bars, 14)
        
        # Date predictive
        IFI = predictive.IFI
        bp_up = predictive.breakout_probability_up
        bp_down = predictive.breakout_probability_down
        ecr = predictive.energy_collapse_risk
        timestamp = predictive.timestamp
        
        # IFI crescător
        last_IFI = self._last_IFI.get(symbol)
        IFI_rising = last_IFI is not None and IFI > last_IFI
        self._last_IFI[symbol] = IFI
        
        # Vortex prezent
        has_vortex = len(topology.vortexes) > 0
        
        # ====== SEMNAL LONG ======
        if bp_up >= self.breakout_threshold:
            # Filtre pentru LONG
            rsi_ok = rsi < self.rsi_overbought  # Nu cumpăra în overbought
            trend_ok = trend != TrendDirection.DOWN if self.require_trend_confirmation else True
            
            if rsi_ok and trend_ok:
                # Calculează confidence bazat pe factori
                base_confidence = 0.4 + (bp_up - self.breakout_threshold)
                
                # Boost pentru trend confirmat
                if trend == TrendDirection.UP:
                    base_confidence += 0.15
                
                # Boost pentru RSI în oversold
                if rsi < self.rsi_oversold:
                    base_confidence += 0.10
                
                # Boost pentru vortex
                if has_vortex:
                    base_confidence += 0.10
                
                # Boost pentru IFI crescător
                if IFI_rising:
                    base_confidence += 0.05
                
                confidence = min(1.0, base_confidence)
                
                signals.append(IndicesSignal(
                    symbol=symbol,
                    timestamp=timestamp,
                    type="indices_breakout_long",
                    confidence=confidence,
                    breakout_probability=bp_up,
                    IFI=IFI,
                    energy_collapse_risk=ecr,
                    description=f"Long signal: RSI={rsi:.1f}, Trend={trend.value}, MA cross bullish",
                    rsi=rsi,
                    trend=trend.value,
                    ma_short=ma_short,
                    ma_long=ma_long,
                    atr=atr
                ))
        
        # ====== SEMNAL SHORT ======
        elif bp_down >= self.breakout_threshold:
            # Filtre pentru SHORT
            rsi_ok = rsi > self.rsi_oversold  # Nu vinde în oversold
            trend_ok = trend != TrendDirection.UP if self.require_trend_confirmation else True
            
            if rsi_ok and trend_ok:
                base_confidence = 0.4 + (bp_down - self.breakout_threshold)
                
                if trend == TrendDirection.DOWN:
                    base_confidence += 0.15
                
                if rsi > self.rsi_overbought:
                    base_confidence += 0.10
                
                if has_vortex:
                    base_confidence += 0.10
                
                if IFI_rising:
                    base_confidence += 0.05
                
                confidence = min(1.0, base_confidence)
                
                signals.append(IndicesSignal(
                    symbol=symbol,
                    timestamp=timestamp,
                    type="indices_breakout_short",
                    confidence=confidence,
                    breakout_probability=bp_down,
                    IFI=IFI,
                    energy_collapse_risk=ecr,
                    description=f"Short signal: RSI={rsi:.1f}, Trend={trend.value}, MA cross bearish",
                    rsi=rsi,
                    trend=trend.value,
                    ma_short=ma_short,
                    ma_long=ma_long,
                    atr=atr
                ))
        
        # ====== SEMNAL NEUTRAL ======
        else:
            max_bp = max(bp_up, bp_down)
            confidence = max(0.0, min(1.0, 1.0 - max_bp))
            
            signals.append(IndicesSignal(
                symbol=symbol,
                timestamp=timestamp,
                type="indices_neutral_watch",
                confidence=confidence,
                breakout_probability=max_bp,
                IFI=IFI,
                energy_collapse_risk=ecr,
                description=f"Neutral: RSI={rsi:.1f}, Trend={trend.value}, waiting for setup",
                rsi=rsi,
                trend=trend.value,
                ma_short=ma_short,
                ma_long=ma_long,
                atr=atr
            ))
        
        return signals


# ============================================================================
# CONFIGURAȚIE SPECIALĂ PENTRU INDICI
# ============================================================================

@dataclass
class IndicesBacktestConfig:
    """Configurație backtest optimizată pentru indici"""
    
    # Ferestre mai scurte
    topology_window: int = 50
    predictive_window: int = 100
    
    # Praguri mai mici (volatilitate redusă)
    min_confidence: float = 0.45
    max_hold_bars: int = 20  # ~5h la 15m
    
    # Stop loss/Take profit mai mici
    stop_loss_pct: float = 0.3   # 0.3% stop loss
    take_profit_pct: float = 0.6  # 0.6% take profit
    
    # ATR-based stops (opțional)
    use_atr_stops: bool = True
    atr_stop_mult: float = 1.5
    atr_tp_mult: float = 2.5
    
    # Filtre
    min_IFI: float = 0.0
    require_vortex: bool = False
    require_trend_confirmation: bool = True
    
    # RSI filters
    rsi_overbought: float = 70
    rsi_oversold: float = 30
    
    # Capital
    initial_capital: float = 10000.0
    position_size_pct: float = 50.0  # Mai conservator


# Export pentru utilizare în backtest runner
__all__ = [
    'IndicesTopologyEngine',
    'IndicesSignalsEngine',
    'IndicesSignal',
    'IndicesBacktestConfig',
    'calculate_rsi',
    'calculate_sma',
    'calculate_ema',
    'calculate_atr',
    'calculate_bollinger_bands',
    'detect_trend',
    'TrendDirection'
]
