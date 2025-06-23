from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
import logging
from pydantic import BaseModel

from database import get_db
from models import RedditAccount, User, AccountHealth, AutomationSettings
from reddit_service import reddit_service
from error_handler import (
    ErrorHandler, ValidationError, handle_errors,
    validate_account_id, validate_required_field
)

class ManualAccountRequest(BaseModel):
    username: str
    refresh_token: str

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", summary="List Reddit accounts")
def list_accounts(db: Session = Depends(get_db)):
    """Get all Reddit accounts"""
    try:
        accounts = db.query(RedditAccount).all()
        return [
            {
                "id": account.id,
                "reddit_username": account.reddit_username,
                "created_at": account.created_at,
                "user_id": account.user_id
            }
            for account in accounts
        ]
    except Exception as e:
        logger.error(f"Error listing accounts: {e}")
        raise HTTPException(status_code=500, detail="Failed to list accounts")

@router.post("/manual-add", summary="Manually add Reddit account (for testing)")
def manual_add_account(request: ManualAccountRequest, db: Session = Depends(get_db)):
    """Manually add a Reddit account for testing purposes"""
    try:
        # Check if account already exists
        existing_account = db.query(RedditAccount).filter(
            RedditAccount.reddit_username == request.username
        ).first()

        if existing_account:
            raise HTTPException(status_code=400, detail="Account already exists")

        # Create new Reddit account
        new_account = RedditAccount(
            user_id=1,  # Default user ID
            reddit_username=request.username,
            refresh_token=request.refresh_token
        )

        db.add(new_account)
        db.flush()  # Get the account ID

        # Create account health record
        account_health = AccountHealth(
            account_id=new_account.id,
            account_age_days=30,  # Default for test accounts
            bans=0,
            deletions=0,
            removals=0,
            trust_score=1.0,
            shadowbanned=False,
            captcha_triggered=False,
            login_issues=False
        )

        # Create default automation settings
        automation_settings = AutomationSettings(
            account_id=new_account.id,
            selected_subreddits=[],
            active_keywords=[],
            engagement_schedule={},
            max_daily_comments=10,
            max_daily_upvotes=50
        )

        db.add(account_health)
        db.add(automation_settings)
        db.commit()

        return {
            "message": "Test account added successfully",
            "account_id": new_account.id,
            "username": request.username,
            "note": "This is a test account for UI testing only"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding manual account: {e}")
        raise HTTPException(status_code=500, detail="Failed to add test account")

@router.post("/add", summary="Initiate Reddit OAuth flow")
def initiate_oauth():
    """Start Reddit OAuth2 flow"""
    try:
        state = str(uuid.uuid4())
        oauth_url = reddit_service.get_oauth_url(state)

        return {
            "oauth_url": oauth_url,
            "state": state,
            "message": "Visit the OAuth URL to authorize the application"
        }
    except Exception as e:
        logger.error(f"Error initiating OAuth: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate OAuth flow")

@router.get("/oauth/callback", summary="Handle Reddit OAuth callback")
def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db)
):
    """Handle OAuth callback and create account"""
    return handle_oauth_callback(code, state, db)

@router.get("/callback", summary="Handle Reddit OAuth callback (alternative)")
def oauth_callback_alt(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db)
):
    """Handle OAuth callback and create account (alternative endpoint)"""
    return handle_oauth_callback(code, state, db)

