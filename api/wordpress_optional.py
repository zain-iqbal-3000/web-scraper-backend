"""
Optional WordPress Integration Module
====================================

This module provides WordPress integration features when available.
If WordPress dependencies are missing, it gracefully falls back to disabled state.

Environment Variables:
- WORDPRESS_SITE_URL: Default WordPress site URL
- WORDPRESS_USERNAME: Default WordPress username
- WORDPRESS_PASSWORD: Default WordPress application password
"""

import logging
import os

logger = logging.getLogger(__name__)

# WordPress environment variables
WORDPRESS_SITE_URL = os.environ.get('WORDPRESS_SITE_URL', 'https://royalblue-worm-557866.hostingersite.com')
WORDPRESS_USERNAME = os.environ.get('WORDPRESS_USERNAME', 'zainiqbal.35201@gmail.com')
WORDPRESS_PASSWORD = os.environ.get('WORDPRESS_PASSWORD', 'Zain@AiceXpert1')

# Try to import WordPress integration
try:
    import sys
    import os
    
    # Add parent directory to path to import wordpress_integration
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    sys.path.insert(0, parent_dir)
    
    from wordpress_integration import (
        WordPressPageDuplicator, 
        WordPressConfig, 
        ContentChange, 
        parse_frontend_changes
    )
    
    WORDPRESS_AVAILABLE = True
    logger.info("WordPress integration loaded successfully")
    
    # Export the classes and functions
    __all__ = [
        'WordPressPageDuplicator',
        'WordPressConfig', 
        'ContentChange',
        'parse_frontend_changes',
        'WORDPRESS_AVAILABLE'
    ]
    
except ImportError as e:
    logger.warning(f"WordPress integration not available: {str(e)}")
    WORDPRESS_AVAILABLE = False
    
    # Create dummy classes to prevent import errors
    class WordPressPageDuplicator:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("WordPress integration not available")
    
    class WordPressConfig:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("WordPress integration not available")
    
    class ContentChange:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("WordPress integration not available")
    
    def parse_frontend_changes(*args, **kwargs):
        raise RuntimeError("WordPress integration not available")
    
    __all__ = ['WORDPRESS_AVAILABLE']

except Exception as e:
    logger.error(f"Unexpected error loading WordPress integration: {str(e)}")
    WORDPRESS_AVAILABLE = False
    
    # Create dummy classes
    class WordPressPageDuplicator:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("WordPress integration failed to load")
    
    class WordPressConfig:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("WordPress integration failed to load")
    
    class ContentChange:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("WordPress integration failed to load")
    
    def parse_frontend_changes(*args, **kwargs):
        raise RuntimeError("WordPress integration failed to load")
    
    __all__ = ['WORDPRESS_AVAILABLE']


def get_wordpress_status():
    """Get WordPress integration status"""
    status = {
        'available': WORDPRESS_AVAILABLE,
        'status': 'enabled' if WORDPRESS_AVAILABLE else 'disabled - dependencies not available',
        'features': ['page_duplication', 'content_replacement', 'ab_testing'] if WORDPRESS_AVAILABLE else [],
        'environment_configured': bool(WORDPRESS_SITE_URL and WORDPRESS_USERNAME and WORDPRESS_PASSWORD),
        'site_url': WORDPRESS_SITE_URL if WORDPRESS_SITE_URL else 'Not configured'
    }
    return status

def get_wordpress_credentials():
    """Get WordPress credentials from environment variables"""
    return {
        'site_url': WORDPRESS_SITE_URL,
        'username': WORDPRESS_USERNAME,
        'password': WORDPRESS_PASSWORD,
        'configured': bool(WORDPRESS_SITE_URL and WORDPRESS_USERNAME and WORDPRESS_PASSWORD)
    }
