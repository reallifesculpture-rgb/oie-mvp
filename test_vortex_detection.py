"""
Quick validation: Test vortex detection with adjusted threshold (15°)
"""
import math
import sys
from datetime import datetime, timedelta

sys.path.insert(0, r'c:\Users\gyorg\OneDrive\Desktop\OIE')

from backend.data.models import Bar
from backend.topology.engine import TopologyEngine

# Create aggressive bars (same as before)
base_time = datetime(2025, 1, 1, 9, 30, 0)
bars = []

# Baseline
for i in range(3):
    bar = Bar(
        timestamp=base_time + timedelta(minutes=i),
        open=100.0, high=100.1, low=99.9, close=100.05,
        volume=1000.0, buy_volume=600.0, sell_volume=400.0, delta=200.0, atr=0.1
    )
    bars.append(bar)

# Vortex Zone 1: Extreme swings
bars.append(Bar(timestamp=base_time + timedelta(minutes=3), open=100.05, high=103.05, low=99.55, close=102.55,
               volume=5000.0, buy_volume=4500.0, sell_volume=500.0, delta=4000.0, atr=1.5))
bars.append(Bar(timestamp=base_time + timedelta(minutes=4), open=102.55, high=103.05, low=100.55, close=100.55,
               volume=5000.0, buy_volume=500.0, sell_volume=4500.0, delta=-4000.0, atr=1.5))
bars.append(Bar(timestamp=base_time + timedelta(minutes=5), open=100.55, high=102.55, low=100.05, close=102.55,
               volume=5000.0, buy_volume=4500.0, sell_volume=500.0, delta=4000.0, atr=1.5))

# Stabilize
for i in range(3):
    bar = Bar(
        timestamp=base_time + timedelta(minutes=6+i),
        open=102.55, high=102.85, low=102.35, close=102.70,
        volume=1500.0, buy_volume=950.0, sell_volume=550.0, delta=400.0, atr=0.3
    )
    bars.append(bar)

# Vortex Zone 2
bars.append(Bar(timestamp=base_time + timedelta(minutes=9), open=102.70, high=102.70, low=99.70, close=99.70,
               volume=5500.0, buy_volume=500.0, sell_volume=5000.0, delta=-4500.0, atr=1.8))
bars.append(Bar(timestamp=base_time + timedelta(minutes=10), open=99.70, high=102.20, low=99.20, close=102.20,
               volume=5000.0, buy_volume=4750.0, sell_volume=250.0, delta=4500.0, atr=1.6))
bars.append(Bar(timestamp=base_time + timedelta(minutes=11), open=102.20, high=102.20, low=100.20, close=100.70,
               volume=5200.0, buy_volume=600.0, sell_volume=4600.0, delta=-4000.0, atr=1.4))

# Settle
for i in range(3):
    bar = Bar(
        timestamp=base_time + timedelta(minutes=12+i),
        open=100.70, high=100.90, low=100.60, close=100.75,
        volume=1200.0, buy_volume=700.0, sell_volume=500.0, delta=200.0, atr=0.2
    )
    bars.append(bar)

print("\n" + "="*80)
print("VORTEX DETECTION TEST - WITH 15° ANGLE THRESHOLD")
print("="*80)

engine = TopologyEngine()
snapshot = engine.compute("AGGRESSIVE", bars)

print(f"\nDataset: {len(bars)} bars")
print(f"Price range: {min(b.close for b in bars):.2f} - {max(b.close for b in bars):.2f}")
print(f"\nTopologySnapshot:")
print(f"  Coherence: {snapshot.coherence:.6f}")
print(f"  Energy: {snapshot.energy:.4f}")
print(f"  Vortexes detected: {len(snapshot.vortexes)}")

if snapshot.vortexes:
    print(f"\n✓ VORTEXES DETECTED!")
    for i, marker in enumerate(snapshot.vortexes, 1):
        print(f"\n  Vortex {i}:")
        print(f"    Bar index: {marker.index}")
        print(f"    Price: {marker.price:.4f}")
        print(f"    Strength: {marker.strength:.6f}")
        print(f"    Direction: {marker.direction}")
else:
    print(f"\n⚠ No vortexes detected")
    print(f"  Note: With 15° threshold, should detect rotations in high-energy zones")

print("\n" + "="*80)
