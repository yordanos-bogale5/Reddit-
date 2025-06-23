# 🚀 Reddit Actions Testing Guide

## Quick Start for Live Reddit Testing

### 1. Start the Server

```bash
# Option 1: Use the quick start script
python start_server.py

# Option 2: Manual start
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Access the Test Interface

- **Test Form**: http://localhost:8000/test-form
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/

### 3. Setup Reddit Account Connection

Before testing, you need to connect a Reddit account:

#### Option A: Use API Endpoints (Recommended)
1. Go to http://localhost:8000/docs
2. Use the `/accounts/connect` endpoint to connect your Reddit account
3. Provide your Reddit refresh token

#### Option B: Direct Database Insert (if needed)
If you already have a refresh token, you can add it directly to the database.

### 4. Test Reddit Actions

#### 📝 Submit a Post
1. Open http://localhost:8000/test-form
2. Click "Load Connected Accounts" to see available accounts
3. Fill in the post form:
   - **Account**: Select your connected account
   - **Subreddit**: Use `test` or any subreddit you have access to
   - **Title**: "Test post from automation dashboard"
   - **Body**: "This is a test post from my Reddit automation dashboard."
   - **URL**: Leave empty for text post, or add URL for link post
4. Click "Submit Post"
5. Check the response for success/failure and permalink

#### 💬 Submit a Comment
1. Find a Reddit post and copy its ID from the URL
   - Example: `reddit.com/r/test/comments/ABC123/title` → Post ID is `ABC123`
2. Fill in the comment form:
   - **Account**: Select your connected account
   - **Parent Post ID**: The post ID you copied
   - **Comment Text**: "This is a test comment from my automation dashboard."
   - **Subreddit**: Optional, for logging purposes
3. Click "Submit Comment"
4. Check the response for success/failure and permalink

### 5. API Endpoints Available

#### Reddit Actions
- `GET /reddit/accounts` - List connected accounts
- `POST /reddit/submit-post` - Submit a post
- `POST /reddit/submit-comment` - Submit a comment
- `GET /reddit/test-account/{account_id}` - Test account connection

#### Example API Calls

**Submit Post:**
```bash
curl -X POST "http://localhost:8000/reddit/submit-post" \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": 1,
    "subreddit": "test",
    "title": "Test post from API",
    "body": "This is a test post submitted via API"
  }'
```

**Submit Comment:**
```bash
curl -X POST "http://localhost:8000/reddit/submit-comment" \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": 1,
    "parent_post_id": "abc123",
    "comment_text": "Test comment from API"
  }'
```

### 6. Troubleshooting

#### Common Issues:

1. **"Account not found"**
   - Make sure you've connected a Reddit account first
   - Check the account ID is correct

2. **"Account not connected to Reddit"**
   - The account doesn't have a valid refresh token
   - Re-connect the account using OAuth2 flow

3. **"Reddit API error"**
   - Check your Reddit API credentials in .env file
   - Ensure the refresh token is still valid
   - Check if you have permission to post in the subreddit

4. **"Failed to submit post/comment"**
   - Check Reddit's posting rules for the subreddit
   - Ensure you're not rate limited
   - Verify the post ID is correct for comments

#### Environment Setup:

Make sure your `.env` file contains:
```
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=your_app_name/1.0
```

### 7. Success Indicators

✅ **Successful Post:**
- Response shows `"success": true`
- You get a `post_id` and `permalink`
- The post appears on Reddit

✅ **Successful Comment:**
- Response shows `"success": true`
- You get a `comment_id` and `permalink`
- The comment appears on the Reddit post

### 8. Next Steps

Once basic posting/commenting works:
1. Test the automation features
2. Set up scheduling
3. Configure safety monitoring
4. Use the advanced analytics features

---

## 🔧 Development Notes

- All actions are logged in the database
- Safety monitoring is active by default
- Rate limiting is implemented to prevent API abuse
- NLP quality control can be enabled for automated content

## 📞 Support

If you encounter issues:
1. Check the server logs for detailed error messages
2. Verify your Reddit API credentials
3. Test account connection using the test endpoint
4. Check Reddit's API status and rate limits
