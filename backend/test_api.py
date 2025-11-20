#!/usr/bin/env python3
"""
Test script to verify API endpoints are working.
"""

import requests
import json
from time import sleep

BASE_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint."""
    print("Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/api/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    return response.status_code == 200

def test_scanner_workflow():
    """Test scanner configuration and signals."""
    print("Testing scanner workflow...")
    
    # Create scanner config
    config = {
        "exchange": "binance",
        "symbols": ["BTC/USDT", "ETH/USDT"],
        "timeframes": ["1h", "4h"],
        "min_score": 70,
        "indicators": {
            "order_blocks": True,
            "fvg": True,
            "liquidity_sweeps": True
        }
    }
    
    response = requests.post(f"{BASE_URL}/api/scanner/config", json=config)
    print(f"Create config - Status: {response.status_code}")
    config_data = response.json()
    print(f"Response: {json.dumps(config_data, indent=2)}\n")
    
    if response.status_code != 200:
        return False
    
    config_id = config_data["config_id"]
    
    # Start scanner
    response = requests.post(f"{BASE_URL}/api/scanner/{config_id}/start")
    print(f"Start scanner - Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    
    # Get signals
    response = requests.get(f"{BASE_URL}/api/scanner/signals?limit=10")
    print(f"Get signals - Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    
    return response.status_code == 200

def test_bot_workflow():
    """Test bot configuration and trading."""
    print("Testing bot workflow...")
    
    # Create bot config
    config = {
        "exchange": "binance",
        "leverage": 3,
        "risk_per_trade": 2.0,
        "max_positions": 3,
        "stop_loss_pct": 2.0,
        "take_profit_pct": 6.0
    }
    
    response = requests.post(f"{BASE_URL}/api/bot/config", json=config)
    print(f"Create config - Status: {response.status_code}")
    config_data = response.json()
    print(f"Response: {json.dumps(config_data, indent=2)}\n")
    
    if response.status_code != 200:
        return False
    
    config_id = config_data["config_id"]
    
    # Get bot status
    response = requests.get(f"{BASE_URL}/api/bot/status")
    print(f"Get status - Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    
    # Place an order
    order = {
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_type": "MARKET",
        "quantity": 0.001,
        "price": 50000,
        "leverage": 1
    }
    
    response = requests.post(f"{BASE_URL}/api/bot/order", json=order)
    print(f"Place order - Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    
    # Get positions
    response = requests.get(f"{BASE_URL}/api/bot/positions")
    print(f"Get positions - Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    
    return response.status_code == 200

def test_risk_management():
    """Test risk management endpoints."""
    print("Testing risk management...")
    
    response = requests.get(f"{BASE_URL}/api/risk/summary")
    print(f"Get risk summary - Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    
    return response.status_code == 200

def main():
    """Run all tests."""
    print("=" * 60)
    print("SniperSight API Integration Tests")
    print("=" * 60 + "\n")
    
    tests = [
        ("Health Check", test_health),
        ("Scanner Workflow", test_scanner_workflow),
        ("Bot Workflow", test_bot_workflow),
        ("Risk Management", test_risk_management),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, "PASSED" if passed else "FAILED"))
        except Exception as e:
            print(f"ERROR: {str(e)}\n")
            results.append((name, "ERROR"))
    
    print("\n" + "=" * 60)
    print("Test Results")
    print("=" * 60)
    for name, result in results:
        status_symbol = "✓" if result == "PASSED" else "✗"
        print(f"{status_symbol} {name}: {result}")
    
    all_passed = all(r[1] == "PASSED" for r in results)
    print("\n" + ("All tests passed! ✓" if all_passed else "Some tests failed ✗"))

if __name__ == "__main__":
    main()
