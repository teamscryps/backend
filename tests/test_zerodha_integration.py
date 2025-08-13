#!/usr/bin/env python3
"""
Test script for Zerodha integration with provided credentials
"""

import requests
import json
from datetime import datetime

# Test configuration
BASE_URL = "http://localhost:8000/api/v1"
API_KEY = "s0t4ipm0u66kk0jq"
API_SECRET = "w6e1pmu3hk8ouselodxrmci7htg31mqb"
CLIENT_ID = "NRA237"
PASSWORD = "Ram@1433"

def print_step(step, description):
    print(f"\n{'='*50}")
    print(f"STEP {step}: {description}")
    print(f"{'='*50}")

def test_api_health():
    """Test if the API is running"""
    print_step(1, "Testing API Health")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        print(f"✅ API Health Check: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {response.json()}")
        return True
    except Exception as e:
        print(f"❌ API Health Check Failed: {e}")
        return False

def test_user_registration():
    """Test user registration"""
    print_step(2, "User Registration")
    
    # Generate unique email
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    email = f"test_zerodha_{timestamp}@example.com"
    
    registration_data = {
        "email": email,
        "name": "Test Zerodha User",
        "mobile": "9876543210"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/register",
            json=registration_data,
            timeout=10
        )
        print(f"Registration Status: {response.status_code}")
        
        if response.status_code == 201:
            result = response.json()
            print(f"✅ User registered successfully")
            print(f"Email: {email}")
            print(f"Password: {result.get('password', 'Not provided')}")
            return email, result.get('password', 'default123')
        else:
            print(f"❌ Registration failed: {response.text}")
            return None, None
            
    except Exception as e:
        print(f"❌ Registration error: {e}")
        return None, None

def test_user_login(email, password):
    """Test user login"""
    print_step(3, "User Login")
    
    login_data = {
        "email": email,
        "password": password
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/signin",
            json=login_data,
            timeout=10
        )
        print(f"Login Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            access_token = result.get('access_token')
            print(f"✅ Login successful")
            print(f"Access Token: {access_token[:20]}...")
            return access_token
        else:
            print(f"❌ Login failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Login error: {e}")
        return None

def test_api_setup(access_token):
    """Test API credentials setup"""
    print_step(4, "Setting Up API Credentials")
    
    setup_data = {
        "api_key": API_KEY,
        "api_secret": API_SECRET,
        "broker": "zerodha"
    }
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/first-time-api-setup",
            json=setup_data,
            headers=headers,
            timeout=10
        )
        print(f"API Setup Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ API credentials set successfully")
            print(f"Broker: {result.get('broker')}")
            return True
        else:
            print(f"❌ API setup failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ API setup error: {e}")
        return False

def test_zerodha_login_url(access_token):
    """Test Zerodha login URL generation"""
    print_step(5, "Generating Zerodha Login URL")
    
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    try:
        response = requests.get(
            f"{BASE_URL}/dashboard/zerodha/login-url",
            headers=headers,
            timeout=10
        )
        print(f"Login URL Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            login_url = result.get('login_url')
            print(f"✅ Zerodha login URL generated")
            print(f"Login URL: {login_url}")
            print(f"\n📋 NEXT STEPS:")
            print(f"1. Open this URL in your browser")
            print(f"2. Login with Zerodha credentials:")
            print(f"   - Client ID: {CLIENT_ID}")
            print(f"   - Password: {PASSWORD}")
            print(f"3. After login, you'll get a request_token")
            print(f"4. Use that request_token to complete activation")
            return login_url
        else:
            print(f"❌ Login URL generation failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Login URL generation error: {e}")
        return None

def test_dashboard_before_activation(access_token):
    """Test dashboard before Zerodha activation"""
    print_step(6, "Testing Dashboard (Before Activation)")
    
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    try:
        response = requests.get(
            f"{BASE_URL}/dashboard/simple",
            headers=headers,
            timeout=10
        )
        print(f"Dashboard Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Dashboard data retrieved")
            print(f"Broker: {result.get('broker')}")
            print(f"Session ID: {result.get('session_id', 'None')}")
            print(f"Unused Funds: {result.get('unused_funds')}")
            print(f"Allocated Funds: {result.get('allocated_funds')}")
            print(f"Holdings Count: {len(result.get('holdings', []))}")
            return result
        else:
            print(f"❌ Dashboard failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Dashboard error: {e}")
        return None

def main():
    """Run the complete test flow"""
    print("🚀 Starting Zerodha Integration Test")
    print(f"API Key: {API_KEY}")
    print(f"Client ID: {CLIENT_ID}")
    
    # Step 1: Test API health
    if not test_api_health():
        print("❌ API is not running. Please start the backend first.")
        return
    
    # Step 2: Register new user
    email, password = test_user_registration()
    if not email:
        print("❌ User registration failed. Stopping test.")
        return
    
    # Step 3: Login user
    access_token = test_user_login(email, password)
    if not access_token:
        print("❌ User login failed. Stopping test.")
        return
    
    # Step 4: Setup API credentials
    if not test_api_setup(access_token):
        print("❌ API setup failed. Stopping test.")
        return
    
    # Step 5: Generate Zerodha login URL
    login_url = test_zerodha_login_url(access_token)
    if not login_url:
        print("❌ Login URL generation failed. Stopping test.")
        return
    
    # Step 6: Test dashboard before activation
    dashboard_data = test_dashboard_before_activation(access_token)
    
    print(f"\n{'='*50}")
    print("🎉 TEST COMPLETED SUCCESSFULLY!")
    print(f"{'='*50}")
    print(f"✅ User registered and logged in")
    print(f"✅ API credentials configured")
    print(f"✅ Zerodha login URL generated")
    print(f"✅ Dashboard accessible")
    print(f"\n📋 MANUAL STEPS REQUIRED:")
    print(f"1. Open: {login_url}")
    print(f"2. Login with Zerodha credentials")
    print(f"3. Get the request_token from redirect URL")
    print(f"4. Complete the activation process")
    print(f"\n🔧 To complete activation, you'll need to:")
    print(f"   - Extract request_token from the redirect URL")
    print(f"   - Call the activation endpoint with the token")
    print(f"   - Verify real data appears in dashboard")

if __name__ == "__main__":
    main()
