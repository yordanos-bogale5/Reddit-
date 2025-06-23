"""
NLP Comment Quality Control Service for Reddit Automation Dashboard
Provides sentiment analysis, spam detection, and comment quality scoring
"""
import logging
import re
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import asyncio

# NLP Libraries
try:
    import nltk
    from nltk.sentiment import SentimentIntensityAnalyzer
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize
    from nltk.stem import WordNetLemmatizer
except ImportError:
    nltk = None

try:
    from textblob import TextBlob
except ImportError:
    TextBlob = None

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer as VaderAnalyzer
except ImportError:
    VaderAnalyzer = None

try:
    from langdetect import detect, LangDetectError
except ImportError:
    detect = None

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
import pickle
import os

logger = logging.getLogger(__name__)

@dataclass
class CommentQualityScore:
    """Data class for comment quality analysis results"""
    overall_score: float  # 0-100 scale
    sentiment_score: float  # -1 to 1 scale
    spam_probability: float  # 0-1 scale
    readability_score: float  # 0-100 scale
    relevance_score: float  # 0-100 scale
    toxicity_score: float  # 0-1 scale
    language: str
    word_count: int
    issues: List[str]
    recommendations: List[str]

@dataclass
class SentimentAnalysis:
    """Data class for sentiment analysis results"""
    compound: float  # Overall sentiment (-1 to 1)
    positive: float  # Positive sentiment (0 to 1)
    negative: float  # Negative sentiment (0 to 1)
    neutral: float   # Neutral sentiment (0 to 1)
    confidence: float  # Confidence in analysis (0 to 1)

