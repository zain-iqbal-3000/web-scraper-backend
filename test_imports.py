#!/usr/bin/env python3

def test_imports():
    try:
        print("Testing imports...")
        
        # Test basic imports
        import requests
        import base64
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
        print("✓ Basic imports OK")
        
        # Test our functions
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        try:
            from api.index import download_and_inline_resources, process_css_content
            print("✓ Custom function imports OK")
        except Exception as e:
            print(f"✗ Function import error: {e}")
            return False
        
        # Test a simple HTML processing
        simple_html = '<html><head><title>Test</title></head><body><h1>Hello</h1></body></html>'
        result = download_and_inline_resources(simple_html, 'https://example.com')
        print(f"✓ Function test OK, result length: {len(result)}")
        
        return True
        
    except Exception as e:
        print(f"✗ Import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    print(f"Import test {'PASSED' if success else 'FAILED'}")
