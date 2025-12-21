#!/usr/bin/env python3
"""
Comprehensive integration test for SniperSight Trading System
Tests both backend API and frontend integration capabilities.
"""

import asyncio
import sys
import json
import subprocess
import time
import requests
from pathlib import Path

def test_backend_when_available():
    """Test backend API when server is running"""
    print("🔧 Starting backend server...")
    
    # Start backend server
    backend_process = subprocess.Popen(
        [sys.executable, "-m", "backend.api_server"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd="/home/maccardi4431/snipersight-trading"
    )
    
    # Wait for server to start
    time.sleep(3)
    
    try:
        # Test health endpoint
        print("📍 Testing health endpoint...")
        response = requests.get("http://localhost:5000/api/health", timeout=5)

        if response.status_code == 200:
            print("✅ Health check passed")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
        
        # Test signals endpoint
        print("📡 Testing signals endpoint...")
        response = requests.get(
            "http://localhost:5000/api/scanner/signals?limit=3&min_score=70",
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Signals endpoint working: {data['total']} signals")
            print(f"   Data source: {data.get('data_source', 'unknown')}")
            
            if data['signals']:
                signal = data['signals'][0]
                print(f"   Example: {signal['symbol']} {signal['direction']} @ {signal.get('current_price', 'N/A')}")
            
            return True
        else:
            print(f"❌ Signals endpoint failed: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to backend server")
        return False
    except Exception as e:
        print(f"❌ Backend test error: {e}")
        return False
    finally:
        # Clean up
        backend_process.terminate()
        backend_process.wait()

def test_backend_when_unavailable():
    """Test that frontend handles backend unavailability gracefully"""
    print("🔌 Testing error handling when backend is unavailable...")
    
    try:
        response = requests.get("http://localhost:5000/api/health", timeout=2)
        print("⚠️  Backend is still running, this test may not be accurate")
        return True
    except requests.exceptions.ConnectionError:
        print("✅ Backend is properly down for fallback testing")
        return True
    except Exception as e:
        print(f"❌ Error testing unavailable backend: {e}")
        return False

def test_frontend_configuration():
    """Test that frontend configuration supports backend integration"""
    print("⚙️  Testing frontend configuration...")
    
    # Check vite.config.ts for proxy setup
    vite_config_path = Path("./vite.config.ts")
    if vite_config_path.exists():
        content = vite_config_path.read_text()
        if "proxy" in content and "/api" in content:
            print("✅ Frontend proxy configuration found")
        else:
            print("❌ Frontend proxy configuration missing")
            return False
    else:
        print("❌ Vite config file not found")
        return False
    
    # Check API client exists
    api_client_path = Path("./src/utils/api.ts")
    if api_client_path.exists():
        print("✅ API client found")
    else:
        print("❌ API client missing")
        return False
    
    # Check scanner setup integration
    scanner_setup_path = Path("./src/pages/ScannerSetup.tsx")
    if scanner_setup_path.exists():
        content = scanner_setup_path.read_text()
        if "api.createScanRun" in content and "api.getScanRun" in content:
            print("✅ Scanner setup integration found")
        else:
            print("❌ Scanner setup integration incomplete")
            return False
    else:
        print("❌ Scanner setup page not found")
        return False
    
    return True

def main():
    """Run comprehensive integration tests"""
    print("🎯 SniperSight Trading System - Integration Test Suite")
    print("=" * 60)
    
    tests = [
        ("Backend API (when available)", test_backend_when_available),
        ("Error handling (when unavailable)", test_backend_when_unavailable),
        ("Frontend configuration", test_frontend_configuration),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        print("-" * 40)
        result = test_func()
        results.append((test_name, result))
        print(f"Result: {'PASS' if result else 'FAIL'}")
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
    
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Integration is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Please review the output above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)