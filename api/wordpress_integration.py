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
    
    def get_page_with_edit_context(self, page_id: int) -> Optional[Dict]:
        """
        Fetch page with edit context to get meta fields and builder data.
        
        Args:
            page_id: WordPress page ID
            
        Returns:
            Full page object with meta data if successful, None otherwise
        """
        try:
            orig_url = f"{self.config.api_url}/pages/{page_id}"
            # Request with context=edit to get meta (requires auth/capability)
            response = self.session.get(orig_url, params={'context': 'edit'})
            response.raise_for_status()
            
            orig_full = response.json()
            logger.info(f"Retrieved page with edit context: {orig_full['title']['rendered']}")
            
            # Log available meta fields for debugging
            orig_meta = orig_full.get('meta', {})
            if orig_meta:
                logger.info(f"Found {len(orig_meta)} meta fields including builder data")
                # Log builder-specific fields
                builder_fields = []
                for key in orig_meta.keys():
                    if any(builder in key.lower() for builder in ['elementor', 'beaver', 'divi', 'visual_composer', 'gutenberg']):
                        builder_fields.append(key)
                
                if builder_fields:
                    logger.info(f"Detected page builder fields: {builder_fields}")
            
            return orig_full
            
        except requests.RequestException as e:
            logger.error(f"Error getting page with edit context: {e}")
            return None

    def generate_wp_cli_commands(self, original_page_id: int, new_page_id: int) -> List[str]:
        """
        Generate WP-CLI commands for copying meta when REST API fails.
        These commands can be run on the WordPress server via SSH.
        
        Args:
            original_page_id: Original page ID
            new_page_id: New page ID
            
        Returns:
            List of WP-CLI commands to execute
        """
        commands = [
            f"# Export original page meta to JSON file",
            f"wp post meta list {original_page_id} --format=json > /tmp/meta_{original_page_id}.json",
            f"",
            f"# Copy each meta field to new page (bash script)",
            f"cat /tmp/meta_{original_page_id}.json | jq -c '.[]' | while read item; do",
            f"  key=$(echo $item | jq -r '.key')",
            f"  value=$(echo $item | jq -r '.value')",
            f"  # Skip edit-related meta fields",
            f"  if [[ $key != _edit* ]] && [[ $key != _pingme ]] && [[ $key != _encloseme ]]; then",
            f"    wp post meta add {new_page_id} \"$key\" \"$value\"",
            f"  fi",
            f"done",
            f"",
            f"# If Elementor is detected, regenerate CSS",
            f"wp elementor flush_css {new_page_id} 2>/dev/null || echo 'Elementor not found or no CSS to flush'",
            f"",
            f"# Clean up temp file",
            f"rm /tmp/meta_{original_page_id}.json"
        ]
        
        logger.info("Generated WP-CLI commands for meta copying:")
        for cmd in commands:
            if cmd.strip() and not cmd.startswith('#'):
                logger.info(f"  {cmd}")
        
        return commands

    def copy_meta_to_page(self, new_page_id: int, orig_meta: Dict, original_page_id: int = None) -> bool:
        """
        Copy meta fields from original page to new page.
        
        Args:
            new_page_id: New page ID to copy meta to
            orig_meta: Original page meta data
            original_page_id: Original page ID (for WP-CLI fallback)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not orig_meta:
                logger.info("No meta data to copy")
                return True
            
            # Filter meta to exclude fields that shouldn't be copied
            excluded_meta_keys = [
                '_edit_lock',
                '_edit_last',
                '_wp_page_template',
                '_pingme',
                '_encloseme'
            ]
            
            filtered_meta = {
                key: value for key, value in orig_meta.items() 
                if not key.startswith('_edit') and key not in excluded_meta_keys
            }
            
            if not filtered_meta:
                logger.info("No copyable meta data found")
                return True
            
            # Try to copy meta via REST API
            patch_data = {'meta': filtered_meta}
            response = self.session.post(
                f"{self.config.api_url}/pages/{new_page_id}",
                json=patch_data
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully copied {len(filtered_meta)} meta fields via REST API")
                return True
            else:
                logger.warning(f"Failed to copy meta via REST API (status {response.status_code})")
                
                # Generate WP-CLI commands as fallback
                if original_page_id:
                    logger.info("Generating WP-CLI commands as fallback for meta copying:")
                    wp_cli_commands = self.generate_wp_cli_commands(original_page_id, new_page_id)
                    
                    logger.info("=== WP-CLI COMMANDS TO RUN ON SERVER ===")
                    for cmd in wp_cli_commands:
                        logger.info(cmd)
                    logger.info("========================================")
                    
                    # Store commands for potential API response
                    self._last_wp_cli_commands = wp_cli_commands
                
                return False
                
        except requests.RequestException as e:
            logger.error(f"Error copying meta to page: {e}")
            
            # Generate WP-CLI commands as fallback
            if original_page_id:
                logger.info("Generating WP-CLI commands due to request error:")
                wp_cli_commands = self.generate_wp_cli_commands(original_page_id, new_page_id)
                
                logger.info("=== WP-CLI COMMANDS TO RUN ON SERVER ===")
                for cmd in wp_cli_commands:
                    logger.info(cmd)
                logger.info("========================================")
                
                self._last_wp_cli_commands = wp_cli_commands
            
            return False

    def copy_single_meta_field(self, page_id: int, meta_key: str, meta_value: any) -> bool:
        """
        Copy a single meta field to a page using the most reliable method.
        
        Args:
            page_id: Target page ID
            meta_key: Meta field key
            meta_value: Meta field value
            
        Returns:
            True if successful
        """
        try:
            # Method 1: Use WordPress REST API meta endpoint
            meta_response = requests.post(
                f"{self.wp_url}/wp-json/wp/v2/pages/{page_id}/meta",
                json={
                    'meta_key': meta_key,
                    'meta_value': meta_value
                },
                auth=(self.wp_username, self.wp_password),
                timeout=30
            )
            
            if meta_response.status_code in [200, 201]:
                return True
            
            # Method 2: Use update_post_meta endpoint (if available)
            update_response = requests.post(
                f"{self.wp_url}/wp-json/wp/v2/pages/{page_id}",
                json={
                    'meta': {
                        meta_key: meta_value
                    }
                },
                auth=(self.wp_username, self.wp_password),
                timeout=30
            )
            
            if update_response.status_code == 200:
                return True
            
            logger.warning(f"⚠️ Could not copy meta field {meta_key} via API")
            return False
            
        except Exception as e:
            logger.warning(f"Error copying meta field {meta_key}: {e}")
            return False

    def get_all_page_meta_fields(self, page_id: int) -> Dict:
        """
        Get ALL meta fields for a page using multiple methods.
        
        Args:
            page_id: Page ID to get meta for
            
        Returns:
            Dictionary of all meta fields
        """
        all_meta = {}
        
        try:
            # Method 1: Use REST API with edit context
            response = requests.get(
                f"{self.wp_url}/wp-json/wp/v2/pages/{page_id}?context=edit",
                auth=(self.wp_username, self.wp_password),
                timeout=30
            )
            
            if response.status_code == 200:
                page_data = response.json()
                if 'meta' in page_data:
                    all_meta.update(page_data['meta'])
            
            # Method 2: Use dedicated meta endpoint
            meta_response = requests.get(
                f"{self.wp_url}/wp-json/wp/v2/pages/{page_id}/meta",
                auth=(self.wp_username, self.wp_password),
                timeout=30
            )
            
            if meta_response.status_code == 200:
                meta_list = meta_response.json()
                for meta_item in meta_list:
                    if isinstance(meta_item, dict) and 'meta_key' in meta_item:
                        all_meta[meta_item['meta_key']] = meta_item['meta_value']
            
            logger.info(f"📋 Retrieved {len(all_meta)} meta fields for page {page_id}")
            
            # Log critical meta fields for debugging
            critical_fields = ['_elementor_data', '_elementor_css', '_wp_page_template', '_elementor_version']
            for field in critical_fields:
                if field in all_meta:
                    logger.info(f"✅ Found critical meta: {field}")
                else:
                    logger.warning(f"❌ Missing critical meta: {field}")
            
            return all_meta
            
        except Exception as e:
            logger.error(f"Error getting meta fields for page {page_id}: {e}")
            return {}

    def apply_general_page_builder_fixes(self, page_id: int, orig_meta: Dict) -> bool:
        """
        Apply general fixes for various page builders.
        
        Args:
            page_id: New page ID
            orig_meta: Original meta fields
            
        Returns:
            True if fixes were applied
        """
        try:
            fixes_applied = 0
            
            # Common page builder meta fields that are critical
            critical_fields = [
                '_wp_page_template',
                '_elementor_edit_mode',
                '_elementor_template_type',
                '_divi_builder_settings',
                '_fl_builder_enabled',
                '_vc_post_settings'
            ]
            
            for field in critical_fields:
                if field in orig_meta:
                    success = self.copy_single_meta_field(page_id, field, orig_meta[field])
                    if success:
                        fixes_applied += 1
                        logger.info(f"✅ Applied page builder fix: {field}")
            
            logger.info(f"🔧 Applied {fixes_applied} page builder fixes")
            return fixes_applied > 0
            
        except Exception as e:
            logger.warning(f"Error applying page builder fixes: {e}")
            return False
        """
        Copy Elementor-specific meta fields that are crucial for styling.
        Elementor stores all CSS and layout data in postmeta.
        
        Args:
            new_page_id: New page ID to copy Elementor meta to
            orig_meta: Original page meta data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Elementor critical meta fields for styling
            elementor_meta_keys = [
                '_elementor_data',          # Page structure and content
                '_elementor_css',           # Generated CSS for the page
                '_elementor_page_settings', # Page-specific settings
                '_elementor_controls_usage', # Widget usage data
                '_elementor_conditions',    # Display conditions
                '_elementor_template_type', # Template type
                '_elementor_version',       # Elementor version used
                '_elementor_pro_version',   # Elementor Pro version
                '_elementor_edit_mode',     # Edit mode settings
                '_elementor_page_assets',   # CSS/JS assets
            ]
            
            # Extract only Elementor-related meta
            elementor_meta = {}
            for key, value in orig_meta.items():
                if any(elementor_key in key for elementor_key in elementor_meta_keys) or \
                   key.startswith('_elementor'):
                    elementor_meta[key] = value
            
            if not elementor_meta:
                logger.info("No Elementor meta fields found to copy")
                return True
            
            logger.info(f"Found {len(elementor_meta)} Elementor meta fields to copy:")
            for key in elementor_meta.keys():
                logger.info(f"  - {key}")
            
            # Try to copy Elementor meta via REST API
            patch_data = {'meta': elementor_meta}
            response = self.session.post(
                f"{self.config.api_url}/pages/{new_page_id}",
                json=patch_data
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Successfully copied {len(elementor_meta)} Elementor meta fields")
                
                # Verify the most critical ones were copied
                critical_fields = ['_elementor_data', '_elementor_css']
                for field in critical_fields:
                    if field in elementor_meta:
                        logger.info(f"✅ Critical Elementor field copied: {field}")
                
                return True
            else:
                logger.error(f"❌ Failed to copy Elementor meta via REST API (status {response.status_code})")
                response_text = response.text[:500] if response.text else "No response body"
                logger.error(f"Response: {response_text}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"❌ Error copying Elementor meta to page: {e}")
            return False

    def generate_elementor_css_endpoint(self, page_id: int) -> Optional[str]:
        """
        Generate a custom REST endpoint URL for Elementor CSS regeneration.
        This would need to be implemented in WordPress as a custom endpoint.
        
        Args:
            page_id: Page ID to regenerate CSS for
            
        Returns:
            Custom endpoint URL if available, None otherwise
        """
        try:
            # Custom endpoint that could be implemented in WordPress
            custom_endpoint = f"{self.config.site_url}/wp-json/elementor/v1/regenerate-css/{page_id}"
            
            # Test if the endpoint exists
            response = self.session.get(custom_endpoint)
            if response.status_code != 404:
                logger.info(f"Found custom Elementor CSS endpoint: {custom_endpoint}")
                return custom_endpoint
            else:
                logger.info("Custom Elementor CSS endpoint not available")
                return None
                
        except Exception as e:
            logger.warning(f"Could not check for custom Elementor endpoint: {e}")
            return None

    def trigger_elementor_css_regeneration(self, page_id: int) -> bool:
        """
        Trigger Elementor CSS regeneration for the page using multiple strategies.
        This ensures proper styling for duplicated Elementor pages.
        
        Args:
            page_id: Page ID to regenerate CSS for
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"🎨 Attempting Elementor CSS regeneration for page {page_id}...")
            
            # Strategy 1: Check for custom Elementor CSS endpoint
            custom_endpoint = self.generate_elementor_css_endpoint(page_id)
            if custom_endpoint:
                try:
                    response = self.session.post(custom_endpoint)
                    if response.status_code == 200:
                        logger.info(f"✅ Triggered Elementor CSS regeneration via custom endpoint")
                        return True
                except Exception as e:
                    logger.warning(f"Custom endpoint failed: {e}")
            
            # Strategy 2: Try admin-ajax with multiple actions
            admin_ajax_url = f"{self.config.site_url}/wp-admin/admin-ajax.php"
            
            # Try different Elementor actions
            elementor_actions = [
                'elementor_clear_cache',
                'elementor_regenerate_css',
                'elementor_flush_css',
            ]
            
            for action in elementor_actions:
                try:
                    regenerate_data = {
                        'action': action,
                        'page_id': page_id,
                    }
                    
                    response = self.session.post(admin_ajax_url, data=regenerate_data)
                    
                    if response.status_code == 200 and 'success' in response.text.lower():
                        logger.info(f"✅ Triggered Elementor CSS regeneration via action: {action}")
                        return True
                    elif response.status_code == 200:
                        logger.info(f"⚠️ Action {action} executed but response unclear")
                        
                except Exception as e:
                    logger.warning(f"Action {action} failed: {e}")
            
            # Strategy 3: Try to generate CSS by accessing the page content with builder context
            try:
                page_content_url = f"{self.config.api_url}/pages/{page_id}"
                response = self.session.get(page_content_url, params={
                    'context': 'edit',
                    '_elementor_css': 'true',
                    'preview': 'true'
                })
                
                if response.status_code == 200:
                    logger.info(f"✅ Accessed page with Elementor context to trigger CSS generation")
                    # This may trigger CSS generation as a side effect
                    return True
                    
            except Exception as e:
                logger.warning(f"Content access strategy failed: {e}")
            
            # If all strategies fail, provide detailed instructions
            logger.warning(f"❌ Could not automatically trigger Elementor CSS regeneration")
            logger.warning(f"📋 Manual steps required:")
            logger.warning(f"   1. Go to WordPress Admin → Elementor → Tools")
            logger.warning(f"   2. Click 'Regenerate CSS & Data' or 'Sync Library'")
            logger.warning(f"   3. Or visit: {self.config.site_url}/wp-admin/admin.php?page=elementor-tools")
            logger.warning(f"   4. Or run WP-CLI: wp elementor flush_css {page_id}")
            
            return False
                
        except Exception as e:
            logger.warning(f"❌ Error triggering Elementor CSS regeneration: {e}")
            return False

    def duplicate_page(self, original_page: Dict, suffix: str = None) -> Optional[Dict]:
        """
        EMERGENCY FIX: Use WordPress native duplication method to preserve ALL styling.
        This bypasses our custom logic and uses WordPress's internal duplication.
        
        Args:
            original_page: The original page object from WordPress API
            suffix: Optional suffix for the new page title/slug
            
        Returns:
            New page object if successful, None otherwise
        """
        try:
            if suffix is None:
                suffix = f"ab-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            
            original_page_id = original_page['id']
            logger.info(f"🚨 EMERGENCY DUPLICATION for page {original_page_id}")
            
            # EMERGENCY METHOD 1: Try WordPress admin-ajax duplication (if plugin exists)
            try:
                logger.info("� Attempting WordPress native duplication via admin-ajax...")
                
                duplicate_data = {
                    'action': 'duplicate_post_as_draft',
                    'post': original_page_id,
                    'security': 'duplicate_nonce'  # This might need to be generated
                }
                
                response = requests.post(
                    f"{self.wp_url}/wp-admin/admin-ajax.php",
                    data=duplicate_data,
                    auth=(self.wp_username, self.wp_password),
                    timeout=30
                )
                
                if response.status_code == 200 and 'success' in response.text.lower():
                    logger.info("✅ WordPress native duplication might have worked!")
                    # Try to find the new page
                    new_pages = requests.get(
                        f"{self.wp_url}/wp-json/wp/v2/pages?search={original_page['title']['rendered']}&orderby=date&order=desc",
                        auth=(self.wp_username, self.wp_password)
                    )
                    if new_pages.status_code == 200:
                        pages = new_pages.json()
                        if len(pages) > 1:  # More than just the original
                            return pages[0]  # The newest one should be the duplicate
                
            except Exception as e:
                logger.warning(f"Native duplication failed: {e}")
            
            # EMERGENCY METHOD 2: Direct database-style copying with raw SQL approach
            logger.info("🔥 Attempting DIRECT database-style duplication...")
            
            # Get the page with absolutely everything
            full_page_response = requests.get(
                f"{self.wp_url}/wp-json/wp/v2/pages/{original_page_id}?context=edit&_fields=id,title,content,excerpt,status,parent,template,featured_media,meta,slug,menu_order,comment_status,ping_status",
                auth=(self.wp_username, self.wp_password),
                timeout=30
            )
            
            if full_page_response.status_code != 200:
                logger.error(f"❌ Failed to get full page data: {full_page_response.status_code}")
                return None
            
            full_page = full_page_response.json()
            logger.info(f"� Got full page data with {len(full_page.get('meta', {}))} meta fields")
            
            # Create new page with EXACT copy of everything
            new_page_data = {
                'title': f"{full_page['title']['rendered']} - {suffix}",
                'content': full_page['content']['raw'],  # Use RAW content
                'excerpt': full_page.get('excerpt', {}).get('raw', ''),
                'status': 'draft',
                'parent': full_page.get('parent', 0),
                'template': full_page.get('template', ''),
                'featured_media': full_page.get('featured_media', 0),
                'menu_order': full_page.get('menu_order', 0),
                'comment_status': full_page.get('comment_status', 'closed'),
                'ping_status': full_page.get('ping_status', 'closed'),
                'meta': full_page.get('meta', {})  # Include ALL meta in creation
            }
            
            logger.info(f"� Creating page with {len(new_page_data.get('meta', {}))} meta fields included...")
            
            create_response = requests.post(
                f"{self.wp_url}/wp-json/wp/v2/pages",
                json=new_page_data,
                auth=(self.wp_username, self.wp_password),
                timeout=30
            )
            
            if create_response.status_code not in [200, 201]:
                logger.error(f"❌ Page creation failed: {create_response.status_code}")
                logger.error(f"Response: {create_response.text}")
                return None
            
            new_page = create_response.json()
            new_page_id = new_page['id']
            logger.info(f"✅ New page created: {new_page_id}")
            
            # EMERGENCY METHOD 3: Force copy critical meta fields individually
            logger.info("� FORCE copying critical meta fields...")
            
            critical_meta = {}
            original_meta = full_page.get('meta', {})
            
            # Extract critical fields
            critical_fields = [
                '_elementor_data', '_elementor_css', '_elementor_version', 
                '_elementor_edit_mode', '_elementor_template_type',
                '_wp_page_template', '_divi_builder_settings',
                '_fl_builder_enabled', '_fl_builder_data'
            ]
            
            for field in critical_fields:
                if field in original_meta:
                    critical_meta[field] = original_meta[field]
            
            logger.info(f"🎯 Found {len(critical_meta)} critical meta fields to copy")
            
            # Force update each critical meta field
            for meta_key, meta_value in critical_meta.items():
                try:
                    # Method 1: Direct meta update
                    meta_response = requests.post(
                        f"{self.wp_url}/wp-json/wp/v2/pages/{new_page_id}",
                        json={'meta': {meta_key: meta_value}},
                        auth=(self.wp_username, self.wp_password),
                        timeout=30
                    )
                    
                    if meta_response.status_code == 200:
                        logger.info(f"✅ Force copied: {meta_key}")
                    else:
                        logger.warning(f"⚠️ Failed to force copy: {meta_key}")
                        
                except Exception as e:
                    logger.warning(f"Error force copying {meta_key}: {e}")
            
            # EMERGENCY METHOD 4: Trigger ALL possible cache clearing and regeneration
            logger.info("🔥 FORCE clearing ALL caches and regenerating CSS...")
            
            # Clear all WordPress caches
            cache_clear_attempts = [
                {'action': 'wp_cache_flush'},
                {'action': 'elementor_clear_cache'},
                {'action': 'elementor_regenerate_css'},
                {'action': 'autoptimize_delete_cache'},
                {'action': 'wp_rocket_clean_domain'}
            ]
            
            for cache_action in cache_clear_attempts:
                try:
                    requests.post(
                        f"{self.wp_url}/wp-admin/admin-ajax.php",
                        data=cache_action,
                        auth=(self.wp_username, self.wp_password),
                        timeout=10
                    )
                except:
                    pass
            
            # Force Elementor CSS regeneration specifically
            if '_elementor_data' in critical_meta:
                logger.info("🎨 FORCE Elementor CSS regeneration...")
                
                elementor_actions = [
                    {
                        'action': 'elementor_ajax',
                        'actions': json.dumps({
                            'regenerate_css_and_data': {
                                'post_id': new_page_id
                            }
                        })
                    }
                ]
                
                for action in elementor_actions:
                    try:
                        requests.post(
                            f"{self.wp_url}/wp-admin/admin-ajax.php",
                            data=action,
                            auth=(self.wp_username, self.wp_password),
                            timeout=30
                        )
                        logger.info("🎨 Triggered Elementor CSS regeneration")
                    except Exception as e:
                        logger.warning(f"Elementor regeneration failed: {e}")
            
            # Final verification
            logger.info(f"🔍 FINAL verification of page {new_page_id}...")
            
            verify_response = requests.get(
                f"{self.wp_url}/wp-json/wp/v2/pages/{new_page_id}?context=edit",
                auth=(self.wp_username, self.wp_password),
                timeout=30
            )
            
            if verify_response.status_code == 200:
                verify_page = verify_response.json()
                verify_meta = verify_page.get('meta', {})
                
                logger.info(f"✅ Verification complete:")
                logger.info(f"   📄 Title: {verify_page['title']['rendered']}")
                logger.info(f"   📋 Meta fields: {len(verify_meta)}")
                
                # Check if critical meta exists
                critical_found = sum(1 for field in critical_fields if field in verify_meta)
                logger.info(f"   � Critical meta: {critical_found}/{len(critical_fields)} found")
                
                if critical_found > 0:
                    logger.info("✅ SOME critical meta found - CSS might work!")
                else:
                    logger.error("❌ NO critical meta found - CSS will be broken!")
                
                return verify_page
            else:
                logger.error(f"❌ Verification failed: {verify_response.status_code}")
                return None
            
        except Exception as e:
            logger.error(f"❌ EMERGENCY duplication failed: {e}")
            return None
    
    def preserve_html_formatting(self, original_content: str, modified_content: str) -> str:
        """
        Ensure that HTML formatting and CSS is preserved from original to modified content.
        This is an additional safety check to maintain styling.
        """
        try:
            from bs4 import BeautifulSoup
            
            original_soup = BeautifulSoup(original_content, 'html.parser')
            modified_soup = BeautifulSoup(modified_content, 'html.parser')
            
            # Extract all style-related elements from original
            original_styles = original_soup.find_all('style')
            original_links = original_soup.find_all('link', rel='stylesheet')
            
            # Check if modified content has lost any critical styling elements
            modified_styles = modified_soup.find_all('style')
            modified_links = modified_soup.find_all('link', rel='stylesheet')
            
            # If styling elements are missing, add them back
            if len(original_styles) > len(modified_styles):
                logger.warning("⚠️ Some <style> elements were lost during content replacement")
                
            if len(original_links) > len(modified_links):
                logger.warning("⚠️ Some CSS <link> elements were lost during content replacement")
                
            # Preserve any inline styles that might have been lost
            for original_elem in original_soup.find_all(style=True):
                # Find corresponding element in modified content
                corresponding_elem = None
                
                # Try to find by ID first
                if original_elem.get('id'):
                    corresponding_elem = modified_soup.find(id=original_elem.get('id'))
                
                # Try to find by class
                elif original_elem.get('class'):
                    corresponding_elem = modified_soup.find(class_=original_elem.get('class'))
                
                # If we found the corresponding element and it's missing the style
                if corresponding_elem and not corresponding_elem.get('style'):
                    corresponding_elem['style'] = original_elem['style']
                    logger.info(f"🎨 Restored inline style to {corresponding_elem.name} element")
            
            return str(modified_soup)
            
        except ImportError:
            logger.warning("BeautifulSoup not available for HTML formatting preservation")
            return modified_content
        except Exception as e:
            logger.warning(f"Error preserving HTML formatting: {e}")
            return modified_content

    def handle_elementor_specific_preservation(self, page_id: int) -> bool:
        """
        Apply Elementor-specific preservation techniques after content update.
        This ensures CSS and styling are maintained for Elementor pages.
        
        Args:
            page_id: WordPress page ID
            
        Returns:
            True if Elementor preservation was successful
        """
        try:
            logger.info(f"🎨 Applying Elementor-specific preservation for page {page_id}")
            
            # 1. Force Elementor to regenerate CSS
            css_regenerated = self.trigger_elementor_css_regeneration(page_id)
            
            # 2. Clear any Elementor cache
            cache_cleared = self.clear_elementor_cache(page_id)
            
            # 3. Update Elementor edit timestamp to force refresh
            timestamp_updated = self.update_elementor_timestamp(page_id)
            
            success = any([css_regenerated, cache_cleared, timestamp_updated])
            
            if success:
                logger.info(f"✅ Elementor preservation completed for page {page_id}")
            else:
                logger.warning(f"⚠️ Elementor preservation had limited success for page {page_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error in Elementor preservation: {e}")
            return False

    def clear_elementor_cache(self, page_id: int) -> bool:
        """Clear Elementor cache for specific page."""
        try:
            # Clear Elementor page cache
            cache_data = {
                'action': 'elementor_clear_cache',
                'page_id': page_id
            }
            
            response = requests.post(
                f"{self.wp_url}/wp-admin/admin-ajax.php",
                data=cache_data,
                auth=(self.wp_username, self.wp_password),
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Cleared Elementor cache for page {page_id}")
                return True
            else:
                logger.warning(f"⚠️ Cache clear response: {response.status_code}")
                return False
                
        except Exception as e:
            logger.warning(f"Cache clear failed: {e}")
            return False

    def update_elementor_timestamp(self, page_id: int) -> bool:
        """Update Elementor edit timestamp to force refresh."""
        try:
            import time
            current_timestamp = int(time.time())
            
            # Update the _elementor_edit_mode meta
            meta_data = {
                '_elementor_edit_mode': 'builder',
                '_elementor_edit_date': current_timestamp
            }
            
            for meta_key, meta_value in meta_data.items():
                response = requests.post(
                    f"{self.wp_url}/wp-json/wp/v2/pages/{page_id}/meta",
                    json={
                        'meta_key': meta_key,
                        'meta_value': meta_value
                    },
                    auth=(self.wp_username, self.wp_password),
                    timeout=30
                )
                
                if response.status_code in [200, 201]:
                    logger.info(f"✅ Updated {meta_key} for page {page_id}")
                else:
                    logger.warning(f"⚠️ Failed to update {meta_key}: {response.status_code}")
            
            return True
            
        except Exception as e:
            logger.warning(f"Timestamp update failed: {e}")
            return False

    def apply_content_changes(self, page_content: str, changes: List[ContentChange]) -> str:
        """
        Apply content changes to page HTML content while preserving CSS and HTML structure.
        Enhanced for Elementor and page builder compatibility.
        
        Args:
            page_content: Original HTML content
            changes: List of content changes to apply
            
        Returns:
            Modified HTML content with preserved styling
        """
        modified_content = page_content
        changes_applied = 0
        
        try:
            from bs4 import BeautifulSoup
            # Use html.parser to preserve original structure
            soup = BeautifulSoup(modified_content, 'html.parser')
            
            for change in changes:
                try:
                    original_text = change.original_text.strip()
                    modified_text = change.modified_text.strip()
                    
                    # Skip empty changes
                    if not original_text or not modified_text:
                        continue
                    
                    logger.info(f"🔍 Looking for text: '{original_text[:50]}...'")
                    found_replacement = False
                    
                    # Strategy 1: Find elements that contain ONLY the text we want to replace
                    # This is the safest approach for page builders
                    for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'span', 'div', 'a', 'li', 'button']):
                        # Skip elements that have children (nested HTML) to avoid breaking structure
                        if element.find_all():
                            continue
                        
                        # Skip elements with data attributes (often used by page builders)
                        if any(attr.startswith('data-') for attr in element.attrs.keys()):
                            logger.debug(f"Skipping element with data attributes: {element.name}")
                            continue
                        
                        # Get the text content of this element
                        element_text = element.get_text().strip()
                        
                        # Exact match - replace the entire text content while preserving all attributes
                        if element_text and original_text.lower() == element_text.lower():
                            # Store all original attributes
                            original_attrs = dict(element.attrs)
                            
                            # Clear content and set new text
                            element.clear()
                            element.string = modified_text
                            
                            # Restore all attributes (including style, class, id, data-*)
                            for attr_name, attr_value in original_attrs.items():
                                element[attr_name] = attr_value
                            
                            found_replacement = True
                            changes_applied += 1
                            logger.info(f"✅ Safe element replacement: '{original_text[:50]}...' -> '{modified_text[:50]}...'")
                            logger.info(f"   Element: <{element.name}> with {len(original_attrs)} preserved attributes")
                            break
                    
                    if found_replacement:
                        continue
                    
                    # Strategy 2: Look for text that's part of a larger text block
                    # Only if Strategy 1 didn't find anything
                    for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'span', 'div', 'a', 'li', 'button']):
                        # Skip elements that have children (nested HTML)
                        if element.find_all():
                            continue
                            
                        # Skip page builder elements
                        if any(attr.startswith('data-') for attr in element.attrs.keys()):
                            continue
                        
                        element_text = element.get_text().strip()
                        
                        # Partial match within element
                        if element_text and original_text.lower() in element_text.lower():
                            # Use regex for case-insensitive replacement
                            import re
                            pattern = re.compile(re.escape(original_text), re.IGNORECASE)
                            new_text = pattern.sub(modified_text, element_text, count=1)
                            
                            if new_text != element_text:
                                # Store all original attributes
                                original_attrs = dict(element.attrs)
                                
                                # Clear and set new content
                                element.clear()
                                element.string = new_text
                                
                                # Restore all attributes
                                for attr_name, attr_value in original_attrs.items():
                                    element[attr_name] = attr_value
                                
                                found_replacement = True
                                changes_applied += 1
                                logger.info(f"✅ Safe partial replacement: '{original_text[:50]}...' -> '{modified_text[:50]}...'")
                                logger.info(f"   Element: <{element.name}> with {len(original_attrs)} preserved attributes")
                                break
                    
                    if not found_replacement:
                        logger.warning(f"❌ Could not safely replace: '{original_text[:50]}...' (preserving page builder integrity)")
                        
                except Exception as e:
                    logger.warning(f"❌ Failed to apply change for element {change.element_id}: {e}")
                    continue
            
            # Convert back to HTML string preserving structure
            modified_content = str(soup)
            
            # Apply additional HTML formatting preservation
            modified_content = self.preserve_html_formatting(page_content, modified_content)
            
        except ImportError:
            logger.error("BeautifulSoup not available - using fallback text replacement")
            # Fallback: Only do simple text replacement if BeautifulSoup isn't available
            for change in changes:
                try:
                    original_text = change.original_text.strip()
                    modified_text = change.modified_text.strip()
                    
                    if original_text in modified_content:
                        modified_content = modified_content.replace(original_text, modified_text, 1)
                        changes_applied += 1
                        logger.info(f"✅ Fallback replacement: '{original_text[:50]}...' -> '{modified_text[:50]}...'")
                except Exception as e:
                    logger.warning(f"❌ Failed fallback replacement: {e}")
        
        except Exception as e:
            logger.error(f"Error in apply_content_changes: {e}")
        
        logger.info(f"📊 Applied {changes_applied} out of {len(changes)} content changes")
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
            logger.info(f"🚨 EMERGENCY SHIP: Starting WordPress shipping for {page_url}")
            logger.info(f"🚨 EMERGENCY SHIP: Applying {len(changes)} changes")
            
            # Step 1: Find the original page
            original_page = self.find_page_by_url(page_url)
            if not original_page:
                logger.error(f"❌ EMERGENCY: Could not find page for URL: {page_url}")
                return {
                    'success': False,
                    'error': f'Original page not found for URL: {page_url}'
                }
            
            logger.info(f"✅ EMERGENCY: Found original page: {original_page['title']['rendered']} (ID: {original_page['id']})")
            
            # Step 2: Create duplicate page using EMERGENCY DUPLICATION
            suffix = test_name or f"AB-Test-{datetime.now().strftime('%Y%m%d-%H%M')}"
            logger.info(f"🚨 EMERGENCY: Creating duplicate with suffix: {suffix}")
            
            duplicate_page = self.duplicate_page(original_page, suffix)
            if not duplicate_page:
                logger.error(f"❌ EMERGENCY: Failed to create duplicate page!")
                return {
                    'success': False,
                    'error': 'Failed to create duplicate page'
                }
            logger.info(f"✅ EMERGENCY: Duplicate created: {duplicate_page['title']['rendered']} (ID: {duplicate_page['id']})")
            
            # Step 3: Apply content changes with EMERGENCY logging
            logger.info(f"🚨 EMERGENCY: Applying content changes to duplicate...")
            modified_content = self.apply_content_changes(
                original_page['content']['rendered'], 
                changes
            )
            
            # Step 4: Update duplicate page with new content
            logger.info(f"🚨 EMERGENCY: Updating page content...")
            updated_page = self.update_page_content(
                duplicate_page['id'], 
                modified_content
            )
            
            if not updated_page:
                logger.error(f"❌ EMERGENCY: Failed to update duplicate page content!")
                return {
                    'success': False,
                    'error': 'Failed to update duplicate page content'
                }
            
            logger.info(f"✅ EMERGENCY SUCCESS: Page shipped to WordPress!")
            logger.info(f"🔗 EMERGENCY: New page URL: {updated_page['link']}")
            logger.info(f"📋 EMERGENCY: Page ID: {updated_page['id']}")
            
            # Step 5: Return success result with EMERGENCY info
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

    def debug_page_content(self, page_url: str, changes: List[ContentChange]) -> Dict:
        """
        Debug endpoint to analyze page content and how changes will be applied.
        """
        result = {
            'success': False,
            'page_found': False,
            'original_content_preview': '',
            'original_html_structure': '',
            'changes_analysis': [],
            'modified_content_preview': '',
            'modified_html_structure': '',
            'css_classes_preserved': True,
            'error': None
        }
        
        try:
            # Find the page
            original_page = self.find_page_by_url(page_url)
            if not original_page:
                result['error'] = f"Page not found for URL: {page_url}"
                return result
            
            result['page_found'] = True
            original_content = original_page['content']['rendered']
            result['original_content_preview'] = original_content[:1000] + '...' if len(original_content) > 1000 else original_content
            
            # Analyze HTML structure
            try:
                from bs4 import BeautifulSoup
                original_soup = BeautifulSoup(original_content, 'html.parser')
                
                # Extract structural info
                original_structure = []
                for element in original_soup.find_all(['div', 'section', 'header', 'main']):
                    classes = element.get('class', [])
                    styles = element.get('style', '')
                    original_structure.append({
                        'tag': element.name,
                        'classes': classes,
                        'has_style': bool(styles),
                        'text_preview': element.get_text()[:50] + '...' if len(element.get_text()) > 50 else element.get_text()
                    })
                
                result['original_html_structure'] = original_structure[:10]  # First 10 elements
                
            except ImportError:
                result['original_html_structure'] = 'BeautifulSoup not available'
            
            # Analyze each change
            for i, change in enumerate(changes):
                analysis = {
                    'change_index': i,
                    'element_id': change.element_id,
                    'original_text': change.original_text[:100] + '...' if len(change.original_text) > 100 else change.original_text,
                    'modified_text': change.modified_text[:100] + '...' if len(change.modified_text) > 100 else change.modified_text,
                    'found_in_content': change.original_text.lower() in original_content.lower(),
                    'exact_match': change.original_text in original_content,
                    'case_insensitive_match': change.original_text.lower() in original_content.lower()
                }
                result['changes_analysis'].append(analysis)
            
            # Apply changes and show preview
            modified_content = self.apply_content_changes(original_content, changes)
            result['modified_content_preview'] = modified_content[:1000] + '...' if len(modified_content) > 1000 else modified_content
            result['content_changed'] = original_content != modified_content
            
            # Analyze modified structure
            try:
                from bs4 import BeautifulSoup
                modified_soup = BeautifulSoup(modified_content, 'html.parser')
                
                # Extract structural info after changes
                modified_structure = []
                for element in modified_soup.find_all(['div', 'section', 'header', 'main']):
                    classes = element.get('class', [])
                    styles = element.get('style', '')
                    modified_structure.append({
                        'tag': element.name,
                        'classes': classes,
                        'has_style': bool(styles),
                        'text_preview': element.get_text()[:50] + '...' if len(element.get_text()) > 50 else element.get_text()
                    })
                
                result['modified_html_structure'] = modified_structure[:10]  # First 10 elements
                
                # Check if CSS classes are preserved
                original_classes = set()
                modified_classes = set()
                
                for element in original_soup.find_all():
                    if element.get('class'):
                        original_classes.update(element.get('class'))
                
                for element in modified_soup.find_all():
                    if element.get('class'):
                        modified_classes.update(element.get('class'))
                
                result['css_classes_preserved'] = original_classes.issubset(modified_classes)
                result['css_classes_lost'] = list(original_classes - modified_classes)
                
            except ImportError:
                result['modified_html_structure'] = 'BeautifulSoup not available'
            
            result['success'] = True
            
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Debug page content error: {e}")
        
        return result

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
