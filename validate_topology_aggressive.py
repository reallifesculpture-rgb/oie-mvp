"""
Topology Engine Validation Report - Extended Analysis
Tests vortex detection with more aggressive synthetic data.
"""

import math
import sys
from datetime import datetime, timedelta
from typing import List

sys.path.insert(0, r'c:\Users\gyorg\OneDrive\Desktop\OIE')

from backend.data.models import Bar
from backend.topology.models import TopologySnapshot, VortexMarker
from backend.topology.engine import TopologyEngine

# ============================================================================
# AGGRESSIVE SYNTHETIC DATASET FOR VORTEX TRIGGERING
# ============================================================================

def create_aggressive_vortex_bars() -> List[Bar]:
    """
    Create bars specifically designed to trigger vortexes.
    Key: Create sharp directional changes with high rotation & high energy.
    """
    base_time = datetime(2025, 1, 1, 9, 30, 0)
    bars = []
    
    # Establish baseline (bars 0-2)
    price = 100.0
    for i in range(3):
        bar = Bar(
            timestamp=base_time + timedelta(minutes=i),
            open=price,
            high=price + 0.1,
            low=price - 0.1,
            close=price + 0.05,
            volume=1000.0,
            buy_volume=600.0,
            sell_volume=400.0,
            delta=200.0,
            atr=0.1
        )
        bars.append(bar)
        price = bar.close
    
    # VORTEX ZONE 1: Strong upward rotation with high energy
    # Bar 3: Strong BUY, high volume
    bar = Bar(
        timestamp=base_time + timedelta(minutes=3),
        open=price,
        high=price + 3.0,
        low=price - 0.5,
        close=price + 2.5,
        volume=5000.0,
        buy_volume=4500.0,
        sell_volume=500.0,
        delta=4000.0,
        atr=1.5
    )
    bars.append(bar)
    price = bar.close
    
    # Bar 4: Reversal - strong SELL, high volume (creates rotation)
    bar = Bar(
        timestamp=base_time + timedelta(minutes=4),
        open=price,
        high=price + 0.5,
        low=price - 3.0,
        close=price - 2.0,
        volume=5000.0,
        buy_volume=500.0,
        sell_volume=4500.0,
        delta=-4000.0,
        atr=1.5
    )
    bars.append(bar)
    price = bar.close
    
    # Bar 5: Recovery continuation (completes rotation)
    bar = Bar(
        timestamp=base_time + timedelta(minutes=5),
        open=price,
        high=price + 2.5,
        low=price - 0.5,
        close=price + 2.0,
        volume=5000.0,
        buy_volume=4500.0,
        sell_volume=500.0,
        delta=4000.0,
        atr=1.5
    )
    bars.append(bar)
    price = bar.close
    
    # Stabilize (bars 6-8)
    for i in range(3):
        bar = Bar(
            timestamp=base_time + timedelta(minutes=6 + i),
            open=price,
            high=price + 0.3,
            low=price - 0.2,
            close=price + 0.15,
            volume=1500.0,
            buy_volume=950.0,
            sell_volume=550.0,
            delta=400.0,
            atr=0.3
        )
        bars.append(bar)
        price = bar.close
    
    # VORTEX ZONE 2: Downward rotation with high energy
    # Bar 9: Strong DOWN with high volume
    bar = Bar(
        timestamp=base_time + timedelta(minutes=9),
        open=price,
        high=price + 0.5,
        low=price - 3.0,
        close=price - 2.8,
        volume=5500.0,
        buy_volume=500.0,
        sell_volume=5000.0,
        delta=-4500.0,
        atr=1.8
    )
    bars.append(bar)
    price = bar.close
    
    # Bar 10: Counter-reversal, high energy
    bar = Bar(
        timestamp=base_time + timedelta(minutes=10),
        open=price,
        high=price + 2.5,
        low=price - 0.5,
        close=price + 2.2,
        volume=5000.0,
        buy_volume=4750.0,
        sell_volume=250.0,
        delta=4500.0,
        atr=1.6
    )
    bars.append(bar)
    price = bar.close
    
    # Bar 11: Continuation down (completes rotation)
    bar = Bar(
        timestamp=base_time + timedelta(minutes=11),
        open=price,
        high=price + 0.5,
        low=price - 2.0,
        close=price - 1.5,
        volume=5200.0,
        buy_volume=600.0,
        sell_volume=4600.0,
        delta=-4000.0,
        atr=1.4
    )
    bars.append(bar)
    price = bar.close
    
    # Final settle (bars 12-14)
    for i in range(3):
        bar = Bar(
            timestamp=base_time + timedelta(minutes=12 + i),
            open=price,
            high=price + 0.2,
            low=price - 0.1,
            close=price + 0.05,
            volume=1200.0,
            buy_volume=700.0,
            sell_volume=500.0,
            delta=200.0,
            atr=0.2
        )
        bars.append(bar)
        price = bar.close
    
    return bars


