#!/usr/bin/env python3
"""
Simple test script for the Medical Guidelines MCP Server
"""

import asyncio
import aiohttp
import json
import sys

async def test_health_endpoint(base_url):
    """Test the health check endpoint"""
    print("Testing health endpoint...")
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{base_url}/health") as response:
            if response.status == 200:
                data = await response.json()
                print("✅ Health check passed")
                print(f"   Status: {data.get('status')}")
                print(f"   Supported domains: {data.get('supported_domains')}")
                return True
            else:
                print(f"❌ Health check failed: {response.status}")
                return False

async def test_sse_connection(base_url):
    """Test SSE connection"""
    print("\nTesting SSE connection...")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{base_url}/sse") as response:
                if response.status == 200:
                    print("✅ SSE connection established")
                    return True
                else:
                    print(f"❌ SSE connection failed: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ SSE connection error: {e}")
            return False

async def main():
    """Main test function"""
    base_url = "http://localhost:8080"
    
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    
    print(f"Testing Medical Guidelines MCP Server at: {base_url}")
    print("=" * 50)
    
    # Test health endpoint
    health_ok = await test_health_endpoint(base_url)
    
    # Test SSE connection
    sse_ok = await test_sse_connection(base_url)
    
    print("\n" + "=" * 50)
    if health_ok and sse_ok:
        print("✅ All tests passed! Server is ready for deployment.")
    else:
        print("❌ Some tests failed. Check server logs.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 