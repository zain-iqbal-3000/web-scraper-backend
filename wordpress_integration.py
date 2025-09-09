"""
WordPress Page Duplication and Content Replacement Service
==========================================================

This service integrates with WordPress REST API to:
1. Duplicate existing pages for A/B testing
2. Replace content with AI-optimized suggestions
3. Maintain proper WordPress formatting and structure

Requirements:
- WordPress site with REST API enabled
- Application Password or JWT token for authentication
- Python requests library

Author: LP Optimization Team
Version: 1.0.0
"""

import requests
import json
import re
from urllib.parse import urljoin, urlparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging
import unicodedata
from bs4 import BeautifulSoup
from dataclasses import dataclass, asdict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ContentChange:
    """Represents a single content change from the frontend"""
    element_id: str
    original_text: str
    modified_text: str
    element_type: str  # 'headline', 'subheadline', 'cta', 'description'

@dataclass
class WordPressConfig:
    """WordPress site configuration"""
    site_url: str
    username: str
    password: str  # Application Password
    api_base: str = "wp-json/wp/v2"
    
    def __post_init__(self):
        self.api_url = urljoin(self.site_url.rstrip('/') + '/', self.api_base)

class WordPressPageDuplicator:
    """
    Handles WordPress page duplication and content replacement
    for A/B testing purposes.
    """
    
    def __init__(self, config: WordPressConfig):
        self.config = config
        self.session = requests.Session()
        self.session.auth = (config.username, config.password)
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def find_page_by_url(self, page_url: str) -> Optional[Dict]:
        """
        Find a WordPress page by its URL.
        
        Args:
            page_url: The full URL of the page to find
            
        Returns:
            Page object if found, None otherwise
        """
        try:
            # Extract the slug from the URL
            parsed_url = urlparse(page_url)
            slug = parsed_url.path.strip('/').split('/')[-1]
            
            # Search for pages with this slug
            response = self.session.get(
                f"{self.config.api_url}/pages",
                params={'slug': slug, 'status': 'publish'}
            )
            response.raise_for_status()
            
            pages = response.json()
            if pages:
                logger.info(f"Found page with slug '{slug}': {pages[0]['title']['rendered']}")
                return pages[0]
            
            # If slug search fails, try searching by full URL
            response = self.session.get(
                f"{self.config.api_url}/pages",
                params={'search': page_url, 'status': 'publish'}
            )
            response.raise_for_status()
            
            pages = response.json()
            for page in pages:
                if page_url in page.get('link', ''):
                    logger.info(f"Found page by URL search: {page['title']['rendered']}")
                    return page
            
            logger.warning(f"No page found for URL: {page_url}")
            return None
            
        except requests.RequestException as e:
            logger.error(f"Error finding page: {e}")
            return None
    
    def duplicate_page(self, original_page: Dict, suffix: str = None) -> Optional[Dict]:
        """
        Create a duplicate of a WordPress page.
        
        Args:
            original_page: The original page object from WordPress API
            suffix: Optional suffix for the new page title/slug
            
        Returns:
            New page object if successful, None otherwise
        """
        try:
            if suffix is None:
                suffix = f"ab-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            
            # Prepare new page data
            new_page_data = {
                'title': f"{original_page['title']['rendered']} - {suffix}",
                'content': original_page['content']['rendered'],
                'excerpt': original_page['excerpt']['rendered'],
                'status': 'draft',  # Start as draft for review
                'parent': original_page.get('parent', 0),
                'template': original_page.get('template', ''),
                'meta': original_page.get('meta', {}),
                'featured_media': original_page.get('featured_media', 0),
            }
            
            # Create the new page
            response = self.session.post(
                f"{self.config.api_url}/pages",
                json=new_page_data
            )
            response.raise_for_status()
            
            new_page = response.json()
            logger.info(f"Successfully created duplicate page: {new_page['title']['rendered']}")
            return new_page
            
        except requests.RequestException as e:
            logger.error(f"Error duplicating page: {e}")
            return None
    
    def apply_content_changes(self, page_content: str, changes: List[ContentChange]) -> str:
        """
        Apply content changes to page HTML content with enhanced text replacement.
        
        Args:
            page_content: Original HTML content
            changes: List of content changes to apply
            
        Returns:
            Modified HTML content
        """
        from bs4 import BeautifulSoup
        import unicodedata
        
        modified_content = page_content
        
        for change in changes:
            try:
                logger.info(f"Attempting to replace: '{change.original_text[:100]}...' with '{change.modified_text[:100]}...'")
                
                # Method 1: Direct text replacement (works for simple cases)
                if change.original_text in modified_content:
                    modified_content = modified_content.replace(change.original_text, change.modified_text, 1)
                    logger.info(f"✅ Method 1 (direct replacement) successful")
                    continue
                
                # Method 2: Normalize Unicode and try again (for French accents)
                normalized_original = unicodedata.normalize('NFC', change.original_text)
                normalized_content = unicodedata.normalize('NFC', modified_content)
                
                if normalized_original in normalized_content:
                    modified_content = normalized_content.replace(normalized_original, change.modified_text, 1)
                    logger.info(f"✅ Method 2 (Unicode normalized) successful")
                    continue
                
                # Method 3: Parse HTML and look for text content across tags
                soup = BeautifulSoup(modified_content, 'html.parser')
                
                # Find elements that contain the text (even partially across nested elements)
                target_text = change.original_text.strip()
                
                # Try to find elements whose combined text content matches
                for element in soup.find_all(text=True):
                    parent = element.parent
                    if parent and parent.name:
                        # Get all text from this element and its siblings
                        parent_text = parent.get_text(separator=' ', strip=True)
                        
                        if target_text in parent_text:
                            # Replace the text content while preserving structure
                            new_parent_text = parent_text.replace(target_text, change.modified_text, 1)
                            
                            # If text changed, reconstruct the element
                            if new_parent_text != parent_text:
                                # Simple approach: replace the parent's content
                                parent.clear()
                                parent.append(BeautifulSoup(change.modified_text, 'html.parser'))
                                modified_content = str(soup)
                                logger.info(f"✅ Method 3 (HTML parsing) successful")
                                break
                
                # Method 4: Look for text spread across nested HTML tags
                if target_text not in modified_content:
                    # Remove HTML tags and check if text exists
                    soup_check = BeautifulSoup(modified_content, 'html.parser')
                    plain_text = soup_check.get_text(separator=' ', strip=True)
                    
                    if target_text in plain_text:
                        # The text exists but is broken by HTML tags
                        # Use regex to find and replace across tags
                        import re
                        
                        # Create a pattern that allows HTML tags between words
                        words = target_text.split()
                        if len(words) > 1:
                            # Build pattern with optional HTML tags between words
                            pattern_parts = []
                            for i, word in enumerate(words):
                                escaped_word = re.escape(word)
                                if i > 0:
                                    # Allow HTML tags and whitespace between words
                                    pattern_parts.append(r'(?:<[^>]*>|\s)*')
                                pattern_parts.append(escaped_word)
                            
                            pattern = ''.join(pattern_parts)
                            
                            # Try to replace with this pattern
                            replacement_made = False
                            try:
                                new_content = re.sub(pattern, change.modified_text, modified_content, count=1, flags=re.IGNORECASE | re.DOTALL)
                                if new_content != modified_content:
                                    modified_content = new_content
                                    replacement_made = True
                                    logger.info(f"✅ Method 4 (cross-tag regex) successful")
                            except Exception as regex_error:
                                logger.warning(f"Method 4 regex failed: {regex_error}")
                
                # Method 5: Handle emojis and special characters
                if target_text not in modified_content:
                    # Check if the text contains emojis or special characters
                    import re
                    
                    # Extract emojis from the original text
                    emoji_pattern = re.compile(
                        "["
                        "\U0001F600-\U0001F64F"  # emoticons
                        "\U0001F300-\U0001F5FF"  # symbols & pictographs
                        "\U0001F680-\U0001F6FF"  # transport & map symbols
                        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
                        "\U00002702-\U000027B0"  # dingbats
                        "\U000024C2-\U0001F251"
                        "✅✓☑️"  # checkmarks
                        "]+", flags=re.UNICODE
                    )
                    
                    emojis_in_text = emoji_pattern.findall(target_text)
                    
                    if emojis_in_text:
                        # Try to find the text without emojis first
                        text_without_emojis = emoji_pattern.sub('', target_text).strip()
                        
                        if text_without_emojis and text_without_emojis in modified_content:
                            # Replace the text without emojis, then add emojis to replacement
                            emoji_prefix = ' '.join(emojis_in_text) + ' ' if emojis_in_text else ''
                            full_replacement = emoji_prefix + change.modified_text
                            
                            modified_content = modified_content.replace(text_without_emojis, full_replacement, 1)
                            logger.info(f"✅ Method 5 (emoji handling) successful")
                            continue
                
                # If all methods failed, log it but don't stop processing other changes
                logger.warning(f"⚠️ All replacement methods failed for: '{change.original_text[:50]}...'")
                
            except Exception as e:
                logger.warning(f"Failed to apply change for element {change.element_id}: {e}")
                continue
        
        return modified_content
    
    def update_page_content(self, page_id: int, new_content: str, 
                           new_title: str = None) -> Optional[Dict]:
        """
        Update a WordPress page's content.
        
        Args:
            page_id: WordPress page ID
            new_content: New HTML content
            new_title: Optional new title
            
        Returns:
            Updated page object if successful, None otherwise
        """
        try:
            update_data = {'content': new_content}
            if new_title:
                update_data['title'] = new_title
            
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
    
    def ship_changes_to_wordpress(self, page_url: str, changes: List[ContentChange], 
                                 test_name: str = None) -> Dict:
        """
        Main method to ship changes to WordPress.
        Creates a duplicate page with modified content for A/B testing.
        
        Args:
            page_url: URL of the original WordPress page
            changes: List of content changes to apply
            test_name: Optional name for the A/B test
            
        Returns:
            Dictionary with result information
        """
        try:
            # Step 1: Find the original page
            original_page = self.find_page_by_url(page_url)
            if not original_page:
                return {
                    'success': False,
                    'error': f'Original page not found for URL: {page_url}'
                }
            
            # Step 2: Create duplicate page
            suffix = test_name or f"AB-Test-{datetime.now().strftime('%Y%m%d-%H%M')}"
            duplicate_page = self.duplicate_page(original_page, suffix)
            if not duplicate_page:
                return {
                    'success': False,
                    'error': 'Failed to create duplicate page'
                }
            
            # Step 3: Apply content changes
            modified_content = self.apply_content_changes(
                original_page['content']['rendered'], 
                changes
            )
            
            # Step 4: Update duplicate page with new content
            updated_page = self.update_page_content(
                duplicate_page['id'], 
                modified_content
            )
            
            if not updated_page:
                return {
                    'success': False,
                    'error': 'Failed to update duplicate page content'
                }
            
            # Step 5: Return success result
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
            logger.error(f"Error in ship_changes_to_wordpress: {e}")
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }

