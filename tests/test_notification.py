#!/usr/bin/env python3
"""
Test script to send a notification to the API server.
"""
import requests
import json
import sys

def send_test_notification():
    """Send a test notification to the API server."""
    url = "http://localhost:8000/api/notifications/send"
    
    notification_data = {
        "type": "signal",
        "priority": "high",
        "title": "🎯 Trade Signal Alert",
        "message": "SMC analysis detected a high-probability trade setup on BTCUSDT. Strong bullish momentum with entry at $43,250.",
        "data": {
            "symbol": "BTCUSDT",
            "entry_price": 43250,
            "target_price": 45000,
            "stop_loss": 42800,
            "confidence": 0.87,
            "setup_type": "bullish_engulfing",
            "timeframe": "4h"
        }
    }
    
    try:
        print("Sending test notification...")
        response = requests.post(url, json=notification_data, timeout=10)
        
        print(f"Response Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Body: {response.text}")
        
        if response.status_code == 200:
            print("✅ Notification sent successfully!")
            return True
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False

def get_notifications():
    """Get all notifications from the API server."""
    url = "http://localhost:8000/api/notifications"
    
    try:
        print("Fetching notifications...")
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Found {len(data.get('notifications', []))} notifications")
            for notif in data.get('notifications', [])[:3]:  # Show first 3
                print(f"  - {notif.get('title', 'No title')} ({notif.get('priority', 'normal')})")
            return True
        else:
            print(f"❌ Error fetching notifications: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing SniperSight Notification System")
    print("=" * 50)
    
    # First, try to get existing notifications
    if get_notifications():
        print()
    
    # Then send a test notification
    if send_test_notification():
        print()
        # Get notifications again to verify it was added
        get_notifications()
    
    print("=" * 50)
    print("Test complete!")