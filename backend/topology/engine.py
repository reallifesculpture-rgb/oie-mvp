import math
from typing import List
from backend.topology.models import TopologySnapshot, VortexMarker
from backend.data.models import Bar

# ANGLE_THRESHOLD_DEG: Minimum directional change to detect vortex
# Pure angular deflection between consecutive (return, flow) vectors
# sin(angle) = cross_product / (||v_prev|| * ||v_next||)
# Threshold of 10° captures meaningful directional changes
ANGLE_THRESHOLD_DEG = 10.0

class TopologyEngine:
    def __init__(self, window_size: int = 100):
        self.window_size = window_size

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
            v_curr = (returns[k], flows[k])
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
            
            # Composite score: |rotation| * (energy normalized)
            # Higher score = stronger vortex signal
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
        thr_index = int(0.7 * len(sorted_energies))
        thr_index = max(0, min(thr_index, len(sorted_energies) - 1))
        energy_threshold = sorted_energies[thr_index]

        vortex_markers = []
        for k_idx, k in enumerate(range(1, len(bars) - 1)):
            # Vortex detection: Use composite score threshold instead of pure angle
            # This better captures vortex strength combining rotation + energy
            # Threshold: 0.08 works well for practical markets
            if composite_scores[k_idx] >= 0.08 and energies[k_idx] >= energy_threshold:
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

engine = TopologyEngine(window_size=100)
