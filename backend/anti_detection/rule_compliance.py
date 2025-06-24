"""
Rule Compliance Checker for Anti-Detection
Automatically scans content to ensure compliance with subreddit rules
"""
import re
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from langdetect import detect
import validators

logger = logging.getLogger(__name__)

class RuleComplianceChecker:
    """Advanced rule compliance checking system"""
    
    def __init__(self):
        # Norwegian NSFW subreddit rules (r/norwaygonewildddddddd)
        self.norwegian_nsfw_rules = {
            'no_leaks': {
                'description': 'No leaks',
                'banned_terms': ['leak', 'leaked', 'leaks', 'onlyfans leak', 'of leak'],
                'severity': 'high'
            },
            'no_fake_profile': {
                'description': 'No fake profiles',
                'indicators': ['stock photo', 'fake', 'catfish', 'not real'],
                'severity': 'high'
            },
            'no_buying_selling': {
                'description': 'No buying and selling',
                'banned_terms': [
                    'buy', 'sell', 'selling', 'purchase', 'payment', 'pay', 'money', 
                    'price', 'cost', 'fee', 'subscription', 'premium', 'vip access',
                    'paid', 'cash', 'venmo', 'paypal', 'bitcoin', 'crypto'
                ],
                'severity': 'high'
            },
            'language_requirement': {
                'description': 'Must be Norwegian, Swedish or Danish',
                'required_languages': ['no', 'sv', 'da'],  # ISO codes
                'severity': 'medium'
            },
            'no_dating': {
                'description': 'Not a dating site',
                'banned_terms': [
                    'date', 'dating', 'boyfriend', 'girlfriend', 'relationship',
                    'meet up', 'hookup', 'tinder', 'bumble', 'meet me'
                ],
                'severity': 'medium'
            },
            'no_external_sites': {
                'description': 'Do not mention other sites or apps',
                'banned_terms': [
                    'onlyfans', 'of', 'fansly', 'discord', 'telegram', 'snapchat',
                    'instagram', 'twitter', 'tiktok', 'youtube', 'twitch',
                    'kik', 'whatsapp', 'skype', 'zoom'
                ],
                'banned_domains': [
                    'onlyfans.com', 'fansly.com', 'discord.gg', 'discord.com',
                    't.me', 'telegram.me', 'snapchat.com', 'instagram.com'
                ],
                'severity': 'high'
            },
            'picture_required': {
                'description': 'Include a picture in the post',
                'requirement': 'image_attachment',
                'severity': 'medium'
            },
            'be_creative': {
                'description': 'Be creative',
                'banned_terms': [
                    'upvote if', 'like if', 'comment if', 'dm if you like',
                    'boring title', 'simple post', 'nothing special'
                ],
                'severity': 'low'
            },
            'no_crossposting': {
                'description': 'Do not share from other subreddits',
                'indicators': [
                    'crosspost', 'x-post', 'also posted', 'shared from',
                    'posted in', 'from r/', 'cross posted'
                ],
                'severity': 'medium'
            },
            'no_like_posts': {
                'description': 'Do not participate in like or thumbs up posts',
                'banned_terms': [
                    'like if', 'upvote if', 'thumbs up if', 'vote if',
                    'like this post', 'upvote this', 'give thumbs up'
                ],
                'severity': 'medium'
            }
        }
        
        # Common evasion patterns to detect
        self.evasion_patterns = [
            r'd[i1!]sc[o0]rd',  # discord with character substitution
            r'[o0]nlyf[a@]ns',  # onlyfans variations
            r'tele[g9]ram',     # telegram variations
            r'wh[a@]ts[a@]pp',  # whatsapp variations
        ]
    
    def check_compliance(self, title: str, body: str = "", url: str = "", 
                        has_image: bool = False, subreddit: str = "norwaygonewildddddddd") -> Dict[str, Any]:
        """
        Comprehensive compliance check for content
        """
        try:
            violations = []
            warnings = []
            suggestions = []
            
            content = f"{title} {body}".strip()
            content_lower = content.lower()
            
            # Check each rule
            for rule_name, rule_config in self.norwegian_nsfw_rules.items():
                violation = self._check_rule(rule_name, rule_config, content, content_lower, url, has_image)
                if violation:
                    if violation['severity'] == 'high':
                        violations.append(violation)
                    elif violation['severity'] == 'medium':
                        warnings.append(violation)
                    else:
                        suggestions.append(violation)
            
            # Check for evasion attempts
            evasion_detected = self._detect_evasion_attempts(content_lower)
            if evasion_detected:
                violations.extend(evasion_detected)
            
            # Language detection
            language_check = self._check_language(content)
            if not language_check['compliant']:
                warnings.append(language_check)
            
            # Calculate overall compliance score
            compliance_score = self._calculate_compliance_score(violations, warnings, suggestions)
            
            return {
                'is_compliant': len(violations) == 0,
                'compliance_score': compliance_score,
                'violations': violations,
                'warnings': warnings,
                'suggestions': suggestions,
                'language_detected': language_check.get('detected_language'),
                'checked_at': datetime.utcnow().isoformat(),
                'subreddit': subreddit
            }
            
        except Exception as e:
            logger.error(f"Compliance check failed: {str(e)}")
            return {
                'error': str(e),
                'is_compliant': False,
                'compliance_score': 0
            }
    
    def _check_rule(self, rule_name: str, rule_config: Dict, content: str, 
                   content_lower: str, url: str, has_image: bool) -> Optional[Dict[str, Any]]:
        """Check a specific rule against content"""
        
        if rule_name == 'no_leaks':
            return self._check_banned_terms(rule_config, content_lower, rule_name)
        
        elif rule_name == 'no_fake_profile':
            return self._check_banned_terms(rule_config, content_lower, rule_name, 'indicators')
        
        elif rule_name == 'no_buying_selling':
            return self._check_banned_terms(rule_config, content_lower, rule_name)
        
        elif rule_name == 'no_dating':
            return self._check_banned_terms(rule_config, content_lower, rule_name)
        
        elif rule_name == 'no_external_sites':
            # Check banned terms
            term_violation = self._check_banned_terms(rule_config, content_lower, rule_name)
            if term_violation:
                return term_violation
            
            # Check URLs
            if url:
                for domain in rule_config.get('banned_domains', []):
                    if domain in url.lower():
                        return {
                            'rule': rule_name,
                            'description': rule_config['description'],
                            'violation': f"URL contains banned domain: {domain}",
                            'severity': rule_config['severity']
                        }
        
        elif rule_name == 'picture_required':
            if not has_image:
                return {
                    'rule': rule_name,
                    'description': rule_config['description'],
                    'violation': "Post must include a picture",
                    'severity': rule_config['severity']
                }
        
        elif rule_name == 'be_creative':
            return self._check_banned_terms(rule_config, content_lower, rule_name)
        
        elif rule_name == 'no_crossposting':
            return self._check_banned_terms(rule_config, content_lower, rule_name, 'indicators')
        
        elif rule_name == 'no_like_posts':
            return self._check_banned_terms(rule_config, content_lower, rule_name)
        
        return None
    
    def _check_banned_terms(self, rule_config: Dict, content_lower: str, 
                           rule_name: str, terms_key: str = 'banned_terms') -> Optional[Dict[str, Any]]:
        """Check for banned terms in content"""
        terms = rule_config.get(terms_key, [])
        
        for term in terms:
            if term.lower() in content_lower:
                return {
                    'rule': rule_name,
                    'description': rule_config['description'],
                    'violation': f"Contains banned term: '{term}'",
                    'severity': rule_config['severity'],
                    'found_term': term
                }
        
        return None
    
    def _detect_evasion_attempts(self, content_lower: str) -> List[Dict[str, Any]]:
        """Detect attempts to evade filters using character substitution"""
        violations = []
        
        for pattern in self.evasion_patterns:
            matches = re.findall(pattern, content_lower)
            if matches:
                violations.append({
                    'rule': 'evasion_attempt',
                    'description': 'Detected attempt to evade filters',
                    'violation': f"Suspicious pattern detected: {matches[0]}",
                    'severity': 'high',
                    'pattern': pattern
                })
        
        return violations
    
    def _check_language(self, content: str) -> Dict[str, Any]:
        """Check if content is in Norwegian, Swedish, or Danish"""
        try:
            if len(content.strip()) < 10:
                return {
                    'compliant': True,
                    'reason': 'Content too short for language detection'
                }
            
            detected_lang = detect(content)
            required_languages = ['no', 'sv', 'da']
            
            return {
                'compliant': detected_lang in required_languages,
                'detected_language': detected_lang,
                'required_languages': required_languages,
                'rule': 'language_requirement',
                'description': 'Must be Norwegian, Swedish or Danish',
                'violation': f"Content appears to be in '{detected_lang}', not Norwegian/Swedish/Danish" if detected_lang not in required_languages else None,
                'severity': 'medium'
            }
            
        except Exception as e:
            logger.warning(f"Language detection failed: {str(e)}")
            return {
                'compliant': True,
                'reason': 'Language detection failed, assuming compliant'
            }
    
    def _calculate_compliance_score(self, violations: List, warnings: List, suggestions: List) -> float:
        """Calculate overall compliance score (0-100)"""
        base_score = 100
        
        # Deduct points for violations
        for violation in violations:
            if violation.get('severity') == 'high':
                base_score -= 25
            elif violation.get('severity') == 'medium':
                base_score -= 15
            else:
                base_score -= 5
        
        # Deduct points for warnings
        for warning in warnings:
            if warning.get('severity') == 'medium':
                base_score -= 10
            else:
                base_score -= 5
        
        # Minor deduction for suggestions
        base_score -= len(suggestions) * 2
        
        return max(0, base_score)
    
    def suggest_fixes(self, compliance_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Suggest fixes for compliance issues"""
        fixes = []
        
        for violation in compliance_result.get('violations', []):
            if violation['rule'] == 'no_external_sites':
                fixes.append({
                    'issue': violation['violation'],
                    'fix': f"Replace '{violation.get('found_term', '')}' with 'private group' or 'community'",
                    'priority': 'high'
                })
            
            elif violation['rule'] == 'no_buying_selling':
                fixes.append({
                    'issue': violation['violation'],
                    'fix': f"Remove '{violation.get('found_term', '')}' and any payment references",
                    'priority': 'high'
                })
            
            elif violation['rule'] == 'picture_required':
                fixes.append({
                    'issue': violation['violation'],
                    'fix': "Add an attractive image to your post",
                    'priority': 'medium'
                })
        
        return fixes
    
    def get_safe_alternatives(self, banned_term: str) -> List[str]:
        """Get safe alternatives for banned terms"""
        alternatives = {
            'discord': ['private group', 'community', 'chat group', 'exclusive group'],
            'onlyfans': ['private content', 'exclusive content', 'premium content'],
            'buy': ['access', 'join', 'get'],
            'sell': ['share', 'offer', 'provide'],
            'money': ['support', 'contribution'],
            'payment': ['access fee', 'membership'],
            'date': ['meet', 'chat', 'talk'],
            'dating': ['socializing', 'chatting', 'meeting people']
        }
        
        return alternatives.get(banned_term.lower(), ['private alternative'])

# Global instance
compliance_checker = RuleComplianceChecker()
