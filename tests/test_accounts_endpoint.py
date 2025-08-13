#!/usr/bin/env python3
"""
Test script for the accounts endpoint
"""

import requests
import json

# Base URL for the API
BASE_URL = "http://localhost:8000/api/v1"

def test_accounts_endpoint():
    """Test the accounts endpoint without authentication"""
    try:
        # Test the accounts endpoint (should return 401 without auth)
        response = requests.get(f"{BASE_URL}/accounts/accounts")
        print(f"GET /accounts/accounts (no auth): {response.status_code}")
        
        if response.status_code == 401:
            print("✓ Correctly requires authentication")
        else:
            print(f"✗ Unexpected status code: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("✗ Could not connect to the server. Make sure the backend is running.")
    except Exception as e:
        print(f"✗ Error testing endpoint: {e}")

def test_accounts_endpoint_structure():
    """Test the endpoint structure by checking if it's accessible"""
    try:
        # Test if the server is running and the endpoint exists
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            print("✓ Backend server is running")
            
            # Try to get the OpenAPI docs to see if the accounts endpoint is registered
            try:
                docs_response = requests.get(f"{BASE_URL}/docs")
                if docs_response.status_code == 200:
                    print("✓ API documentation is accessible")
                    print("  You can view the full API docs at: http://localhost:8000/docs")
                else:
                    print("✗ API documentation not accessible")
            except:
                print("✗ Could not access API documentation")
        else:
            print(f"✗ Backend server returned status: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("✗ Could not connect to the server. Make sure the backend is running.")
    except Exception as e:
        print(f"✗ Error testing server: {e}")

if __name__ == "__main__":
    print("Testing Accounts Endpoint")
    print("=" * 40)
    
    test_accounts_endpoint_structure()
    print()
    test_accounts_endpoint()
    
    print("\n" + "=" * 40)
    print("Test completed!")
    print("\nTo test with authentication:")
    print("1. Start the backend server: python3 main.py")
    print("2. Get an access token by logging in")
    print("3. Use the token in the Authorization header")
    print("4. Test: curl -H 'Authorization: Bearer <token>' http://localhost:8000/api/v1/accounts/accounts")
