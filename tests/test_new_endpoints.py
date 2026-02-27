#!/usr/bin/env python3
"""
Test script for new bulk prices and background scan endpoints.
Run backend server first: python -m uvicorn backend.api_server:app --host 0.0.0.0 --port 5000
"""
import asyncio
import httpx

BASE_URL = "http://localhost:5000"

async def test_bulk_prices():
    """Test /api/market/prices endpoint with multiple symbols."""
    print("\n🧪 Testing bulk prices endpoint...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test with 5 symbols
        symbols = "BTC/USDT,ETH/USDT,BNB/USDT,SOL/USDT,XRP/USDT"
        response = await client.get(
            f"{BASE_URL}/api/market/prices",
            params={"symbols": symbols, "exchange": "phemex"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Received {data['total']} prices:")
            for item in data['prices'][:3]:  # Show first 3
                print(f"   {item['symbol']}: ${item['price']:,.2f}")
            if data.get('errors'):
                print(f"⚠️  {len(data['errors'])} errors:")
                for err in data['errors']:
                    print(f"   {err['symbol']}: {err['error']}")
        else:
            print(f"❌ Failed: {response.status_code}")
            print(response.text)

async def test_background_scan():
    """Test background scan job endpoints."""
    print("\n🧪 Testing background scan job system...")
    
    async with httpx.AsyncClient(timeout=180.0) as client:
        # Start a scan job
        print("Starting scan job...")
        create_response = await client.post(
            f"{BASE_URL}/api/scanner/runs",
            params={
                "limit": 3,
                "min_score": 0,
                "sniper_mode": "surgical",
                "majors": True,
                "altcoins": False,
                "meme_mode": False,
                "exchange": "phemex",
                "leverage": 1
            }
        )
        
        if create_response.status_code != 200:
            print(f"❌ Failed to create job: {create_response.status_code}")
            print(create_response.text)
            return
        
        job_data = create_response.json()
        run_id = job_data['run_id']
        print(f"✅ Job created: {run_id}")
        
        # Poll for completion
        max_attempts = 60
        for i in range(max_attempts):
            await asyncio.sleep(2)
            
            status_response = await client.get(f"{BASE_URL}/api/scanner/runs/{run_id}")
            if status_response.status_code != 200:
                print(f"❌ Failed to get status: {status_response.status_code}")
                break
            
            status = status_response.json()
            print(f"  [{i+1}] Status: {status['status']} | Progress: {status['progress']}/{status['total']}", end='')
            if status.get('current_symbol'):
                print(f" | Current: {status['current_symbol']}")
            else:
                print()
            
            if status['status'] == 'completed':
                print(f"✅ Scan completed!")
                print(f"   Signals: {len(status.get('signals', []))}")
                print(f"   Metadata: {status.get('metadata', {})}")
                break
            elif status['status'] in ['failed', 'cancelled']:
                print(f"❌ Job {status['status']}: {status.get('error', 'No error message')}")
                break
        else:
            print(f"⏱️ Timeout after {max_attempts} attempts")

async def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing New Endpoints")
    print("=" * 60)
    
    try:
        await test_bulk_prices()
        await test_background_scan()
        print("\n✅ All tests completed!")
    except Exception as e:
        print(f"\n❌ Test error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
