"""
Image-Based Promotion for Anti-Detection
Generates images with embedded QR codes and subtle promotional elements
"""
import qrcode
import random
import logging
import io
import base64
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os

logger = logging.getLogger(__name__)

class ImagePromotionGenerator:
    """Advanced image generation with embedded promotional content"""
    
    def __init__(self):
        # Color schemes for attractive images
        self.color_schemes = {
            'pink_gradient': {
                'primary': '#FF69B4',
                'secondary': '#FFB6C1',
                'accent': '#FFFFFF',
                'text': '#333333'
            },
            'purple_gradient': {
                'primary': '#9370DB',
                'secondary': '#DDA0DD',
                'accent': '#FFFFFF',
                'text': '#333333'
            },
            'blue_gradient': {
                'primary': '#4169E1',
                'secondary': '#87CEEB',
                'accent': '#FFFFFF',
                'text': '#333333'
            },
            'coral_gradient': {
                'primary': '#FF7F50',
                'secondary': '#FFA07A',
                'accent': '#FFFFFF',
                'text': '#333333'
            }
        }
        
        # Text overlays for Norwegian content
        self.norwegian_overlays = [
            "Norsk jente 🇳🇴",
            "Hei Norge! 💕",
            "Norsk dame ✨",
            "Søt norsk pike 🌸",
            "Norsk skjønnhet 💋",
            "Hei dere! 😘",
            "Norsk babe 🔥",
            "Cute Norwegian 💭"
        ]
        
        # QR code positioning options
        self.qr_positions = [
            'bottom_right',
            'bottom_left', 
            'top_right',
            'top_left',
            'center_bottom'
        ]
        
        # Image dimensions for different platforms
        self.dimensions = {
            'reddit_standard': (800, 600),
            'reddit_mobile': (600, 800),
            'square': (600, 600),
            'wide': (1200, 600)
        }
    
    def generate_promotional_image(self, discord_url: str, style: str = 'auto', 
                                 include_qr: bool = True, text_overlay: str = None) -> Dict[str, Any]:
        """
        Generate an attractive image with embedded Discord promotion
        """
        try:
            # Auto-select style if not specified
            if style == 'auto':
                style = random.choice(list(self.color_schemes.keys()))
            
            # Select dimensions
            dimensions = self.dimensions['reddit_standard']
            
            # Create base image
            image = self._create_base_image(dimensions, style)
            
            # Add QR code if requested
            if include_qr:
                qr_position = random.choice(self.qr_positions)
                image = self._add_qr_code(image, discord_url, qr_position, style)
            
            # Add text overlay
            if not text_overlay:
                text_overlay = random.choice(self.norwegian_overlays)
            
            image = self._add_text_overlay(image, text_overlay, style)
            
            # Add subtle promotional elements
            image = self._add_promotional_elements(image, style)
            
            # Convert to base64 for API response
            image_data = self._image_to_base64(image)
            
            return {
                'success': True,
                'image_data': image_data,
                'format': 'PNG',
                'dimensions': dimensions,
                'style': style,
                'qr_included': include_qr,
                'text_overlay': text_overlay,
                'discord_url': discord_url,
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to generate promotional image: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _create_base_image(self, dimensions: Tuple[int, int], style: str) -> Image.Image:
        """Create attractive base image with gradient background"""
        width, height = dimensions
        image = Image.new('RGB', dimensions, color='white')
        draw = ImageDraw.Draw(image)
        
        colors = self.color_schemes[style]
        
        # Create gradient background
        for y in range(height):
            # Calculate gradient ratio
            ratio = y / height
            
            # Interpolate between primary and secondary colors
            primary = self._hex_to_rgb(colors['primary'])
            secondary = self._hex_to_rgb(colors['secondary'])
            
            r = int(primary[0] * (1 - ratio) + secondary[0] * ratio)
            g = int(primary[1] * (1 - ratio) + secondary[1] * ratio)
            b = int(primary[2] * (1 - ratio) + secondary[2] * ratio)
            
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        
        # Add some texture/noise for more attractive look
        image = self._add_texture(image)
        
        return image
    
    def _add_qr_code(self, image: Image.Image, url: str, position: str, style: str) -> Image.Image:
        """Add QR code to image at specified position"""
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=4,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)
        
        # Create QR code image with transparent background
        qr_img = qr.make_image(fill_color='black', back_color='white')
        qr_size = 80  # Small, subtle size
        qr_img = qr_img.resize((qr_size, qr_size))
        
        # Calculate position
        img_width, img_height = image.size
        margin = 20
        
        if position == 'bottom_right':
            x = img_width - qr_size - margin
            y = img_height - qr_size - margin
        elif position == 'bottom_left':
            x = margin
            y = img_height - qr_size - margin
        elif position == 'top_right':
            x = img_width - qr_size - margin
            y = margin
        elif position == 'top_left':
            x = margin
            y = margin
        else:  # center_bottom
            x = (img_width - qr_size) // 2
            y = img_height - qr_size - margin
        
        # Add semi-transparent background for QR code
        overlay = Image.new('RGBA', image.size, (255, 255, 255, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        
        # White background with some transparency
        overlay_draw.rectangle(
            [x-5, y-5, x+qr_size+5, y+qr_size+5],
            fill=(255, 255, 255, 200)
        )
        
        # Paste QR code
        overlay.paste(qr_img, (x, y))
        
        # Composite with original image
        image = Image.alpha_composite(image.convert('RGBA'), overlay).convert('RGB')
        
        return image
    
    def _add_text_overlay(self, image: Image.Image, text: str, style: str) -> Image.Image:
        """Add attractive text overlay to image"""
        draw = ImageDraw.Draw(image)
        colors = self.color_schemes[style]
        
        # Try to load a nice font, fallback to default
        try:
            font_size = 36
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except:
            font = ImageFont.load_default()
        
        # Calculate text position (center top)
        img_width, img_height = image.size
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (img_width - text_width) // 2
        y = 50
        
        # Add text shadow for better readability
        shadow_offset = 2
        draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill='black')
        
        # Add main text
        draw.text((x, y), text, font=font, fill=colors['accent'])
        
        return image
    
    def _add_promotional_elements(self, image: Image.Image, style: str) -> Image.Image:
        """Add subtle promotional elements like decorative borders or patterns"""
        draw = ImageDraw.Draw(image)
        colors = self.color_schemes[style]
        
        # Add decorative border
        img_width, img_height = image.size
        border_width = 3
        
        # Top and bottom borders
        draw.rectangle([0, 0, img_width, border_width], fill=colors['accent'])
        draw.rectangle([0, img_height-border_width, img_width, img_height], fill=colors['accent'])
        
        # Add some decorative elements (hearts, stars, etc.)
        self._add_decorative_elements(image, style)
        
        return image
    
    def _add_decorative_elements(self, image: Image.Image, style: str) -> Image.Image:
        """Add small decorative elements like hearts or stars"""
        draw = ImageDraw.Draw(image)
        colors = self.color_schemes[style]
        img_width, img_height = image.size
        
        # Add small hearts in corners
        heart_size = 20
        heart_color = colors['accent']
        
        # Simple heart shape using circles and triangle
        positions = [
            (30, 30),  # top left
            (img_width - 50, 30),  # top right
            (30, img_height - 50),  # bottom left
        ]
        
        for x, y in positions:
            # Draw heart using two circles and a triangle
            draw.ellipse([x, y, x+heart_size//2, y+heart_size//2], fill=heart_color)
            draw.ellipse([x+heart_size//2, y, x+heart_size, y+heart_size//2], fill=heart_color)
            draw.polygon([
                (x+heart_size//4, y+heart_size//2),
                (x+3*heart_size//4, y+heart_size//2),
                (x+heart_size//2, y+heart_size)
            ], fill=heart_color)
        
        return image
    
    def _add_texture(self, image: Image.Image) -> Image.Image:
        """Add subtle texture to make image more attractive"""
        # Apply a very light blur for softer look
        image = image.filter(ImageFilter.GaussianBlur(radius=0.5))
        return image
    
    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string"""
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        return base64.b64encode(buffer.getvalue()).decode()
    
    def create_qr_only_image(self, discord_url: str, size: int = 200) -> Dict[str, Any]:
        """Create a standalone QR code image"""
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=4,
            )
            qr.add_data(discord_url)
            qr.make(fit=True)
            
            qr_img = qr.make_image(fill_color='black', back_color='white')
            qr_img = qr_img.resize((size, size))
            
            image_data = self._image_to_base64(qr_img)
            
            return {
                'success': True,
                'image_data': image_data,
                'format': 'PNG',
                'size': size,
                'type': 'qr_only',
                'discord_url': discord_url
            }
            
        except Exception as e:
            logger.error(f"Failed to create QR code: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_image_suggestions(self, content_type: str = 'norwegian_nsfw') -> List[Dict[str, Any]]:
        """Get suggestions for image content based on type"""
        if content_type == 'norwegian_nsfw':
            return [
                {
                    'style': 'pink_gradient',
                    'text': 'Norsk jente 🇳🇴',
                    'description': 'Pink gradient with Norwegian text'
                },
                {
                    'style': 'purple_gradient', 
                    'text': 'Hei Norge! 💕',
                    'description': 'Purple gradient with greeting'
                },
                {
                    'style': 'blue_gradient',
                    'text': 'Søt norsk pike 🌸',
                    'description': 'Blue gradient with cute text'
                }
            ]
        
        return []

# Global instance
image_generator = ImagePromotionGenerator()