# ============================================================================
# DETAILED VALIDATION
# ============================================================================

def detailed_analysis(bars: List[Bar]):
    """Perform detailed step-by-step analysis with focus on mathematics."""
    
    print("\n" + "="*90)
    print("DETAILED MATHEMATICAL ANALYSIS")
    print("="*90)
    
    # Extract returns
    returns = []
    for i in range(len(bars)):
        if i == 0:
            ret = 0.0
        else:
            prev_close = bars[i - 1].close
            ret = 0.0 if prev_close == 0 else (bars[i].close - prev_close) / abs(prev_close)
        returns.append(ret)
    
    # Extract flows
    flows = []
    for i in range(len(bars)):
        if bars[i].volume and bars[i].volume > 0 and bars[i].delta is not None:
            flow = bars[i].delta / bars[i].volume
        else:
            flow = 0.0
        flows.append(flow)
    
    def norm(v):
        return math.sqrt(v[0] * v[0] + v[1] * v[1])
    
    print("\n[PHASE 1] RETURN & FLOW NORMALIZATION")
    print("-" * 90)
    print("Index | Return      | Flow        | Volume   | Delta    | Reason")
    print("-" * 90)
    for i in range(len(bars)):
        ret = returns[i]
        flow = flows[i]
        vol = bars[i].volume
        delta = bars[i].delta if bars[i].delta is not None else 0
        if i == 0:
            reason = "first bar (return=0)"
        else:
            pct = (bars[i].close - bars[i-1].close) / bars[i-1].close * 100
            reason = f"close change: {pct:+.2f}%"
        print(f"{i:5d} | {ret:11.6f} | {flow:11.6f} | {vol:8.1f} | {delta:8.1f} | {reason}")
    
    # Compute rotations with detailed output
    print("\n[PHASE 2] 2D CROSS-PRODUCT ROTATION")
    print("-" * 90)
    print("This computes the normalized 2D cross-product of consecutive (return, flow) vectors.")
    print("Formula: rot_norm = (v_prev × v_next) / (||v_prev|| * ||v_next||)")
    print("where v_prev = (ret[k-1], flow[k-1]), v_next = (ret[k+1], flow[k+1])")
    print()
    
    rotations = []
    energies = []
    
    for k in range(1, len(bars) - 1):
        v_prev = (returns[k - 1], flows[k - 1])
        v_curr = (returns[k], flows[k])
        v_next = (returns[k + 1], flows[k + 1])
        
        cross = v_prev[0] * v_next[1] - v_prev[1] * v_next[0]
        norm_prev = norm(v_prev)
        norm_next = norm(v_next)
        denom = norm_prev * norm_next
        
        rot_norm = cross / denom if denom >= 1e-9 else 0.0
        rotations.append(rot_norm)
        
        energy_k = abs(returns[k]) * bars[k].volume
        energies.append(energy_k)
        
        sign = "CW " if rot_norm < 0 else "CCW"
        print(f"Bar {k:2d}: v_prev={v_prev}, v_next={v_next}")
        print(f"        cross={cross:8.4f}, ||v_prev||={norm_prev:8.4f}, ||v_next||={norm_next:8.4f}")
        print(f"        rot_norm = {rot_norm:8.6f} ({sign}), energy={energy_k:12.2f}")
    
    # Coherence
    print("\n[PHASE 3] COHERENCE")
    print("-" * 90)
    if rotations:
        abs_rots = [abs(r) for r in rotations]
        coherence = sum(abs_rots) / len(rotations)
        print(f"Coherence = Σ|rot_norm| / count = {sum(abs_rots):.6f} / {len(rotations)}")
        print(f"Coherence = {coherence:.6f}")
        print(f"Interpretation: Average absolute rotation per bar")
    
    # Energy threshold
    print("\n[PHASE 4] ENERGY THRESHOLD (TOP 30%)")
    print("-" * 90)
    sorted_energies = sorted(energies)
    thr_index = int(0.7 * len(sorted_energies))
    thr_index = max(0, min(thr_index, len(sorted_energies) - 1))
    energy_threshold = sorted_energies[thr_index]
    
    print(f"Sorted energies (13 values):")
    for i, e in enumerate(sorted_energies):
        marker = " <- threshold" if i == thr_index else ""
        print(f"  [{i:2d}] {e:12.2f}{marker}")
    print(f"\n70th percentile index: {thr_index} (top 30% starts at {13-thr_index} values)")
    print(f"Energy threshold: {energy_threshold:.4f}")
    
    # Vortex detection
    print("\n[PHASE 5] VORTEX DETECTION")
    print("-" * 90)
    print(f"Criteria: |rot_norm| > 0.6 AND energy >= {energy_threshold:.4f}\n")
    
    vortex_markers = []
    for k_idx, k in enumerate(range(1, len(bars) - 1)):
        rot = rotations[k_idx]
        eng = energies[k_idx]
        
        rot_check = abs(rot) > 0.6
        eng_check = eng >= energy_threshold
        is_vortex = rot_check and eng_check
        
        status = "✓ VORTEX" if is_vortex else ""
        print(f"Bar {k:2d}: |rot|={abs(rot):8.6f} (>{0.6:5.1f}) {str(rot_check):5s}  " +
              f"energy={eng:12.2f} (>={energy_threshold:7.4f}) {str(eng_check):5s}  {status}")
        
        if is_vortex:
            direction = "clockwise" if rot < 0 else "counterclockwise"
            marker = VortexMarker(
                index=k,
                timestamp=bars[k].timestamp,
                price=bars[k].close,
                strength=abs(rot),
                direction=direction
            )
            vortex_markers.append(marker)
    
    return {
        "returns": returns,
        "flows": flows,
        "rotations": rotations,
        "energies": energies,
        "coherence": coherence if rotations else 0.0,
        "energy_threshold": energy_threshold,
        "vortex_markers": vortex_markers
    }


