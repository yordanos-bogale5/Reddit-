"""
Anti-Detection API endpoints for Discord promotion
Provides comprehensive anti-detection features for bypassing subreddit rules
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import logging

from database import get_db
from anti_detection.url_manager import url_manager
from anti_detection.content_variation import content_engine
from anti_detection.rule_compliance import compliance_checker
from anti_detection.image_promotion import image_generator
from anti_detection.stealth_strategies import stealth_strategies

router = APIRouter()
logger = logging.getLogger(__name__)

# Pydantic models for API requests
class UrlShortenRequest(BaseModel):
    url: str
    service: Optional[str] = None
    create_redirect_chain: bool = False

class ContentGenerationRequest(BaseModel):
    discord_url: Optional[str] = None
    strategy: Optional[str] = None
    num_variations: int = 1

class ComplianceCheckRequest(BaseModel):
    title: str
    body: Optional[str] = ""
    url: Optional[str] = ""
    has_image: bool = False
    subreddit: str = "norwaygonewildddddddd"

class ImageGenerationRequest(BaseModel):
    discord_url: str
    style: str = "auto"
    include_qr: bool = True
    text_overlay: Optional[str] = None

class StealthCampaignRequest(BaseModel):
    discord_url: str
    target_subreddit: str
    strategy: str = "auto"

class AntiDetectionResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

@router.post("/shorten-url", response_model=AntiDetectionResponse)
async def shorten_url(request: UrlShortenRequest, db: Session = Depends(get_db)):
    """
    Shorten a Discord URL with anti-detection features
    """
    try:
        if request.create_redirect_chain:
            result = url_manager.create_redirect_chain(request.url, db)
        else:
            result = url_manager.shorten_url(request.url, request.service, db)
        
        if result['success']:
            return AntiDetectionResponse(
                success=True,
                message="URL shortened successfully",
                data=result
            )
        else:
            return AntiDetectionResponse(
                success=False,
                message="Failed to shorten URL",
                error=result.get('error')
            )
            
    except Exception as e:
        logger.error(f"URL shortening failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-content", response_model=AntiDetectionResponse)
async def generate_content(request: ContentGenerationRequest):
    """
    Generate compliant Norwegian NSFW content with hidden Discord promotion
    """
    try:
        if request.num_variations == 1:
            result = content_engine.generate_norwegian_post(
                discord_url=request.discord_url,
                strategy=request.strategy
            )
            data = result
        else:
            base_content = content_engine.generate_norwegian_post()
            variations = content_engine.create_content_variations(
                base_content, 
                request.num_variations
            )
            data = {
                'base_content': base_content,
                'variations': variations,
                'total_variations': len(variations)
            }
        
        return AntiDetectionResponse(
            success=True,
            message=f"Generated {request.num_variations} content variation(s)",
            data=data
        )
        
    except Exception as e:
        logger.error(f"Content generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/check-compliance", response_model=AntiDetectionResponse)
async def check_compliance(request: ComplianceCheckRequest):
    """
    Check content compliance with subreddit rules
    """
    try:
        result = compliance_checker.check_compliance(
            title=request.title,
            body=request.body,
            url=request.url,
            has_image=request.has_image,
            subreddit=request.subreddit
        )
        
        # Add fix suggestions if there are violations
        if not result['is_compliant']:
            fixes = compliance_checker.suggest_fixes(result)
            result['suggested_fixes'] = fixes
        
        return AntiDetectionResponse(
            success=True,
            message=f"Compliance check completed. Score: {result['compliance_score']}/100",
            data=result
        )
        
    except Exception as e:
        logger.error(f"Compliance check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-image", response_model=AntiDetectionResponse)
async def generate_promotional_image(request: ImageGenerationRequest):
    """
    Generate attractive image with embedded QR code for Discord promotion
    """
    try:
        result = image_generator.generate_promotional_image(
            discord_url=request.discord_url,
            style=request.style,
            include_qr=request.include_qr,
            text_overlay=request.text_overlay
        )
        
        if result['success']:
            return AntiDetectionResponse(
                success=True,
                message="Promotional image generated successfully",
                data=result
            )
        else:
            return AntiDetectionResponse(
                success=False,
                message="Failed to generate image",
                error=result.get('error')
            )
            
    except Exception as e:
        logger.error(f"Image generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/plan-stealth-campaign", response_model=AntiDetectionResponse)
async def plan_stealth_campaign(request: StealthCampaignRequest):
    """
    Plan a comprehensive stealth posting campaign
    """
    try:
        result = stealth_strategies.plan_stealth_campaign(
            discord_url=request.discord_url,
            target_subreddit=request.target_subreddit,
            strategy=request.strategy
        )
        
        if result['success']:
            return AntiDetectionResponse(
                success=True,
                message=f"Stealth campaign planned with {result['strategy']} strategy",
                data=result
            )
        else:
            return AntiDetectionResponse(
                success=False,
                message="Failed to plan stealth campaign",
                error=result.get('error')
            )
            
    except Exception as e:
        logger.error(f"Stealth campaign planning failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/obfuscate-text")
async def obfuscate_text(text: str):
    """
    Obfuscate text to replace Discord mentions with safe alternatives
    """
    try:
        obfuscated = url_manager.obfuscate_discord_mention(text)
        
        return AntiDetectionResponse(
            success=True,
            message="Text obfuscated successfully",
            data={
                'original_text': text,
                'obfuscated_text': obfuscated,
                'changes_made': text != obfuscated
            }
        )
        
    except Exception as e:
        logger.error(f"Text obfuscation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/safe-alternatives")
async def get_safe_alternatives(banned_term: str):
    """
    Get safe alternatives for banned terms
    """
    try:
        alternatives = compliance_checker.get_safe_alternatives(banned_term)
        
        return AntiDetectionResponse(
            success=True,
            message=f"Found {len(alternatives)} safe alternatives",
            data={
                'banned_term': banned_term,
                'safe_alternatives': alternatives
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get safe alternatives: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/url-analytics")
async def get_url_analytics(db: Session = Depends(get_db)):
    """
    Get analytics for shortened URLs
    """
    try:
        analytics = url_manager.get_url_analytics(db)
        
        return AntiDetectionResponse(
            success=True,
            message="URL analytics retrieved successfully",
            data=analytics
        )
        
    except Exception as e:
        logger.error(f"Failed to get URL analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/image-suggestions")
async def get_image_suggestions(content_type: str = "norwegian_nsfw"):
    """
    Get suggestions for image content
    """
    try:
        suggestions = image_generator.get_image_suggestions(content_type)
        
        return AntiDetectionResponse(
            success=True,
            message=f"Found {len(suggestions)} image suggestions",
            data={
                'content_type': content_type,
                'suggestions': suggestions
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get image suggestions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/optimal-posting-time")
async def get_optimal_posting_time():
    """
    Get optimal posting times for Norwegian audience
    """
    try:
        timing = content_engine.get_optimal_posting_time()
        
        return AntiDetectionResponse(
            success=True,
            message="Optimal posting time calculated",
            data=timing
        )
        
    except Exception as e:
        logger.error(f"Failed to get optimal posting time: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create-qr-code")
async def create_qr_code(discord_url: str, size: int = 200):
    """
    Create a standalone QR code for Discord URL
    """
    try:
        result = image_generator.create_qr_only_image(discord_url, size)
        
        if result['success']:
            return AntiDetectionResponse(
                success=True,
                message="QR code created successfully",
                data=result
            )
        else:
            return AntiDetectionResponse(
                success=False,
                message="Failed to create QR code",
                error=result.get('error')
            )
            
    except Exception as e:
        logger.error(f"QR code creation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
