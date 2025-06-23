from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, JSON, Float
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    reddit_accounts = relationship('RedditAccount', back_populates='user')

class RedditAccount(Base):
    __tablename__ = 'reddit_accounts'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    reddit_username = Column(String, unique=True, nullable=False)
    refresh_token = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship('User', back_populates='reddit_accounts')
    karma_logs = relationship('KarmaLog', back_populates='account')
    engagement_logs = relationship('EngagementLog', back_populates='account')
    activity_logs = relationship('ActivityLog', back_populates='account')
    subreddit_performance = relationship('SubredditPerformance', back_populates='account')
    account_health = relationship('AccountHealth', back_populates='account', uselist=False)
    automation_settings = relationship('AutomationSettings', back_populates='account', uselist=False)

class KarmaLog(Base):
    __tablename__ = 'karma_logs'
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('reddit_accounts.id'))
    timestamp = Column(DateTime, default=datetime.utcnow)
    total_karma = Column(Integer)
    post_karma = Column(Integer)
    comment_karma = Column(Integer)
    by_subreddit = Column(JSON)
    by_content_type = Column(JSON)
    account = relationship('RedditAccount', back_populates='karma_logs')

class EngagementLog(Base):
    __tablename__ = 'engagement_logs'
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('reddit_accounts.id'))
    timestamp = Column(DateTime, default=datetime.utcnow)
    action_type = Column(String)  # upvote, comment, post
    target_id = Column(String)
    subreddit = Column(String)
    status = Column(String)  # success, failed, removed
    details = Column(JSON)
    account = relationship('RedditAccount', back_populates='engagement_logs')

class ActivityLog(Base):
    __tablename__ = 'activity_logs'
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('reddit_accounts.id'))
    timestamp = Column(DateTime, default=datetime.utcnow)
    action = Column(String)
    details = Column(JSON)
    account = relationship('RedditAccount', back_populates='activity_logs')

class SubredditPerformance(Base):
    __tablename__ = 'subreddit_performance'
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('reddit_accounts.id'))
    subreddit = Column(String)
    karma_gain = Column(Integer)
    engagement_score = Column(Float)
    removed_count = Column(Integer)
    ignored_count = Column(Integer)
    account = relationship('RedditAccount', back_populates='subreddit_performance')

class AccountHealth(Base):
    __tablename__ = 'account_health'
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('reddit_accounts.id'))
    account_age_days = Column(Integer)
    bans = Column(Integer)
    deletions = Column(Integer)
    removals = Column(Integer)
    trust_score = Column(Float)
    shadowbanned = Column(Boolean)
    captcha_triggered = Column(Boolean)
    login_issues = Column(Boolean)
    account = relationship('RedditAccount', back_populates='account_health')

class AutomationSettings(Base):
    __tablename__ = 'automation_settings'
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('reddit_accounts.id'))
    selected_subreddits = Column(JSON)
    active_keywords = Column(JSON)
    engagement_schedule = Column(JSON)
    max_daily_comments = Column(Integer)
    max_daily_upvotes = Column(Integer)
    auto_upvote_enabled = Column(Boolean, default=False)
    auto_comment_enabled = Column(Boolean, default=False)
    auto_post_enabled = Column(Boolean, default=False)
    # NLP Quality Control Settings
    min_quality_score = Column(Float, default=70.0)
    max_spam_probability = Column(Float, default=0.3)
    max_toxicity_score = Column(Float, default=0.2)
    enable_quality_filter = Column(Boolean, default=True)
    account = relationship('RedditAccount', back_populates='automation_settings')

class CommentQualityLog(Base):
    __tablename__ = 'comment_quality_logs'
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('reddit_accounts.id'))
    engagement_log_id = Column(Integer, ForeignKey('engagement_logs.id'))
    timestamp = Column(DateTime, default=datetime.utcnow)
    comment_text = Column(String)
    overall_score = Column(Float)
    sentiment_score = Column(Float)
    spam_probability = Column(Float)
    readability_score = Column(Float)
    relevance_score = Column(Float)
    toxicity_score = Column(Float)
    language = Column(String)
    word_count = Column(Integer)
    issues = Column(JSON)
    recommendations = Column(JSON)
    passed_filter = Column(Boolean)
    account = relationship('RedditAccount')
    engagement_log = relationship('EngagementLog')