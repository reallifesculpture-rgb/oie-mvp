"""
Test backend endpoints: /api/v1/topology/TEST
"""
import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

print("\n" + "="*80)
print("TESTING BACKEND ENDPOINTS")
print("="*80)

# Test 1: GET /api/v1/topology/TEST
print("\n[1] GET /api/v1/topology/TEST")
print("-" * 80)

try:
    response = requests.get(f"{BASE_URL}/api/v1/topology/TEST")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Response:")
        print(json.dumps(data, indent=2, default=str))
    else:
        print(f"❌ Error: {response.text}")
except Exception as e:
    print(f"❌ Connection error: {e}")

# Test 2: POST /api/v1/replay/bars (if exists)
print("\n[2] Check available endpoints")
print("-" * 80)

try:
    response = requests.get(f"{BASE_URL}/openapi.json")
    if response.status_code == 200:
        openapi = response.json()
        paths = openapi.get("paths", {})
        print(f"Available endpoints ({len(paths)}):")
        for path in sorted(paths.keys()):
            methods = list(paths[path].keys())
            print(f"  {path}: {', '.join(methods)}")
except Exception as e:
    print(f"Could not fetch OpenAPI schema: {e}")

print("\n" + "="*80)
print("To access Swagger UI: http://localhost:8000/docs")
print("="*80)
