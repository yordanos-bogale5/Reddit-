import praw
import os
from dotenv import load_dotenv
from typing import Optional, Dict, Any, List
import logging

load_dotenv()

logger = logging.getLogger(__name__)

class RedditService:
    def __init__(self):
        self.client_id = os.getenv("REDDIT_CLIENT_ID")
        self.client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        self.redirect_uri = os.getenv("REDDIT_REDIRECT_URI", "http://localhost:8000/accounts/oauth/callback")
        self.user_agent = os.getenv("REDDIT_USER_AGENT", "RedditTool:v1.0 (by /u/YourUsername)")
        
        if not self.client_id or not self.client_secret:
            logger.warning("Reddit API credentials not found in environment variables")
    
    def get_oauth_url(self, state: str) -> str:
        """Generate Reddit OAuth authorization URL"""
        reddit = praw.Reddit(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            user_agent=self.user_agent
        )
        
        scopes = ["identity", "read", "submit", "vote", "edit", "history"]
        return reddit.auth.url(scopes, state, "permanent")
    
    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access and refresh tokens"""
        reddit = praw.Reddit(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            user_agent=self.user_agent
        )
        
        try:
            refresh_token = reddit.auth.authorize(code)
            
            # Get user info
            user = reddit.user.me()
            
            return {
                "refresh_token": refresh_token,
                "username": user.name,
                "user_id": user.id,
                "created_utc": user.created_utc,
                "link_karma": user.link_karma,
                "comment_karma": user.comment_karma,
                "total_karma": user.link_karma + user.comment_karma
            }
        except Exception as e:
            logger.error(f"Error exchanging code for tokens: {e}")
            raise
    
    def get_reddit_instance(self, refresh_token: str) -> praw.Reddit:
        """Create authenticated Reddit instance using refresh token"""
        return praw.Reddit(
            client_id=self.client_id,
            client_secret=self.client_secret,
            refresh_token=refresh_token,
            user_agent=self.user_agent
        )
    
    def get_user_karma(self, refresh_token: str) -> Dict[str, int]:
        """Get current karma for a user"""
        reddit = self.get_reddit_instance(refresh_token)
        user = reddit.user.me()
        
        return {
            "total_karma": user.link_karma + user.comment_karma,
            "post_karma": user.link_karma,
            "comment_karma": user.comment_karma
        }
    
    def check_shadowban(self, refresh_token: str) -> bool:
        """Check if account is shadowbanned"""
        try:
            reddit = self.get_reddit_instance(refresh_token)
            user = reddit.user.me()
            
            # Try to access user's profile page
            # If shadowbanned, this will raise an exception
            list(user.submissions.new(limit=1))
            return False
        except Exception as e:
            logger.warning(f"Possible shadowban detected: {e}")
            return True
    
    def get_account_age(self, refresh_token: str) -> int:
        """Get account age in days"""
        import time
        reddit = self.get_reddit_instance(refresh_token)
        user = reddit.user.me()

        current_time = time.time()
        account_age_seconds = current_time - user.created_utc
        return int(account_age_seconds / 86400)  # Convert to days

    def get_detailed_karma(self, refresh_token: str) -> Dict[str, Any]:
        """Get detailed karma breakdown by subreddit and content type"""
        reddit = self.get_reddit_instance(refresh_token)
        user = reddit.user.me()

        # Get basic karma
        basic_karma = {
            "total_karma": user.link_karma + user.comment_karma,
            "post_karma": user.link_karma,
            "comment_karma": user.comment_karma
        }

        # Get karma by subreddit from recent submissions and comments
        subreddit_karma = {}
        content_type_karma = {"posts": 0, "comments": 0}

        try:
            # Analyze recent submissions (posts)
            for submission in user.submissions.new(limit=100):
                subreddit_name = submission.subreddit.display_name
                if subreddit_name not in subreddit_karma:
                    subreddit_karma[subreddit_name] = {"post_karma": 0, "comment_karma": 0}
                subreddit_karma[subreddit_name]["post_karma"] += submission.score
                content_type_karma["posts"] += submission.score

            # Analyze recent comments
            for comment in user.comments.new(limit=100):
                subreddit_name = comment.subreddit.display_name
                if subreddit_name not in subreddit_karma:
                    subreddit_karma[subreddit_name] = {"post_karma": 0, "comment_karma": 0}
                subreddit_karma[subreddit_name]["comment_karma"] += comment.score
                content_type_karma["comments"] += comment.score

        except Exception as e:
            logger.warning(f"Error getting detailed karma breakdown: {e}")

        return {
            **basic_karma,
            "by_subreddit": subreddit_karma,
            "by_content_type": content_type_karma
        }

    def get_user_activity_summary(self, refresh_token: str) -> Dict[str, Any]:
        """Get summary of user's recent activity"""
        reddit = self.get_reddit_instance(refresh_token)
        user = reddit.user.me()

        activity_summary = {
            "recent_posts": 0,
            "recent_comments": 0,
            "avg_post_score": 0,
            "avg_comment_score": 0,
            "active_subreddits": set(),
            "last_activity": None
        }

        try:
            # Analyze recent submissions
            post_scores = []
            for submission in user.submissions.new(limit=50):
                activity_summary["recent_posts"] += 1
                post_scores.append(submission.score)
                activity_summary["active_subreddits"].add(submission.subreddit.display_name)
                if not activity_summary["last_activity"] or submission.created_utc > activity_summary["last_activity"]:
                    activity_summary["last_activity"] = submission.created_utc

            # Analyze recent comments
            comment_scores = []
            for comment in user.comments.new(limit=50):
                activity_summary["recent_comments"] += 1
                comment_scores.append(comment.score)
                activity_summary["active_subreddits"].add(comment.subreddit.display_name)
                if not activity_summary["last_activity"] or comment.created_utc > activity_summary["last_activity"]:
                    activity_summary["last_activity"] = comment.created_utc

            # Calculate averages
            if post_scores:
                activity_summary["avg_post_score"] = sum(post_scores) / len(post_scores)
            if comment_scores:
                activity_summary["avg_comment_score"] = sum(comment_scores) / len(comment_scores)

            # Convert set to list for JSON serialization
            activity_summary["active_subreddits"] = list(activity_summary["active_subreddits"])

        except Exception as e:
            logger.warning(f"Error getting activity summary: {e}")

        return activity_summary

    def upvote_content(self, refresh_token: str, content_id: str) -> Dict[str, Any]:
        """Upvote a post or comment"""
        try:
            reddit = self.get_reddit_instance(refresh_token)

            # Get the content (could be submission or comment)
            try:
                # Try as submission first
                content = reddit.submission(id=content_id)
                content.upvote()
                content_type = "submission"
                subreddit = content.subreddit.display_name
            except:
                # Try as comment
                content = reddit.comment(id=content_id)
                content.upvote()
                content_type = "comment"
                subreddit = content.subreddit.display_name

            return {
                "success": True,
                "content_id": content_id,
                "content_type": content_type,
                "subreddit": subreddit,
                "message": f"Successfully upvoted {content_type}"
            }

        except Exception as e:
            logger.error(f"Error upvoting content {content_id}: {e}")
            return {
                "success": False,
                "content_id": content_id,
                "error": str(e),
                "message": f"Failed to upvote content"
            }

    def submit_comment(self, refresh_token: str, parent_id: str, comment_text: str) -> Dict[str, Any]:
        """Submit a comment to a post or reply to a comment"""
        try:
            reddit = self.get_reddit_instance(refresh_token)

            # Get the parent content
            try:
                # Try as submission first
                parent = reddit.submission(id=parent_id)
                parent_type = "submission"
            except:
                # Try as comment
                parent = reddit.comment(id=parent_id)
                parent_type = "comment"

            # Submit the comment
            comment = parent.reply(comment_text)

            return {
                "success": True,
                "comment_id": comment.id,
                "parent_id": parent_id,
                "parent_type": parent_type,
                "subreddit": comment.subreddit.display_name,
                "comment_text": comment_text,
                "message": f"Successfully posted comment"
            }

        except Exception as e:
            logger.error(f"Error submitting comment to {parent_id}: {e}")
            return {
                "success": False,
                "parent_id": parent_id,
                "comment_text": comment_text,
                "error": str(e),
                "message": f"Failed to submit comment"
            }

    def submit_post(self, refresh_token: str, subreddit_name: str, title: str,
                   content: str = None, url: str = None, flair_id: str = None) -> Dict[str, Any]:
        """Submit a post to a subreddit"""
        try:
            reddit = self.get_reddit_instance(refresh_token)
            subreddit = reddit.subreddit(subreddit_name)

            # Determine post type and submit
            if url:
                # Link post
                submission = subreddit.submit(title=title, url=url, flair_id=flair_id)
                post_type = "link"
            else:
                # Text post
                submission = subreddit.submit(title=title, selftext=content or "", flair_id=flair_id)
                post_type = "text"

            return {
                "success": True,
                "post_id": submission.id,
                "title": title,
                "subreddit": subreddit_name,
                "post_type": post_type,
                "url": f"https://reddit.com{submission.permalink}",
                "message": f"Successfully posted to r/{subreddit_name}"
            }

        except Exception as e:
            logger.error(f"Error submitting post to r/{subreddit_name}: {e}")
            return {
                "success": False,
                "title": title,
                "subreddit": subreddit_name,
                "error": str(e),
                "message": f"Failed to submit post to r/{subreddit_name}"
            }

    def get_subreddit_info(self, refresh_token: str, subreddit_name: str) -> Dict[str, Any]:
        """Get information about a subreddit"""
        try:
            reddit = self.get_reddit_instance(refresh_token)
            subreddit = reddit.subreddit(subreddit_name)

            return {
                "name": subreddit.display_name,
                "title": subreddit.title,
                "description": subreddit.description[:200] + "..." if len(subreddit.description) > 200 else subreddit.description,
                "subscribers": subreddit.subscribers,
                "active_users": subreddit.active_user_count,
                "created_utc": subreddit.created_utc,
                "over18": subreddit.over18,
                "public_description": subreddit.public_description
            }

        except Exception as e:
            logger.error(f"Error getting subreddit info for r/{subreddit_name}: {e}")
            return {}

    def get_hot_posts(self, refresh_token: str, subreddit_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get hot posts from a subreddit"""
        try:
            reddit = self.get_reddit_instance(refresh_token)
            subreddit = reddit.subreddit(subreddit_name)

            posts = []
            for submission in subreddit.hot(limit=limit):
                posts.append({
                    "id": submission.id,
                    "title": submission.title,
                    "score": submission.score,
                    "num_comments": submission.num_comments,
                    "created_utc": submission.created_utc,
                    "author": str(submission.author) if submission.author else "[deleted]",
                    "url": submission.url,
                    "permalink": f"https://reddit.com{submission.permalink}",
                    "is_self": submission.is_self,
                    "selftext": submission.selftext[:200] + "..." if len(submission.selftext) > 200 else submission.selftext
                })

            return posts

        except Exception as e:
            logger.error(f"Error getting hot posts from r/{subreddit_name}: {e}")
            return []

    def get_user_info(self, refresh_token: str) -> Dict[str, Any]:
        """Get information about the authenticated user"""
        try:
            reddit = self.get_reddit_instance(refresh_token)
            user = reddit.user.me()

            return {
                "success": True,
                "username": user.name,
                "total_karma": user.link_karma + user.comment_karma,
                "link_karma": user.link_karma,
                "comment_karma": user.comment_karma,
                "created_utc": user.created_utc,
                "has_verified_email": user.has_verified_email,
                "is_gold": user.is_gold,
                "is_mod": user.is_mod,
                "id": user.id
            }

        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to get user information"
            }

    def comment_on_post(self, refresh_token: str, post_id: str, comment_text: str) -> Dict[str, Any]:
        """Submit a comment on a Reddit post"""
        try:
            reddit = self.get_reddit_instance(refresh_token)
            submission = reddit.submission(id=post_id)

            # Submit the comment
            comment = submission.reply(comment_text)

            return {
                "success": True,
                "comment_id": comment.id,
                "parent_post_id": post_id,
                "comment_text": comment_text,
                "permalink": f"https://reddit.com{comment.permalink}",
                "url": f"https://reddit.com{comment.permalink}",
                "message": "Comment successfully submitted"
            }

        except Exception as e:
            logger.error(f"Error submitting comment to post {post_id}: {e}")
            return {
                "success": False,
                "parent_post_id": post_id,
                "comment_text": comment_text,
                "error": str(e),
                "message": f"Failed to submit comment: {str(e)}"
            }

reddit_service = RedditService()
