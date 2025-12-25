from typing import List, Dict, Optional
from collections import deque

from backend.topology.models import TopologySnapshot
from backend.predictive.models import PredictiveSnapshot
from backend.signals.models import Signal, SignalType
from backend.data.models import Bar


class SignalsEngine:
    def __init__(
        self,
        breakout_threshold_long: float = 0.60,   # 60% pentru LONG (performanță mai bună)
        breakout_threshold_short: float = 0.65,  # 65% pentru SHORT (necesită confirmare mai puternică)
        delta_lookback: int = 10,  # Număr de lumânări pentru delta cumulativ
        delta_threshold: float = 0.6,  # Procentaj minim din volume ca delta trend
        min_delta_strength: float = 0.30,  # Minim 30% delta strength pentru semnale valide
        block_contratrend: bool = True,  # Blochează semnale contratrend puternice
    ) -> None:
        self.breakout_threshold_long = breakout_threshold_long
        self.breakout_threshold_short = breakout_threshold_short
        self.delta_lookback = delta_lookback
        self.delta_threshold = delta_threshold
        self.min_delta_strength = min_delta_strength
        self.block_contratrend = block_contratrend
        self._last_IFI: Dict[str, float] = {}
        self._bars_history: Dict[str, deque] = {}  # Istoricul barelor per simbol

    def update_bars(self, symbol: str, bars: List[Bar]):
        """Actualizează istoricul barelor pentru calcul delta trend"""
        if symbol not in self._bars_history:
            self._bars_history[symbol] = deque(maxlen=self.delta_lookback)

        # Adaugă barele noi (sau înlocuiește cu ultimele)
        self._bars_history[symbol].clear()
        for bar in bars[-self.delta_lookback:]:
            self._bars_history[symbol].append(bar)

    def _compute_delta_trend(self, symbol: str) -> tuple:
        """
        Calculează trendul bazat pe Delta cumulativ al ultimelor N lumânări.

        Returns:
            (trend_direction, trend_strength)
            trend_direction: 'BULLISH', 'BEARISH', sau 'NEUTRAL'
            trend_strength: 0.0 - 1.0 (cât de puternic este trendul)
        """
        if symbol not in self._bars_history or len(self._bars_history[symbol]) < 3:
            return 'NEUTRAL', 0.0

        bars = list(self._bars_history[symbol])

        # Calculează delta cumulativ și volume total
        cumulative_delta = 0.0
        total_volume = 0.0

        for bar in bars:
            if bar.delta is not None:
                cumulative_delta += bar.delta
            elif bar.buy_volume is not None and bar.sell_volume is not None:
                cumulative_delta += (bar.buy_volume - bar.sell_volume)

            if bar.volume:
                total_volume += bar.volume

        if total_volume == 0:
            return 'NEUTRAL', 0.0

        # Delta ratio: ce procent din volume este în direcția dominantă
        delta_ratio = abs(cumulative_delta) / total_volume

        # Normalizare: dacă delta_ratio > threshold, avem trend clar
        trend_strength = min(1.0, delta_ratio / self.delta_threshold)

        if cumulative_delta > 0 and delta_ratio > 0.1:  # Minim 10% bias pentru trend
            return 'BULLISH', trend_strength
        elif cumulative_delta < 0 and delta_ratio > 0.1:
            return 'BEARISH', trend_strength
        else:
            return 'NEUTRAL', trend_strength

    def compute(
        self,
        symbol: str,
        topology: TopologySnapshot,
        predictive: PredictiveSnapshot,
        bars: Optional[List[Bar]] = None,  # Opțional: pentru delta trend
    ) -> List[Signal]:
        signals: List[Signal] = []

        # Update bars history dacă sunt furnizate
        if bars:
            self.update_bars(symbol, bars)

        IFI = predictive.IFI
        bp_up = predictive.breakout_probability_up
        bp_down = predictive.breakout_probability_down
        ecr = predictive.energy_collapse_risk
        timestamp = predictive.timestamp

        last_IFI = self._last_IFI.get(symbol)
        IFI_rising = last_IFI is not None and IFI > last_IFI
        self._last_IFI[symbol] = IFI

        # Calculează delta trend
        delta_trend, delta_strength = self._compute_delta_trend(symbol)

        # BLOCARE CONTRATREND: Nu genera LONG când delta e puternic BEARISH
        if self.block_contratrend and delta_trend == 'BEARISH' and delta_strength >= 0.5:
            # Skip LONG signal - piața merge în direcția opusă
            pass
        # LONG signal: bp_up + IFI_rising + delta trend BULLISH (sau NEUTRAL)
        elif bp_up >= self.breakout_threshold_long and IFI_rising:
            # Verifică delta strength minim pentru semnal valid
            if delta_trend != 'NEUTRAL' and delta_strength < self.min_delta_strength:
                # Delta prea slab - semnal incert, skip
                pass
            else:
                base_confidence = 0.5 + (bp_up - self.breakout_threshold_long)

                # Ajustează confidence bazat pe delta trend
                if delta_trend == 'BULLISH':
                    # Delta confirmă direcția - boost confidence
                    confidence = min(1.0, base_confidence + delta_strength * 0.25)
                    description = f"LONG: bp_up={bp_up:.0%}, IFI rising, Delta BULLISH ({delta_strength:.0%})"
                elif delta_trend == 'BEARISH':
                    # Delta contratrend - penalizare severă
                    confidence = max(0.0, base_confidence - delta_strength * 0.5)
                    description = f"LONG WEAK: bp_up={bp_up:.0%}, but Delta BEARISH ({delta_strength:.0%})"
                else:
                    confidence = base_confidence
                    description = f"LONG: bp_up={bp_up:.0%}, IFI rising, Delta neutral"

                signals.append(
                    Signal(
                        symbol=symbol,
                        timestamp=timestamp,
                        type="predictive_breakout_long",
                        confidence=confidence,
                        breakout_probability=bp_up,
                        IFI=IFI,
                        energy_collapse_risk=ecr,
                        description=description,
                    )
                )

        # BLOCARE CONTRATREND: Nu genera SHORT când delta e puternic BULLISH
        if self.block_contratrend and delta_trend == 'BULLISH' and delta_strength >= 0.5:
            # Skip SHORT signal - piața merge în direcția opusă
            pass
        # SHORT signal: bp_down + IFI_rising + delta trend BEARISH (sau NEUTRAL)
        # Folosim threshold mai mare pentru SHORT (65% vs 60%) bazat pe backtest
        elif bp_down >= self.breakout_threshold_short and IFI_rising:
            # Verifică delta strength minim pentru semnal valid
            if delta_trend != 'NEUTRAL' and delta_strength < self.min_delta_strength:
                # Delta prea slab - semnal incert, skip
                pass
            else:
                base_confidence = 0.5 + (bp_down - self.breakout_threshold_short)

                # Ajustează confidence bazat pe delta trend
                if delta_trend == 'BEARISH':
                    # Delta confirmă direcția - boost confidence
                    confidence = min(1.0, base_confidence + delta_strength * 0.25)
                    description = f"SHORT: bp_down={bp_down:.0%}, IFI rising, Delta BEARISH ({delta_strength:.0%})"
                elif delta_trend == 'BULLISH':
                    # Delta contratrend - penalizare severă
                    confidence = max(0.0, base_confidence - delta_strength * 0.5)
                    description = f"SHORT WEAK: bp_down={bp_down:.0%}, but Delta BULLISH ({delta_strength:.0%})"
                else:
                    confidence = base_confidence
                    description = f"SHORT: bp_down={bp_down:.0%}, IFI rising, Delta neutral"

                signals.append(
                    Signal(
                        symbol=symbol,
                        timestamp=timestamp,
                        type="predictive_breakout_short",
                        confidence=confidence,
                        breakout_probability=bp_down,
                        IFI=IFI,
                        energy_collapse_risk=ecr,
                        description=description,
                    )
                )

        else:
            max_bp = max(bp_up, bp_down)
            confidence = max(0.0, min(1.0, 1.0 - max_bp))

            signals.append(
                Signal(
                    symbol=symbol,
                    timestamp=timestamp,
                    type="flow_neutral_watch",
                    confidence=confidence,
                    breakout_probability=max_bp,
                    IFI=IFI,
                    energy_collapse_risk=ecr,
                    description=f"Neutral. Delta trend: {delta_trend} ({delta_strength:.0%})",
                )
            )

        return signals


engine = SignalsEngine()
