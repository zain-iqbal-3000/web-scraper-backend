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
        Apply content changes to page HTML content.
        
        Args:
            page_content: Original HTML content
            changes: List of content changes to apply
            
        Returns:
            Modified HTML content
        """
        modified_content = page_content
        
        for change in changes:
            try:
                # Escape special regex characters in original text
                escaped_original = re.escape(change.original_text)
                
                # Replace the content (case-insensitive, first occurrence only)
                pattern = re.compile(escaped_original, re.IGNORECASE)
                modified_content = pattern.sub(change.modified_text, modified_content, count=1)
                
                logger.info(f"Applied change: '{change.original_text[:50]}...' -> '{change.modified_text[:50]}...'")
                
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
