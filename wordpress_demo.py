#!/usr/bin/env python3
"""
WordPress Integration Demo Script
==================================

This script demonstrates how to use the WordPress integration
to ship content optimizations for A/B testing.

Usage:
    python wordpress_demo.py

Requirements:
    - WordPress site with REST API enabled
    - Application password configured
    - Python requests library
"""

import json
import sys
import os

# Add the current directory to path to import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from wordpress_integration import (
    WordPressPageDuplicator, 
    WordPressConfig, 
    ContentChange, 
    parse_frontend_changes
)

def demo_wordpress_integration():
    """
    Demo function showing complete WordPress integration workflow
    """
    print("🚀 WordPress A/B Testing Integration Demo")
    print("=" * 50)
    
    # Step 1: Configuration
    print("\n📋 Step 1: WordPress Configuration")
    print("-" * 30)
    
    # Replace these with your actual WordPress details
    config = WordPressConfig(
        site_url="https://your-wordpress-site.com",  # Your WordPress site URL
        username="your-username",                     # Your WordPress username
        password="xxxx xxxx xxxx xxxx"               # Your application password
    )
    
    print(f"✅ Site URL: {config.site_url}")
    print(f"✅ API URL: {config.api_url}")
    print(f"✅ Username: {config.username}")
    print(f"✅ Password: {'*' * len(config.password)}")
    
    # Step 2: Sample Changes (simulating frontend savedChanges)
    print("\n🎯 Step 2: Sample Content Changes")
    print("-" * 30)
    
    # This simulates the savedChanges data from your frontend
    sample_frontend_changes = {
        'headline-1': {
            'original': 'Welcome to Our Amazing Service',
            'modified': 'Transform Your Business in 30 Days'
        },
        'cta-button-1': {
            'original': 'Sign Up Now',
            'modified': 'Start Your Transformation'
        },
        'description-1': {
            'original': 'We provide excellent services to help you grow your business',
            'modified': 'Join 10,000+ businesses that have increased revenue by 40% with our proven system'
        },
        'subheadline-1': {
            'original': 'Grow your business with our platform',
            'modified': 'The only platform you need to scale from startup to enterprise'
        }
    }
    
    # Parse frontend changes into ContentChange objects
    changes = parse_frontend_changes(sample_frontend_changes)
    
    print(f"✅ Changes to apply: {len(changes)}")
    for i, change in enumerate(changes, 1):
        print(f"   {i}. {change.element_type.title()}: '{change.original_text[:50]}...' → '{change.modified_text[:50]}...'")
    
    # Step 3: Test WordPress Connection
    print("\n🔗 Step 3: Testing WordPress Connection")
    print("-" * 30)
    
    duplicator = WordPressPageDuplicator(config)
    
    try:
        # Test API connection
        response = duplicator.session.get(f"{config.api_url}/pages", params={'per_page': 1})
        response.raise_for_status()
        
        print("✅ WordPress API connection successful!")
        print(f"✅ API endpoint accessible: {config.api_url}")
        
        pages = response.json()
        if pages:
            print(f"✅ Found {len(pages)} page(s) - API is working correctly")
        
    except Exception as e:
        print(f"❌ WordPress connection failed: {str(e)}")
        print("\n🔧 Troubleshooting tips:")
        print("   1. Verify your site URL is correct and accessible")
        print("   2. Check your username and application password")
        print("   3. Ensure WordPress REST API is enabled")
        print("   4. Try regenerating your application password")
        return False
    
    # Step 4: Find Target Page
    print("\n🔍 Step 4: Finding Target Page")
    print("-" * 30)
    
    # Replace with the actual URL of the page you want to optimize
    target_page_url = "https://your-wordpress-site.com/landing-page"
    
    print(f"🎯 Target page URL: {target_page_url}")
    
    original_page = duplicator.find_page_by_url(target_page_url)
    
    if not original_page:
        print(f"❌ Could not find page at URL: {target_page_url}")
        print("\n🔧 Troubleshooting tips:")
        print("   1. Verify the page URL is correct and published")
        print("   2. Check the page is accessible without authentication")
        print("   3. Ensure the page exists in WordPress")
        print("\n📝 Demo mode: Creating a simulated page result...")
        
        # For demo purposes, create a simulated page
        original_page = {
            'id': 123,
            'title': {'rendered': 'Demo Landing Page'},
            'content': {'rendered': '<h1>Welcome to Our Amazing Service</h1><p>We provide excellent services to help you grow your business</p><a href="#signup">Sign Up Now</a>'},
            'link': target_page_url
        }
        
    print(f"✅ Found page: '{original_page['title']['rendered']}'")
    print(f"✅ Page ID: {original_page['id']}")
    
    # Step 5: Ship Changes (Demo Mode)
    print("\n🚢 Step 5: Shipping Changes to WordPress")
    print("-" * 30)
    
    print("⚠️  DEMO MODE: This will show what would happen without actually modifying WordPress")
    print("    To run for real, set DEMO_MODE = False in the script")
    
    DEMO_MODE = True  # Set to False to actually ship changes
    
    if DEMO_MODE:
        # Simulate the shipping process
        print("\n📝 Demo simulation:")
        print("   1. ✅ Original page found and validated")
        print("   2. ✅ Duplicate page would be created with title: 'Demo Landing Page - AB-Test-20241204-1500'")
        print("   3. ✅ Content changes would be applied:")
        
        for i, change in enumerate(changes, 1):
            print(f"      {i}. Replace '{change.original_text}' → '{change.modified_text}'")
        
        print("   4. ✅ Duplicate page would be saved as draft for review")
        print("   5. ✅ WordPress editor link would be provided")
        
        # Simulated result
        demo_result = {
            'success': True,
            'original_page': {
                'id': original_page['id'],
                'title': original_page['title']['rendered'],
                'url': original_page['link']
            },
            'duplicate_page': {
                'id': 456,
                'title': f"{original_page['title']['rendered']} - AB-Test-20241204-1500",
                'url': f"{target_page_url}-ab-test-20241204-1500",
                'edit_url': f"{config.site_url}/wp-admin/post.php?post=456&action=edit"
            },
            'changes_applied': len(changes),
            'test_name': 'Demo-AB-Test'
        }
        
        print(f"\n🎉 Demo Result:")
        print(json.dumps(demo_result, indent=2))
        
    else:
        # Actually ship the changes
        print("🚀 Shipping changes to WordPress...")
        
        result = duplicator.ship_changes_to_wordpress(
            page_url=target_page_url,
            changes=changes,
            test_name="Demo-Optimization-Test"
        )
        
        if result['success']:
            print("🎉 Successfully shipped to WordPress!")
            print(f"✅ Original page: {result['original_page']['title']}")
            print(f"✅ Duplicate page: {result['duplicate_page']['title']}")
            print(f"✅ Changes applied: {result['changes_applied']}")
            print(f"🔗 View new page: {result['duplicate_page']['url']}")
            print(f"✏️  Edit in WordPress: {result['duplicate_page']['edit_url']}")
        else:
            print(f"❌ Failed to ship changes: {result['error']}")
            return False
    
    # Step 6: Next Steps
    print("\n🎯 Step 6: Next Steps for A/B Testing")
    print("-" * 30)
    print("1. 📝 Review the duplicate page in WordPress admin")
    print("2. ✅ Publish the duplicate page when ready")
    print("3. 🔄 Set up A/B testing tool to split traffic")
    print("4. 📊 Monitor conversion rates between versions")
    print("5. 🏆 Choose the winning version")
    
    print("\n🎉 WordPress Integration Demo Complete!")
    return True

