"""
Content Variation Engine for Anti-Detection
Creates dynamic content templates and variations to avoid detection patterns
"""
import random
import re
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)

class ContentVariationEngine:
    """Advanced content variation system to avoid detection patterns"""
    
    def __init__(self):
        # Norwegian NSFW content templates (compliant with subreddit rules)
        self.norwegian_templates = {
            'titles': [
                "Norsk jente søker selsskap 🇳🇴",
                "Kjedelig kveld, noen som vil chatte? 💬",
                "Norsk dame her, hvem vil snakke? 🌸",
                "Søker norske venner til hyggelig prat ✨",
                "Norsk pike som vil møte nye folk 🌺",
                "Hei Norge! Noen som vil bli kjent? 🇳🇴",
                "Norsk jente søker interessante samtaler 💭",
                "Kjedelig dag, trenger noen å snakke med 😊",
                "Norsk dame som vil utvide vennekretsen 🌟",
                "Hei dere! Norsk jente her 👋"
            ],
            'bodies': [
                "Hei alle sammen! Jeg er en {age} år gammel norsk jente som søker hyggelige folk å snakke med. Liker {interests}. Send meg en melding hvis du vil bli kjent! 😊",
                "Hei Norge! {age} år gammel dame her som leter etter interessante samtaler. Jeg er interessert i {interests}. Skriv til meg! 💕",
                "Norsk jente på {age} år søker nye venner. Liker {interests} og hyggelige samtaler. Ta kontakt! 🌸",
                "Hei! Jeg er {age} år og kommer fra Norge. Interessert i {interests}. Hvem vil chatte? 😘",
                "Norsk dame her! {age} år gammel og leter etter folk å snakke med. Liker {interests}. Send melding! ✨"
            ],
            'interests': [
                "musikk og film", "reising og mat", "trening og yoga", "bøker og serier", 
                "kunst og kultur", "natur og friluftsliv", "gaming og teknologi", 
                "matlaging og baking", "fotografering", "dans og musikk"
            ],
            'ages': ["20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30"]
        }
        
        # Innocent call-to-action phrases
        self.cta_variations = [
            "Send meg en melding!",
            "Ta kontakt!",
            "Skriv til meg!",
            "Send DM!",
            "Meld deg!",
            "Kontakt meg!",
            "Skriv gjerne!",
            "Send beskjed!",
            "Ta kontakt da!",
            "Skriv til meg da!"
        ]
        
        # Link placement strategies
        self.link_strategies = [
            "comment_only",      # Link only in comments
            "bio_redirect",      # "Link in bio" approach
            "image_embedded",    # QR code in image
            "coded_message",     # Coded instructions
            "delayed_comment"    # Comment with link after some time
        ]
        
        # Emoji variations for Norwegian content
        self.norwegian_emojis = [
            "🇳🇴", "🌸", "💕", "✨", "😊", "💭", "🌺", "🌟", "😘", "💬", "👋", "🔥", "💋", "😍"
        ]
    
    def generate_norwegian_post(self, discord_url: str = None, strategy: str = None) -> Dict[str, Any]:
        """
        Generate a compliant Norwegian NSFW post with hidden Discord promotion
        """
        try:
            # Select random elements
            title_template = random.choice(self.norwegian_templates['titles'])
            body_template = random.choice(self.norwegian_templates['bodies'])
            age = random.choice(self.norwegian_templates['ages'])
            interests = random.choice(self.norwegian_templates['interests'])
            cta = random.choice(self.cta_variations)
            
            # Add random emojis
            emoji = random.choice(self.norwegian_emojis)
            if emoji not in title_template:
                title_template += f" {emoji}"
            
            # Generate content
            title = title_template
            body = body_template.format(age=age, interests=interests)
            body += f" {cta}"
            
            # Select promotion strategy
            if not strategy:
                strategy = random.choice(self.link_strategies)
            
            result = {
                'title': title,
                'body': body,
                'strategy': strategy,
                'metadata': {
                    'age': age,
                    'interests': interests,
                    'emoji_used': emoji,
                    'generated_at': datetime.utcnow().isoformat()
                }
            }
            
            # Apply promotion strategy
            if discord_url:
                result.update(self._apply_promotion_strategy(result, discord_url, strategy))
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to generate Norwegian post: {str(e)}")
            return {'error': str(e)}
    
    def _apply_promotion_strategy(self, post_data: Dict, discord_url: str, strategy: str) -> Dict[str, Any]:
        """Apply specific promotion strategy to the post"""
        
        if strategy == "comment_only":
            # Keep post clean, add promotion instructions for comments
            return {
                **post_data,
                'comment_instructions': {
                    'delay_minutes': random.randint(5, 15),
                    'comment_text': self._generate_comment_with_link(discord_url),
                    'strategy': 'comment_only'
                }
            }
        
        elif strategy == "bio_redirect":
            # Add "link in bio" to post
            post_data['body'] += " Link i bio for mer! 😉"
            return {
                **post_data,
                'bio_update_required': True,
                'bio_link': discord_url
            }
        
        elif strategy == "image_embedded":
            # Instructions for QR code in image
            return {
                **post_data,
                'image_required': True,
                'qr_code_url': discord_url,
                'image_instructions': 'Generate attractive image with QR code in corner'
            }
        
        elif strategy == "coded_message":
            # Add coded message to body
            coded_msg = self._generate_coded_message()
            post_data['body'] += f" {coded_msg}"
            return {
                **post_data,
                'coded_instructions': {
                    'meaning': 'DM for Discord invite',
                    'discord_url': discord_url
                }
            }
        
        elif strategy == "delayed_comment":
            # Similar to comment_only but with longer delay
            return {
                **post_data,
                'comment_instructions': {
                    'delay_minutes': random.randint(30, 60),
                    'comment_text': self._generate_delayed_comment(discord_url),
                    'strategy': 'delayed_comment'
                }
            }
        
        return post_data
    
    def _generate_comment_with_link(self, discord_url: str) -> str:
        """Generate innocent comment with Discord link"""
        comment_templates = [
            "Hei! For de som vil chatte mer privat: {link} 😊",
            "Opprettet en liten gruppe for oss som vil snakke mer: {link}",
            "For de interesserte, her er linken til vår private chat: {link}",
            "Bli med i vår hyggelige gruppe: {link} 💕",
            "Link til vår private community: {link} ✨"
        ]
        
        template = random.choice(comment_templates)
        return template.format(link=discord_url)
    
    def _generate_delayed_comment(self, discord_url: str) -> str:
        """Generate delayed comment with link"""
        delayed_templates = [
            "Takk for alle de hyggelige meldingene! Opprettet en gruppe for oss: {link}",
            "Siden så mange spurte, her er linken til vår private chat: {link}",
            "Mange ville chatte mer, så opprettet dette: {link} 😊",
            "For dere som vil fortsette samtalen: {link} 💬"
        ]
        
        template = random.choice(delayed_templates)
        return template.format(link=discord_url)
    
    def _generate_coded_message(self) -> str:
        """Generate coded message that hints at DM for invite"""
        coded_messages = [
            "DM for spesiell invitasjon 😉",
            "Send melding for eksklusiv tilgang ✨",
            "PM for VIP-gruppe 💕",
            "Meld deg for privat chat 🌸",
            "DM for mer info 😘"
        ]
        
        return random.choice(coded_messages)
    
    def create_content_variations(self, base_content: Dict, num_variations: int = 5) -> List[Dict[str, Any]]:
        """Create multiple variations of the same content"""
        variations = []
        
        for i in range(num_variations):
            variation = self.generate_norwegian_post()
            variation['variation_id'] = i + 1
            variation['base_content_hash'] = hashlib.md5(str(base_content).encode()).hexdigest()[:8]
            variations.append(variation)
        
        return variations
    
    def analyze_content_safety(self, title: str, body: str) -> Dict[str, Any]:
        """Analyze content for rule compliance"""
        issues = []
        
        # Check for banned words/phrases
        banned_terms = [
            'discord', 'onlyfans', 'of', 'fansly', 'telegram', 'snapchat',
            'buy', 'sell', 'payment', 'price', 'cost', 'money'
        ]
        
        content_lower = (title + " " + body).lower()
        
        for term in banned_terms:
            if term in content_lower:
                issues.append(f"Contains banned term: '{term}'")
        
        # Check for dating language
        dating_terms = ['date', 'dating', 'boyfriend', 'relationship', 'meet up']
        for term in dating_terms:
            if term in content_lower:
                issues.append(f"Contains dating language: '{term}'")
        
        # Check for cross-posting indicators
        crosspost_terms = ['crosspost', 'x-post', 'also posted', 'shared from']
        for term in crosspost_terms:
            if term in content_lower:
                issues.append(f"Indicates cross-posting: '{term}'")
        
        return {
            'is_safe': len(issues) == 0,
            'issues': issues,
            'risk_level': 'low' if len(issues) == 0 else 'medium' if len(issues) <= 2 else 'high'
        }
    
    def get_optimal_posting_time(self) -> Dict[str, Any]:
        """Get optimal posting times for Norwegian audience"""
        # Norwegian timezone considerations
        optimal_hours = [19, 20, 21, 22, 23]  # Evening hours
        optimal_days = ['friday', 'saturday', 'sunday']  # Weekends
        
        return {
            'optimal_hours': optimal_hours,
            'optimal_days': optimal_days,
            'timezone': 'Europe/Oslo',
            'reasoning': 'Evening hours and weekends have higher engagement in Norwegian NSFW communities'
        }

# Global instance
content_engine = ContentVariationEngine()
