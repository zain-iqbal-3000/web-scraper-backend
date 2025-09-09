"""
Simple WordPress integration with direct text replacement to preserve CSS.
This approach doesn't parse HTML at all to avoid breaking styling.
"""
import requests
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import re

logger = logging.getLogger(__name__)

@dataclass
class ContentChange:
    element_id: str
    original_text: str
    modified_text: str
    element_type: str = 'text'

@dataclass
class WordPressConfig:
    site_url: str
    username: str
    password: str
    
    @property
    def api_url(self) -> str:
        return f"{self.site_url.rstrip('/')}/wp-json/wp/v2"

class SimpleWordPressIntegration:
    def __init__(self, config: WordPressConfig):
        self.config = config
        self.session = requests.Session()
        self.session.auth = (config.username, config.password)
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'LP-Optimizer/1.0'
        })

    def apply_content_changes_simple(self, page_content: str, changes: List[ContentChange]) -> str:
        """
        Apply content changes using intelligent text replacement that preserves CSS.
        Only replaces text content between HTML tags, never inside tag attributes.
        """
        modified_content = page_content
        changes_applied = 0
        
        for change in changes:
            try:
                original_text = change.original_text.strip()
                modified_text = change.modified_text.strip()
                
                # Skip empty changes
                if not original_text or not modified_text:
                    continue
                
                logger.info(f"🔍 Looking for text: '{original_text[:50]}...'")
                
                # Use regex to find text that's NOT inside HTML tags or attributes
                # This pattern matches text content between > and < (i.e., text content of HTML elements)
                import re
                
                # Pattern to find text content between tags that matches our original text
                # (?<=>)[^<]*?ORIGINAL_TEXT[^<]*?(?=<) - finds text between > and < containing our text
                escaped_original = re.escape(original_text)
                
                # Strategy 1: Find exact text content between HTML tags
                pattern1 = rf'(?<=>)([^<]*?){escaped_original}([^<]*?)(?=<)'
                match1 = re.search(pattern1, modified_content, re.IGNORECASE)
                
                if match1:
                    # Replace only the text part, keeping any surrounding text in the same element
                    before_text = match1.group(1)
                    after_text = match1.group(2)
                    
                    # Create the replacement preserving any text before/after
                    replacement_pattern = rf'(?<=>){re.escape(before_text)}{escaped_original}{re.escape(after_text)}(?=<)'
                    new_content = before_text + modified_text + after_text
                    
                    modified_content = re.sub(replacement_pattern, new_content, modified_content, count=1, flags=re.IGNORECASE)
                    changes_applied += 1
                    logger.info(f"✅ Smart tag content replacement: '{original_text[:50]}...' -> '{modified_text[:50]}...'")
                    continue
                
                # Strategy 2: Find text at the start of tag content
                pattern2 = rf'(?<=>)\s*{escaped_original}'
                match2 = re.search(pattern2, modified_content, re.IGNORECASE)
                
                if match2:
                    modified_content = re.sub(pattern2, f'{match2.group().split(original_text)[0]}{modified_text}', modified_content, count=1, flags=re.IGNORECASE)
                    changes_applied += 1
                    logger.info(f"✅ Start of tag replacement: '{original_text[:50]}...' -> '{modified_text[:50]}...'")
                    continue
                
                # Strategy 3: Find text at the end of tag content
                pattern3 = rf'{escaped_original}\s*(?=<)'
                match3 = re.search(pattern3, modified_content, re.IGNORECASE)
                
                if match3:
                    modified_content = re.sub(pattern3, f'{modified_text}{match3.group().split(original_text)[1]}', modified_content, count=1, flags=re.IGNORECASE)
                    changes_applied += 1
                    logger.info(f"✅ End of tag replacement: '{original_text[:50]}...' -> '{modified_text[:50]}...'")
                    continue
                
                # Strategy 4: Fallback - simple replacement but log warning
                if original_text in modified_content:
                    # Check if the text is inside an HTML attribute (dangerous)
                    text_pos = modified_content.lower().find(original_text.lower())
                    # Look backward to see if we're inside a tag
                    last_open = modified_content.rfind('<', 0, text_pos)
                    last_close = modified_content.rfind('>', 0, text_pos)
                    
                    if last_open > last_close:
                        logger.warning(f"⚠️ Text found inside HTML tag - skipping to preserve CSS: '{original_text[:50]}...'")
                        continue
                    
                    modified_content = modified_content.replace(original_text, modified_text, 1)
                    changes_applied += 1
                    logger.info(f"✅ Fallback replacement: '{original_text[:50]}...' -> '{modified_text[:50]}...'")
                    continue
                
                logger.warning(f"❌ Could not safely replace text: '{original_text[:50]}...'")
                
            except Exception as e:
                logger.warning(f"❌ Failed to apply change for element {change.element_id}: {e}")
                continue
        
        logger.info(f"📊 Applied {changes_applied} out of {len(changes)} content changes")
        return modified_content

    def find_page_by_url(self, page_url: str) -> Optional[Dict]:
        """Find WordPress page by URL."""
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(page_url)
            slug = parsed_url.path.strip('/').split('/')[-1]
            
            response = self.session.get(
                f"{self.config.api_url}/pages",
                params={'slug': slug, 'status': 'publish'}
            )
            response.raise_for_status()
            
            pages = response.json()
            if pages:
                logger.info(f"Found page with slug '{slug}': {pages[0]['title']['rendered']}")
                return pages[0]
            
            return None
            
        except requests.RequestException as e:
            logger.error(f"Error finding page: {e}")
            return None

    def duplicate_page(self, original_page: Dict, suffix: str = None) -> Optional[Dict]:
        """Create a duplicate of a WordPress page with enhanced meta copying."""
        try:
            if suffix is None:
                suffix = f"ab-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            
            original_page_id = original_page['id']
            
            # Fetch original page with edit context to get meta
            try:
                orig_url = f"{self.config.api_url}/pages/{original_page_id}"
                response = self.session.get(orig_url, params={'context': 'edit'})
                response.raise_for_status()
                orig_full = response.json()
                orig_meta = orig_full.get('meta', {})
                logger.info(f"Retrieved page with meta data - {len(orig_meta)} fields found")
            except Exception as e:
                logger.warning(f"Could not fetch edit context: {e}")
                orig_meta = original_page.get('meta', {})
            
            new_page_data = {
                'title': f"{original_page['title']['rendered']} - {suffix}",
                'content': original_page['content']['rendered'],
                'status': 'draft',
                'parent': original_page.get('parent', 0),
            }
            
            # Include meta if available
            if orig_meta:
                new_page_data['meta'] = orig_meta
            
            response = self.session.post(
                f"{self.config.api_url}/pages",
                json=new_page_data
            )
            response.raise_for_status()
            
            new_page = response.json()
            new_page_id = new_page['id']
            
            # Check for page builders and log warnings
            if orig_meta:
                builders = []
                if any('elementor' in key.lower() for key in orig_meta.keys()):
                    builders.append('Elementor')
                if any('beaver' in key.lower() for key in orig_meta.keys()):
                    builders.append('Beaver Builder')
                if any('divi' in key.lower() for key in orig_meta.keys()):
                    builders.append('Divi')
                
                if builders:
                    logger.warning(f"Page builders detected: {', '.join(builders)}. "
                                 f"Manual CSS regeneration may be required for page {new_page_id}")
            
            logger.info(f"Successfully created duplicate page: {new_page['title']['rendered']}")
            return new_page
            
        except requests.RequestException as e:
            logger.error(f"Error duplicating page: {e}")
            return None

    def update_page_content(self, page_id: int, new_content: str) -> Optional[Dict]:
        """Update a WordPress page's content."""
        try:
            update_data = {'content': new_content}
            
            response = self.session.post(
                f"{self.config.api_url}/pages/{page_id}",
                json=update_data
            )
            response.raise_for_status()
            
            updated_page = response.json()
            logger.info(f"Successfully updated page content: {updated_page['title']['rendered']}")
            return updated_page
            
        except requests.RequestException as e:
            logger.error(f"Error updating page content: {e}")
            return None

    def ship_changes_simple(self, page_url: str, changes: List[ContentChange], test_name: str = None) -> Dict:
        """Ship changes to WordPress using simple text replacement."""
        try:
            # Find original page
            original_page = self.find_page_by_url(page_url)
            if not original_page:
                return {'success': False, 'error': f'Page not found for URL: {page_url}'}
            
            # Create duplicate
            suffix = test_name or f"test final version"
            duplicate_page = self.duplicate_page(original_page, suffix)
            if not duplicate_page:
                return {'success': False, 'error': 'Failed to create duplicate page'}
            
            # Apply changes using simple replacement
            modified_content = self.apply_content_changes_simple(
                original_page['content']['rendered'], 
                changes
            )
            
            # Update duplicate page
            updated_page = self.update_page_content(duplicate_page['id'], modified_content)
            if not updated_page:
                return {'success': False, 'error': 'Failed to update duplicate page content'}
            
            return {
                'success': True,
                'original_page': {
                    'id': original_page['id'],
                    'title': original_page['title']['rendered'],
                    'url': original_page['link']
                },
                'duplicate_page': {
                    'id': updated_page['id'],
                    'title': updated_page['title']['rendered'],
                    'url': updated_page['link'],
                    'edit_url': f"{self.config.site_url}/wp-admin/post.php?post={updated_page['id']}&action=edit"
                },
                'changes_applied': len(changes),
                'test_name': suffix
            }
            
        except Exception as e:
            logger.error(f"Error in ship_changes_simple: {e}")
            return {'success': False, 'error': f'Unexpected error: {str(e)}'}
