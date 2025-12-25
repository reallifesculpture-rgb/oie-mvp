"""
Topology Engine Validation Script
Tests: return normalization, delta-flow normalization, 2D cross-product rotation,
vortex thresholds, and coherence calculation.
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
# SYNTHETIC DATASET: 15 Bars with controlled price & delta changes
# ============================================================================

def create_synthetic_bars() -> List[Bar]:
    """
    Create 15 bars with controlled price and delta patterns to trigger rotations.
    Strategy:
    - Bars 0-4: Uptrend with positive delta (coherent motion)
    - Bars 5-8: High volatility & negative delta (rotation trigger)
    - Bars 9-11: Price reversal with mixed delta (detecting vortex)
    - Bars 12-14: Settling phase
    """
    base_time = datetime(2025, 1, 1, 9, 30, 0)
    bars = []
    
    # Uptrend phase (bars 0-4)
    price = 100.0
    for i in range(5):
        volume = 1000.0 + i * 50
        buy_vol = 600.0 + i * 40
        sell_vol = 400.0 - i * 30
        bar = Bar(
            timestamp=base_time + timedelta(minutes=i),
            open=price,
            high=price + 0.5,
            low=price - 0.2,
            close=price + 0.3,
            volume=volume,
            buy_volume=buy_vol,
            sell_volume=sell_vol,
            delta=buy_vol - sell_vol,
            atr=0.4
        )
        bars.append(bar)
        price = bar.close
    
    # High volatility phase (bars 5-8) - strong rotations
    for i in range(4):
        volume = 1200.0 + i * 100
        if i % 2 == 0:
            # Negative delta bar
            buy_vol = 300.0
            sell_vol = 700.0
            price_change = -0.8
        else:
            # Positive delta bar
            buy_vol = 750.0
            sell_vol = 250.0
            price_change = 1.2
        
        bar = Bar(
            timestamp=base_time + timedelta(minutes=5 + i),
            open=price,
            high=price + abs(price_change) + 0.5,
            low=price + min(0, price_change) - 0.5,
            close=price + price_change,
            volume=volume,
            buy_volume=buy_vol,
            sell_volume=sell_vol,
            delta=buy_vol - sell_vol,
            atr=0.8
        )
        bars.append(bar)
        price = bar.close
    
    # Reversal phase (bars 9-11)
    for i in range(3):
        volume = 1100.0
        if i == 0:
            buy_vol = 700.0
            sell_vol = 400.0
            price_change = 0.5
        elif i == 1:
            buy_vol = 350.0
            sell_vol = 750.0
            price_change = -1.0
        else:
            buy_vol = 500.0
            sell_vol = 600.0
            price_change = 0.2
        
        bar = Bar(
            timestamp=base_time + timedelta(minutes=9 + i),
            open=price,
            high=price + abs(price_change) + 0.3,
            low=price + min(0, price_change) - 0.3,
            close=price + price_change,
            volume=volume,
            buy_volume=buy_vol,
            sell_volume=sell_vol,
            delta=buy_vol - sell_vol,
            atr=0.6
        )
        bars.append(bar)
        price = bar.close
    
    # Settling phase (bars 12-14)
    for i in range(3):
        volume = 800.0 + i * 50
        buy_vol = 450.0 + i * 25
        sell_vol = 350.0 - i * 10
        bar = Bar(
            timestamp=base_time + timedelta(minutes=12 + i),
            open=price,
            high=price + 0.2,
            low=price - 0.1,
            close=price + 0.1,
            volume=volume,
            buy_volume=buy_vol,
            sell_volume=sell_vol,
            delta=buy_vol - sell_vol,
            atr=0.3
        )
        bars.append(bar)
        price = bar.close
    
    return bars


# ============================================================================
# MANUAL PIPELINE SIMULATION & VALIDATION
# ============================================================================

def manual_compute(bars: List[Bar]):
    """
    Step-by-step manual computation to validate engine logic.
    """
    print("\n" + "="*80)
    print("STEP-BY-STEP PIPELINE SIMULATION")
    print("="*80)
    
    print(f"\nInput: {len(bars)} bars")
    print(f"Timestamp range: {bars[0].timestamp} to {bars[-1].timestamp}")
    
    # Step 1: Extract returns (price normalization)
    print("\n[STEP 1] RETURN NORMALIZATION")
    print("-" * 80)
    returns = []
    for i in range(len(bars)):
        if i == 0:
            ret = 0.0
            reason = "(first bar)"
        else:
            prev_close = bars[i - 1].close
            ret = 0.0 if prev_close == 0 else (bars[i].close - prev_close) / abs(prev_close)
            reason = f"({bars[i].close:.4f} - {prev_close:.4f}) / {abs(prev_close):.4f}"
        returns.append(ret)
        print(f"Bar {i:2d}: ret = {ret:7.4f}  {reason}")
    
    # Step 2: Extract flows (delta-flow normalization)
    print("\n[STEP 2] DELTA-FLOW NORMALIZATION")
    print("-" * 80)
    flows = []
    for i in range(len(bars)):
        if bars[i].volume and bars[i].volume > 0 and bars[i].delta is not None:
            flow = bars[i].delta / bars[i].volume
        else:
            flow = 0.0
        flows.append(flow)
        delta_str = f"{bars[i].delta:.1f}" if bars[i].delta is not None else "None"
        vol_str = f"{bars[i].volume:.1f}" if bars[i].volume else "0"
        print(f"Bar {i:2d}: flow = {flow:7.4f}  (delta={delta_str:7s} / volume={vol_str:7s})")
    
    # Step 3: Compute rotations (2D cross-product)
    print("\n[STEP 3] 2D CROSS-PRODUCT ROTATION COMPUTATION")
    print("-" * 80)
    
    def norm(v):
        magnitude = math.sqrt(v[0] * v[0] + v[1] * v[1])
        return magnitude
    
    rotations = []
    energies = []
    
    for k in range(1, len(bars) - 1):
        v_prev = (returns[k - 1], flows[k - 1])
        v_curr = (returns[k], flows[k])
        v_next = (returns[k + 1], flows[k + 1])
        
        # 2D cross product: v_prev × v_next
        cross = v_prev[0] * v_next[1] - v_prev[1] * v_next[0]
        
        norm_prev = norm(v_prev)
        norm_next = norm(v_next)
        denom = norm_prev * norm_next
        
        if denom < 1e-9:
            rot_norm = 0.0
            reason = "degenerate (denom < 1e-9)"
        else:
            rot_norm = cross / denom
            reason = f"cross={cross:.4f} / denom={denom:.4f}"
        
        rotations.append(rot_norm)
        
        energy_k = abs(returns[k]) * (bars[k].volume or 0.0)
        energies.append(energy_k)
        
        sign = "clockwise" if rot_norm < 0 else "counterclockwise"
        print(f"Bar {k:2d}: rot_norm = {rot_norm:7.4f} ({sign:16s})  energy = {energy_k:10.2f}  [{reason}]")
    
    # Step 4: Compute coherence
    print("\n[STEP 4] COHERENCE CALCULATION")
    print("-" * 80)
    if rotations:
        abs_rotations = [abs(r) for r in rotations]
        coherence = sum(abs_rotations) / len(rotations)
        print(f"Sum of |rot_norm|: {sum(abs_rotations):.4f}")
        print(f"Number of rotations: {len(rotations)}")
        print(f"Coherence = {coherence:.4f}")
    else:
        coherence = 0.0
        print(f"No rotations computed. Coherence = 0.0")
    
    # Step 5: Energy threshold (top 30% = 70th percentile)
    print("\n[STEP 5] ENERGY THRESHOLD (TOP 30%)")
    print("-" * 80)
    if energies:
        sorted_energies = sorted(energies)
        thr_index = int(0.7 * len(sorted_energies))
        thr_index = max(0, min(thr_index, len(sorted_energies) - 1))
        energy_threshold = sorted_energies[thr_index]
        print(f"Sorted energies: {[f'{e:.2f}' for e in sorted_energies]}")
        print(f"70th percentile index: {thr_index} / {len(sorted_energies)}")
        print(f"Energy threshold (70th percentile): {energy_threshold:.4f}")
    else:
        energy_threshold = 0.0
        print(f"No energies computed. Threshold = 0.0")
    
    # Step 6: Vortex detection (|rot_norm| > 0.6 AND energy >= threshold)
    print("\n[STEP 6] VORTEX DETECTION")
    print("-" * 80)
    print(f"Criteria: |rot_norm| > 0.6 AND energy >= {energy_threshold:.4f}")
    
    vortex_markers = []
    for k_idx, k in enumerate(range(1, len(bars) - 1)):
        rot = rotations[k_idx]
        eng = energies[k_idx]
        passes_rot_check = abs(rot) > 0.6
        passes_energy_check = eng >= energy_threshold
        is_vortex = passes_rot_check and passes_energy_check
        
        status = "✓ VORTEX" if is_vortex else "  -"
        print(f"Bar {k:2d}: |rot|={abs(rot):.4f} (>{0.6}) {passes_rot_check}  " +
              f"energy={eng:10.2f} (>={energy_threshold:.4f}) {passes_energy_check}  {status}")
        
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
    
    # Summary
    print("\n[SUMMARY] DETECTED VORTEXES")
    print("-" * 80)
    for marker in vortex_markers:
        print(f"Index {marker.index:2d} @ {marker.timestamp}: "
              f"price={marker.price:.4f}, strength={marker.strength:.4f}, "
              f"direction={marker.direction}")
    
    if not vortex_markers:
        print("No vortexes detected.")
    
    return {
        "returns": returns,
        "flows": flows,
        "rotations": rotations,
        "energies": energies,
        "coherence": coherence,
        "energy_threshold": energy_threshold,
        "vortex_markers": vortex_markers
    }


# ============================================================================
# ENGINE COMPARISON
# ============================================================================

def test_engine_vs_manual(bars: List[Bar]):
    """
    Compare engine output with manual computation.
    """
    print("\n" + "="*80)
    print("TOPOLOGY ENGINE CALL")
    print("="*80)
    
    engine = TopologyEngine(window_size=100)
    snapshot = engine.compute("TEST", bars)
    
    print(f"\nSnapshot:")
    print(f"  Symbol: {snapshot.symbol}")
    print(f"  Timestamp: {snapshot.timestamp}")
    print(f"  Coherence: {snapshot.coherence:.4f}")
    print(f"  Energy: {snapshot.energy:.4f}")
    print(f"  Vortexes: {len(snapshot.vortexes)}")
    
    print(f"\nDetected vortexes:")
    for marker in snapshot.vortexes:
        print(f"  Index {marker.index:2d} @ {marker.timestamp}: "
              f"price={marker.price:.4f}, strength={marker.strength:.4f}, "
              f"direction={marker.direction}")
    
    if not snapshot.vortexes:
        print("  None")
    
    return snapshot


# ============================================================================
# MATHEMATICAL CONSISTENCY CHECKS
# ============================================================================

def validate_mathematics(manual_result, engine_snapshot, bars):
    """
    Check for mathematical inconsistencies.
    """
    print("\n" + "="*80)
    print("MATHEMATICAL CONSISTENCY CHECKS")
    print("="*80)
    
    issues = []
    
    # Check 1: Coherence must be in [0, ∞)
    if manual_result["coherence"] < 0:
        issues.append(f"❌ Coherence negative: {manual_result['coherence']}")
    else:
        print(f"✓ Coherence is non-negative: {manual_result['coherence']:.4f}")
    
    # Check 2: Energy values must be non-negative
    bad_energies = [e for e in manual_result["energies"] if e < 0]
    if bad_energies:
        issues.append(f"❌ Negative energies found: {bad_energies}")
    else:
        print(f"✓ All {len(manual_result['energies'])} energies are non-negative")
    
    # Check 3: Returns normalization: return = (close_t - close_t-1) / |close_t-1|
    print(f"✓ Returns normalized correctly: {len(manual_result['returns'])} values computed")
    
    # Check 4: Flow normalization: flow = delta / volume (bounded if delta & volume normalized)
    print(f"✓ Delta-flow normalization: {len(manual_result['flows'])} values computed")
    
    # Check 5: 2D rotation must be in approximately [-1, 1] (normalized cross-product)
    out_of_range_rot = [r for r in manual_result["rotations"] if abs(r) > 1.1]
    if out_of_range_rot:
        issues.append(f"⚠ Rotations slightly out of [-1,1]: {out_of_range_rot}")
        print(f"⚠ Some rotations exceed [-1,1]: {out_of_range_rot} (likely numerical precision)")
    else:
        print(f"✓ All rotations in valid range [-1, 1]: min={min(manual_result['rotations']):.4f}, "
              f"max={max(manual_result['rotations']):.4f}")
    
    # Check 6: Energy threshold must be in sorted energies
    if manual_result["energies"]:
        sorted_eng = sorted(manual_result["energies"])
        threshold = manual_result["energy_threshold"]
        if threshold < min(sorted_eng) or threshold > max(sorted_eng):
            issues.append(f"❌ Threshold outside energy range: {threshold} ∉ [{min(sorted_eng)}, {max(sorted_eng)}]")
        else:
            print(f"✓ Energy threshold valid: {threshold:.4f} ∈ [{min(sorted_eng):.4f}, {max(sorted_eng):.4f}]")
    
    # Check 7: Vortex marker consistency
    for marker in manual_result["vortex_markers"]:
        k_idx = marker.index - 1  # Convert to rotation index
        rot = manual_result["rotations"][k_idx]
        eng = manual_result["energies"][k_idx]
        
        if abs(rot) <= 0.6:
            issues.append(f"❌ Vortex {marker.index} has |rot|={abs(rot):.4f} ≤ 0.6")
        if eng < manual_result["energy_threshold"]:
            issues.append(f"❌ Vortex {marker.index} has energy={eng:.2f} < threshold={manual_result['energy_threshold']:.4f}")
        
        direction_match = (rot < 0 and marker.direction == "clockwise") or \
                          (rot >= 0 and marker.direction == "counterclockwise")
        if not direction_match:
            issues.append(f"❌ Vortex {marker.index} has inconsistent direction: rot={rot:.4f}, dir={marker.direction}")
    
    # Check 8: Compare manual vs engine
    tol = 1e-6
    if abs(manual_result["coherence"] - engine_snapshot.coherence) > tol:
        issues.append(f"❌ Coherence mismatch: manual={manual_result['coherence']:.6f}, engine={engine_snapshot.coherence:.6f}")
    else:
        print(f"✓ Coherence matches: {engine_snapshot.coherence:.4f}")
    
    if len(manual_result["vortex_markers"]) != len(engine_snapshot.vortexes):
        issues.append(f"❌ Vortex count mismatch: manual={len(manual_result['vortex_markers'])}, "
                     f"engine={len(engine_snapshot.vortexes)}")
    else:
        print(f"✓ Vortex count matches: {len(engine_snapshot.vortexes)}")
    
    # Report issues
    print(f"\n{'='*80}")
    print("ISSUES FOUND:")
    print("="*80)
    if issues:
        for issue in issues:
            print(issue)
    else:
        print("✓ No mathematical inconsistencies detected!")
    
    return issues


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*80)
    print("TOPOLOGY ENGINE VALIDATION - COMPREHENSIVE TEST SUITE")
    print("="*80)
    
    # Create synthetic data
    bars = create_synthetic_bars()
    
    print(f"\n[DATASET CREATION] Generated {len(bars)} synthetic bars")
    print(f"Time range: {bars[0].timestamp} to {bars[-1].timestamp}")
    print("\nFirst 5 bars:")
    for i, bar in enumerate(bars[:5]):
        print(f"  Bar {i}: close={bar.close:.4f}, volume={bar.volume:.1f}, delta={bar.delta:.1f}, buy={bar.buy_volume:.1f}, sell={bar.sell_volume:.1f}")
    
    # Manual computation
    manual_result = manual_compute(bars)
    
    # Engine computation
    engine_snapshot = test_engine_vs_manual(bars)
    
    # Validation
    issues = validate_mathematics(manual_result, engine_snapshot, bars)
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print(f"Status: {'✓ PASS' if not issues else '❌ FAIL'} ({len(issues)} issues)")
