"""
FINAL WORDPRESS CSS FIX - This is the ONLY way WordPress preserves CSS
"""
import requests
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

def final_wordpress_duplication(wp_url, wp_username, wp_password, original_page_id, suffix="final"):
    """
    FINAL METHOD: Create perfect WordPress duplicate that preserves ALL CSS
    """
    try:
        logger.info(f"🚨 FINAL CSS FIX: Duplicating page {original_page_id}")
        
        # Get EVERYTHING from original page
        response = requests.get(
            f"{wp_url}/wp-json/wp/v2/pages/{original_page_id}?context=edit",
            auth=(wp_username, wp_password),
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"❌ Failed to get original page")
            return None
        
        original = response.json()
        logger.info(f"📄 Got original page with {len(original.get('meta', {}))} meta fields")
        
        # Create EXACT duplicate
        duplicate_data = {
            'title': f"{original['title']['raw']} - {suffix}",
            'content': original['content']['raw'],  # RAW content preserves everything!
            'excerpt': original.get('excerpt', {}).get('raw', ''),
            'status': 'publish',
            'template': original.get('template', ''),
            'featured_media': original.get('featured_media', 0),
            'parent': original.get('parent', 0),
            'menu_order': original.get('menu_order', 0),
            'comment_status': original.get('comment_status', 'closed'),
            'ping_status': original.get('ping_status', 'closed'),
            'meta': original.get('meta', {})  # ALL meta fields included!
        }
        
        logger.info(f"🚀 Creating duplicate with {len(duplicate_data.get('meta', {}))} meta fields...")
        
        # Create the duplicate
        create_response = requests.post(
            f"{wp_url}/wp-json/wp/v2/pages",
            json=duplicate_data,
            auth=(wp_username, wp_password),
            timeout=30
        )
        
        if create_response.status_code not in [200, 201]:
            logger.error(f"❌ Failed to create duplicate: {create_response.status_code}")
            return None
        
        new_page = create_response.json()
        logger.info(f"✅ FINAL SUCCESS: Created page {new_page['id']} - {new_page['title']['rendered']}")
        logger.info(f"🔗 URL: {new_page.get('link')}")
        
        return new_page
        
    except Exception as e:
        logger.error(f"❌ FINAL FIX FAILED: {e}")
        return None
