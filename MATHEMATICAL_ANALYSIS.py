"""
CRITICAL ANALYSIS: Rotation Threshold Issue
============================================

Issue Discovered:
The rotation threshold of |rot_norm| > 0.6 is mathematically sound but
practically unrealistic. Even extreme synthetic data produces rotations < 0.03.

This script identifies the root cause and proposes solutions.
"""

import math

print("\n" + "="*90)
print("MATHEMATICAL ANALYSIS: WHY ROTATION THRESHOLD IS UNREALISTIC")
print("="*90)

print("\n[PROBLEM STATEMENT]")
print("-" * 90)
print("""
The vortex detection requires |rot_norm| > 0.6, where:
  rot_norm = (v_prev × v_next) / (||v_prev|| * ||v_next||)

In testing with aggressive synthetic data:
  - Maximum rotation observed: 0.028690
  - Required for detection: 0.6
  - Gap: ~20x too small

Question: Is the threshold unrealistic or is the metric unsuitable?
""")

print("\n[ROOT CAUSE ANALYSIS]")
print("-" * 90)

print("\n1. WHAT DOES ROTATION MEASURE?")
print("   " + "-" * 86)
print("""
   rot_norm measures the ANGULAR DEFLECTION between consecutive vectors
   in (return, flow) space.
   
   Formula: sin(θ) ≈ cross_product / (||v1|| * ||v2||)
   
   Key insight: This is normalized cross-product, NOT magnitude.
   
   Example:
   v1 = (0.01, 0.8)   [small return, large flow]
   v2 = (0.02, 0.8)   [small return, large flow]
   
   These vectors point in similar directions:
   - Same flow sign/magnitude
   - Slightly different return
   - Angular separation is SMALL
   - Result: low rotation
   
   Another example:
   v1 = (0.01, 0.8)   [up-right]
   v2 = (-0.01, -0.8) [down-left]
   
   These point in opposite directions:
   - Opposite signs
   - Angular separation is LARGE (~180°)
   - Result: high rotation
   
   BUT: If both vectors are small in magnitude:
   v1 = (0.001, 0.01) [both small]
   v2 = (-0.001, -0.01) [opposite, both small]
   
   Angular separation is still ~180° but:
   - cross ≈ tiny * tiny (very small)
   - norm products ≈ tiny (very small)
   - ratio could be moderate
""")

print("\n2. WHY ARE OBSERVED ROTATIONS SO SMALL?")
print("   " + "-" * 86)
print("""
   In test data:
   - Returns are small: [-0.027158, +0.024963]
   - Flows vary but still moderate: [-0.818182, +0.900000]
   - Vector magnitudes: typically 0.2 - 0.9
   
   For extreme rotation to occur, need:
   - Large cross product (large angular deflection)
   - Small denominator (small vector magnitudes)
   
   But when markets move dramatically:
   - Both return AND flow are large
   - Denominator grows quickly
   - Rotation gets normalized down
   
   Example: Sharp reversal in test data
   Bar 3→4→5 (extreme swing):
     v_prev = (0.024963, 0.8)     with ||v_prev|| = 0.8004
     v_next = (0.019871, 0.8)     with ||v_next|| = 0.8002
     cross = 0.024963 * 0.8 - 0.8 * 0.019871 = 0.0041
     rot_norm = 0.0041 / (0.8004 * 0.8002) = 0.0064
   
   Despite extreme price reversal: rotation only 0.0064!
   Reason: Both bars had large flow, which dominates the computation.
""")

print("\n[MATHEMATICAL FORMULATION]")
print("-" * 90)

