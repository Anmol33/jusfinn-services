#!/usr/bin/env python3
"""
Simple test script to verify the FastAPI setup and MongoDB connection.
"""

import asyncio
import sys
from motor.motor_asyncio import AsyncIOMotorClient


async def test_mongodb_connection():
    """Test MongoDB connection."""
    try:
        # Test connection to MongoDB Atlas
        # This will use the connection string from environment variables
        from app.config import settings
        client = AsyncIOMotorClient(settings.mongodb_url)
        await client.admin.command('ping')
        print("✅ MongoDB Atlas connection successful!")
        client.close()
        return True
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        print("   Make sure your MongoDB Atlas connection string is correct")
        print("   and your IP address is whitelisted in MongoDB Atlas")
        return False


def test_imports():
    """Test if all required modules can be imported."""
    try:
        import fastapi
        import uvicorn
        import motor
        import pydantic
        import httpx
        print("✅ All required packages imported successfully!")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("Testing JusFinn Services API setup...\n")
    
    # Test imports
    imports_ok = test_imports()
    
    # Test MongoDB connection
    mongo_ok = await test_mongodb_connection()
    
    print("\n" + "="*50)
    if imports_ok and mongo_ok:
        print("✅ All tests passed! You can start the server with:")
        print("   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 