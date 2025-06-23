"""
Account Health Dashboard Service for Reddit Automation Dashboard
Provides comprehensive health metrics, trust score calculation, and trend analysis
"""
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from collections import defaultdict
import statistics

from database import SessionLocal
from models import (
    RedditAccount, AccountHealth, EngagementLog, KarmaLog, 
    ActivityLog, AutomationSettings
)
from safety_tasks import get_safety_status, get_safety_alerts

logger = logging.getLogger(__name__)

@dataclass
class HealthMetrics:
    """Comprehensive health metrics for an account"""
    trust_score: float
    activity_score: float
    engagement_score: float
    safety_score: float
    consistency_score: float
    growth_score: float
    overall_health: float
    health_grade: str
    risk_level: str

@dataclass
class TrendAnalysis:
    """Trend analysis for account metrics"""
    metric_name: str
    current_value: float
    previous_value: float
    change_percentage: float
    trend_direction: str  # 'improving', 'declining', 'stable'
    confidence: float

@dataclass
class HealthAlert:
    """Health-related alert"""
    alert_type: str
    severity: str
    message: str
    metric_affected: str
    current_value: float
    threshold: float
    recommendations: List[str]

class HealthDashboardService:
    """Service for comprehensive account health monitoring and analysis"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Health scoring weights
        self.score_weights = {
            'trust': 0.25,
            'activity': 0.20,
            'engagement': 0.20,
            'safety': 0.20,
            'consistency': 0.10,
            'growth': 0.05
        }
        
        # Health thresholds
        self.health_thresholds = {
            'excellent': 85,
            'good': 70,
            'fair': 55,
            'poor': 40,
            'critical': 0
        }
    
    def calculate_comprehensive_health(self, account_id: int) -> HealthMetrics:
        """
        Calculate comprehensive health metrics for an account
        
        Args:
            account_id: Account to analyze
            
        Returns:
            Complete health metrics
        """
        try:
            # Calculate individual scores
            trust_score = self._calculate_trust_score(account_id)
            activity_score = self._calculate_activity_score(account_id)
            engagement_score = self._calculate_engagement_score(account_id)
            safety_score = self._calculate_safety_score(account_id)
            consistency_score = self._calculate_consistency_score(account_id)
            growth_score = self._calculate_growth_score(account_id)
            
            # Calculate overall health
            overall_health = (
                trust_score * self.score_weights['trust'] +
                activity_score * self.score_weights['activity'] +
                engagement_score * self.score_weights['engagement'] +
                safety_score * self.score_weights['safety'] +
                consistency_score * self.score_weights['consistency'] +
                growth_score * self.score_weights['growth']
            )
            
            # Determine health grade and risk level
            health_grade = self._get_health_grade(overall_health)
            risk_level = self._get_risk_level(overall_health, safety_score)
            
            return HealthMetrics(
                trust_score=trust_score,
                activity_score=activity_score,
                engagement_score=engagement_score,
                safety_score=safety_score,
                consistency_score=consistency_score,
                growth_score=growth_score,
                overall_health=overall_health,
                health_grade=health_grade,
                risk_level=risk_level
            )
            
        except Exception as e:
            self.logger.error(f"Error calculating comprehensive health: {e}")
            # Return default metrics
            return HealthMetrics(
                trust_score=50.0, activity_score=50.0, engagement_score=50.0,
                safety_score=50.0, consistency_score=50.0, growth_score=50.0,
                overall_health=50.0, health_grade="Unknown", risk_level="Medium"
            )
    
    def _calculate_trust_score(self, account_id: int) -> float:
        """Calculate trust score based on account age, karma, and history"""
        try:
            db = SessionLocal()
            account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
            
            if not account:
                return 0.0
            
            score = 0.0
            
            # Account age factor (0-30 points)
            if account.account_health:
                age_days = account.account_health.account_age_days or 0
                age_score = min(30, age_days / 10)  # 1 point per 10 days, max 30
                score += age_score
            
            # Karma factor (0-40 points)
            latest_karma = db.query(KarmaLog).filter(
                KarmaLog.account_id == account_id
            ).order_by(KarmaLog.timestamp.desc()).first()
            
            if latest_karma:
                total_karma = latest_karma.total_karma
                karma_score = min(40, math.log10(max(1, total_karma)) * 10)  # Log scale
                score += karma_score
            
            # Safety history factor (0-30 points)
            safety_violations = 0
            if account.account_health:
                safety_violations = (
                    (account.account_health.bans or 0) * 10 +
                    (account.account_health.deletions or 0) * 2 +
                    (account.account_health.removals or 0) * 1
                )
            
            safety_score = max(0, 30 - safety_violations)
            score += safety_score
            
            db.close()
            return min(100.0, score)
            
        except Exception as e:
            self.logger.error(f"Error calculating trust score: {e}")
            if 'db' in locals():
                db.close()
            return 50.0
    
    def _calculate_activity_score(self, account_id: int) -> float:
        """Calculate activity score based on engagement frequency and patterns"""
        try:
            db = SessionLocal()
            
            # Get recent activity (last 30 days)
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            recent_logs = db.query(EngagementLog).filter(
                EngagementLog.account_id == account_id,
                EngagementLog.timestamp >= cutoff_date
            ).all()
            
            if not recent_logs:
                db.close()
                return 0.0
            
            # Activity frequency score (0-50 points)
            daily_activity = len(recent_logs) / 30
            frequency_score = min(50, daily_activity * 5)  # 5 points per daily action, max 50
            
            # Activity diversity score (0-30 points)
            action_types = set(log.action_type for log in recent_logs)
            diversity_score = len(action_types) * 10  # 10 points per action type
            diversity_score = min(30, diversity_score)
            
            # Success rate score (0-20 points)
            successful_actions = sum(1 for log in recent_logs if log.status == 'success')
            success_rate = successful_actions / len(recent_logs) if recent_logs else 0
            success_score = success_rate * 20
            
            total_score = frequency_score + diversity_score + success_score
            
            db.close()
            return min(100.0, total_score)
            
        except Exception as e:
            self.logger.error(f"Error calculating activity score: {e}")
            if 'db' in locals():
                db.close()
            return 50.0
    
    def _calculate_engagement_score(self, account_id: int) -> float:
        """Calculate engagement score based on karma gains and interaction quality"""
        try:
            db = SessionLocal()
            
            # Get recent engagement with karma data
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            recent_logs = db.query(EngagementLog).filter(
                EngagementLog.account_id == account_id,
                EngagementLog.timestamp >= cutoff_date,
                EngagementLog.score.isnot(None)
            ).all()
            
            if not recent_logs:
                db.close()
                return 50.0  # Neutral score if no data
            
            # Average karma score (0-60 points)
            karma_scores = [log.score for log in recent_logs if log.score is not None]
            if karma_scores:
                avg_karma = statistics.mean(karma_scores)
                karma_score = min(60, max(0, (avg_karma + 5) * 6))  # Scale -5 to +5 karma to 0-60
            else:
                karma_score = 30
            
            # Positive engagement ratio (0-25 points)
            positive_engagements = sum(1 for score in karma_scores if score > 0)
            positive_ratio = positive_engagements / len(karma_scores) if karma_scores else 0.5
            positive_score = positive_ratio * 25
            
            # Engagement consistency (0-15 points)
            if len(karma_scores) > 1:
                karma_std = statistics.stdev(karma_scores)
                consistency = max(0, 1 - (karma_std / 10))  # Lower std dev = higher consistency
                consistency_score = consistency * 15
            else:
                consistency_score = 7.5  # Neutral
            
            total_score = karma_score + positive_score + consistency_score
            
            db.close()
            return min(100.0, total_score)
            
        except Exception as e:
            self.logger.error(f"Error calculating engagement score: {e}")
            if 'db' in locals():
                db.close()
            return 50.0
    
    def _calculate_safety_score(self, account_id: int) -> float:
        """Calculate safety score based on violations and risk factors"""
        try:
            # Get safety status
            safety_status = get_safety_status(account_id)
            
            if 'error' in safety_status:
                return 50.0
            
            base_score = 100.0
            
            # Deduct for safety issues
            if not safety_status.get('is_safe', True):
                base_score -= 30
            
            # Check recent safety alerts
            recent_alerts = get_safety_alerts(account_id, 24 * 7)  # Last week
            
            for alert in recent_alerts:
                severity = alert.get('severity', 'low')
                if severity == 'critical':
                    base_score -= 20
                elif severity == 'high':
                    base_score -= 10
                elif severity == 'medium':
                    base_score -= 5
                else:  # low
                    base_score -= 2
            
            # Account health factors
            db = SessionLocal()
            account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
            
            if account and account.account_health:
                health = account.account_health
                
                if health.shadowbanned:
                    base_score -= 50
                if health.login_issues:
                    base_score -= 15
                if health.captcha_triggered:
                    base_score -= 10
                
                # Deduct for violations
                base_score -= (health.bans or 0) * 25
                base_score -= (health.deletions or 0) * 5
                base_score -= (health.removals or 0) * 2
            
            db.close()
            return max(0.0, min(100.0, base_score))
            
        except Exception as e:
            self.logger.error(f"Error calculating safety score: {e}")
            if 'db' in locals():
                db.close()
            return 50.0
    
    def _calculate_consistency_score(self, account_id: int) -> float:
        """Calculate consistency score based on activity patterns"""
        try:
            db = SessionLocal()
            
            # Get activity over last 14 days
            cutoff_date = datetime.utcnow() - timedelta(days=14)
            recent_logs = db.query(EngagementLog).filter(
                EngagementLog.account_id == account_id,
                EngagementLog.timestamp >= cutoff_date
            ).all()
            
            if len(recent_logs) < 7:  # Need at least a week of data
                db.close()
                return 50.0
            
            # Group by day
            daily_activity = defaultdict(int)
            for log in recent_logs:
                day_key = log.timestamp.date()
                daily_activity[day_key] += 1
            
            # Calculate consistency
            daily_counts = list(daily_activity.values())
            if len(daily_counts) > 1:
                mean_activity = statistics.mean(daily_counts)
                std_activity = statistics.stdev(daily_counts)
                
                # Lower coefficient of variation = higher consistency
                if mean_activity > 0:
                    cv = std_activity / mean_activity
                    consistency_score = max(0, (1 - cv) * 100)
                else:
                    consistency_score = 0
            else:
                consistency_score = 50
            
            db.close()
            return min(100.0, consistency_score)
            
        except Exception as e:
            self.logger.error(f"Error calculating consistency score: {e}")
            if 'db' in locals():
                db.close()
            return 50.0
    
    def _calculate_growth_score(self, account_id: int) -> float:
        """Calculate growth score based on karma progression"""
        try:
            db = SessionLocal()
            
            # Get karma logs from last 30 days
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            karma_logs = db.query(KarmaLog).filter(
                KarmaLog.account_id == account_id,
                KarmaLog.timestamp >= cutoff_date
            ).order_by(KarmaLog.timestamp).all()
            
            if len(karma_logs) < 2:
                db.close()
                return 50.0
            
            # Calculate growth rate
            first_karma = karma_logs[0].total_karma
            last_karma = karma_logs[-1].total_karma
            
            if first_karma > 0:
                growth_rate = (last_karma - first_karma) / first_karma
                # Scale growth rate to 0-100
                growth_score = min(100, max(0, (growth_rate + 0.1) * 500))  # -10% to +10% maps to 0-100
            else:
                growth_score = 50 if last_karma > 0 else 0
            
            db.close()
            return growth_score
            
        except Exception as e:
            self.logger.error(f"Error calculating growth score: {e}")
            if 'db' in locals():
                db.close()
            return 50.0
    
    def _get_health_grade(self, overall_health: float) -> str:
        """Get health grade based on overall health score"""
        if overall_health >= self.health_thresholds['excellent']:
            return "A"
        elif overall_health >= self.health_thresholds['good']:
            return "B"
        elif overall_health >= self.health_thresholds['fair']:
            return "C"
        elif overall_health >= self.health_thresholds['poor']:
            return "D"
        else:
            return "F"
    
    def _get_risk_level(self, overall_health: float, safety_score: float) -> str:
        """Determine risk level based on health and safety scores"""
        if safety_score < 30 or overall_health < 30:
            return "High"
        elif safety_score < 60 or overall_health < 60:
            return "Medium"
        else:
            return "Low"

    def analyze_health_trends(self, account_id: int, days: int = 30) -> List[TrendAnalysis]:
        """
        Analyze health trends over time

        Args:
            account_id: Account to analyze
            days: Number of days to analyze

        Returns:
            List of trend analyses for different metrics
        """
        try:
            trends = []

            # Calculate current metrics
            current_metrics = self.calculate_comprehensive_health(account_id)

            # Calculate metrics from comparison period
            comparison_date = datetime.utcnow() - timedelta(days=days)
            previous_metrics = self._calculate_historical_health(account_id, comparison_date)

            # Analyze trends for each metric
            metrics_to_analyze = [
                ('trust_score', current_metrics.trust_score, previous_metrics.get('trust_score', 50)),
                ('activity_score', current_metrics.activity_score, previous_metrics.get('activity_score', 50)),
                ('engagement_score', current_metrics.engagement_score, previous_metrics.get('engagement_score', 50)),
                ('safety_score', current_metrics.safety_score, previous_metrics.get('safety_score', 50)),
                ('overall_health', current_metrics.overall_health, previous_metrics.get('overall_health', 50))
            ]

            for metric_name, current_value, previous_value in metrics_to_analyze:
                if previous_value > 0:
                    change_percentage = ((current_value - previous_value) / previous_value) * 100
                else:
                    change_percentage = 0

                # Determine trend direction
                if abs(change_percentage) < 5:
                    trend_direction = "stable"
                elif change_percentage > 0:
                    trend_direction = "improving"
                else:
                    trend_direction = "declining"

                # Calculate confidence based on data availability
                confidence = self._calculate_trend_confidence(account_id, days)

                trends.append(TrendAnalysis(
                    metric_name=metric_name,
                    current_value=current_value,
                    previous_value=previous_value,
                    change_percentage=change_percentage,
                    trend_direction=trend_direction,
                    confidence=confidence
                ))

            return trends

        except Exception as e:
            self.logger.error(f"Error analyzing health trends: {e}")
            return []

    def generate_health_alerts(self, account_id: int) -> List[HealthAlert]:
        """
        Generate health alerts based on current metrics and thresholds

        Args:
            account_id: Account to analyze

        Returns:
            List of health alerts
        """
        try:
            alerts = []
            metrics = self.calculate_comprehensive_health(account_id)

            # Critical health alert
            if metrics.overall_health < 30:
                alerts.append(HealthAlert(
                    alert_type="critical_health",
                    severity="critical",
                    message="Account health is critically low",
                    metric_affected="overall_health",
                    current_value=metrics.overall_health,
                    threshold=30,
                    recommendations=[
                        "Pause all automation immediately",
                        "Review recent activity for violations",
                        "Contact support if shadowbanned",
                        "Implement stricter safety measures"
                    ]
                ))

            # Safety score alert
            if metrics.safety_score < 50:
                severity = "critical" if metrics.safety_score < 30 else "high"
                alerts.append(HealthAlert(
                    alert_type="safety_concern",
                    severity=severity,
                    message="Safety score indicates potential risks",
                    metric_affected="safety_score",
                    current_value=metrics.safety_score,
                    threshold=50,
                    recommendations=[
                        "Review recent safety alerts",
                        "Reduce automation frequency",
                        "Check for shadowban status",
                        "Monitor rate limits closely"
                    ]
                ))

            # Low engagement alert
            if metrics.engagement_score < 40:
                alerts.append(HealthAlert(
                    alert_type="low_engagement",
                    severity="medium",
                    message="Engagement quality is below optimal levels",
                    metric_affected="engagement_score",
                    current_value=metrics.engagement_score,
                    threshold=40,
                    recommendations=[
                        "Review content quality",
                        "Analyze subreddit targeting",
                        "Improve comment relevance",
                        "Focus on high-performing subreddits"
                    ]
                ))

            # Activity consistency alert
            if metrics.consistency_score < 30:
                alerts.append(HealthAlert(
                    alert_type="inconsistent_activity",
                    severity="low",
                    message="Activity patterns are inconsistent",
                    metric_affected="consistency_score",
                    current_value=metrics.consistency_score,
                    threshold=30,
                    recommendations=[
                        "Establish regular activity schedule",
                        "Use behavior simulation features",
                        "Avoid burst activity patterns",
                        "Maintain steady engagement levels"
                    ]
                ))

            # Trust score alert
            if metrics.trust_score < 40:
                alerts.append(HealthAlert(
                    alert_type="low_trust",
                    severity="medium",
                    message="Account trust score needs improvement",
                    metric_affected="trust_score",
                    current_value=metrics.trust_score,
                    threshold=40,
                    recommendations=[
                        "Build karma gradually",
                        "Avoid policy violations",
                        "Maintain account age",
                        "Focus on quality contributions"
                    ]
                ))

            return alerts

        except Exception as e:
            self.logger.error(f"Error generating health alerts: {e}")
            return []

    def _calculate_historical_health(self, account_id: int, target_date: datetime) -> Dict[str, float]:
        """Calculate health metrics for a historical point in time"""
        try:
            # This is a simplified version - in production, you'd want to store
            # historical health snapshots or calculate based on historical data

            # For now, return estimated values based on available historical data
            db = SessionLocal()

            # Get historical karma
            historical_karma = db.query(KarmaLog).filter(
                KarmaLog.account_id == account_id,
                KarmaLog.timestamp <= target_date
            ).order_by(KarmaLog.timestamp.desc()).first()

            # Get historical activity
            historical_activity = db.query(EngagementLog).filter(
                EngagementLog.account_id == account_id,
                EngagementLog.timestamp <= target_date,
                EngagementLog.timestamp >= target_date - timedelta(days=30)
            ).count()

            db.close()

            # Estimate historical scores (simplified)
            estimated_scores = {
                'trust_score': 50.0,  # Would need more sophisticated calculation
                'activity_score': min(100, historical_activity * 2),
                'engagement_score': 50.0,  # Would need historical karma analysis
                'safety_score': 75.0,  # Assume good unless violations found
                'overall_health': 60.0
            }

            return estimated_scores

        except Exception as e:
            self.logger.error(f"Error calculating historical health: {e}")
            if 'db' in locals():
                db.close()
            return {}

    def _calculate_trend_confidence(self, account_id: int, days: int) -> float:
        """Calculate confidence in trend analysis based on data availability"""
        try:
            db = SessionLocal()

            # Count data points in the analysis period
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            data_points = db.query(EngagementLog).filter(
                EngagementLog.account_id == account_id,
                EngagementLog.timestamp >= cutoff_date
            ).count()

            db.close()

            # More data points = higher confidence
            confidence = min(1.0, data_points / (days * 2))  # 2 actions per day for full confidence
            return confidence

        except Exception as e:
            self.logger.error(f"Error calculating trend confidence: {e}")
            if 'db' in locals():
                db.close()
            return 0.5

    def get_health_recommendations(self, account_id: int) -> List[str]:
        """
        Get personalized health improvement recommendations

        Args:
            account_id: Account to analyze

        Returns:
            List of actionable recommendations
        """
        try:
            metrics = self.calculate_comprehensive_health(account_id)
            recommendations = []

            # Overall health recommendations
            if metrics.overall_health < 50:
                recommendations.append("Focus on improving overall account health")
                recommendations.append("Review and address safety concerns")

            # Specific metric recommendations
            if metrics.trust_score < 60:
                recommendations.append("Build account trust through consistent, quality engagement")
                recommendations.append("Avoid any policy violations or suspicious activity")

            if metrics.activity_score < 60:
                recommendations.append("Increase engagement frequency with quality content")
                recommendations.append("Diversify activity types (comments, upvotes, posts)")

            if metrics.engagement_score < 60:
                recommendations.append("Focus on higher-quality comments and posts")
                recommendations.append("Target subreddits with better engagement rates")

            if metrics.safety_score < 70:
                recommendations.append("Review safety alerts and address any issues")
                recommendations.append("Implement stricter rate limiting")

            if metrics.consistency_score < 60:
                recommendations.append("Maintain more consistent activity patterns")
                recommendations.append("Use scheduling features for regular engagement")

            if metrics.growth_score < 60:
                recommendations.append("Focus on karma-generating activities")
                recommendations.append("Analyze and replicate successful content patterns")

            # Add general recommendations if no specific issues
            if not recommendations:
                recommendations.extend([
                    "Maintain current excellent performance",
                    "Continue monitoring health metrics",
                    "Consider gradual expansion of activities"
                ])

            return recommendations[:10]  # Limit to top 10 recommendations

        except Exception as e:
            self.logger.error(f"Error generating health recommendations: {e}")
            return ["Unable to generate recommendations at this time"]

# Global instance
health_dashboard = HealthDashboardService()
