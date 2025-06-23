"""
Enhanced Human Behavior Simulation for Reddit Automation Dashboard
Provides sophisticated algorithms to mimic realistic human activity patterns
"""
import random
import logging
import math
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import json

from database import SessionLocal
from models import RedditAccount, ActivityLog, EngagementLog, AutomationSettings

logger = logging.getLogger(__name__)

class ActivityType(Enum):
    """Types of activities for behavior simulation"""
    UPVOTE = "upvote"
    COMMENT = "comment"
    POST = "post"
    BROWSE = "browse"
    SEARCH = "search"

class UserPersonality(Enum):
    """User personality types affecting behavior patterns"""
    CASUAL = "casual"          # Sporadic activity, longer breaks
    ACTIVE = "active"          # Regular activity, consistent patterns
    POWER_USER = "power_user"  # High activity, multiple sessions
    LURKER = "lurker"          # Mostly browsing, minimal posting

@dataclass
class ActivitySession:
    """Represents a realistic activity session"""
    start_time: datetime
    duration_minutes: int
    activity_types: List[ActivityType]
    intensity: float  # 0.0 to 1.0
    break_probability: float
    personality_type: UserPersonality

@dataclass
class BehaviorPattern:
    """Behavior pattern configuration"""
    personality: UserPersonality
    daily_sessions: int
    session_duration_range: Tuple[int, int]  # min, max minutes
    preferred_hours: List[int]
    activity_distribution: Dict[ActivityType, float]
    break_frequency: float
    weekend_modifier: float

