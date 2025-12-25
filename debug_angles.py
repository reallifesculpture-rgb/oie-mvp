"""
Debug: Analyze angles and energies in detail
"""
import math
import sys
from datetime import datetime, timedelta

sys.path.insert(0, r'c:\Users\gyorg\OneDrive\Desktop\OIE')

from backend.data.models import Bar

# Create aggressive bars
base_time = datetime(2025, 1, 1, 9, 30, 0)
bars = []

prices = [100.0, 100.05, 100.05, 102.55, 100.55, 102.55, 102.70, 102.70, 102.70, 99.70, 102.20, 100.70, 100.75, 100.75, 100.75]
volumes = [1000, 1000, 1000, 5000, 5000, 5000, 1500, 1500, 1500, 5500, 5000, 5200, 1200, 1200, 1200]
deltas = [200, 200, 200, 4000, -4000, 4000, 400, 400, 400, -4500, 4500, -4000, 200, 200, 200]

for i, (p, v, d) in enumerate(zip(prices, volumes, deltas)):
    bar = Bar(
        timestamp=base_time + timedelta(minutes=i),
        open=p, high=p+0.5, low=p-0.5, close=p,
        volume=v, buy_volume=v/2+d/2, sell_volume=v/2-d/2,
        delta=d, atr=0.5
    )
    bars.append(bar)

print("\n" + "="*100)
print("DETAILED ANGLE & ENERGY ANALYSIS")
print("="*100)

# Compute returns and flows
returns = []
for i in range(len(bars)):
    if i == 0:
        ret = 0.0
    else:
        prev_close = bars[i-1].close
        ret = 0.0 if prev_close == 0 else (bars[i].close - prev_close) / abs(prev_close)
    returns.append(ret)

flows = []
for i in range(len(bars)):
    if bars[i].volume and bars[i].volume > 0 and bars[i].delta is not None:
        flow = bars[i].delta / bars[i].volume
    else:
        flow = 0.0
    flows.append(flow)

print("\nReturns and Flows:")
for i in range(len(bars)):
    print(f"  Bar {i:2d}: ret={returns[i]:8.6f}, flow={flows[i]:8.6f}")

# Compute angles
def norm(v):
    return math.sqrt(v[0]**2 + v[1]**2)

print("\n" + "="*100)
print("Angle Computations:")
print("="*100)

for k in range(1, len(bars)-1):
    v_prev = (returns[k-1], flows[k-1])
    v_next = (returns[k+1], flows[k+1])
    
    cross = v_prev[0] * v_next[1] - v_prev[1] * v_next[0]
    denom = norm(v_prev) * norm(v_next)
    
    if denom < 1e-9:
        rot_norm = 0.0
    else:
        rot_norm = cross / denom
    
    clamped = max(-1.0, min(1.0, rot_norm))
    angle_deg = math.degrees(math.asin(clamped))
    
    energy = abs(returns[k]) * bars[k].volume
    
    # Highlight high energy + large angle
    marker = ""
    if abs(angle_deg) > 15 and energy > 50:
        marker = " ← ✓ VORTEX"
    elif abs(angle_deg) > 15:
        marker = " ← High angle"
    elif energy > 50:
        marker = " ← High energy"
    
    print(f"Bar {k:2d}: angle={angle_deg:7.2f}°, energy={energy:10.2f}, |angle|>15={abs(angle_deg)>15}, energy>50={energy>50}{marker}")

# Get thresholds
energies = []
for k in range(1, len(bars)-1):
    energy = abs(returns[k]) * bars[k].volume
    energies.append(energy)

sorted_energies = sorted(energies)
thr_index = int(0.7 * len(sorted_energies))
thr_index = max(0, min(thr_index, len(sorted_energies)-1))
energy_threshold = sorted_energies[thr_index]

print(f"\n70th percentile energy threshold: {energy_threshold:.2f}")
print(f"Sorted energies: {sorted_energies}")
print(f"Threshold at index {thr_index}: {energy_threshold:.2f}")

print("\n" + "="*100)