def parse_frontend_changes(saved_changes_data: Dict) -> List[ContentChange]:
    """
    Parse the savedChanges data from the frontend into ContentChange objects.
    
    Args:
        saved_changes_data: Dictionary containing the saved changes from frontend
        
    Returns:
        List of ContentChange objects
    """
    changes = []
    
    for element_id, change_data in saved_changes_data.items():
        # Determine element type based on element_id or content
        element_type = 'text'  # default
        
        if 'headline' in element_id.lower() or 'h1' in element_id.lower():
            element_type = 'headline'
        elif 'subheadline' in element_id.lower() or any(tag in element_id.lower() for tag in ['h2', 'h3', 'subtitle']):
            element_type = 'subheadline'
        elif any(cta_term in element_id.lower() for cta_term in ['cta', 'button', 'btn', 'call-to-action']):
            element_type = 'cta'
        elif any(desc_term in element_id.lower() for desc_term in ['description', 'desc', 'paragraph', 'p']):
            element_type = 'description'
        
        changes.append(ContentChange(
            element_id=element_id,
            original_text=change_data['original'],
            modified_text=change_data['modified'],
            element_type=element_type
        ))
    
    return changes

# Example usage and testing functions
def test_wordpress_integration():
    """Test function to demonstrate the WordPress integration"""
    
    # Configuration (replace with your WordPress details)
    config = WordPressConfig(
        site_url="https://your-wordpress-site.com",
        username="your-username",
        password="your-application-password"  # Generate in WP Admin > Users > Application Passwords
    )
    
    # Sample changes data (similar to what your frontend sends)
    sample_changes = {
        'headline-1': {
            'original': 'Original Headline Text',
            'modified': 'AI-Optimized Headline Text'
        },
        'cta-button-1': {
            'original': 'Sign Up Now',
            'modified': 'Get Started Today'
        },
        'description-1': {
            'original': 'Original description text here',
            'modified': 'Improved description with better conversion copy'
        }
    }
    
    # Parse changes
    changes = parse_frontend_changes(sample_changes)
    
    # Initialize duplicator and ship changes
    duplicator = WordPressPageDuplicator(config)
    result = duplicator.ship_changes_to_wordpress(
        page_url="https://your-wordpress-site.com/landing-page",
        changes=changes,
        test_name="Homepage-Optimization-Test"
    )
    
    return result

if __name__ == "__main__":
    # Run test (comment out for production use)
    # result = test_wordpress_integration()
    # print(json.dumps(result, indent=2))
    pass