def handle_oauth_callback(code: str, state: str, db: Session):
    """Handle OAuth callback and create account"""
    try:
        logger.info(f"Processing OAuth callback with code: {code[:10]}... and state: {state}")

        # Exchange code for tokens and user info
        token_data = reddit_service.exchange_code_for_tokens(code)
        logger.info(f"Token exchange successful for user: {token_data.get('username', 'unknown')}")

        # Check if account already exists
        existing_account = db.query(RedditAccount).filter(
            RedditAccount.reddit_username == token_data["username"]
        ).first()

        if existing_account:
            raise HTTPException(status_code=400, detail="Account already exists")

        # Create new Reddit account
        new_account = RedditAccount(
            user_id=1,  # For now, use default user ID
            reddit_username=token_data["username"],
            refresh_token=token_data["refresh_token"]
        )

        db.add(new_account)
        db.flush()  # Get the account ID

        # Create account health record
        account_health = AccountHealth(
            account_id=new_account.id,
            account_age_days=reddit_service.get_account_age(token_data["refresh_token"]),
            bans=0,
            deletions=0,
            removals=0,
            trust_score=1.0,
            shadowbanned=reddit_service.check_shadowban(token_data["refresh_token"]),
            captcha_triggered=False,
            login_issues=False
        )

        # Create default automation settings
        automation_settings = AutomationSettings(
            account_id=new_account.id,
            selected_subreddits=[],
            active_keywords=[],
            engagement_schedule={},
            max_daily_comments=10,
            max_daily_upvotes=50
        )

        db.add(account_health)
        db.add(automation_settings)
        db.commit()

        # Return HTML success page instead of JSON for better user experience
        success_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Reddit Account Connected</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
                .success {{ background-color: #d4edda; border: 1px solid #c3e6cb; color: #155724; padding: 20px; border-radius: 5px; }}
                .button {{ background-color: #ff4500; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin-top: 15px; }}
            </style>
        </head>
        <body>
            <div class="success">
                <h2>✅ Reddit Account Connected Successfully!</h2>
                <p><strong>Username:</strong> {token_data["username"]}</p>
                <p><strong>Account ID:</strong> {new_account.id}</p>
                <p><strong>Total Karma:</strong> {token_data.get("total_karma", "N/A")}</p>
                <p><strong>Post Karma:</strong> {token_data.get("link_karma", "N/A")}</p>
                <p><strong>Comment Karma:</strong> {token_data.get("comment_karma", "N/A")}</p>

                <p>Your Reddit account is now connected and ready to use!</p>

                <a href="/test-form" class="button">Go to Test Form</a>
                <a href="/docs" class="button">View API Docs</a>
            </div>

            <script>
                // Auto-close this window after 3 seconds if it was opened in a popup
                if (window.opener) {{
                    setTimeout(() => {{
                        window.close();
                    }}, 3000);
                }}
            </script>
        </body>
        </html>
        """

        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=success_html)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error in OAuth callback: {e}")
        raise HTTPException(status_code=500, detail="Failed to process OAuth callback")

@router.delete("/{account_id}", summary="Remove a Reddit account")
def remove_account(account_id: int, db: Session = Depends(get_db)):
    """Remove a Reddit account and all associated data"""
    try:
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()

        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Delete account (cascade will handle related records)
        db.delete(account)
        db.commit()

        return {"message": f"Account {account.reddit_username} removed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error removing account: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove account")

@router.get("/{account_id}", summary="Get account details")
@handle_errors
def get_account(account_id: int, db: Session = Depends(get_db)):
    """Get detailed information about a specific account"""
    # Validate input
    validate_account_id(account_id)

    # Get account
    account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    try:
        # Get current karma from Reddit (this might fail with dummy tokens)
        current_karma = reddit_service.get_user_karma(account.refresh_token)
    except Exception as e:
        logger.warning(f"Failed to get current karma for account {account_id}: {e}")
        # Return cached data instead of failing completely
        current_karma = {
            "total_karma": 0,
            "post_karma": 0,
            "comment_karma": 0
        }

    return {
        "id": account.id,
        "reddit_username": account.reddit_username,
        "created_at": account.created_at.isoformat(),
        "current_karma": current_karma,
        "health": {
            "account_age_days": account.account_health.account_age_days if account.account_health else None,
            "shadowbanned": account.account_health.shadowbanned if account.account_health else None,
            "trust_score": account.account_health.trust_score if account.account_health else None
        } if account.account_health else None
    }