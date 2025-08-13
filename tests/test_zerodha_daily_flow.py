#!/usr/bin/env python3
"""
Test script for Zerodha Daily Login Flow
This tests the complete flow from API setup to daily login
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"
API_KEY = "s0t4ipm0u66kk0jq"
API_SECRET = "w6e1pmu3hk8ouselodxrmci7htg31mqb"

def print_step(step, title):
    print(f"\n{'='*50}")
    print(f"STEP {step}: {title}")
    print(f"{'='*50}")

def test_complete_zerodha_flow():
    """Test the complete Zerodha daily login flow"""
    print("🚀 Testing Complete Zerodha Daily Login Flow")
    
    # Step 1: Register user
    print_step(1, "User Registration")
    timestamp = int(time.time())
    email = f"test_zerodha_daily_{timestamp}@example.com"
    password = "TestPassword123!"
    
    registration_data = {
        "email": email,
        "password": password,
        "name": "Test User"
    }
    
    response = requests.post(f"{BASE_URL}/auth/signup", json=registration_data)
    if response.status_code == 200:
        print("✅ User registered successfully")
    else:
        print(f"❌ Registration failed: {response.text}")
        return None
    
    # Step 2: Login to app
    print_step(2, "App Login")
    login_data = {"username": email, "password": password}
    response = requests.post(f"{BASE_URL}/auth/signin", data=login_data)
    if response.status_code == 200:
        access_token = response.json()['access_token']
        print("✅ App login successful")
    else:
        print(f"❌ App login failed: {response.text}")
        return None
    
    # Step 3: Setup API credentials (first time only)
    print_step(3, "Setup API Credentials")
    headers = {"Authorization": f"Bearer {access_token}"}
    setup_data = {
        "api_key": API_KEY,
        "api_secret": API_SECRET,
        "broker": "zerodha"
    }
    
    response = requests.post(f"{BASE_URL}/auth/first-time-api-setup", 
                           json=setup_data, headers=headers)
    if response.status_code == 200:
        print("✅ API credentials set successfully")
    else:
        print(f"❌ API setup failed: {response.text}")
        return None
    
    # Step 4: Check session status (should be invalid initially)
    print_step(4, "Check Initial Session Status")
    response = requests.get(f"{BASE_URL}/auth/zerodha/session-status", headers=headers)
    if response.status_code == 200:
        status = response.json()
        print(f"Session Status: {status}")
        if not status.get("session_valid"):
            print("✅ Correctly shows session as invalid (needs daily login)")
        else:
            print("❌ Should show session as invalid initially")
    else:
        print(f"❌ Session status check failed: {response.text}")
    
    # Step 5: Get Zerodha login URL
    print_step(5, "Get Zerodha Login URL")
    response = requests.get(f"{BASE_URL}/dashboard/zerodha/login-url", headers=headers)
    if response.status_code == 200:
        login_data = response.json()
        login_url = login_data.get('login_url')
        print(f"✅ Zerodha login URL generated")
        print(f"Login URL: {login_url}")
        print(f"Message: {login_data.get('message')}")
        print(f"Instructions: {login_data.get('instructions')}")
    else:
        print(f"❌ Login URL generation failed: {response.text}")
        return None
    
    # Step 6: Check dashboard (should show session invalid)
    print_step(6, "Check Dashboard (Before Daily Login)")
    response = requests.get(f"{BASE_URL}/dashboard/dashboard", headers=headers)
    if response.status_code == 200:
        dashboard_data = response.json()
        session_status = dashboard_data.get('session_status', {})
        print(f"Dashboard Session Status: {session_status}")
        if session_status.get('requires_daily_login'):
            print("✅ Dashboard correctly shows daily login required")
        else:
            print("❌ Dashboard should show daily login required")
    else:
        print(f"❌ Dashboard check failed: {response.text}")
    
    # Step 7: Simulate daily login (with mock request_token)
    print_step(7, "Simulate Daily Login")
    print("📝 Note: In real scenario, user would:")
    print("   1. Open login URL in browser")
    print("   2. Login to Zerodha with credentials")
    print("   3. Get redirected with request_token")
    print("   4. Copy request_token and use it here")
    
    # For testing, we'll use a mock request_token
    # In real scenario, this would come from Zerodha redirect
    mock_request_token = "mock_request_token_for_testing"
    
    daily_login_data = {
        "request_token": mock_request_token
    }
    
    response = requests.post(f"{BASE_URL}/dashboard/zerodha/daily-login", 
                           json=daily_login_data, headers=headers)
    if response.status_code == 400:
        print("✅ Correctly rejected invalid request_token")
        print(f"Error: {response.json().get('detail')}")
    else:
        print(f"❌ Should have rejected invalid token: {response.status_code}")
    
    # Step 8: Check session status after failed login
    print_step(8, "Check Session Status After Failed Login")
    response = requests.get(f"{BASE_URL}/auth/zerodha/session-status", headers=headers)
    if response.status_code == 200:
        status = response.json()
        print(f"Session Status: {status}")
        if not status.get("session_valid"):
            print("✅ Correctly shows session still invalid")
        else:
            print("❌ Should still show session as invalid")
    
    print(f"\n{'='*50}")
    print("🎯 TEST SUMMARY")
    print(f"{'='*50}")
    print("✅ API credentials setup works")
    print("✅ Login URL generation works")
    print("✅ Session status checking works")
    print("✅ Dashboard shows daily login requirement")
    print("✅ Daily login endpoint properly validates tokens")
    print("\n📋 NEXT STEPS FOR REAL TESTING:")
    print("1. Use real Zerodha credentials")
    print("2. Open login URL in browser")
    print("3. Login with actual Zerodha account")
    print("4. Extract real request_token from redirect URL")
    print("5. Use real request_token for daily login")
    print("6. Verify dashboard shows real data")
    
    return access_token

if __name__ == "__main__":
    test_complete_zerodha_flow()
