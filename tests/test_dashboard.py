#!/usr/bin/env python3
import requests
import json

BASE_URL = "http://localhost:8000"

def test_dashboard_endpoints():
    # Step 1: Get access token
    login_data = {
        "username": "riturithesh66@gmail.com",
        "password": "string"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/signin",
        data=login_data
    )
    
    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data["access_token"]
        print(f"✅ Access token obtained: {access_token[:20]}...")
        
        # Step 2: Test dashboard data endpoint
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Test GET /dashboard
        dashboard_response = requests.get(
            f"{BASE_URL}/api/v1/dashboard/dashboard",
            headers=headers
        )
        print(f"Dashboard endpoint: {dashboard_response.status_code}")
        if dashboard_response.status_code == 200:
            print("✅ Dashboard data retrieved successfully")
        
        # Test POST /activate-brokerage
        brokerage_data = {
            "brokerage": "zerodha",
            "api_url": "https://api.kite.trade",
            "api_key": "test_api_key",
            "api_secret": "test_api_secret",
            "request_token": "test_request_token"
        }
        
        brokerage_response = requests.post(
            f"{BASE_URL}/api/v1/dashboard/activate-brokerage",
            headers=headers,
            json=brokerage_data
        )
        print(f"Brokerage activation: {brokerage_response.status_code}")
        if brokerage_response.status_code == 200:
            print("✅ Brokerage activation successful")
            
    else:
        print(f"❌ Login failed: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    test_dashboard_endpoints() 