"""
Smart URL Management for Anti-Detection
Handles URL shortening, rotation, and obfuscation to bypass Discord link detection
"""
import random
import time
import hashlib
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pyshorteners
import requests
import validators
from sqlalchemy.orm import Session
from models import Base, ShortenedUrl

logger = logging.getLogger(__name__)

class SmartUrlManager:
    """Advanced URL management with anti-detection features"""
    
    def __init__(self):
        self.shorteners = {
            'tinyurl': pyshorteners.Shortener().tinyurl,
            'dagd': pyshorteners.Shortener().dagd,
            'osdb': pyshorteners.Shortener().osdb,
        }
        
        # Custom domain redirects (you can add your own domains)
        self.custom_domains = [
            "3ly.link",
            "short.link", 
            "tiny.one",
            "rb.gy"
        ]
        
        # Rotation patterns to avoid detection
        self.rotation_index = 0
        
    def shorten_url(self, original_url: str, service: str = None, db: Session = None) -> Dict[str, Any]:
        """
        Shorten a URL using various services with rotation
        """
        try:
            if not validators.url(original_url):
                raise ValueError(f"Invalid URL: {original_url}")
            
            # Auto-select service if not specified
            if not service:
                service = self._get_next_service()
            
            # Try to shorten the URL
            if service in self.shorteners:
                shortened = self.shorteners[service].short(original_url)
            else:
                # Fallback to tinyurl
                shortened = self.shorteners['tinyurl'].short(original_url)
                service = 'tinyurl'
            
            # Store in database if session provided
            if db:
                url_record = ShortenedUrl(
                    original_url=original_url,
                    shortened_url=shortened,
                    service=service,
                    expires_at=datetime.utcnow() + timedelta(days=30),
                    url_metadata={
                        'created_by': 'anti_detection_system',
                        'purpose': 'discord_promotion'
                    }
                )
                db.add(url_record)
                db.commit()
            
            return {
                'success': True,
                'original_url': original_url,
                'shortened_url': shortened,
                'service': service,
                'created_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to shorten URL {original_url}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'original_url': original_url
            }
    
    def _get_next_service(self) -> str:
        """Rotate through available services to avoid patterns"""
        services = list(self.shorteners.keys())
        service = services[self.rotation_index % len(services)]
        self.rotation_index += 1
        return service
    
    def create_redirect_chain(self, discord_url: str, db: Session = None) -> Dict[str, Any]:
        """
        Create a chain of redirects to further obfuscate the final destination
        """
        try:
            # First level: Shorten the Discord URL
            first_short = self.shorten_url(discord_url, db=db)
            if not first_short['success']:
                return first_short
            
            # Second level: Shorten the shortened URL (double obfuscation)
            second_short = self.shorten_url(
                first_short['shortened_url'], 
                service=self._get_next_service(),
                db=db
            )
            
            return {
                'success': True,
                'original_url': discord_url,
                'first_redirect': first_short['shortened_url'],
                'final_url': second_short['shortened_url'] if second_short['success'] else first_short['shortened_url'],
                'chain_length': 2 if second_short['success'] else 1
            }
            
        except Exception as e:
            logger.error(f"Failed to create redirect chain: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def generate_custom_redirect(self, discord_url: str) -> str:
        """
        Generate a custom redirect URL that looks innocent
        """
        # Create a hash-based identifier
        url_hash = hashlib.md5(discord_url.encode()).hexdigest()[:8]
        
        # Generate innocent-looking paths
        innocent_paths = [
            f"join/{url_hash}",
            f"invite/{url_hash}",
            f"group/{url_hash}",
            f"chat/{url_hash}",
            f"community/{url_hash}",
            f"members/{url_hash}"
        ]
        
        path = random.choice(innocent_paths)
        domain = random.choice(self.custom_domains)
        
        return f"https://{domain}/{path}"
    
    def obfuscate_discord_mention(self, text: str) -> str:
        """
        Replace Discord mentions with coded language
        """
        replacements = {
            'discord': ['private chat', 'group chat', 'community', 'exclusive group', 'VIP chat'],
            'Discord': ['Private Chat', 'Group Chat', 'Community', 'Exclusive Group', 'VIP Chat'],
            'discord.gg': ['private link', 'group link', 'community link', 'exclusive invite'],
            'join our discord': ['join our private group', 'join our community', 'join our exclusive chat'],
            'discord server': ['private server', 'community group', 'exclusive chat room'],
            'dm for discord': ['dm for invite', 'pm for group', 'message for access'],
        }
        
        result = text
        for original, alternatives in replacements.items():
            if original.lower() in result.lower():
                replacement = random.choice(alternatives)
                # Preserve original case pattern
                if original.isupper():
                    replacement = replacement.upper()
                elif original.istitle():
                    replacement = replacement.title()
                
                result = result.replace(original, replacement)
        
        return result
    
    def get_url_analytics(self, db: Session) -> Dict[str, Any]:
        """
        Get analytics for shortened URLs
        """
        try:
            urls = db.query(ShortenedUrl).filter(ShortenedUrl.is_active == True).all()
            
            analytics = {
                'total_urls': len(urls),
                'total_clicks': sum(url.clicks for url in urls),
                'services_used': {},
                'recent_urls': []
            }
            
            # Service breakdown
            for url in urls:
                service = url.service
                if service not in analytics['services_used']:
                    analytics['services_used'][service] = {'count': 0, 'clicks': 0}
                analytics['services_used'][service]['count'] += 1
                analytics['services_used'][service]['clicks'] += url.clicks
            
            # Recent URLs (last 10)
            recent = sorted(urls, key=lambda x: x.created_at, reverse=True)[:10]
            for url in recent:
                analytics['recent_urls'].append({
                    'shortened_url': url.shortened_url,
                    'clicks': url.clicks,
                    'service': url.service,
                    'created_at': url.created_at.isoformat()
                })
            
            return analytics
            
        except Exception as e:
            logger.error(f"Failed to get URL analytics: {str(e)}")
            return {'error': str(e)}

# Global instance
url_manager = SmartUrlManager()
