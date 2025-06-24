"""
Discord Server Promotion API endpoints for Reddit automation dashboard
Provides Discord server promotion campaigns with link posting, subreddit rotation, and monitoring
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, HttpUrl
from datetime import datetime, timedelta
import logging
import random

from database import get_db
from models import (
    RedditAccount, PromotionCampaign, CampaignPost, SubredditTarget,
    EngagementLog, ActivityLog, AccountHealth
)
from reddit_service import reddit_service

router = APIRouter()
logger = logging.getLogger(__name__)

# Pydantic models for API requests
class CreateCampaignRequest(BaseModel):
    name: str
    description: Optional[str] = None
    discord_url: str
    short_url: Optional[str] = None
    post_title: str
    target_subreddits: List[str]
    preferred_subreddits: List[str]
    posting_schedule: Dict[str, Any]  # Schedule configuration

class UpdateCampaignRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    discord_url: Optional[str] = None
    short_url: Optional[str] = None
    post_title: Optional[str] = None
    target_subreddits: Optional[List[str]] = None
    preferred_subreddits: Optional[List[str]] = None
    posting_schedule: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class PromotionPostRequest(BaseModel):
    campaign_id: int
    account_id: int
    subreddit: Optional[str] = None  # If None, will auto-select from campaign targets

class CampaignResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    discord_url: str
    short_url: Optional[str]
    post_title: str
    target_subreddits: List[str]
    preferred_subreddits: List[str]
    posting_schedule: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    total_posts: int
    successful_posts: int
    success_rate: float

class PostResultResponse(BaseModel):
    success: bool
    message: str
    post_id: Optional[str] = None
    permalink: Optional[str] = None
    subreddit: str
    campaign_id: int
    account_id: int
    details: Optional[Dict[str, Any]] = None

@router.post("/campaigns", response_model=CampaignResponse)
async def create_campaign(
    request: CreateCampaignRequest,
    db: Session = Depends(get_db)
):
    """
    Create a new Discord promotion campaign
    
    Args:
        request: Campaign creation details
        
    Returns:
        Created campaign details
    """
    try:
        # Validate Discord URL
        if not request.discord_url.startswith(('http://discord.gg/', 'https://discord.gg/')):
            raise HTTPException(status_code=400, detail="Invalid Discord URL format")
        
        # Ensure we have a default user
        from models import User
        default_user = db.query(User).first()
        if not default_user:
            # Create a default user for testing
            default_user = User(
                username="default_user",
                password_hash="test_hash"
            )
            db.add(default_user)
            db.flush()

        # Create campaign
        campaign = PromotionCampaign(
            user_id=default_user.id,
            name=request.name,
            description=request.description,
            discord_url=request.discord_url,
            short_url=request.short_url,
            post_title=request.post_title,
            target_subreddits=request.target_subreddits,
            preferred_subreddits=request.preferred_subreddits,
            posting_schedule=request.posting_schedule
        )
        
        db.add(campaign)
        db.flush()  # Get the campaign ID
        
        # Create subreddit targets
        for subreddit in request.target_subreddits:
            is_preferred = subreddit in request.preferred_subreddits
            priority = 1 if is_preferred else 2
            
            target = SubredditTarget(
                campaign_id=campaign.id,
                subreddit_name=subreddit,
                priority=priority,
                is_preferred=is_preferred
            )
            db.add(target)
        
        db.commit()
        
        logger.info(f"Created Discord promotion campaign: {campaign.name} (ID: {campaign.id})")
        
        return CampaignResponse(
            id=campaign.id,
            name=campaign.name,
            description=campaign.description,
            discord_url=campaign.discord_url,
            short_url=campaign.short_url,
            post_title=campaign.post_title,
            target_subreddits=campaign.target_subreddits,
            preferred_subreddits=campaign.preferred_subreddits,
            posting_schedule=campaign.posting_schedule,
            is_active=campaign.is_active,
            created_at=campaign.created_at,
            updated_at=campaign.updated_at,
            total_posts=0,
            successful_posts=0,
            success_rate=0.0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating campaign: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create campaign: {str(e)}")

@router.get("/campaigns", response_model=List[CampaignResponse])
async def get_campaigns(
    active_only: bool = Query(True, description="Only return active campaigns"),
    db: Session = Depends(get_db)
):
    """
    Get all Discord promotion campaigns
    
    Args:
        active_only: Filter to only active campaigns
        
    Returns:
        List of campaigns with statistics
    """
    try:
        query = db.query(PromotionCampaign)
        if active_only:
            query = query.filter(PromotionCampaign.is_active == True)
        
        campaigns = query.all()
        
        campaign_responses = []
        for campaign in campaigns:
            # Calculate statistics
            total_posts = db.query(CampaignPost).filter(
                CampaignPost.campaign_id == campaign.id
            ).count()
            
            successful_posts = db.query(CampaignPost).filter(
                CampaignPost.campaign_id == campaign.id,
                CampaignPost.status == 'success'
            ).count()
            
            success_rate = (successful_posts / total_posts * 100) if total_posts > 0 else 0.0
            
            campaign_responses.append(CampaignResponse(
                id=campaign.id,
                name=campaign.name,
                description=campaign.description,
                discord_url=campaign.discord_url,
                short_url=campaign.short_url,
                post_title=campaign.post_title,
                target_subreddits=campaign.target_subreddits,
                preferred_subreddits=campaign.preferred_subreddits,
                posting_schedule=campaign.posting_schedule,
                is_active=campaign.is_active,
                created_at=campaign.created_at,
                updated_at=campaign.updated_at,
                total_posts=total_posts,
                successful_posts=successful_posts,
                success_rate=success_rate
            ))
        
        return campaign_responses
        
    except Exception as e:
        logger.error(f"Error getting campaigns: {e}")
        raise HTTPException(status_code=500, detail="Failed to get campaigns")

@router.get("/campaigns/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific Discord promotion campaign
    
    Args:
        campaign_id: Campaign ID
        
    Returns:
        Campaign details with statistics
    """
    try:
        campaign = db.query(PromotionCampaign).filter(
            PromotionCampaign.id == campaign_id
        ).first()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Calculate statistics
        total_posts = db.query(CampaignPost).filter(
            CampaignPost.campaign_id == campaign.id
        ).count()
        
        successful_posts = db.query(CampaignPost).filter(
            CampaignPost.campaign_id == campaign.id,
            CampaignPost.status == 'success'
        ).count()
        
        success_rate = (successful_posts / total_posts * 100) if total_posts > 0 else 0.0
        
        return CampaignResponse(
            id=campaign.id,
            name=campaign.name,
            description=campaign.description,
            discord_url=campaign.discord_url,
            short_url=campaign.short_url,
            post_title=campaign.post_title,
            target_subreddits=campaign.target_subreddits,
            preferred_subreddits=campaign.preferred_subreddits,
            posting_schedule=campaign.posting_schedule,
            is_active=campaign.is_active,
            created_at=campaign.created_at,
            updated_at=campaign.updated_at,
            total_posts=total_posts,
            successful_posts=successful_posts,
            success_rate=success_rate
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting campaign: {e}")
        raise HTTPException(status_code=500, detail="Failed to get campaign")

@router.post("/campaigns/{campaign_id}/post", response_model=PostResultResponse)
async def submit_promotion_post(
    campaign_id: int,
    request: PromotionPostRequest,
    db: Session = Depends(get_db)
):
    """
    Submit a Discord promotion post to Reddit

    Args:
        campaign_id: Campaign ID
        request: Post submission details

    Returns:
        Post submission result
    """
    try:
        # Get campaign
        campaign = db.query(PromotionCampaign).filter(
            PromotionCampaign.id == campaign_id
        ).first()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        if not campaign.is_active:
            raise HTTPException(status_code=400, detail="Campaign is not active")

        # Get account
        account = db.query(RedditAccount).filter(
            RedditAccount.id == request.account_id
        ).first()

        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        if not account.refresh_token:
            raise HTTPException(status_code=400, detail="Account not connected to Reddit")

        # Select subreddit if not specified
        target_subreddit = request.subreddit
        if not target_subreddit:
            target_subreddit = _select_optimal_subreddit(campaign, db)
            if not target_subreddit:
                raise HTTPException(status_code=400, detail="No available subreddits for posting")

        # Check if we've posted to this subreddit recently
        recent_post = db.query(CampaignPost).filter(
            CampaignPost.campaign_id == campaign_id,
            CampaignPost.subreddit == target_subreddit,
            CampaignPost.posted_at > datetime.utcnow() - timedelta(hours=24)
        ).first()

        if recent_post:
            logger.warning(f"Recent post found in r/{target_subreddit} within 24 hours")

        # Determine URL to post (prefer short URL if available)
        post_url = campaign.short_url if campaign.short_url else campaign.discord_url

        # Submit the post
        try:
            result = reddit_service.submit_post(
                refresh_token=account.refresh_token,
                subreddit_name=target_subreddit,
                title=campaign.post_title,
                url=post_url
            )

            # Create campaign post record
            campaign_post = CampaignPost(
                campaign_id=campaign_id,
                account_id=request.account_id,
                subreddit=target_subreddit,
                status='success' if result.get('success') else 'failed',
                error_message=result.get('error') if not result.get('success') else None,
                details=result
            )

            if result.get('success'):
                campaign_post.post_id = result.get('post_id')
                campaign_post.permalink = result.get('permalink')

            db.add(campaign_post)

            # Log engagement
            engagement_log = EngagementLog(
                account_id=request.account_id,
                action_type='discord_promotion_post',
                target_id=result.get('post_id'),
                subreddit=target_subreddit,
                status='success' if result.get('success') else 'failed',
                details={
                    'campaign_id': campaign_id,
                    'campaign_name': campaign.name,
                    'discord_url': post_url,
                    'result': result
                }
            )
            db.add(engagement_log)

            # Update subreddit target statistics
            _update_subreddit_stats(campaign_id, target_subreddit, result.get('success', False), db)

            db.commit()

            if result.get('success'):
                logger.info(f"Successfully posted Discord promotion to r/{target_subreddit}: {result.get('post_id')}")
                return PostResultResponse(
                    success=True,
                    message=f"Discord promotion posted successfully to r/{target_subreddit}",
                    post_id=result.get('post_id'),
                    permalink=result.get('permalink'),
                    subreddit=target_subreddit,
                    campaign_id=campaign_id,
                    account_id=request.account_id,
                    details=result
                )
            else:
                error_msg = result.get('error', 'Unknown error')
                logger.error(f"Failed to post Discord promotion: {error_msg}")
                return PostResultResponse(
                    success=False,
                    message=f"Failed to post: {error_msg}",
                    subreddit=target_subreddit,
                    campaign_id=campaign_id,
                    account_id=request.account_id,
                    details=result
                )

        except Exception as reddit_error:
            logger.error(f"Reddit API error during Discord promotion: {reddit_error}")

            # Create failed campaign post record
            campaign_post = CampaignPost(
                campaign_id=campaign_id,
                account_id=request.account_id,
                subreddit=target_subreddit,
                status='failed',
                error_message=str(reddit_error),
                details={'error': str(reddit_error)}
            )
            db.add(campaign_post)

            # Update subreddit stats
            _update_subreddit_stats(campaign_id, target_subreddit, False, db)

            db.commit()

            return PostResultResponse(
                success=False,
                message=f"Reddit API error: {str(reddit_error)}",
                subreddit=target_subreddit,
                campaign_id=campaign_id,
                account_id=request.account_id,
                details={'error': str(reddit_error)}
            )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error submitting promotion post: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to submit promotion post: {str(e)}")

def _select_optimal_subreddit(campaign: PromotionCampaign, db: Session) -> Optional[str]:
    """
    Select the optimal subreddit for posting based on priority and recent activity
    """
    # Get subreddit targets ordered by priority and success rate
    targets = db.query(SubredditTarget).filter(
        SubredditTarget.campaign_id == campaign.id,
        SubredditTarget.is_active == True
    ).order_by(
        SubredditTarget.priority.asc(),
        SubredditTarget.success_rate.desc()
    ).all()

    if not targets:
        return None

    # Prefer subreddits that haven't been posted to recently
    for target in targets:
        recent_post = db.query(CampaignPost).filter(
            CampaignPost.campaign_id == campaign.id,
            CampaignPost.subreddit == target.subreddit_name,
            CampaignPost.posted_at > datetime.utcnow() - timedelta(hours=12)
        ).first()

        if not recent_post:
            return target.subreddit_name

    # If all have recent posts, select randomly from preferred subreddits
    preferred_targets = [t for t in targets if t.is_preferred]
    if preferred_targets:
        return random.choice(preferred_targets).subreddit_name

    # Fallback to random selection
    return random.choice(targets).subreddit_name

def _update_subreddit_stats(campaign_id: int, subreddit: str, success: bool, db: Session):
    """
    Update subreddit target statistics
    """
    target = db.query(SubredditTarget).filter(
        SubredditTarget.campaign_id == campaign_id,
        SubredditTarget.subreddit_name == subreddit
    ).first()

    if target:
        target.total_posts += 1
        if success:
            target.successful_posts += 1
        target.success_rate = (target.successful_posts / target.total_posts) * 100
        target.last_posted = datetime.utcnow()

@router.get("/campaigns/{campaign_id}/subreddits")
async def get_campaign_subreddits(
    campaign_id: int,
    db: Session = Depends(get_db)
):
    """
    Get subreddit targets for a campaign with performance statistics

    Args:
        campaign_id: Campaign ID

    Returns:
        List of subreddit targets with statistics
    """
    try:
        campaign = db.query(PromotionCampaign).filter(
            PromotionCampaign.id == campaign_id
        ).first()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        targets = db.query(SubredditTarget).filter(
            SubredditTarget.campaign_id == campaign_id
        ).order_by(
            SubredditTarget.priority.asc(),
            SubredditTarget.success_rate.desc()
        ).all()

        subreddit_data = []
        for target in targets:
            # Get recent post count
            recent_posts = db.query(CampaignPost).filter(
                CampaignPost.campaign_id == campaign_id,
                CampaignPost.subreddit == target.subreddit_name,
                CampaignPost.posted_at > datetime.utcnow() - timedelta(days=7)
            ).count()

            subreddit_data.append({
                "id": target.id,
                "subreddit_name": target.subreddit_name,
                "priority": target.priority,
                "is_preferred": target.is_preferred,
                "is_active": target.is_active,
                "last_posted": target.last_posted.isoformat() if target.last_posted else None,
                "success_rate": target.success_rate,
                "total_posts": target.total_posts,
                "successful_posts": target.successful_posts,
                "removed_posts": target.removed_posts,
                "banned_posts": target.banned_posts,
                "avg_upvotes": target.avg_upvotes,
                "recent_posts_7d": recent_posts,
                "notes": target.notes
            })

        return {
            "campaign_id": campaign_id,
            "campaign_name": campaign.name,
            "total_subreddits": len(subreddit_data),
            "active_subreddits": len([s for s in subreddit_data if s["is_active"]]),
            "preferred_subreddits": len([s for s in subreddit_data if s["is_preferred"]]),
            "subreddits": subreddit_data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting campaign subreddits: {e}")
        raise HTTPException(status_code=500, detail="Failed to get campaign subreddits")

@router.post("/campaigns/{campaign_id}/subreddits")
async def add_campaign_subreddit(
    campaign_id: int,
    subreddit_name: str,
    priority: int = 2,
    is_preferred: bool = False,
    db: Session = Depends(get_db)
):
    """
    Add a new subreddit target to a campaign

    Args:
        campaign_id: Campaign ID
        subreddit_name: Name of subreddit to add
        priority: Priority level (1=high, 2=medium, 3=low)
        is_preferred: Whether this is a preferred subreddit

    Returns:
        Created subreddit target
    """
    try:
        campaign = db.query(PromotionCampaign).filter(
            PromotionCampaign.id == campaign_id
        ).first()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        # Check if subreddit already exists for this campaign
        existing = db.query(SubredditTarget).filter(
            SubredditTarget.campaign_id == campaign_id,
            SubredditTarget.subreddit_name == subreddit_name
        ).first()

        if existing:
            raise HTTPException(status_code=400, detail="Subreddit already exists for this campaign")

        # Create new subreddit target
        target = SubredditTarget(
            campaign_id=campaign_id,
            subreddit_name=subreddit_name,
            priority=priority,
            is_preferred=is_preferred
        )

        db.add(target)
        db.commit()

        logger.info(f"Added subreddit r/{subreddit_name} to campaign {campaign_id}")

        return {
            "id": target.id,
            "campaign_id": campaign_id,
            "subreddit_name": target.subreddit_name,
            "priority": target.priority,
            "is_preferred": target.is_preferred,
            "is_active": target.is_active,
            "message": f"Successfully added r/{subreddit_name} to campaign"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding campaign subreddit: {e}")
        raise HTTPException(status_code=500, detail="Failed to add subreddit to campaign")

@router.put("/campaigns/{campaign_id}/subreddits/{target_id}")
async def update_campaign_subreddit(
    campaign_id: int,
    target_id: int,
    priority: Optional[int] = None,
    is_preferred: Optional[bool] = None,
    is_active: Optional[bool] = None,
    notes: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Update a subreddit target for a campaign

    Args:
        campaign_id: Campaign ID
        target_id: Subreddit target ID
        priority: New priority level
        is_preferred: New preferred status
        is_active: New active status
        notes: New notes

    Returns:
        Updated subreddit target
    """
    try:
        target = db.query(SubredditTarget).filter(
            SubredditTarget.id == target_id,
            SubredditTarget.campaign_id == campaign_id
        ).first()

        if not target:
            raise HTTPException(status_code=404, detail="Subreddit target not found")

        # Update fields if provided
        if priority is not None:
            target.priority = priority
        if is_preferred is not None:
            target.is_preferred = is_preferred
        if is_active is not None:
            target.is_active = is_active
        if notes is not None:
            target.notes = notes

        db.commit()

        logger.info(f"Updated subreddit target {target_id} for campaign {campaign_id}")

        return {
            "id": target.id,
            "campaign_id": campaign_id,
            "subreddit_name": target.subreddit_name,
            "priority": target.priority,
            "is_preferred": target.is_preferred,
            "is_active": target.is_active,
            "notes": target.notes,
            "message": "Subreddit target updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating campaign subreddit: {e}")
        raise HTTPException(status_code=500, detail="Failed to update subreddit target")

@router.get("/campaigns/{campaign_id}/posts")
async def get_campaign_posts(
    campaign_id: int,
    limit: int = Query(50, description="Number of posts to return"),
    status: Optional[str] = Query(None, description="Filter by status"),
    subreddit: Optional[str] = Query(None, description="Filter by subreddit"),
    db: Session = Depends(get_db)
):
    """
    Get posts for a campaign with filtering options

    Args:
        campaign_id: Campaign ID
        limit: Number of posts to return
        status: Filter by post status
        subreddit: Filter by subreddit

    Returns:
        List of campaign posts
    """
    try:
        campaign = db.query(PromotionCampaign).filter(
            PromotionCampaign.id == campaign_id
        ).first()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        query = db.query(CampaignPost).filter(
            CampaignPost.campaign_id == campaign_id
        )

        if status:
            query = query.filter(CampaignPost.status == status)

        if subreddit:
            query = query.filter(CampaignPost.subreddit == subreddit)

        posts = query.order_by(CampaignPost.posted_at.desc()).limit(limit).all()

        post_data = []
        for post in posts:
            post_data.append({
                "id": post.id,
                "post_id": post.post_id,
                "subreddit": post.subreddit,
                "status": post.status,
                "posted_at": post.posted_at.isoformat(),
                "removed_at": post.removed_at.isoformat() if post.removed_at else None,
                "permalink": post.permalink,
                "upvotes": post.upvotes,
                "downvotes": post.downvotes,
                "comments_count": post.comments_count,
                "error_message": post.error_message,
                "account_username": post.account.reddit_username if post.account else None
            })

        return {
            "campaign_id": campaign_id,
            "campaign_name": campaign.name,
            "total_posts": len(post_data),
            "posts": post_data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting campaign posts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get campaign posts")

@router.get("/campaigns/{campaign_id}/analytics")
async def get_campaign_analytics(
    campaign_id: int,
    days: int = Query(30, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """
    Get analytics and performance data for a campaign

    Args:
        campaign_id: Campaign ID
        days: Number of days to analyze

    Returns:
        Campaign analytics data
    """
    try:
        campaign = db.query(PromotionCampaign).filter(
            PromotionCampaign.id == campaign_id
        ).first()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        # Date range for analysis
        start_date = datetime.utcnow() - timedelta(days=days)

        # Get posts in date range
        posts = db.query(CampaignPost).filter(
            CampaignPost.campaign_id == campaign_id,
            CampaignPost.posted_at >= start_date
        ).all()

        # Calculate statistics
        total_posts = len(posts)
        successful_posts = len([p for p in posts if p.status == 'success'])
        failed_posts = len([p for p in posts if p.status == 'failed'])
        removed_posts = len([p for p in posts if p.status == 'removed'])

        success_rate = (successful_posts / total_posts * 100) if total_posts > 0 else 0

        # Subreddit performance
        subreddit_stats = {}
        for post in posts:
            if post.subreddit not in subreddit_stats:
                subreddit_stats[post.subreddit] = {
                    'total': 0,
                    'successful': 0,
                    'failed': 0,
                    'removed': 0,
                    'upvotes': 0,
                    'comments': 0
                }

            stats = subreddit_stats[post.subreddit]
            stats['total'] += 1

            if post.status == 'success':
                stats['successful'] += 1
            elif post.status == 'failed':
                stats['failed'] += 1
            elif post.status == 'removed':
                stats['removed'] += 1

            stats['upvotes'] += post.upvotes or 0
            stats['comments'] += post.comments_count or 0

        # Calculate success rates for each subreddit
        for subreddit, stats in subreddit_stats.items():
            stats['success_rate'] = (stats['successful'] / stats['total'] * 100) if stats['total'] > 0 else 0
            stats['avg_upvotes'] = stats['upvotes'] / stats['successful'] if stats['successful'] > 0 else 0
            stats['avg_comments'] = stats['comments'] / stats['successful'] if stats['successful'] > 0 else 0

        # Daily posting activity
        daily_activity = {}
        for post in posts:
            date_key = post.posted_at.strftime('%Y-%m-%d')
            if date_key not in daily_activity:
                daily_activity[date_key] = 0
            daily_activity[date_key] += 1

        return {
            "campaign_id": campaign_id,
            "campaign_name": campaign.name,
            "analysis_period_days": days,
            "summary": {
                "total_posts": total_posts,
                "successful_posts": successful_posts,
                "failed_posts": failed_posts,
                "removed_posts": removed_posts,
                "success_rate": round(success_rate, 2),
                "total_upvotes": sum(p.upvotes or 0 for p in posts),
                "total_comments": sum(p.comments_count or 0 for p in posts),
                "avg_upvotes_per_post": round(sum(p.upvotes or 0 for p in posts) / successful_posts, 2) if successful_posts > 0 else 0
            },
            "subreddit_performance": subreddit_stats,
            "daily_activity": daily_activity,
            "top_performing_subreddits": sorted(
                [(k, v) for k, v in subreddit_stats.items()],
                key=lambda x: x[1]['success_rate'],
                reverse=True
            )[:5]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting campaign analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get campaign analytics")

@router.post("/campaigns/{campaign_id}/schedule")
async def start_campaign_schedule(
    campaign_id: int,
    account_ids: List[int],
    db: Session = Depends(get_db)
):
    """
    Start automated posting schedule for a campaign

    Args:
        campaign_id: Campaign ID
        account_ids: List of account IDs to use for posting

    Returns:
        Schedule activation result
    """
    try:
        # Try to import Celery task, but make it optional for testing
        try:
            from discord_promotion_tasks import schedule_campaign_posts
            celery_available = True
        except ImportError:
            celery_available = False

        campaign = db.query(PromotionCampaign).filter(
            PromotionCampaign.id == campaign_id
        ).first()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        if not campaign.is_active:
            raise HTTPException(status_code=400, detail="Campaign is not active")

        # Verify accounts exist and are valid
        accounts = db.query(RedditAccount).filter(
            RedditAccount.id.in_(account_ids),
            RedditAccount.refresh_token.isnot(None)
        ).all()

        if len(accounts) != len(account_ids):
            raise HTTPException(status_code=400, detail="Some accounts not found or not connected")

        # Start the scheduling task if Celery is available
        if celery_available:
            task = schedule_campaign_posts.delay(campaign_id)

            logger.info(f"Started automated schedule for campaign {campaign_id}")

            return {
                "success": True,
                "message": f"Automated posting schedule started for campaign '{campaign.name}'",
                "campaign_id": campaign_id,
                "task_id": task.id,
                "accounts_count": len(accounts),
                "schedule_config": campaign.posting_schedule
            }
        else:
            # Celery not available - just mark campaign as active
            campaign.is_active = True
            db.commit()

            return {
                "success": True,
                "message": f"Campaign '{campaign.name}' marked as active (Celery not available for scheduling)",
                "campaign_id": campaign_id,
                "task_id": "manual",
                "accounts_count": len(accounts),
                "schedule_config": campaign.posting_schedule,
                "note": "Celery not configured - use manual testing instead"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting campaign schedule: {e}")
        raise HTTPException(status_code=500, detail="Failed to start campaign schedule")

@router.post("/campaigns/{campaign_id}/schedule/stop")
async def stop_campaign_schedule(
    campaign_id: int,
    db: Session = Depends(get_db)
):
    """
    Stop automated posting schedule for a campaign

    Args:
        campaign_id: Campaign ID

    Returns:
        Schedule deactivation result
    """
    try:
        campaign = db.query(PromotionCampaign).filter(
            PromotionCampaign.id == campaign_id
        ).first()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        # Update campaign to inactive
        campaign.is_active = False
        db.commit()

        logger.info(f"Stopped automated schedule for campaign {campaign_id}")

        return {
            "success": True,
            "message": f"Automated posting schedule stopped for campaign '{campaign.name}'",
            "campaign_id": campaign_id
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error stopping campaign schedule: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop campaign schedule")

class TestPostRequest(BaseModel):
    campaign_id: int
    account_id: int
    subreddit: Optional[str] = None

@router.post("/campaigns/{campaign_id}/test-post")
async def test_campaign_post(
    campaign_id: int,
    request: TestPostRequest,
    db: Session = Depends(get_db)
):
    """
    Test a single Discord promotion post for a campaign

    Args:
        campaign_id: Campaign ID
        request: Test post request data

    Returns:
        Test post result
    """
    try:
        # Try to import Celery task, but make it optional for testing
        try:
            from discord_promotion_tasks import automated_discord_promotion
            celery_available = True
        except ImportError:
            celery_available = False

        campaign = db.query(PromotionCampaign).filter(
            PromotionCampaign.id == campaign_id
        ).first()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        account = db.query(RedditAccount).filter(
            RedditAccount.id == request.account_id
        ).first()

        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        if not account.refresh_token:
            raise HTTPException(status_code=400, detail="Account not connected to Reddit")

        # Execute test post
        if request.subreddit:
            # Manual subreddit selection for testing
            post_request = PromotionPostRequest(
                campaign_id=campaign_id,
                account_id=request.account_id,
                subreddit=request.subreddit
            )
            result = await submit_promotion_post(campaign_id, post_request, db)
            return result
        else:
            # Use automated task for testing if Celery is available
            if celery_available:
                task = automated_discord_promotion.delay(campaign_id, request.account_id)

                return {
                    "success": True,
                    "message": "Test post task started",
                    "campaign_id": campaign_id,
                    "account_id": request.account_id,
                    "task_id": task.id,
                    "note": "Check task result or campaign posts for outcome"
                }
            else:
                # Fallback to direct posting without Celery
                post_request = PromotionPostRequest(
                    campaign_id=campaign_id,
                    account_id=request.account_id,
                    subreddit=None  # Auto-select
                )
                result = await submit_promotion_post(campaign_id, post_request, db)
                return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing campaign post: {e}")
        raise HTTPException(status_code=500, detail="Failed to test campaign post")

# Predefined subreddit lists for easy campaign setup
NORWEGIAN_NSFW_SUBREDDITS = {
    "preferred": [
        "norwaygonewildddddddd",
        "BDSMNorge",
        "norskefemboys",
        "norgesex",
        "nordicslut"
    ],
    "additional": [
        "HookupsNorway",
        "KosekrokenNorgeNSFW",
        "SigridFans",
        "NordGW",
        "dirtyr4rSverige",
        "GoontownSwe",
        "swedishOnlyFanss",
        "bildtrosorfilmer25",
        "ScandinavianCocks",
        "NordicBlondes",
        "finlandssvenskNSFW"
    ]
}

@router.get("/subreddit-templates")
async def get_subreddit_templates():
    """
    Get predefined subreddit templates for quick campaign setup

    Returns:
        Available subreddit templates
    """
    return {
        "norwegian_nsfw": {
            "name": "Norwegian NSFW Subreddits",
            "description": "Curated list of Norwegian NSFW subreddits for Discord promotion",
            "preferred_subreddits": NORWEGIAN_NSFW_SUBREDDITS["preferred"],
            "additional_subreddits": NORWEGIAN_NSFW_SUBREDDITS["additional"],
            "total_subreddits": len(NORWEGIAN_NSFW_SUBREDDITS["preferred"]) + len(NORWEGIAN_NSFW_SUBREDDITS["additional"]),
            "recommended_schedule": {
                "interval_hours": 6,
                "randomization_minutes": 90,
                "max_posts_per_day": 4,
                "preferred_times": ["10:00", "14:00", "18:00", "22:00"]
            }
        }
    }

class QuickSetupRequest(BaseModel):
    name: str
    discord_url: str
    template: str = "norwegian_nsfw"
    short_url: Optional[str] = None
    custom_title: Optional[str] = None

@router.post("/campaigns/quick-setup")
async def quick_setup_campaign(
    request: QuickSetupRequest,
    db: Session = Depends(get_db)
):
    """
    Quick setup for a Discord promotion campaign using predefined templates

    Args:
        request: Quick setup request data

    Returns:
        Created campaign with predefined settings
    """
    try:
        if request.template != "norwegian_nsfw":
            raise HTTPException(status_code=400, detail="Only 'norwegian_nsfw' template is currently supported")

        # Default title for Norwegian NSFW promotion
        default_title = "Norsk NSFW Gruppe - Deilig innhold deles daglig - Grovt & digg."
        post_title = request.custom_title if request.custom_title else default_title

        # Get template data
        template_data = NORWEGIAN_NSFW_SUBREDDITS

        # Create campaign request
        campaign_request = CreateCampaignRequest(
            name=request.name,
            description=f"Discord promotion campaign using {request.template} template",
            discord_url=request.discord_url,
            short_url=request.short_url,
            post_title=post_title,
            target_subreddits=template_data["preferred"] + template_data["additional"],
            preferred_subreddits=template_data["preferred"],
            posting_schedule={
                "interval_hours": 6,
                "randomization_minutes": 90,
                "max_posts_per_day": 4,
                "preferred_times": ["10:00", "14:00", "18:00", "22:00"]
            }
        )

        # Create the campaign
        campaign = await create_campaign(campaign_request, db)

        logger.info(f"Quick setup campaign created: {request.name} using {request.template} template")

        return {
            **campaign.dict(),
            "template_used": request.template,
            "setup_type": "quick_setup",
            "message": f"Campaign '{request.name}' created successfully with {len(template_data['preferred'])} preferred and {len(template_data['additional'])} additional subreddits"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in quick setup campaign: {e}")
        raise HTTPException(status_code=500, detail="Failed to create quick setup campaign")

@router.post("/campaigns/{campaign_id}/monitor")
async def start_campaign_monitoring(
    campaign_id: int,
    db: Session = Depends(get_db)
):
    """
    Start monitoring for a Discord promotion campaign

    Args:
        campaign_id: Campaign ID to monitor

    Returns:
        Monitoring activation result
    """
    try:
        # Try to import monitoring task, but make it optional for testing
        try:
            from discord_promotion_monitoring import monitor_campaign_posts
            monitoring_available = True
        except ImportError:
            monitoring_available = False

        campaign = db.query(PromotionCampaign).filter(
            PromotionCampaign.id == campaign_id
        ).first()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        # Start monitoring task if available
        if monitoring_available:
            task = monitor_campaign_posts.delay(campaign_id)

            logger.info(f"Started monitoring for campaign {campaign_id}")

            return {
                "success": True,
                "message": f"Monitoring started for campaign '{campaign.name}'",
                "campaign_id": campaign_id,
                "task_id": task.id
            }
        else:
            return {
                "success": True,
                "message": f"Monitoring not available (Celery not configured) for campaign '{campaign.name}'",
                "campaign_id": campaign_id,
                "task_id": "manual",
                "note": "Use manual post checking instead"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting campaign monitoring: {e}")
        raise HTTPException(status_code=500, detail="Failed to start campaign monitoring")

@router.get("/campaigns/{campaign_id}/health-report")
async def get_campaign_health_report(
    campaign_id: int,
    db: Session = Depends(get_db)
):
    """
    Get comprehensive health report for a Discord promotion campaign

    Args:
        campaign_id: Campaign ID

    Returns:
        Campaign health report
    """
    try:
        # Try to import monitoring task, but make it optional for testing
        try:
            from discord_promotion_monitoring import generate_promotion_safety_report
            monitoring_available = True
        except ImportError:
            monitoring_available = False

        campaign = db.query(PromotionCampaign).filter(
            PromotionCampaign.id == campaign_id
        ).first()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        # Generate safety report if monitoring is available
        if monitoring_available:
            task = generate_promotion_safety_report.delay(campaign_id)
            task_id = task.id
        else:
            task_id = "manual"

        # For immediate response, also calculate basic stats
        total_posts = db.query(CampaignPost).filter(
            CampaignPost.campaign_id == campaign_id
        ).count()

        successful_posts = db.query(CampaignPost).filter(
            CampaignPost.campaign_id == campaign_id,
            CampaignPost.status == 'success'
        ).count()

        removed_posts = db.query(CampaignPost).filter(
            CampaignPost.campaign_id == campaign_id,
            CampaignPost.status == 'removed'
        ).count()

        # Get account health for accounts used in this campaign
        account_ids = db.query(CampaignPost.account_id).filter(
            CampaignPost.campaign_id == campaign_id
        ).distinct().all()

        account_health_summary = []
        for (account_id,) in account_ids:
            account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
            health = db.query(AccountHealth).filter(AccountHealth.account_id == account_id).first()

            if account and health:
                account_health_summary.append({
                    "account_id": account_id,
                    "username": account.reddit_username,
                    "trust_score": health.trust_score,
                    "shadowbanned": health.shadowbanned,
                    "captcha_triggered": health.captcha_triggered
                })

        return {
            "campaign_id": campaign_id,
            "campaign_name": campaign.name,
            "report_task_id": task_id,
            "quick_stats": {
                "total_posts": total_posts,
                "successful_posts": successful_posts,
                "removed_posts": removed_posts,
                "success_rate": (successful_posts / total_posts * 100) if total_posts > 0 else 0,
                "removal_rate": (removed_posts / total_posts * 100) if total_posts > 0 else 0
            },
            "account_health": account_health_summary,
            "message": "Detailed safety report is being generated. Check task result for complete analysis."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting campaign health report: {e}")
        raise HTTPException(status_code=500, detail="Failed to get campaign health report")

@router.post("/accounts/{account_id}/health-check")
async def check_account_health(
    account_id: int,
    db: Session = Depends(get_db)
):
    """
    Perform comprehensive health check for an account used in Discord promotion

    Args:
        account_id: Account ID to check

    Returns:
        Account health check results
    """
    try:
        # Try to import monitoring task, but make it optional for testing
        try:
            from discord_promotion_monitoring import check_account_health_for_promotion
            monitoring_available = True
        except ImportError:
            monitoring_available = False

        account = db.query(RedditAccount).filter(
            RedditAccount.id == account_id
        ).first()

        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Start health check task if monitoring is available
        if monitoring_available:
            task = check_account_health_for_promotion.delay(account_id)
            task_id = task.id
        else:
            task_id = "manual"

        # Get current health record for immediate response
        current_health = db.query(AccountHealth).filter(
            AccountHealth.account_id == account_id
        ).first()

        return {
            "account_id": account_id,
            "username": account.reddit_username,
            "health_check_task_id": task_id,
            "current_health": {
                "trust_score": current_health.trust_score if current_health else None,
                "shadowbanned": current_health.shadowbanned if current_health else None,
                "captcha_triggered": current_health.captcha_triggered if current_health else None,
                "account_age_days": current_health.account_age_days if current_health else None
            } if current_health else None,
            "message": "Comprehensive health check started. Check task result for detailed analysis."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking account health: {e}")
        raise HTTPException(status_code=500, detail="Failed to check account health")

@router.get("/campaigns/{campaign_id}/alerts")
async def get_campaign_alerts(
    campaign_id: int,
    days: int = Query(7, description="Number of days to look back for alerts"),
    db: Session = Depends(get_db)
):
    """
    Get alerts and warnings for a Discord promotion campaign

    Args:
        campaign_id: Campaign ID
        days: Number of days to analyze

    Returns:
        Campaign alerts and warnings
    """
    try:
        campaign = db.query(PromotionCampaign).filter(
            PromotionCampaign.id == campaign_id
        ).first()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        start_date = datetime.utcnow() - timedelta(days=days)

        alerts = []

        # Check for high removal rates
        recent_posts = db.query(CampaignPost).filter(
            CampaignPost.campaign_id == campaign_id,
            CampaignPost.posted_at >= start_date
        ).all()

        if recent_posts:
            removed_count = len([p for p in recent_posts if p.status == 'removed'])
            removal_rate = (removed_count / len(recent_posts)) * 100

            if removal_rate > 50:
                alerts.append({
                    "type": "high_removal_rate",
                    "severity": "critical",
                    "message": f"High removal rate: {removal_rate:.1f}% of posts removed",
                    "recommendation": "Consider pausing campaign and reviewing subreddit rules"
                })
            elif removal_rate > 25:
                alerts.append({
                    "type": "moderate_removal_rate",
                    "severity": "warning",
                    "message": f"Moderate removal rate: {removal_rate:.1f}% of posts removed",
                    "recommendation": "Monitor closely and consider adjusting posting strategy"
                })

        # Check for shadowbanned accounts
        account_ids = list(set(post.account_id for post in recent_posts))
        for account_id in account_ids:
            health = db.query(AccountHealth).filter(
                AccountHealth.account_id == account_id
            ).first()

            if health and health.shadowbanned:
                account = db.query(RedditAccount).filter(
                    RedditAccount.id == account_id
                ).first()

                alerts.append({
                    "type": "shadowbanned_account",
                    "severity": "critical",
                    "message": f"Account {account.reddit_username} appears to be shadowbanned",
                    "recommendation": "Stop using this account immediately and verify status"
                })

        # Check for posting frequency issues
        today_posts = len([p for p in recent_posts if p.posted_at.date() == datetime.utcnow().date()])
        if today_posts > 10:
            alerts.append({
                "type": "high_posting_frequency",
                "severity": "warning",
                "message": f"High posting frequency: {today_posts} posts today",
                "recommendation": "Consider reducing posting frequency to appear more natural"
            })

        return {
            "campaign_id": campaign_id,
            "campaign_name": campaign.name,
            "analysis_period_days": days,
            "total_alerts": len(alerts),
            "critical_alerts": len([a for a in alerts if a["severity"] == "critical"]),
            "warning_alerts": len([a for a in alerts if a["severity"] == "warning"]),
            "alerts": alerts,
            "overall_status": "critical" if any(a["severity"] == "critical" for a in alerts) else "warning" if alerts else "good"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting campaign alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get campaign alerts")
