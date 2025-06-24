#!/usr/bin/env python3
"""
Test script for Discord Promotion API endpoints
Run this to verify the backend is working correctly
"""

import requests
import json
import time

API_BASE = "http://localhost:8000"

def test_api_endpoint(method, endpoint, data=None, expected_status=200):
    """Test an API endpoint and return the response"""
    url = f"{API_BASE}{endpoint}"
    
    print(f"\n🧪 Testing {method} {endpoint}")
    
    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data)
        elif method == "PUT":
            response = requests.put(url, json=data)
        else:
            print(f"❌ Unsupported method: {method}")
            return None
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == expected_status:
            print("✅ Status code matches expected")
        else:
            print(f"⚠️ Expected {expected_status}, got {response.status_code}")
        
        try:
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2)}")
            return result
        except:
            print(f"Response (text): {response.text}")
            return response.text
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed - make sure the backend server is running on localhost:8000")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def main():
    print("🚀 Discord Promotion API Test Suite")
    print("=" * 50)
    
    # Test 1: Health check
    print("\n📋 Step 1: Health Check")
    health = test_api_endpoint("GET", "/")
    if not health:
        print("❌ Backend server is not running. Please start it first:")
        print("   cd backend && python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000")
        return
    
    # Test 2: Check accounts
    print("\n📋 Step 2: Check Connected Accounts")
    accounts = test_api_endpoint("GET", "/reddit/accounts")
    
    # Test 3: Get subreddit templates
    print("\n📋 Step 3: Get Subreddit Templates")
    templates = test_api_endpoint("GET", "/discord-promotion/subreddit-templates")
    
    # Test 4: Create a test campaign
    print("\n📋 Step 4: Create Test Campaign")
    campaign_data = {
        "name": "Test Discord Server",
        "discord_url": "http://discord.gg/Norskedamerr",
        "template": "norwegian_nsfw"
    }
    campaign = test_api_endpoint("POST", "/discord-promotion/campaigns/quick-setup", campaign_data)
    
    if campaign and 'id' in campaign:
        campaign_id = campaign['id']
        print(f"✅ Campaign created with ID: {campaign_id}")
        
        # Test 5: Get campaigns
        print("\n📋 Step 5: Get All Campaigns")
        campaigns = test_api_endpoint("GET", "/discord-promotion/campaigns")
        
        # Test 6: Get specific campaign
        print(f"\n📋 Step 6: Get Campaign {campaign_id}")
        specific_campaign = test_api_endpoint("GET", f"/discord-promotion/campaigns/{campaign_id}")
        
        # Test 7: Get campaign subreddits
        print(f"\n📋 Step 7: Get Campaign Subreddits")
        subreddits = test_api_endpoint("GET", f"/discord-promotion/campaigns/{campaign_id}/subreddits")
        
        # Test 8: Get campaign analytics
        print(f"\n📋 Step 8: Get Campaign Analytics")
        analytics = test_api_endpoint("GET", f"/discord-promotion/campaigns/{campaign_id}/analytics")
        
        # Test 9: Get campaign alerts
        print(f"\n📋 Step 9: Get Campaign Alerts")
        alerts = test_api_endpoint("GET", f"/discord-promotion/campaigns/{campaign_id}/alerts")
        
        # Test 10: Get campaign posts
        print(f"\n📋 Step 10: Get Campaign Posts")
        posts = test_api_endpoint("GET", f"/discord-promotion/campaigns/{campaign_id}/posts")
        
        # Test 11: Test post (only if we have accounts)
        if accounts and accounts.get('accounts'):
            valid_accounts = [acc for acc in accounts['accounts'] if acc.get('is_valid')]
            if valid_accounts:
                print(f"\n📋 Step 11: Test Campaign Post")
                test_post_data = {
                    "campaign_id": campaign_id,
                    "account_id": valid_accounts[0]['id'],
                    "subreddit": "test"  # Safe subreddit for testing
                }
                test_post = test_api_endpoint("POST", f"/discord-promotion/campaigns/{campaign_id}/test-post", test_post_data)
            else:
                print("\n⚠️ Step 11: Skipped - No valid accounts available for testing")
        else:
            print("\n⚠️ Step 11: Skipped - No accounts available for testing")
        
        # Test 12: Start monitoring
        print(f"\n📋 Step 12: Start Campaign Monitoring")
        monitoring = test_api_endpoint("POST", f"/discord-promotion/campaigns/{campaign_id}/monitor")
        
    else:
        print("❌ Campaign creation failed, skipping dependent tests")
    
    print("\n" + "=" * 50)
    print("🎉 Test Suite Complete!")
    print("\n📝 Summary:")
    print("- All API endpoints have been tested")
    print("- Check the responses above for any errors")
    print("- If all tests passed, the Discord promotion system is ready!")
    print("\n🌐 Next Steps:")
    print("1. Open http://localhost:8000/test-form in your browser")
    print("2. Connect a Reddit account (use manual add for testing)")
    print("3. Create a Discord promotion campaign")
    print("4. Test posting to safe subreddits first")
    print("5. Monitor results and analytics")

if __name__ == "__main__":
    main()
