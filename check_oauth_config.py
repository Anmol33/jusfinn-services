#!/usr/bin/env python3
"""
Script to check OAuth2 configuration and help debug redirect_uri_mismatch errors.
"""

import httpx
import json
from urllib.parse import urlparse, parse_qs


def check_oauth_config():
    """Check the OAuth2 configuration."""
    print("🔍 Checking OAuth2 Configuration")
    print("=" * 50)
    
    # Test backend health
    print("\n1. Testing backend health...")
    try:
        response = httpx.get("http://localhost:8000/health")
        if response.status_code == 200:
            print("✅ Backend is running")
        else:
            print(f"❌ Backend health check failed: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Cannot connect to backend: {e}")
        print("Make sure the backend is running: uvicorn app.main:app --reload --port 8000")
        return
    
    # Test OAuth login endpoint
    print("\n2. Testing OAuth login endpoint...")
    try:
        response = httpx.get("http://localhost:8000/auth/google/login")
        if response.status_code == 200:
            data = response.json()
            auth_url = data.get("authorization_url")
            print("✅ OAuth login endpoint working")
            
            # Parse the authorization URL
            parsed = urlparse(auth_url)
            params = parse_qs(parsed.query)
            
            print(f"\n📋 Authorization URL details:")
            print(f"   Base URL: {parsed.scheme}://{parsed.netloc}{parsed.path}")
            print(f"   Client ID: {params.get('client_id', ['Not found'])[0]}")
            print(f"   Redirect URI: {params.get('redirect_uri', ['Not found'])[0]}")
            print(f"   Response Type: {params.get('response_type', ['Not found'])[0]}")
            print(f"   Scope: {params.get('scope', ['Not found'])[0]}")
            
            # Check if redirect URI matches expected
            expected_redirect = "http://localhost:8000/auth/google/callback"
            actual_redirect = params.get('redirect_uri', [''])[0]
            
            if actual_redirect == expected_redirect:
                print(f"✅ Redirect URI matches expected: {actual_redirect}")
            else:
                print(f"❌ Redirect URI mismatch!")
                print(f"   Expected: {expected_redirect}")
                print(f"   Actual:   {actual_redirect}")
                print("\n🔧 To fix this:")
                print("1. Go to Google Cloud Console")
                print("2. Navigate to APIs & Services > Credentials")
                print("3. Edit your OAuth 2.0 Client ID")
                print("4. Add this redirect URI: http://localhost:8000/auth/google/callback")
            
        else:
            print(f"❌ OAuth login endpoint failed: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error testing OAuth endpoint: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 Configuration Check Complete")
    print("\nIf you see redirect_uri_mismatch errors:")
    print("1. Make sure the redirect URI in Google Cloud Console matches exactly:")
    print("   http://localhost:8000/auth/google/callback")
    print("2. Check that there are no extra spaces or characters")
    print("3. Make sure the protocol (http/https) matches")
    print("4. Make sure the port number matches")


if __name__ == "__main__":
    check_oauth_config() 