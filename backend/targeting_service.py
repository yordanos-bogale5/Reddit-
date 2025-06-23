"""
Advanced Subreddit & Keyword Targeting Service for Reddit Automation Dashboard
Provides intelligent targeting algorithms, performance analysis, and content filtering
"""
import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import json

from database import SessionLocal
from models import (
    RedditAccount, EngagementLog, SubredditPerformance, 
    AutomationSettings, KarmaLog
)
from reddit_service import reddit_service

logger = logging.getLogger(__name__)

@dataclass
class SubredditMetrics:
    """Metrics for subreddit performance analysis"""
    subreddit: str
    total_actions: int
    successful_actions: int
    success_rate: float
    avg_karma_gain: float
    avg_response_time: float
    engagement_rate: float
    risk_score: float
    recommendation: str

@dataclass
class KeywordAnalysis:
    """Analysis results for keyword performance"""
    keyword: str
    frequency: int
    success_rate: float
    avg_karma: float
    sentiment_score: float
    relevance_score: float
    recommendation: str

@dataclass
class TargetingRecommendation:
    """Targeting recommendation with reasoning"""
    subreddit: str
    confidence: float
    reasons: List[str]
    optimal_times: List[int]
    suggested_keywords: List[str]
    risk_level: str

class TargetingService:
    """Advanced targeting service for subreddit and keyword optimization"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_subreddit_performance(self, account_id: int, days: int = 30) -> List[SubredditMetrics]:
        """
        Analyze performance across different subreddits
        
        Args:
            account_id: Account to analyze
            days: Number of days to analyze
            
        Returns:
            List of subreddit performance metrics
        """
        try:
            db = SessionLocal()
            
            # Get engagement logs for the period
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            logs = db.query(EngagementLog).filter(
                EngagementLog.account_id == account_id,
                EngagementLog.timestamp >= cutoff_date,
                EngagementLog.subreddit.isnot(None)
            ).all()
            
            # Group by subreddit
            subreddit_data = defaultdict(list)
            for log in logs:
                subreddit_data[log.subreddit].append(log)
            
            metrics = []
            for subreddit, subreddit_logs in subreddit_data.items():
                if len(subreddit_logs) < 3:  # Skip subreddits with too few actions
                    continue
                
                # Calculate metrics
                total_actions = len(subreddit_logs)
                successful_actions = sum(1 for log in subreddit_logs if log.status == 'success')
                success_rate = successful_actions / total_actions if total_actions > 0 else 0
                
                # Calculate karma gain
                karma_gains = [log.score or 0 for log in subreddit_logs if log.score is not None]
                avg_karma_gain = sum(karma_gains) / len(karma_gains) if karma_gains else 0
                
                # Calculate response time
                response_times = [log.response_time or 0 for log in subreddit_logs if log.response_time is not None]
                avg_response_time = sum(response_times) / len(response_times) if response_times else 0
                
                # Calculate engagement rate (simplified)
                engagement_rate = avg_karma_gain * success_rate
                
                # Calculate risk score
                risk_score = self._calculate_subreddit_risk(subreddit, subreddit_logs)
                
                # Generate recommendation
                recommendation = self._generate_subreddit_recommendation(
                    success_rate, avg_karma_gain, risk_score
                )
                
                metrics.append(SubredditMetrics(
                    subreddit=subreddit,
                    total_actions=total_actions,
                    successful_actions=successful_actions,
                    success_rate=success_rate,
                    avg_karma_gain=avg_karma_gain,
                    avg_response_time=avg_response_time,
                    engagement_rate=engagement_rate,
                    risk_score=risk_score,
                    recommendation=recommendation
                ))
            
            # Sort by engagement rate (best performing first)
            metrics.sort(key=lambda x: x.engagement_rate, reverse=True)
            
            db.close()
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error analyzing subreddit performance: {e}")
            if 'db' in locals():
                db.close()
            return []
    
    def analyze_keyword_performance(self, account_id: int, days: int = 30) -> List[KeywordAnalysis]:
        """
        Analyze keyword performance in comments and posts
        
        Args:
            account_id: Account to analyze
            days: Number of days to analyze
            
        Returns:
            List of keyword performance analysis
        """
        try:
            db = SessionLocal()
            
            # Get engagement logs with content
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            logs = db.query(EngagementLog).filter(
                EngagementLog.account_id == account_id,
                EngagementLog.timestamp >= cutoff_date,
                EngagementLog.content.isnot(None)
            ).all()
            
            # Extract keywords from content
            keyword_data = defaultdict(list)
            for log in logs:
                if log.content:
                    keywords = self._extract_keywords(log.content)
                    for keyword in keywords:
                        keyword_data[keyword].append(log)
            
            analyses = []
            for keyword, keyword_logs in keyword_data.items():
                if len(keyword_logs) < 2:  # Skip keywords with too few occurrences
                    continue
                
                # Calculate metrics
                frequency = len(keyword_logs)
                successful_actions = sum(1 for log in keyword_logs if log.status == 'success')
                success_rate = successful_actions / frequency if frequency > 0 else 0
                
                # Calculate average karma
                karma_scores = [log.score or 0 for log in keyword_logs if log.score is not None]
                avg_karma = sum(karma_scores) / len(karma_scores) if karma_scores else 0
                
                # Calculate sentiment and relevance (simplified)
                sentiment_score = self._calculate_keyword_sentiment(keyword, keyword_logs)
                relevance_score = self._calculate_keyword_relevance(keyword, keyword_logs)
                
                # Generate recommendation
                recommendation = self._generate_keyword_recommendation(
                    success_rate, avg_karma, sentiment_score
                )
                
                analyses.append(KeywordAnalysis(
                    keyword=keyword,
                    frequency=frequency,
                    success_rate=success_rate,
                    avg_karma=avg_karma,
                    sentiment_score=sentiment_score,
                    relevance_score=relevance_score,
                    recommendation=recommendation
                ))
            
            # Sort by performance (success rate * avg karma)
            analyses.sort(key=lambda x: x.success_rate * x.avg_karma, reverse=True)
            
            db.close()
            return analyses
            
        except Exception as e:
            self.logger.error(f"Error analyzing keyword performance: {e}")
            if 'db' in locals():
                db.close()
            return []
    
    def get_targeting_recommendations(self, account_id: int, days: int = 30) -> List[TargetingRecommendation]:
        """
        Get intelligent targeting recommendations for an account
        
        Args:
            account_id: Account to analyze
            days: Number of days to analyze
            
        Returns:
            List of targeting recommendations
        """
        try:
            # Get subreddit performance
            subreddit_metrics = self.analyze_subreddit_performance(account_id, days)
            
            # Get keyword analysis
            keyword_analysis = self.analyze_keyword_performance(account_id, days)
            
            # Get optimal posting times
            optimal_times = self._analyze_optimal_times(account_id, days)
            
            recommendations = []
            
            # Generate recommendations for top performing subreddits
            for metric in subreddit_metrics[:10]:  # Top 10 subreddits
                confidence = self._calculate_recommendation_confidence(metric)
                reasons = self._generate_recommendation_reasons(metric)
                risk_level = self._determine_risk_level(metric.risk_score)
                
                # Get relevant keywords for this subreddit
                relevant_keywords = [
                    kw.keyword for kw in keyword_analysis[:5] 
                    if kw.success_rate > 0.5
                ]
                
                recommendations.append(TargetingRecommendation(
                    subreddit=metric.subreddit,
                    confidence=confidence,
                    reasons=reasons,
                    optimal_times=optimal_times.get(metric.subreddit, []),
                    suggested_keywords=relevant_keywords,
                    risk_level=risk_level
                ))
            
            return recommendations
            
        except Exception as e:
            self.logger.error(f"Error generating targeting recommendations: {e}")
            return []
    
    def create_blocklist_recommendations(self, account_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Analyze and recommend subreddits for blocklist
        
        Args:
            account_id: Account to analyze
            days: Number of days to analyze
            
        Returns:
            Blocklist recommendations with reasons
        """
        try:
            subreddit_metrics = self.analyze_subreddit_performance(account_id, days)
            
            blocklist_candidates = []
            for metric in subreddit_metrics:
                # Criteria for blocklist recommendation
                should_block = (
                    metric.success_rate < 0.3 or  # Low success rate
                    metric.risk_score > 0.7 or    # High risk
                    metric.avg_karma_gain < 0     # Negative karma
                )
                
                if should_block:
                    reasons = []
                    if metric.success_rate < 0.3:
                        reasons.append(f"Low success rate: {metric.success_rate:.1%}")
                    if metric.risk_score > 0.7:
                        reasons.append(f"High risk score: {metric.risk_score:.2f}")
                    if metric.avg_karma_gain < 0:
                        reasons.append(f"Negative karma gain: {metric.avg_karma_gain:.1f}")
                    
                    blocklist_candidates.append({
                        'subreddit': metric.subreddit,
                        'reasons': reasons,
                        'metrics': {
                            'success_rate': metric.success_rate,
                            'risk_score': metric.risk_score,
                            'avg_karma_gain': metric.avg_karma_gain,
                            'total_actions': metric.total_actions
                        }
                    })
            
            return {
                'blocklist_candidates': blocklist_candidates,
                'total_analyzed': len(subreddit_metrics),
                'recommended_blocks': len(blocklist_candidates),
                'analysis_period_days': days
            }
            
        except Exception as e:
            self.logger.error(f"Error creating blocklist recommendations: {e}")
            return {'error': str(e)}
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text"""
        # Simple keyword extraction (can be enhanced with NLP)
        text = text.lower()
        
        # Remove common words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we',
            'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'her',
            'its', 'our', 'their'
        }
        
        # Extract words (3+ characters, alphanumeric)
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
        keywords = [word for word in words if word not in stop_words]
        
        # Return unique keywords
        return list(set(keywords))
    
    def _calculate_subreddit_risk(self, subreddit: str, logs: List) -> float:
        """Calculate risk score for a subreddit"""
        risk_factors = 0
        
        # Check for failed actions
        failed_actions = sum(1 for log in logs if log.status == 'failed')
        failure_rate = failed_actions / len(logs) if logs else 0
        risk_factors += failure_rate * 0.4
        
        # Check for negative karma
        negative_karma_actions = sum(1 for log in logs if log.score and log.score < 0)
        negative_rate = negative_karma_actions / len(logs) if logs else 0
        risk_factors += negative_rate * 0.3
        
        # Check for slow response times (potential rate limiting)
        slow_responses = sum(1 for log in logs if log.response_time and log.response_time > 5)
        slow_rate = slow_responses / len(logs) if logs else 0
        risk_factors += slow_rate * 0.3
        
        return min(1.0, risk_factors)
    
    def _generate_subreddit_recommendation(self, success_rate: float, avg_karma: float, risk_score: float) -> str:
        """Generate recommendation for subreddit"""
        if success_rate > 0.8 and avg_karma > 2 and risk_score < 0.3:
            return "Excellent - Prioritize this subreddit"
        elif success_rate > 0.6 and avg_karma > 1 and risk_score < 0.5:
            return "Good - Continue engaging"
        elif success_rate > 0.4 and risk_score < 0.7:
            return "Moderate - Monitor performance"
        else:
            return "Poor - Consider avoiding or reducing activity"
    
    def _calculate_keyword_sentiment(self, keyword: str, logs: List) -> float:
        """Calculate sentiment score for keyword usage"""
        # Simplified sentiment calculation
        positive_indicators = ['good', 'great', 'awesome', 'excellent', 'amazing', 'love', 'best']
        negative_indicators = ['bad', 'terrible', 'awful', 'hate', 'worst', 'horrible']
        
        sentiment = 0.5  # Neutral baseline
        
        if keyword in positive_indicators:
            sentiment += 0.3
        elif keyword in negative_indicators:
            sentiment -= 0.3
        
        # Adjust based on karma performance
        avg_karma = sum(log.score or 0 for log in logs) / len(logs) if logs else 0
        if avg_karma > 1:
            sentiment += 0.1
        elif avg_karma < 0:
            sentiment -= 0.2
        
        return max(0.0, min(1.0, sentiment))
    
    def _calculate_keyword_relevance(self, keyword: str, logs: List) -> float:
        """Calculate relevance score for keyword"""
        # Simple relevance based on frequency and context
        frequency = len(logs)
        
        # Higher frequency in successful posts indicates relevance
        successful_uses = sum(1 for log in logs if log.status == 'success')
        success_rate = successful_uses / frequency if frequency > 0 else 0
        
        # Base relevance on success rate and frequency
        relevance = success_rate * min(1.0, frequency / 10)  # Normalize frequency
        
        return relevance
    
    def _generate_keyword_recommendation(self, success_rate: float, avg_karma: float, sentiment: float) -> str:
        """Generate recommendation for keyword usage"""
        if success_rate > 0.7 and avg_karma > 1 and sentiment > 0.6:
            return "Highly recommended - Use frequently"
        elif success_rate > 0.5 and avg_karma > 0:
            return "Recommended - Use moderately"
        elif success_rate > 0.3:
            return "Use with caution"
        else:
            return "Avoid - Poor performance"
    
    def _analyze_optimal_times(self, account_id: int, days: int) -> Dict[str, List[int]]:
        """Analyze optimal posting times by subreddit"""
        try:
            db = SessionLocal()
            
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            logs = db.query(EngagementLog).filter(
                EngagementLog.account_id == account_id,
                EngagementLog.timestamp >= cutoff_date,
                EngagementLog.status == 'success'
            ).all()
            
            subreddit_times = defaultdict(list)
            for log in logs:
                hour = log.timestamp.hour
                subreddit_times[log.subreddit].append(hour)
            
            optimal_times = {}
            for subreddit, hours in subreddit_times.items():
                # Find most common hours
                hour_counts = Counter(hours)
                optimal_times[subreddit] = [hour for hour, count in hour_counts.most_common(3)]
            
            db.close()
            return optimal_times
            
        except Exception as e:
            self.logger.error(f"Error analyzing optimal times: {e}")
            if 'db' in locals():
                db.close()
            return {}
    
    def _calculate_recommendation_confidence(self, metric: SubredditMetrics) -> float:
        """Calculate confidence score for recommendation"""
        # Base confidence on sample size and performance consistency
        sample_size_factor = min(1.0, metric.total_actions / 20)  # More actions = higher confidence
        performance_factor = metric.success_rate * (1 - metric.risk_score)
        
        confidence = (sample_size_factor * 0.4 + performance_factor * 0.6)
        return max(0.1, min(1.0, confidence))
    
    def _generate_recommendation_reasons(self, metric: SubredditMetrics) -> List[str]:
        """Generate reasons for recommendation"""
        reasons = []
        
        if metric.success_rate > 0.7:
            reasons.append(f"High success rate ({metric.success_rate:.1%})")
        if metric.avg_karma_gain > 2:
            reasons.append(f"Good karma gain (avg: {metric.avg_karma_gain:.1f})")
        if metric.risk_score < 0.3:
            reasons.append("Low risk profile")
        if metric.total_actions > 10:
            reasons.append(f"Sufficient data ({metric.total_actions} actions)")
        
        if not reasons:
            reasons.append("Limited positive indicators")
        
        return reasons
    
    def _determine_risk_level(self, risk_score: float) -> str:
        """Determine risk level from score"""
        if risk_score < 0.3:
            return "Low"
        elif risk_score < 0.6:
            return "Medium"
        else:
            return "High"

    def update_automation_targeting(self, account_id: int, recommendations: List[TargetingRecommendation]) -> Dict[str, Any]:
        """
        Update automation settings based on targeting recommendations

        Args:
            account_id: Account to update
            recommendations: Targeting recommendations to apply

        Returns:
            Update results
        """
        try:
            db = SessionLocal()
            account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
            if not account:
                return {'success': False, 'error': 'Account not found'}

            # Get or create automation settings
            settings = account.automation_settings
            if not settings:
                from models import AutomationSettings
                settings = AutomationSettings(account_id=account_id)
                db.add(settings)

            # Extract recommended subreddits (high confidence, low risk)
            recommended_subreddits = [
                rec.subreddit for rec in recommendations
                if rec.confidence > 0.6 and rec.risk_level in ['Low', 'Medium']
            ]

            # Extract suggested keywords
            all_keywords = []
            for rec in recommendations:
                all_keywords.extend(rec.suggested_keywords)

            # Get most common keywords
            keyword_counts = Counter(all_keywords)
            top_keywords = [kw for kw, _ in keyword_counts.most_common(10)]

            # Update settings
            settings.selected_subreddits = recommended_subreddits
            settings.active_keywords = top_keywords

            # Create engagement schedule based on optimal times
            engagement_schedule = {}
            for rec in recommendations:
                if rec.optimal_times:
                    engagement_schedule[rec.subreddit] = rec.optimal_times

            settings.engagement_schedule = engagement_schedule

            db.commit()
            db.close()

            return {
                'success': True,
                'updated_subreddits': len(recommended_subreddits),
                'updated_keywords': len(top_keywords),
                'engagement_schedule_entries': len(engagement_schedule),
                'recommendations_applied': len(recommendations)
            }

        except Exception as e:
            self.logger.error(f"Error updating automation targeting: {e}")
            if 'db' in locals():
                db.rollback()
                db.close()
            return {'success': False, 'error': str(e)}

# Global instance
targeting_service = TargetingService()
