#!/usr/bin/env python3
"""
Test script for OAuth2 flow endpoints.
Run this script to test the OAuth2 implementation.
"""

import asyncio
import httpx
import json
from urllib.parse import urlparse, parse_qs


async def test_oauth_flow():
    """Test the OAuth2 flow endpoints."""
    base_url = "http://localhost:8000"
    
    print("🧪 Testing OAuth2 Flow")
    print("=" * 50)
    
    # Test 1: Get authorization URL
    print("\n1. Testing GET /auth/google/login")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/auth/google/login")
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                auth_url = data.get("authorization_url")
                print(f"✅ Authorization URL received")
                print(f"URL: {auth_url[:100]}...")
                
                # Parse the URL to check parameters
                parsed = urlparse(auth_url)
                params = parse_qs(parsed.query)
                
                required_params = ["client_id", "redirect_uri", "response_type", "scope"]
                missing_params = [param for param in required_params if param not in params]
                
                if not missing_params:
                    print("✅ All required OAuth parameters present")
                else:
                    print(f"❌ Missing parameters: {missing_params}")
            else:
                print(f"❌ Failed to get authorization URL: {response.text}")
                
    except Exception as e:
        print(f"❌ Error testing authorization URL: {e}")
    
    # Test 2: Test callback endpoint with invalid code
    print("\n2. Testing GET /auth/google/callback (with invalid code)")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/auth/google/callback?code=invalid_code")
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ Callback endpoint responds (should redirect to frontend)")
            else:
                print(f"❌ Callback endpoint error: {response.text}")
                
    except Exception as e:
        print(f"❌ Error testing callback: {e}")
    
    # Test 3: Test health endpoint
    print("\n3. Testing GET /health")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/health")
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health check passed: {data}")
            else:
                print(f"❌ Health check failed: {response.text}")
                
    except Exception as e:
        print(f"❌ Error testing health endpoint: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 OAuth2 Flow Test Complete")
    print("\nNext steps:")
    print("1. Start the backend: uvicorn app.main:app --reload --port 8001")
    print("2. Start the frontend: npm run dev")
    print("3. Navigate to http://localhost:8000/signin")
    print("4. Click 'Sign in with Google'")
    print("5. Complete the OAuth flow")


if __name__ == "__main__":
    asyncio.run(test_oauth_flow()) 