print("\nTo achieve rot_norm > 0.6, need:")
print("  |cross| / (||v_prev|| * ||v_next||) > 0.6")
print("\nWorst case (maximum cross product): cross = ||v_prev|| * ||v_next||")
print("This gives: rot_norm ≤ 1.0 (normalized)")
print("\nTo get rot_norm = 0.6 from highly directional change:")
print("  cross / (||v_prev|| * ||v_next||) = 0.6")
print("  cross = 0.6 * ||v_prev|| * ||v_next||")
print("\nExample:")
print("  If ||v_prev|| = 0.3 and ||v_next|| = 0.3:")
print("    Need: cross ≥ 0.6 * 0.3 * 0.3 = 0.054")
print("    Max possible: 0.3 * 0.3 = 0.09 (perfect 90° angle)")
print("    With 90° angle: rot_norm = 0.09 / (0.3 * 0.3) = 1.0 ✓")
print("\nBut (0.3, 0.3) requires:")
print("  Return = 0.3 (30% price move)")
print("  Flow = 0.3 (delta = 30% of volume)")
print("\nWith (0.3, 0.3) magnitude, achieved 1.0 rotation with 90° turn.")
print("To get 0.6 with moderate vectors requires ~37° turn.")
print("This is NOT a large directional change!")

print("\n[THE REAL ISSUE]")
print("-" * 90)
print("""
The threshold of 0.6 is THEORETICALLY sound but:

1. It assumes market observations will produce vector magnitudes of ~0.3
   In reality, flows often range from -1.0 to +1.0 (full spectrum)
   This creates large denominators, suppressing rotation values

2. The metric conflates two concepts:
   - Directional change (angular deflection)
   - Magnitude scaling (how large the vectors are)
   
   A sharp reversal with small flows might produce high rotation,
   but a gradual reversal with large flows produces small rotation.

3. For vortex trading, want to detect:
   - Change in DIRECTION (angular)
   - HIGH ACTIVITY (energy is handled separately)
   
   Current rotation metric doesn't isolate direction change.
""")

print("\n[RECOMMENDED SOLUTION]")
print("-" * 90)
print("""
Option 1: REDUCE THRESHOLD (Quick Fix)
   Current: |rot_norm| > 0.6
   Proposed: |rot_norm| > 0.06
   Rationale: Observed rotations max at ~0.03, use 2x margin
   Cost: May increase false positives
   Benefit: Will actually trigger vortex detection

Option 2: USE PURE ANGLE METRIC (Robust Fix)
   Instead of: rot_norm = cross / (||v|| * ||v||)
   Use: θ = atan2(cross, dot_product)
   Metric: |sin(θ)| > threshold
   
   Benefits:
   - Measures PURE angular change
   - Independent of vector magnitude
   - Easier to interpret (in degrees)
   - Threshold becomes intuitive (e.g., > 20° deflection)
   
   Implementation:
   ```python
   cross = v_prev[0] * v_next[1] - v_prev[1] * v_next[0]
   dot = v_prev[0] * v_next[0] + v_prev[1] * v_next[1]
   angle_sin = cross / (norm(v_prev) * norm(v_next))  # Already correct!
   angle_deg = math.degrees(math.asin(angle_sin))
   
   # Threshold on angle
   if abs(angle_deg) > 20:  # Instead of > 0.6 (sine)
       detect_vortex()
   ```
   Note: sin(0.6 rad) ≈ 36.87°, which IS significant!

Option 3: MULTI-SCALE APPROACH (Sophisticated)
   - Compute rotation at multiple window sizes
   - Require detection at multiple scales
   - Reduces false positives
   - Better captures true vortex structure

Option 4: HYBRID ENERGY-ROTATION METRIC
   Instead of: (|rot| > 0.6) AND (energy > threshold)
   Use: vortex_score = |rot| * sqrt(energy) > threshold
   
   Benefits:
   - Continuous scoring instead of binary
   - No artificial separation of criteria
   - More flexible thresholding
   
   Example:
   bar_score = |rotation| * sqrt(energy / median_energy)
   if bar_score > 0.1:  # Much easier to achieve
       detect_vortex()
""")

print("\n[PROPOSED IMPLEMENTATION]")
print("-" * 90)

