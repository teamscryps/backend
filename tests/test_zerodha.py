import requests
import json

BASE_URL = "http://localhost:8000/api/v1"
API_KEY = "s0t4ipm0u66kk0jq"
API_SECRET = "w6e1pmu3hk8ouselodxrmci7htg31mqb"

def test_zerodha_integration():
    print("🚀 Testing Zerodha Integration")
    
    # Step 1: Register user
    import time
    timestamp = int(time.time())
    email = f"test_zerodha_{timestamp}@example.com"
    password = "TestPassword123!"
    
    registration_data = {
        "email": email,
        "password": password,
        "name": "Test User"
    }
    
    print("\n1. Registering user...")
    response = requests.post(f"{BASE_URL}/auth/signup", json=registration_data)
    if response.status_code == 200:
        print("✅ User registered successfully")
    else:
        print(f"❌ Registration failed: {response.text}")
        return
    
    # Step 2: Login
    print("\n2. Logging in...")
    login_data = {"username": email, "password": password}
    response = requests.post(f"{BASE_URL}/auth/signin", data=login_data)
    if response.status_code == 200:
        access_token = response.json()['access_token']
        print("✅ Login successful")
    else:
        print(f"❌ Login failed: {response.text}")
        return
    
    # Step 3: Setup API credentials
    print("\n3. Setting up API credentials...")
    headers = {"Authorization": f"Bearer {access_token}"}
    setup_data = {
        "api_key": API_KEY,
        "api_secret": API_SECRET,
        "broker": "zerodha"
    }
    response = requests.post(f"{BASE_URL}/auth/first-time-api-setup", 
                           json=setup_data, headers=headers)
    if response.status_code == 200:
        print("✅ API credentials set")
    else:
        print(f"❌ API setup failed: {response.text}")
        return
    
    # Step 4: Get Zerodha login URL
    print("\n4. Getting Zerodha login URL...")
    response = requests.get(f"{BASE_URL}/dashboard/zerodha/login-url", headers=headers)
    if response.status_code == 200:
        login_url = response.json()['login_url']
        print(f"✅ Login URL: {login_url}")
        print(f"\n📋 Open this URL and login with:")
        print(f"   Client ID: NRA237")
        print(f"   Password: Ram@1433")
    else:
        print(f"❌ Login URL failed: {response.text}")
        return
    
    # Step 5: Test dashboard
    print("\n5. Testing dashboard...")
    response = requests.get(f"{BASE_URL}/dashboard/dashboard", headers=headers)
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Dashboard: Broker={data.get('broker')}, Session={data.get('session_id')}")
        print(f"   Unused Funds: {data.get('unused_funds')}")
        print(f"   Allocated Funds: {data.get('allocated_funds')}")
        print(f"   Holdings Count: {len(data.get('holdings', []))}")
    else:
        print(f"❌ Dashboard failed: {response.text}")

if __name__ == "__main__":
    test_zerodha_integration()