class HumanBehaviorSimulator:
    """Advanced human behavior simulation engine"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.behavior_patterns = self._initialize_behavior_patterns()
        self.timezone_offsets = self._initialize_timezone_patterns()
    
    def _initialize_behavior_patterns(self) -> Dict[UserPersonality, BehaviorPattern]:
        """Initialize realistic behavior patterns for different user types"""
        return {
            UserPersonality.CASUAL: BehaviorPattern(
                personality=UserPersonality.CASUAL,
                daily_sessions=2,
                session_duration_range=(5, 20),
                preferred_hours=[12, 13, 19, 20, 21],
                activity_distribution={
                    ActivityType.BROWSE: 0.4,
                    ActivityType.UPVOTE: 0.35,
                    ActivityType.COMMENT: 0.2,
                    ActivityType.POST: 0.05
                },
                break_frequency=0.3,
                weekend_modifier=1.5
            ),
            UserPersonality.ACTIVE: BehaviorPattern(
                personality=UserPersonality.ACTIVE,
                daily_sessions=4,
                session_duration_range=(10, 45),
                preferred_hours=[8, 9, 12, 13, 17, 18, 20, 21, 22],
                activity_distribution={
                    ActivityType.BROWSE: 0.3,
                    ActivityType.UPVOTE: 0.4,
                    ActivityType.COMMENT: 0.25,
                    ActivityType.POST: 0.05
                },
                break_frequency=0.2,
                weekend_modifier=1.3
            ),
            UserPersonality.POWER_USER: BehaviorPattern(
                personality=UserPersonality.POWER_USER,
                daily_sessions=6,
                session_duration_range=(20, 90),
                preferred_hours=[7, 8, 9, 11, 12, 13, 15, 16, 17, 18, 19, 20, 21, 22, 23],
                activity_distribution={
                    ActivityType.BROWSE: 0.25,
                    ActivityType.UPVOTE: 0.35,
                    ActivityType.COMMENT: 0.3,
                    ActivityType.POST: 0.1
                },
                break_frequency=0.15,
                weekend_modifier=1.2
            ),
            UserPersonality.LURKER: BehaviorPattern(
                personality=UserPersonality.LURKER,
                daily_sessions=3,
                session_duration_range=(15, 60),
                preferred_hours=[11, 12, 13, 18, 19, 20, 21, 22],
                activity_distribution={
                    ActivityType.BROWSE: 0.6,
                    ActivityType.UPVOTE: 0.3,
                    ActivityType.COMMENT: 0.08,
                    ActivityType.POST: 0.02
                },
                break_frequency=0.25,
                weekend_modifier=1.4
            )
        }
    
    def _initialize_timezone_patterns(self) -> Dict[str, List[int]]:
        """Initialize timezone-based activity patterns"""
        return {
            'US_Eastern': [7, 8, 9, 12, 13, 17, 18, 19, 20, 21, 22],
            'US_Pacific': [6, 7, 8, 11, 12, 16, 17, 18, 19, 20, 21],
            'Europe': [8, 9, 10, 12, 13, 14, 18, 19, 20, 21, 22],
            'Asia': [9, 10, 11, 13, 14, 15, 19, 20, 21, 22, 23]
        }
    
    def generate_realistic_delay(self, action_type: ActivityType, previous_action: Optional[ActivityType] = None) -> int:
        """
        Generate realistic delays between actions based on human behavior
        
        Args:
            action_type: Type of current action
            previous_action: Type of previous action
            
        Returns:
            Delay in seconds
        """
        base_delays = {
            ActivityType.UPVOTE: (2, 8),      # Quick upvotes
            ActivityType.COMMENT: (30, 180),  # Time to read and write
            ActivityType.POST: (120, 600),    # Time to create content
            ActivityType.BROWSE: (5, 30),     # Browsing between actions
            ActivityType.SEARCH: (10, 45)     # Searching and reading
        }
        
        min_delay, max_delay = base_delays.get(action_type, (5, 30))
        
        # Adjust based on previous action
        if previous_action:
            if previous_action == ActivityType.COMMENT and action_type == ActivityType.UPVOTE:
                # Quick upvote after commenting
                min_delay = max(1, min_delay // 2)
                max_delay = max(3, max_delay // 2)
            elif previous_action == ActivityType.UPVOTE and action_type == ActivityType.COMMENT:
                # Longer delay when switching from upvoting to commenting
                min_delay = int(min_delay * 1.5)
                max_delay = int(max_delay * 1.5)
        
        # Add human-like variability using normal distribution
        mean_delay = (min_delay + max_delay) / 2
        std_dev = (max_delay - min_delay) / 6  # 99.7% within range
        
        delay = max(min_delay, int(random.normalvariate(mean_delay, std_dev)))
        delay = min(delay, max_delay * 2)  # Cap at 2x max for extreme cases
        
        # Add micro-variations (human reaction time)
        micro_variation = random.uniform(0.1, 2.0)
        
        return int(delay + micro_variation)
    
    def calculate_activity_probability(self, account_id: int, action_type: ActivityType, 
                                     current_time: datetime = None) -> float:
        """
        Calculate probability of performing an action at current time
        
        Args:
            account_id: Account to analyze
            action_type: Type of action
            current_time: Current time (defaults to now)
            
        Returns:
            Probability (0.0 to 1.0)
        """
        if current_time is None:
            current_time = datetime.utcnow()
        
        try:
            # Get account personality
            personality = self._get_account_personality(account_id)
            pattern = self.behavior_patterns[personality]
            
            # Base probability from activity distribution
            base_prob = pattern.activity_distribution.get(action_type, 0.1)
            
            # Time-based modifiers
            hour = current_time.hour
            time_modifier = 1.0
            
            if hour in pattern.preferred_hours:
                time_modifier = 1.5
            elif hour < 6 or hour > 23:
                time_modifier = 0.2  # Very low activity during sleep hours
            elif 6 <= hour < 9:
                time_modifier = 0.7  # Lower activity in early morning
            
            # Weekend modifier
            is_weekend = current_time.weekday() >= 5
            weekend_mod = pattern.weekend_modifier if is_weekend else 1.0
            
            # Recent activity modifier (fatigue simulation)
            recent_activity_mod = self._calculate_fatigue_modifier(account_id, current_time)
            
            # Session context modifier
            session_mod = self._calculate_session_modifier(account_id, current_time)
            
            final_probability = base_prob * time_modifier * weekend_mod * recent_activity_mod * session_mod
            
            return min(1.0, max(0.0, final_probability))
            
        except Exception as e:
            self.logger.error(f"Error calculating activity probability: {e}")
            return 0.1  # Default low probability
    
    def generate_activity_schedule(self, account_id: int, days: int = 7) -> List[ActivitySession]:
        """
        Generate a realistic activity schedule for the next N days
        
        Args:
            account_id: Account to schedule for
            days: Number of days to schedule
            
        Returns:
            List of scheduled activity sessions
        """
        try:
            personality = self._get_account_personality(account_id)
            pattern = self.behavior_patterns[personality]
            
            schedule = []
            start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            for day in range(days):
                current_date = start_date + timedelta(days=day)
                is_weekend = current_date.weekday() >= 5
                
                # Adjust session count for weekends
                session_count = pattern.daily_sessions
                if is_weekend:
                    session_count = int(session_count * pattern.weekend_modifier)
                
                # Add randomness to session count
                session_count = max(1, int(random.normalvariate(session_count, session_count * 0.3)))
                
                # Generate sessions for the day
                day_sessions = self._generate_day_sessions(
                    current_date, session_count, pattern, personality
                )
                schedule.extend(day_sessions)
            
            return schedule
            
        except Exception as e:
            self.logger.error(f"Error generating activity schedule: {e}")
            return []
    
    def simulate_reading_time(self, content_length: int, content_type: str = "comment") -> int:
        """
        Simulate realistic reading time based on content length and type
        
        Args:
            content_length: Length of content in characters
            content_type: Type of content (comment, post, title)
            
        Returns:
            Reading time in seconds
        """
        # Average reading speeds (words per minute)
        reading_speeds = {
            "title": 200,      # Quick scanning
            "comment": 150,    # Casual reading
            "post": 120        # Careful reading
        }
        
        wpm = reading_speeds.get(content_type, 150)
        
        # Estimate words (average 5 characters per word)
        estimated_words = content_length / 5
        
        # Calculate base reading time in seconds
        base_time = (estimated_words / wpm) * 60
        
        # Add processing time (comprehension, decision making)
        processing_time = base_time * random.uniform(0.2, 0.5)
        
        # Add human variability
        total_time = base_time + processing_time
        variation = random.normalvariate(1.0, 0.3)
        
        final_time = max(1, int(total_time * variation))
        
        # Cap reading time (people don't read forever)
        max_time = {
            "title": 10,
            "comment": 120,
            "post": 300
        }.get(content_type, 120)
        
        return min(final_time, max_time)
    
    def _get_account_personality(self, account_id: int) -> UserPersonality:
        """Get or assign personality type for account"""
        try:
            db = SessionLocal()
            
            # Check if personality is stored in automation settings
            account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
            if account and account.automation_settings:
                settings = account.automation_settings
                if hasattr(settings, 'personality_type') and settings.personality_type:
                    db.close()
                    return UserPersonality(settings.personality_type)
            
            # Assign personality based on account activity history
            recent_logs = db.query(EngagementLog).filter(
                EngagementLog.account_id == account_id,
                EngagementLog.timestamp >= datetime.utcnow() - timedelta(days=30)
            ).count()
            
            db.close()
            
            # Assign personality based on activity level
            if recent_logs > 200:
                return UserPersonality.POWER_USER
            elif recent_logs > 100:
                return UserPersonality.ACTIVE
            elif recent_logs > 20:
                return UserPersonality.CASUAL
            else:
                return UserPersonality.LURKER
                
        except Exception as e:
            self.logger.error(f"Error getting account personality: {e}")
            return UserPersonality.CASUAL  # Default
    
    def _calculate_fatigue_modifier(self, account_id: int, current_time: datetime) -> float:
        """Calculate fatigue modifier based on recent activity"""
        try:
            db = SessionLocal()
            
            # Check activity in last 2 hours
            recent_cutoff = current_time - timedelta(hours=2)
            recent_activity = db.query(EngagementLog).filter(
                EngagementLog.account_id == account_id,
                EngagementLog.timestamp >= recent_cutoff
            ).count()
            
            db.close()
            
            # More recent activity = more fatigue
            if recent_activity > 20:
                return 0.3  # High fatigue
            elif recent_activity > 10:
                return 0.6  # Medium fatigue
            elif recent_activity > 5:
                return 0.8  # Low fatigue
            else:
                return 1.0  # No fatigue
                
        except Exception as e:
            self.logger.error(f"Error calculating fatigue modifier: {e}")
            return 1.0
    
    def _calculate_session_modifier(self, account_id: int, current_time: datetime) -> float:
        """Calculate session context modifier"""
        try:
            db = SessionLocal()
            
            # Check if we're in an active session (activity in last 30 minutes)
            session_cutoff = current_time - timedelta(minutes=30)
            session_activity = db.query(EngagementLog).filter(
                EngagementLog.account_id == account_id,
                EngagementLog.timestamp >= session_cutoff
            ).count()
            
            db.close()
            
            if session_activity > 0:
                return 1.2  # In active session, higher probability
            else:
                return 0.8  # Not in session, lower probability
                
        except Exception as e:
            self.logger.error(f"Error calculating session modifier: {e}")
            return 1.0
    
    def _generate_day_sessions(self, date: datetime, session_count: int, 
                              pattern: BehaviorPattern, personality: UserPersonality) -> List[ActivitySession]:
        """Generate activity sessions for a specific day"""
        sessions = []
        
        # Distribute sessions throughout preferred hours
        available_hours = pattern.preferred_hours.copy()
        random.shuffle(available_hours)
        
        for i in range(min(session_count, len(available_hours))):
            hour = available_hours[i]
            
            # Add some randomness to the exact time
            minute = random.randint(0, 59)
            start_time = date.replace(hour=hour, minute=minute)
            
            # Generate session duration
            min_duration, max_duration = pattern.session_duration_range
            duration = random.randint(min_duration, max_duration)
            
            # Determine activity types for this session
            activity_types = self._select_session_activities(pattern)
            
            # Calculate session intensity
            intensity = random.uniform(0.3, 1.0)
            
            sessions.append(ActivitySession(
                start_time=start_time,
                duration_minutes=duration,
                activity_types=activity_types,
                intensity=intensity,
                break_probability=pattern.break_frequency,
                personality_type=personality
            ))
        
        return sorted(sessions, key=lambda x: x.start_time)
    
    def _select_session_activities(self, pattern: BehaviorPattern) -> List[ActivityType]:
        """Select activity types for a session based on pattern"""
        activities = []
        
        # Always include browsing
        activities.append(ActivityType.BROWSE)
        
        # Add other activities based on distribution
        for activity_type, probability in pattern.activity_distribution.items():
            if activity_type != ActivityType.BROWSE and random.random() < probability:
                activities.append(activity_type)
        
        return activities

    def simulate_natural_breaks(self, session: ActivitySession, elapsed_minutes: int) -> bool:
        """
        Determine if a natural break should occur during a session

        Args:
            session: Current activity session
            elapsed_minutes: Minutes elapsed in session

        Returns:
            True if a break should occur
        """
        # Probability increases with session length
        base_break_prob = session.break_probability

        # Increase probability as session gets longer
        time_factor = elapsed_minutes / session.duration_minutes
        adjusted_prob = base_break_prob * (1 + time_factor)

        # Higher intensity sessions have more breaks
        intensity_factor = session.intensity * 0.5
        final_prob = adjusted_prob + intensity_factor

        return random.random() < final_prob

    def generate_break_duration(self, session: ActivitySession) -> int:
        """
        Generate realistic break duration

        Args:
            session: Current activity session

        Returns:
            Break duration in seconds
        """
        personality = session.personality_type

        # Break duration ranges by personality
        break_ranges = {
            UserPersonality.CASUAL: (60, 300),      # 1-5 minutes
            UserPersonality.ACTIVE: (30, 180),      # 30 seconds - 3 minutes
            UserPersonality.POWER_USER: (15, 120),  # 15 seconds - 2 minutes
            UserPersonality.LURKER: (120, 600)      # 2-10 minutes
        }

        min_break, max_break = break_ranges.get(personality, (60, 300))

        # Add randomness with normal distribution
        mean_break = (min_break + max_break) / 2
        std_dev = (max_break - min_break) / 6

        duration = max(min_break, int(random.normalvariate(mean_break, std_dev)))
        return min(duration, max_break * 2)

    def simulate_typing_speed(self, text_length: int, user_skill: str = "average") -> int:
        """
        Simulate realistic typing time for comments/posts

        Args:
            text_length: Length of text to type
            user_skill: Typing skill level (slow, average, fast)

        Returns:
            Typing time in seconds
        """
        # Words per minute by skill level
        wpm_ranges = {
            "slow": (20, 35),
            "average": (35, 50),
            "fast": (50, 70)
        }

        min_wpm, max_wpm = wpm_ranges.get(user_skill, (35, 50))
        wpm = random.uniform(min_wpm, max_wpm)

        # Estimate words (average 5 characters per word)
        estimated_words = text_length / 5

        # Base typing time
        base_time = (estimated_words / wpm) * 60

        # Add thinking/editing time (50-100% of typing time)
        thinking_time = base_time * random.uniform(0.5, 1.0)

        # Add pauses and corrections
        pause_time = base_time * random.uniform(0.1, 0.3)

        total_time = base_time + thinking_time + pause_time

        # Add human variability
        variation = random.normalvariate(1.0, 0.2)

        return max(10, int(total_time * variation))  # Minimum 10 seconds

    def calculate_engagement_momentum(self, account_id: int, current_time: datetime = None) -> float:
        """
        Calculate engagement momentum (tendency to continue engaging)

        Args:
            account_id: Account to analyze
            current_time: Current time

        Returns:
            Momentum score (0.0 to 2.0)
        """
        if current_time is None:
            current_time = datetime.utcnow()

        try:
            db = SessionLocal()

            # Check recent activity (last hour)
            recent_cutoff = current_time - timedelta(hours=1)
            recent_logs = db.query(EngagementLog).filter(
                EngagementLog.account_id == account_id,
                EngagementLog.timestamp >= recent_cutoff
            ).all()

            db.close()

            if not recent_logs:
                return 0.5  # Neutral momentum

            # Calculate momentum factors
            activity_count = len(recent_logs)
            success_rate = sum(1 for log in recent_logs if log.status == 'success') / activity_count
            avg_karma = sum(log.score or 0 for log in recent_logs) / activity_count

            # Recent activity increases momentum
            activity_factor = min(2.0, activity_count / 10)

            # Success increases momentum
            success_factor = success_rate * 1.5

            # Positive karma increases momentum
            karma_factor = max(0.5, min(1.5, 1.0 + (avg_karma / 10)))

            momentum = (activity_factor + success_factor + karma_factor) / 3

            return max(0.1, min(2.0, momentum))

        except Exception as e:
            self.logger.error(f"Error calculating engagement momentum: {e}")
            return 0.5

    def should_end_session(self, session: ActivitySession, elapsed_minutes: int,
                          recent_failures: int = 0) -> bool:
        """
        Determine if a session should end based on various factors

        Args:
            session: Current session
            elapsed_minutes: Minutes elapsed
            recent_failures: Number of recent failed actions

        Returns:
            True if session should end
        """
        # Base probability increases with time
        time_factor = elapsed_minutes / session.duration_minutes

        if time_factor >= 1.0:
            return True  # Session duration exceeded

        # Early termination probability
        base_end_prob = 0.05  # 5% base chance per check

        # Increase probability with time
        time_end_prob = base_end_prob * time_factor * 2

        # Failures increase end probability
        failure_end_prob = recent_failures * 0.1

        # Low intensity sessions end earlier
        intensity_factor = (1.0 - session.intensity) * 0.1

        total_end_prob = time_end_prob + failure_end_prob + intensity_factor

        return random.random() < total_end_prob

    def generate_content_interaction_pattern(self, content_type: str, content_length: int) -> Dict[str, Any]:
        """
        Generate realistic content interaction pattern

        Args:
            content_type: Type of content (post, comment, etc.)
            content_length: Length of content

        Returns:
            Interaction pattern with timings and actions
        """
        pattern = {
            "read_time": self.simulate_reading_time(content_length, content_type),
            "actions": [],
            "total_time": 0
        }

        # Determine likely actions based on content type
        if content_type == "post":
            action_probabilities = {
                "upvote": 0.7,
                "downvote": 0.05,
                "comment": 0.3,
                "save": 0.1,
                "share": 0.05
            }
        else:  # comment
            action_probabilities = {
                "upvote": 0.6,
                "downvote": 0.1,
                "reply": 0.2,
                "report": 0.02
            }

        current_time = 0

        # Reading phase
        current_time += pattern["read_time"]

        # Decision phase
        decision_time = random.randint(1, 5)
        current_time += decision_time

        # Action phase
        for action, probability in action_probabilities.items():
            if random.random() < probability:
                action_delay = random.randint(1, 3)
                current_time += action_delay

                pattern["actions"].append({
                    "action": action,
                    "timestamp": current_time,
                    "delay": action_delay
                })

        pattern["total_time"] = current_time

        return pattern

    def adapt_behavior_based_on_feedback(self, account_id: int, recent_performance: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt behavior patterns based on recent performance feedback

        Args:
            account_id: Account to adapt
            recent_performance: Recent performance metrics

        Returns:
            Adapted behavior recommendations
        """
        adaptations = {
            "timing_adjustments": [],
            "activity_adjustments": [],
            "risk_adjustments": [],
            "confidence": 0.0
        }

        try:
            success_rate = recent_performance.get("success_rate", 0.5)
            avg_karma = recent_performance.get("avg_karma", 0)
            failure_rate = recent_performance.get("failure_rate", 0)

            # Timing adaptations
            if success_rate < 0.3:
                adaptations["timing_adjustments"].append("Increase delays between actions")
                adaptations["timing_adjustments"].append("Reduce session frequency")
            elif success_rate > 0.8:
                adaptations["timing_adjustments"].append("Can slightly reduce delays")

            # Activity adaptations
            if avg_karma < 0:
                adaptations["activity_adjustments"].append("Focus on higher-quality subreddits")
                adaptations["activity_adjustments"].append("Reduce comment frequency")
            elif avg_karma > 5:
                adaptations["activity_adjustments"].append("Current activity pattern is effective")

            # Risk adaptations
            if failure_rate > 0.2:
                adaptations["risk_adjustments"].append("Implement longer cooling-off periods")
                adaptations["risk_adjustments"].append("Reduce automation intensity")

            # Calculate confidence in adaptations
            data_points = recent_performance.get("total_actions", 0)
            adaptations["confidence"] = min(1.0, data_points / 50)  # More data = higher confidence

            return adaptations

        except Exception as e:
            self.logger.error(f"Error adapting behavior: {e}")
            return adaptations

# Global instance
behavior_simulator = HumanBehaviorSimulator()