def angle_aware_vortex_detection(v_prev, v_next, energy, energy_threshold, angle_threshold_deg=20):
    """
    Improved vortex detection using pure angle measurement.
    
    Args:
        v_prev: (return, flow) vector at bar k-1
        v_next: (return, flow) vector at bar k+1
        energy: Energy at bar k
        energy_threshold: Min energy for detection
        angle_threshold_deg: Angular deflection threshold in degrees (default: 20°)
    
    Returns:
        (is_vortex, metadata)
    """
    def norm(v):
        return math.sqrt(v[0]**2 + v[1]**2)
    
    # Compute angle
    cross = v_prev[0] * v_next[1] - v_prev[1] * v_next[0]
    dot = v_prev[0] * v_next[0] + v_prev[1] * v_next[1]
    
    norm_prev = norm(v_prev)
    norm_next = norm(v_next)
    denom = norm_prev * norm_next
    
    if denom < 1e-9:
        angle_rad = 0.0
    else:
        sin_angle = cross / denom
        sin_angle = max(-1.0, min(1.0, sin_angle))  # Clamp to [-1, 1]
        angle_rad = math.asin(sin_angle)
    
    angle_deg = math.degrees(abs(angle_rad))
    
    # Detect vortex
    passes_angle = angle_deg > angle_threshold_deg
    passes_energy = energy >= energy_threshold
    is_vortex = passes_angle and passes_energy
    
    metadata = {
        'angle_rad': angle_rad,
        'angle_deg': angle_deg,
        'energy': energy,
        'passes_angle': passes_angle,
        'passes_energy': passes_energy,
        'direction': 'clockwise' if angle_rad < 0 else 'counterclockwise'
    }
    
    return is_vortex, metadata


# Test with example data
print("\nTest Case: Vortex Detection with Improved Metric")
print("=" * 90)

examples = [
    {
        'name': 'Moderate reversal, high energy',
        'v_prev': (0.024963, 0.8),
        'v_next': (-0.019484, -0.8),
        'energy': 124.81,
        'energy_threshold': 99.35
    },
    {
        'name': 'Slight movement, high energy',
        'v_prev': (0.001, 0.2),
        'v_next': (0.001, 0.2),
        'energy': 120.0,
        'energy_threshold': 99.35
    },
    {
        'name': 'Sharp reversal, low volume',
        'v_prev': (0.3, 0.3),
        'v_next': (-0.3, -0.3),
        'energy': 50.0,
        'energy_threshold': 99.35
    }
]

for ex in examples:
    print(f"\n{ex['name']}")
    print(f"  v_prev: {ex['v_prev']}, v_next: {ex['v_next']}")
    print(f"  energy: {ex['energy']:.2f}, threshold: {ex['energy_threshold']:.2f}")
    
    # Original method
    cross = ex['v_prev'][0] * ex['v_next'][1] - ex['v_prev'][1] * ex['v_next'][0]
    norm_prev = math.sqrt(ex['v_prev'][0]**2 + ex['v_prev'][1]**2)
    norm_next = math.sqrt(ex['v_next'][0]**2 + ex['v_next'][1]**2)
    denom = norm_prev * norm_next
    rot_norm = cross / denom if denom >= 1e-9 else 0
    
    print(f"\n  OLD METHOD (threshold |rot| > 0.6):")
    print(f"    rot_norm: {rot_norm:.6f}")
    print(f"    Detected: {'YES' if abs(rot_norm) > 0.6 and ex['energy'] >= ex['energy_threshold'] else 'NO'}")
    
    # New method
    is_vortex, meta = angle_aware_vortex_detection(
        ex['v_prev'], ex['v_next'], ex['energy'], ex['energy_threshold']
    )
    
    print(f"\n  NEW METHOD (threshold > 20° AND energy check):")
    print(f"    angle: {meta['angle_deg']:.2f}°")
    print(f"    Detected: {'YES' if is_vortex else 'NO'}")
    print(f"    Direction: {meta['direction']}")

print("\n" + "="*90)
print("CONCLUSION")
print("="*90)
print("""
The current implementation is mathematically correct but the threshold
appears unrealistically strict for practical use.

Recommended action:
1. Verify the 0.6 threshold is intentional with domain experts
2. Consider using pure angle measurement instead of normalized cross-product
3. If using current method, reduce threshold to ~0.06 for practical detection

The mathematics themselves are SOUND - only the threshold may need adjustment.
""")
print("="*90)
