"""
Full Pipeline Test:
1. POST /api/v1/replay/reset - Initialize replay
2. POST /api/v1/replay/step - Step through bars
3. GET /api/v1/topology/{symbol} - Get topology snapshot
4. GET /api/v1/predictive/{symbol} - Get predictions
5. GET /api/v1/signals/{symbol} - Get signals
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

print("\n" + "="*80)
print("FULL PIPELINE TEST")
print("="*80)

# Step 1: Check replay info
print("\n[1] GET /api/v1/replay/info - Check replay state")
print("-" * 80)
try:
    response = requests.get(f"{BASE_URL}/api/v1/replay/info")
    print(f"Status: {response.status_code}")
    data = response.json()
    print(json.dumps(data, indent=2, default=str))
except Exception as e:
    print(f"Error: {e}")

# Step 2: Reset replay
print("\n[2] POST /api/v1/replay/reset - Initialize")
print("-" * 80)
try:
    response = requests.post(f"{BASE_URL}/api/v1/replay/reset")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("✓ Replay initialized")
    else:
        print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")

# Step 3: Step through some bars
print("\n[3] POST /api/v1/replay/step - Step through bars")
print("-" * 80)
for i in range(5):
    try:
        response = requests.post(f"{BASE_URL}/api/v1/replay/step")
        if response.status_code == 200:
            print(f"Step {i+1}: ✓")
        else:
            print(f"Step {i+1}: ❌ {response.status_code}")
    except Exception as e:
        print(f"Step {i+1}: Error {e}")

# Step 4: Get replay info
print("\n[4] GET /api/v1/replay/info - Check progress")
print("-" * 80)
try:
    response = requests.get(f"{BASE_URL}/api/v1/replay/info")
    data = response.json()
    print(json.dumps(data, indent=2, default=str))
except Exception as e:
    print(f"Error: {e}")

# Step 5: Get topology
print("\n[5] GET /api/v1/topology/{symbol} - Get topology snapshot")
print("-" * 80)
symbol = "TEST"  # Default symbol
try:
    response = requests.get(f"{BASE_URL}/api/v1/topology/{symbol}")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(json.dumps(data, indent=2, default=str))
    else:
        print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")

# Step 6: Get predictive
print("\n[6] GET /api/v1/predictive/{symbol} - Get predictions")
print("-" * 80)
try:
    response = requests.get(f"{BASE_URL}/api/v1/predictive/{symbol}")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(json.dumps(data, indent=2, default=str))
    else:
        print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")

# Step 7: Get signals
print("\n[7] GET /api/v1/signals/{symbol} - Get signals")
print("-" * 80)
try:
    response = requests.get(f"{BASE_URL}/api/v1/signals/api/v1/signals/{symbol}")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(json.dumps(data, indent=2, default=str))
    else:
        print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*80)
print("Pipeline test complete!")
print("="*80)