class NLPService:
    """NLP service for comment quality control and analysis"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.initialized = False
        self.sentiment_analyzer = None
        self.vader_analyzer = None
        self.spam_classifier = None
        self.lemmatizer = None
        self.stop_words = set()
        
        # Initialize the service
        self._initialize()
    
    def _initialize(self):
        """Initialize NLP models and resources"""
        try:
            # Download required NLTK data
            if nltk:
                try:
                    nltk.download('vader_lexicon', quiet=True)
                    nltk.download('punkt', quiet=True)
                    nltk.download('stopwords', quiet=True)
                    nltk.download('wordnet', quiet=True)
                    
                    self.sentiment_analyzer = SentimentIntensityAnalyzer()
                    self.lemmatizer = WordNetLemmatizer()
                    self.stop_words = set(stopwords.words('english'))
                except Exception as e:
                    self.logger.warning(f"Failed to initialize NLTK components: {e}")
            
            # Initialize VADER sentiment analyzer
            if VaderAnalyzer:
                try:
                    self.vader_analyzer = VaderAnalyzer()
                except Exception as e:
                    self.logger.warning(f"Failed to initialize VADER analyzer: {e}")
            
            # Initialize spam classifier (simple rule-based for now)
            self._initialize_spam_classifier()
            
            self.initialized = True
            self.logger.info("NLP service initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize NLP service: {e}")
            self.initialized = False
    
    def _initialize_spam_classifier(self):
        """Initialize spam classification model"""
        # For now, use a simple rule-based approach
        # In production, this would be a trained ML model
        self.spam_patterns = [
            r'\b(buy|sell|cheap|free|money|cash|earn|income)\b',
            r'\b(click|link|visit|website|url)\b',
            r'\b(amazing|incredible|unbelievable|guaranteed)\b',
            r'[A-Z]{3,}',  # Excessive caps
            r'(.)\1{3,}',  # Repeated characters
            r'\b\d+\s*(dollars?|usd|\$)\b',  # Money mentions
        ]
        self.spam_regex = re.compile('|'.join(self.spam_patterns), re.IGNORECASE)
    
    def analyze_comment_quality(self, text: str, context: Optional[Dict] = None) -> CommentQualityScore:
        """
        Comprehensive comment quality analysis
        
        Args:
            text: Comment text to analyze
            context: Optional context (subreddit, post topic, etc.)
            
        Returns:
            CommentQualityScore with detailed analysis
        """
        if not self.initialized:
            self.logger.warning("NLP service not initialized, returning default scores")
            return self._get_default_score(text)
        
        try:
            # Basic text preprocessing
            cleaned_text = self._preprocess_text(text)
            
            # Perform various analyses
            sentiment = self.analyze_sentiment(text)
            spam_prob = self.detect_spam(text)
            readability = self._calculate_readability(text)
            relevance = self._calculate_relevance(text, context)
            toxicity = self._detect_toxicity(text)
            language = self._detect_language(text)
            
            # Calculate overall quality score
            overall_score = self._calculate_overall_score(
                sentiment, spam_prob, readability, relevance, toxicity
            )
            
            # Generate issues and recommendations
            issues = self._identify_issues(text, sentiment, spam_prob, toxicity)
            recommendations = self._generate_recommendations(issues, sentiment)
            
            return CommentQualityScore(
                overall_score=overall_score,
                sentiment_score=sentiment.compound,
                spam_probability=spam_prob,
                readability_score=readability,
                relevance_score=relevance,
                toxicity_score=toxicity,
                language=language,
                word_count=len(text.split()),
                issues=issues,
                recommendations=recommendations
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing comment quality: {e}")
            return self._get_default_score(text)
    
    def analyze_sentiment(self, text: str) -> SentimentAnalysis:
        """
        Analyze sentiment of text using multiple methods
        
        Args:
            text: Text to analyze
            
        Returns:
            SentimentAnalysis with detailed sentiment scores
        """
        try:
            # Use VADER if available
            if self.vader_analyzer:
                scores = self.vader_analyzer.polarity_scores(text)
                return SentimentAnalysis(
                    compound=scores['compound'],
                    positive=scores['pos'],
                    negative=scores['neg'],
                    neutral=scores['neu'],
                    confidence=abs(scores['compound'])
                )
            
            # Fallback to TextBlob if available
            elif TextBlob:
                blob = TextBlob(text)
                polarity = blob.sentiment.polarity
                subjectivity = blob.sentiment.subjectivity
                
                # Convert to VADER-like format
                return SentimentAnalysis(
                    compound=polarity,
                    positive=max(0, polarity),
                    negative=max(0, -polarity),
                    neutral=1 - abs(polarity),
                    confidence=subjectivity
                )
            
            else:
                # Basic fallback
                return SentimentAnalysis(
                    compound=0.0,
                    positive=0.33,
                    negative=0.33,
                    neutral=0.34,
                    confidence=0.1
                )
                
        except Exception as e:
            self.logger.error(f"Error in sentiment analysis: {e}")
            return SentimentAnalysis(0.0, 0.33, 0.33, 0.34, 0.1)
    
    def detect_spam(self, text: str) -> float:
        """
        Detect spam probability in text
        
        Args:
            text: Text to analyze
            
        Returns:
            Spam probability (0-1)
        """
        try:
            spam_score = 0.0
            
            # Check for spam patterns
            if self.spam_regex:
                matches = len(self.spam_regex.findall(text))
                spam_score += min(matches * 0.2, 0.8)
            
            # Check text characteristics
            if len(text) < 10:
                spam_score += 0.3  # Very short comments
            
            if text.count('!') > 3:
                spam_score += 0.2  # Excessive exclamation
            
            if len(re.findall(r'[A-Z]', text)) / max(len(text), 1) > 0.5:
                spam_score += 0.3  # Too many caps
            
            # Check for repeated patterns
            words = text.split()
            if len(set(words)) < len(words) * 0.5 and len(words) > 5:
                spam_score += 0.4  # Too much repetition
            
            return min(spam_score, 1.0)
            
        except Exception as e:
            self.logger.error(f"Error in spam detection: {e}")
            return 0.0
    
    def _preprocess_text(self, text: str) -> str:
        """Preprocess text for analysis"""
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _calculate_readability(self, text: str) -> float:
        """Calculate readability score (simplified)"""
        try:
            words = text.split()
            sentences = text.count('.') + text.count('!') + text.count('?') + 1
            
            if len(words) == 0:
                return 0.0
            
            avg_words_per_sentence = len(words) / sentences
            avg_syllables = sum(self._count_syllables(word) for word in words) / len(words)
            
            # Simplified Flesch Reading Ease
            score = 206.835 - (1.015 * avg_words_per_sentence) - (84.6 * avg_syllables)
            return max(0, min(100, score))
            
        except Exception:
            return 50.0  # Default moderate readability
    
    def _count_syllables(self, word: str) -> int:
        """Count syllables in a word (approximation)"""
        word = word.lower()
        vowels = 'aeiouy'
        syllable_count = 0
        previous_was_vowel = False
        
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not previous_was_vowel:
                syllable_count += 1
            previous_was_vowel = is_vowel
        
        # Handle silent e
        if word.endswith('e'):
            syllable_count -= 1
        
        return max(1, syllable_count)
    
    def _calculate_relevance(self, text: str, context: Optional[Dict]) -> float:
        """Calculate relevance score based on context"""
        # Simplified relevance calculation
        # In production, this would use more sophisticated methods
        base_score = 70.0
        
        if not context:
            return base_score
        
        # Check if text mentions relevant keywords
        subreddit = context.get('subreddit', '').lower()
        if subreddit and subreddit in text.lower():
            base_score += 10.0
        
        # Check length appropriateness
        word_count = len(text.split())
        if 10 <= word_count <= 200:
            base_score += 10.0
        elif word_count < 5:
            base_score -= 20.0
        
        return min(100.0, base_score)
    
    def _detect_toxicity(self, text: str) -> float:
        """Detect toxicity in text (simplified)"""
        toxic_patterns = [
            r'\b(hate|stupid|idiot|moron|dumb)\b',
            r'\b(kill|die|death)\b',
            r'\b(fuck|shit|damn)\b',
        ]
        
        toxicity_score = 0.0
        for pattern in toxic_patterns:
            matches = len(re.findall(pattern, text, re.IGNORECASE))
            toxicity_score += matches * 0.2
        
        return min(1.0, toxicity_score)
    
    def _detect_language(self, text: str) -> str:
        """Detect language of text"""
        try:
            if detect:
                return detect(text)
        except (LangDetectError, Exception):
            pass
        return 'en'  # Default to English
    
    def _calculate_overall_score(self, sentiment: SentimentAnalysis, spam_prob: float, 
                                readability: float, relevance: float, toxicity: float) -> float:
        """Calculate overall quality score"""
        # Weight different factors
        sentiment_factor = (sentiment.compound + 1) * 50  # Convert -1,1 to 0,100
        spam_factor = (1 - spam_prob) * 100
        toxicity_factor = (1 - toxicity) * 100
        
        # Weighted average
        score = (
            sentiment_factor * 0.2 +
            spam_factor * 0.3 +
            readability * 0.2 +
            relevance * 0.2 +
            toxicity_factor * 0.1
        )
        
        return max(0, min(100, score))
    
    def _identify_issues(self, text: str, sentiment: SentimentAnalysis, 
                        spam_prob: float, toxicity: float) -> List[str]:
        """Identify issues with the comment"""
        issues = []
        
        if spam_prob > 0.7:
            issues.append("High spam probability detected")
        
        if toxicity > 0.5:
            issues.append("Potentially toxic content detected")
        
        if sentiment.negative > 0.8:
            issues.append("Very negative sentiment")
        
        if len(text.split()) < 3:
            issues.append("Comment too short")
        
        if len(text.split()) > 500:
            issues.append("Comment too long")
        
        return issues
    
    def _generate_recommendations(self, issues: List[str], sentiment: SentimentAnalysis) -> List[str]:
        """Generate recommendations for improvement"""
        recommendations = []
        
        if "High spam probability detected" in issues:
            recommendations.append("Remove promotional content and focus on genuine discussion")
        
        if "Potentially toxic content detected" in issues:
            recommendations.append("Use more respectful language")
        
        if "Very negative sentiment" in issues:
            recommendations.append("Consider a more balanced or constructive tone")
        
        if "Comment too short" in issues:
            recommendations.append("Provide more detailed thoughts or explanations")
        
        if "Comment too long" in issues:
            recommendations.append("Consider breaking into shorter, more focused points")
        
        if not recommendations:
            recommendations.append("Comment quality looks good!")
        
        return recommendations
    
    def _get_default_score(self, text: str) -> CommentQualityScore:
        """Return default score when NLP service is not available"""
        return CommentQualityScore(
            overall_score=50.0,
            sentiment_score=0.0,
            spam_probability=0.0,
            readability_score=50.0,
            relevance_score=50.0,
            toxicity_score=0.0,
            language='en',
            word_count=len(text.split()),
            issues=[],
            recommendations=["NLP service not available for detailed analysis"]
        )

# Global instance
nlp_service = NLPService()