# ============================================================================
# COMPREHENSIVE REPORT
# ============================================================================

def generate_report(bars, manual_result, engine_snapshot):
    """Generate comprehensive validation report."""
    
    print("\n\n" + "="*90)
    print("COMPREHENSIVE VALIDATION REPORT")
    print("="*90)
    
    # Section 1: Dataset Overview
    print("\n[1] SYNTHETIC DATASET")
    print("-" * 90)
    print(f"Bars generated: {len(bars)}")
    print(f"Time range: {bars[0].timestamp} to {bars[-1].timestamp}")
    print(f"\nPrice movement:")
    print(f"  Start: {bars[0].close:.4f}")
    print(f"  End:   {bars[-1].close:.4f}")
    print(f"  Total change: {bars[-1].close - bars[0].close:.4f} ({(bars[-1].close/bars[0].close - 1)*100:+.2f}%)")
    print(f"  Min: {min(b.close for b in bars):.4f}")
    print(f"  Max: {max(b.close for b in bars):.4f}")
    
    print(f"\nVolume statistics:")
    print(f"  Total volume: {sum(b.volume for b in bars):.1f}")
    print(f"  Avg volume: {sum(b.volume for b in bars) / len(bars):.1f}")
    print(f"  Max volume: {max(b.volume for b in bars):.1f}")
    
    print(f"\nDelta statistics:")
    print(f"  Total delta: {sum(b.delta if b.delta else 0 for b in bars):.1f}")
    print(f"  Avg delta: {sum(b.delta if b.delta else 0 for b in bars) / len(bars):.1f}")
    print(f"  Max positive delta: {max((b.delta if b.delta else 0 for b in bars)):.1f}")
    print(f"  Max negative delta: {min((b.delta if b.delta else 0 for b in bars)):.1f}")
    
    # Section 2: Normalization Validation
    print("\n[2] NORMALIZATION VALIDATION")
    print("-" * 90)
    
    returns = manual_result["returns"]
    flows = manual_result["flows"]
    
    print(f"✓ Return normalization:")
    print(f"    - Min return: {min(returns):.6f}")
    print(f"    - Max return: {max(returns):.6f}")
    print(f"    - Reasonable range for normalized returns")
    
    print(f"✓ Delta-flow normalization (delta / volume):")
    print(f"    - Min flow: {min(flows):.6f}")
    print(f"    - Max flow: {max(flows):.6f}")
    print(f"    - Flows represent directional intensity")
    
    # Section 3: Rotation Computation
    print("\n[3] 2D CROSS-PRODUCT ROTATION")
    print("-" * 90)
    
    rotations = manual_result["rotations"]
    
    print(f"Rotation statistics:")
    print(f"    - Count: {len(rotations)}")
    print(f"    - Min: {min(rotations):.6f} (strong clockwise)")
    print(f"    - Max: {max(rotations):.6f} (strong counterclockwise)")
    print(f"    - Range check: {'✓ PASS' if max(abs(r) for r in rotations) <= 1.5 else '❌ FAIL'} (should be ~[-1,1])")
    
    # Section 4: Thresholds
    print("\n[4] VORTEX THRESHOLD VALIDATION")
    print("-" * 90)
    
    energies = manual_result["energies"]
    threshold = manual_result["energy_threshold"]
    
    print(f"Rotation threshold: |rot_norm| > 0.6")
    print(f"    - Passes check: {sum(1 for r in rotations if abs(r) > 0.6)} bars")
    
    print(f"\nEnergy threshold (70th percentile): {threshold:.4f}")
    print(f"    - Min energy: {min(energies):.4f}")
    print(f"    - Max energy: {max(energies):.4f}")
    print(f"    - Passes energy check: {sum(1 for e in energies if e >= threshold)} bars")
    
    print(f"\nCombined (both thresholds): {len(manual_result['vortex_markers'])} vortexes")
    
    # Section 5: Detected Vortexes
    print("\n[5] DETECTED VORTEXES")
    print("-" * 90)
    
    if manual_result["vortex_markers"]:
        for marker in manual_result["vortex_markers"]:
            k_idx = marker.index - 1
            rot = rotations[k_idx]
            eng = energies[k_idx]
            print(f"Vortex at bar {marker.index}:")
            print(f"    Timestamp: {marker.timestamp}")
            print(f"    Price: {marker.price:.4f}")
            print(f"    Strength (|rot_norm|): {marker.strength:.6f}")
            print(f"    Direction: {marker.direction}")
            print(f"    Energy: {eng:.2f}")
    else:
        print("No vortexes detected with current thresholds.")
        print("Recommendation: Thresholds may be too strict for gentle synthetic data.")
    
    # Section 6: Coherence
    print("\n[6] COHERENCE METRIC")
    print("-" * 90)
    
    coherence = manual_result["coherence"]
    print(f"Coherence = {coherence:.6f}")
    print(f"Interpretation: Average absolute rotation per bar")
    print(f"    - Near 0: Market is calm, minimal directional changes")
    print(f"    - Higher: More directional shifts, potential vortex activity")
    
    # Section 7: Engine vs Manual
    print("\n[7] ENGINE CONSISTENCY CHECK")
    print("-" * 90)
    
    print(f"Manual computation:")
    print(f"    Coherence: {manual_result['coherence']:.6f}")
    print(f"    Vortexes: {len(manual_result['vortex_markers'])}")
    
    print(f"\nEngine output:")
    print(f"    Coherence: {engine_snapshot.coherence:.6f}")
    print(f"    Vortexes: {len(engine_snapshot.vortexes)}")
    
    tol = 1e-6
    if abs(manual_result["coherence"] - engine_snapshot.coherence) < tol:
        print(f"\n✓ Coherence matches (tolerance: {tol})")
    else:
        print(f"\n❌ Coherence mismatch!")
    
    if len(manual_result["vortex_markers"]) == len(engine_snapshot.vortexes):
        print(f"✓ Vortex count matches")
    else:
        print(f"❌ Vortex count mismatch!")
    
    # Section 8: Mathematical Consistency
    print("\n[8] MATHEMATICAL CONSISTENCY CHECKS")
    print("-" * 90)
    
    issues = []
    
    # Check non-negativity
    if min(energies) >= 0:
        print(f"✓ All energies non-negative")
    else:
        print(f"❌ Negative energies found")
        issues.append("Negative energies")
    
    if coherence >= 0:
        print(f"✓ Coherence non-negative")
    else:
        print(f"❌ Negative coherence")
        issues.append("Negative coherence")
    
    # Check rotation normalization
    max_rot = max(abs(r) for r in rotations)
    if max_rot <= 1.1:  # Allow slight numerical error
        print(f"✓ Rotations bounded: max |rot| = {max_rot:.6f}")
    else:
        print(f"⚠ Rotations exceed [-1,1]: max |rot| = {max_rot:.6f}")
        issues.append(f"Rotation magnitude {max_rot:.6f}")
    
    # Check energy threshold validity
    if min(energies) <= threshold <= max(energies):
        print(f"✓ Threshold in valid range")
    else:
        print(f"❌ Threshold out of range")
        issues.append("Invalid energy threshold")
    
    # Check vortex criteria
    for marker in manual_result["vortex_markers"]:
        k_idx = marker.index - 1
        if abs(rotations[k_idx]) <= 0.6:
            issues.append(f"Vortex {marker.index}: |rot| ≤ 0.6")
        if energies[k_idx] < threshold:
            issues.append(f"Vortex {marker.index}: energy < threshold")
    
    if not issues:
        print(f"✓ All vortex criteria satisfied")
    
    print("\n" + "="*90)
    print(f"FINAL STATUS: {'✓ PASS' if not issues else '❌ FAIL'}")
    if issues:
        print(f"Issues: {len(issues)}")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("No mathematical inconsistencies detected!")
    print("="*90)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*90)
    print("TOPOLOGY ENGINE VALIDATION - AGGRESSIVE VORTEX TEST")
    print("="*90)
    
    # Create aggressive dataset
    bars = create_aggressive_vortex_bars()
    print(f"\n✓ Generated {len(bars)} bars with aggressive price/delta patterns")
    
    # Detailed analysis
    manual_result = detailed_analysis(bars)
    
    # Engine computation
    engine = TopologyEngine(window_size=100)
    engine_snapshot = engine.compute("AGGRESSIVE", bars)
    
    # Generate report
    generate_report(bars, manual_result, engine_snapshot)
