"""
Direct Reddit Actions API endpoints for immediate testing
Provides simple endpoints to submit posts and comments using PRAW
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from pydantic import BaseModel
import logging

from database import get_db
from models import RedditAccount, EngagementLog, ActivityLog
from reddit_service import reddit_service

router = APIRouter()
logger = logging.getLogger(__name__)

# Pydantic models for API requests
class SubmitPostRequest(BaseModel):
    account_id: int
    subreddit: str
    title: str
    body: Optional[str] = None
    url: Optional[str] = None
    flair_id: Optional[str] = None
    flair_text: Optional[str] = None

class SubmitCommentRequest(BaseModel):
    account_id: int
    parent_post_id: str
    comment_text: str
    subreddit: Optional[str] = None

class RedditActionResponse(BaseModel):
    success: bool
    message: str
    post_id: Optional[str] = None
    comment_id: Optional[str] = None
    permalink: Optional[str] = None
    url: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

@router.get("/accounts")
async def get_connected_accounts(db: Session = Depends(get_db)):
    """
    Get list of connected Reddit accounts available for posting
    
    Returns:
        List of connected accounts with basic info
    """
    try:
        accounts = db.query(RedditAccount).filter(
            RedditAccount.refresh_token.isnot(None)
        ).all()
        
        account_list = []
        for account in accounts:
            # Test if account is still valid
            try:
                user_info = reddit_service.get_user_info(account.refresh_token)
                is_valid = user_info.get('success', False)
            except:
                is_valid = False
            
            account_list.append({
                "id": account.id,
                "username": account.reddit_username,
                "is_valid": is_valid,
                "created_at": account.created_at.isoformat() if account.created_at else None
            })
        
        return {
            "total_accounts": len(account_list),
            "valid_accounts": len([a for a in account_list if a["is_valid"]]),
            "accounts": account_list
        }
        
    except Exception as e:
        logger.error(f"Error getting connected accounts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get connected accounts")

@router.post("/submit-post", response_model=RedditActionResponse)
async def submit_reddit_post(
    request: SubmitPostRequest,
    db: Session = Depends(get_db)
):
    """
    Submit a post to Reddit using PRAW
    
    Args:
        request: Post submission details
        
    Returns:
        Success/failure response with post details
    """
    try:
        # Verify account exists and has valid token
        account = db.query(RedditAccount).filter(RedditAccount.id == request.account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        if not account.refresh_token:
            raise HTTPException(status_code=400, detail="Account not connected to Reddit")
        
        # Validate request
        if not request.title.strip():
            raise HTTPException(status_code=400, detail="Post title is required")
        
        if not request.subreddit.strip():
            raise HTTPException(status_code=400, detail="Subreddit is required")
        
        # Determine post type
        if request.url and request.body:
            raise HTTPException(status_code=400, detail="Cannot submit both URL and text content")
        
        # Submit post using reddit_service
        try:
            result = reddit_service.submit_post(
                refresh_token=account.refresh_token,
                subreddit_name=request.subreddit,
                title=request.title,
                content=request.body,
                url=request.url,
                flair_id=request.flair_id
            )
            
            if not result.get('success'):
                error_msg = result.get('error', 'Unknown error occurred')
                logger.error(f"Reddit post submission failed: {error_msg}")
                
                # Log failed attempt
                engagement_log = EngagementLog(
                    account_id=request.account_id,
                    action_type='post',
                    target_id=None,
                    subreddit=request.subreddit,
                    status='failed',
                    details={'error': error_msg, 'title': request.title, 'request': request.dict()}
                )
                db.add(engagement_log)
                db.commit()
                
                return RedditActionResponse(
                    success=False,
                    message=f"Failed to submit post: {error_msg}",
                    details=result
                )
            
            # Extract post details
            post_id = result.get('post_id')
            permalink = result.get('permalink')
            url = result.get('url')
            
            # Log successful submission
            engagement_log = EngagementLog(
                account_id=request.account_id,
                action_type='post',
                target_id=post_id,
                subreddit=request.subreddit,
                status='success',
                details=result
            )
            db.add(engagement_log)
            
            # Log activity
            activity_log = ActivityLog(
                account_id=request.account_id,
                action='manual_post_submission',
                details={
                    'post_id': post_id,
                    'subreddit': request.subreddit,
                    'title': request.title,
                    'post_type': 'link' if request.url else 'text',
                    'result': result
                }
            )
            db.add(activity_log)
            
            db.commit()
            
            logger.info(f"Successfully submitted post to r/{request.subreddit}: {post_id}")
            
            return RedditActionResponse(
                success=True,
                message=f"Post successfully submitted to r/{request.subreddit}",
                post_id=post_id,
                permalink=permalink,
                url=url,
                details=result
            )
            
        except Exception as reddit_error:
            logger.error(f"Reddit API error: {reddit_error}")
            
            # Log failed attempt
            engagement_log = EngagementLog(
                account_id=request.account_id,
                action_type='post',
                target_id=None,
                subreddit=request.subreddit,
                status='failed',
                details={'error': str(reddit_error), 'title': request.title, 'request': request.dict()}
            )
            db.add(engagement_log)
            db.commit()
            
            return RedditActionResponse(
                success=False,
                message=f"Reddit API error: {str(reddit_error)}",
                details={'error': str(reddit_error)}
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting post: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to submit post: {str(e)}")

@router.post("/submit-comment", response_model=RedditActionResponse)
async def submit_reddit_comment(
    request: SubmitCommentRequest,
    db: Session = Depends(get_db)
):
    """
    Submit a comment to Reddit using PRAW
    
    Args:
        request: Comment submission details
        
    Returns:
        Success/failure response with comment details
    """
    try:
        # Verify account exists and has valid token
        account = db.query(RedditAccount).filter(RedditAccount.id == request.account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        if not account.refresh_token:
            raise HTTPException(status_code=400, detail="Account not connected to Reddit")
        
        # Validate request
        if not request.comment_text.strip():
            raise HTTPException(status_code=400, detail="Comment text is required")
        
        if not request.parent_post_id.strip():
            raise HTTPException(status_code=400, detail="Parent post ID is required")
        
        # Submit comment using reddit_service
        try:
            result = reddit_service.comment_on_post(
                refresh_token=account.refresh_token,
                post_id=request.parent_post_id,
                comment_text=request.comment_text
            )
            
            if not result.get('success'):
                error_msg = result.get('error', 'Unknown error occurred')
                logger.error(f"Reddit comment submission failed: {error_msg}")
                
                # Log failed attempt
                engagement_log = EngagementLog(
                    account_id=request.account_id,
                    action_type='comment',
                    target_id=request.parent_post_id,
                    subreddit=request.subreddit,
                    status='failed',
                    details={'error': error_msg, 'comment_text': request.comment_text, 'request': request.dict()}
                )
                db.add(engagement_log)
                db.commit()
                
                return RedditActionResponse(
                    success=False,
                    message=f"Failed to submit comment: {error_msg}",
                    details=result
                )
            
            # Extract comment details
            comment_id = result.get('comment_id')
            permalink = result.get('permalink')
            
            # Log successful submission
            engagement_log = EngagementLog(
                account_id=request.account_id,
                action_type='comment',
                target_id=request.parent_post_id,
                subreddit=request.subreddit,
                status='success',
                details=result
            )
            db.add(engagement_log)
            
            # Log activity
            activity_log = ActivityLog(
                account_id=request.account_id,
                action='manual_comment_submission',
                details={
                    'comment_id': comment_id,
                    'parent_post_id': request.parent_post_id,
                    'subreddit': request.subreddit,
                    'comment_text': request.comment_text[:100] + '...' if len(request.comment_text) > 100 else request.comment_text,
                    'result': result
                }
            )
            db.add(activity_log)
            
            db.commit()
            
            logger.info(f"Successfully submitted comment: {comment_id}")
            
            return RedditActionResponse(
                success=True,
                message="Comment successfully submitted",
                comment_id=comment_id,
                permalink=permalink,
                details=result
            )
            
        except Exception as reddit_error:
            logger.error(f"Reddit API error: {reddit_error}")
            
            # Log failed attempt
            engagement_log = EngagementLog(
                account_id=request.account_id,
                action_type='comment',
                target_id=request.parent_post_id,
                subreddit=request.subreddit,
                status='failed',
                details={'error': str(reddit_error), 'comment_text': request.comment_text, 'request': request.dict()}
            )
            db.add(engagement_log)
            db.commit()
            
            return RedditActionResponse(
                success=False,
                message=f"Reddit API error: {str(reddit_error)}",
                details={'error': str(reddit_error)}
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting comment: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to submit comment: {str(e)}")

@router.get("/test-account/{account_id}")
async def test_account_connection(
    account_id: int,
    db: Session = Depends(get_db)
):
    """
    Test if an account's Reddit connection is working
    
    Args:
        account_id: Account to test
        
    Returns:
        Connection test results
    """
    try:
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        if not account.refresh_token:
            return {
                "success": False,
                "message": "Account not connected to Reddit",
                "account_id": account_id,
                "username": account.reddit_username
            }
        
        # Test connection
        try:
            user_info = reddit_service.get_user_info(account.refresh_token)
            
            if user_info.get('success'):
                return {
                    "success": True,
                    "message": "Account connection is working",
                    "account_id": account_id,
                    "username": account.reddit_username,
                    "reddit_username": user_info.get('username'),
                    "karma": user_info.get('total_karma'),
                    "account_created": user_info.get('created_utc')
                }
            else:
                return {
                    "success": False,
                    "message": f"Connection test failed: {user_info.get('error', 'Unknown error')}",
                    "account_id": account_id,
                    "username": account.reddit_username,
                    "details": user_info
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Connection test error: {str(e)}",
                "account_id": account_id,
                "username": account.reddit_username
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing account connection: {e}")
        raise HTTPException(status_code=500, detail="Failed to test account connection")