def interactive_setup():
    """
    Interactive setup to help users configure their WordPress credentials
    """
    print("🔧 WordPress Integration Setup")
    print("=" * 40)
    
    print("\nThis will help you set up WordPress integration for A/B testing.")
    print("You'll need:")
    print("  1. Your WordPress site URL")
    print("  2. Your WordPress username")
    print("  3. An Application Password (not your regular password)")
    
    print("\n📋 Setting up Application Password:")
    print("  1. Go to your WordPress admin")
    print("  2. Navigate to Users → Your Profile")
    print("  3. Scroll to 'Application Passwords'")
    print("  4. Enter 'LP Optimization' as the name")
    print("  5. Click 'Add New Application Password'")
    print("  6. Copy the generated password (format: xxxx xxxx xxxx xxxx)")
    
    proceed = input("\nHave you created an Application Password? (y/n): ").lower().strip()
    
    if proceed != 'y':
        print("\nPlease create an Application Password first, then run this script again.")
        return False
    
    # Get user input
    site_url = input("\nEnter your WordPress site URL (e.g., https://mysite.com): ").strip()
    username = input("Enter your WordPress username: ").strip()
    password = input("Enter your Application Password (xxxx xxxx xxxx xxxx): ").strip()
    
    if not all([site_url, username, password]):
        print("❌ All fields are required. Please try again.")
        return False
    
    # Test the configuration
    print(f"\n🔗 Testing connection to {site_url}...")
    
    config = WordPressConfig(
        site_url=site_url,
        username=username,
        password=password
    )
    
    duplicator = WordPressPageDuplicator(config)
    
    try:
        response = duplicator.session.get(f"{config.api_url}/pages", params={'per_page': 1})
        response.raise_for_status()
        
        print("✅ Connection successful!")
        print("✅ WordPress REST API is accessible")
        print("✅ Authentication working")
        
        # Save configuration for future use
        config_data = {
            "site_url": site_url,
            "username": username,
            "password": password
        }
        
        with open("wordpress_config.json", "w") as f:
            json.dump(config_data, f, indent=2)
        
        print("\n💾 Configuration saved to 'wordpress_config.json'")
        print("🔒 Keep this file secure - it contains your credentials")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        print("\n🔧 Common issues:")
        print("  - Incorrect site URL (should include https://)")
        print("  - Wrong username or application password")
        print("  - WordPress REST API disabled")
        print("  - Site not accessible")
        return False

def main():
    """
    Main function - choose between demo or setup
    """
    print("🚀 WordPress A/B Testing Integration")
    print("=" * 50)
    print("Choose an option:")
    print("1. Run demo with sample data")
    print("2. Interactive setup and configuration")
    print("3. Exit")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == "1":
        return demo_wordpress_integration()
    elif choice == "2":
        success = interactive_setup()
        if success:
            print("\n🎉 Setup complete! You can now use the WordPress integration.")
            print("💡 Try the demo or integrate with your web app.")
        return success
    elif choice == "3":
        print("👋 Goodbye!")
        return True
    else:
        print("❌ Invalid choice. Please try again.")
        return main()

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n👋 Demo interrupted by user. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        print("Please check your configuration and try again.")
        sys.exit(1)
