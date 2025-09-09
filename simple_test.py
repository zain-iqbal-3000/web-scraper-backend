#!/usr/bin/env python3

import requests
import json
import time

def test_simple_html():
    url = "http://127.0.0.1:5000/scrape-self-contained"
    # Use a simple test page that definitely works
    data = {"url": "https://httpbin.org/html"}
    
    try:
        print("Testing with httpbin.org/html...")
        print("Sending request...")
        
        response = requests.post(url, json=data, timeout=30)
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            status = result.get('status', 'unknown')
            print(f"API Status: {status}")
            
            if status == 'success':
                html_content = result.get('html', '')
                processing_info = result.get('processing_info', {})
                
                print(f"HTML length: {len(html_content)} characters")
                print(f"CORS safe: {processing_info.get('cors_safe', False)}")
                print(f"Processing type: {processing_info.get('type', 'unknown')}")
                
                # Save to file for manual inspection
                with open('test_output.html', 'w', encoding='utf-8') as f:
                    f.write(html_content)
                print("HTML saved to test_output.html")
                
                return True
            else:
                print(f"API returned error: {result}")
        else:
            print(f"HTTP Error {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return False

if __name__ == "__main__":
    print("Starting self-contained scraping test...")
    success = test_simple_html()
    print(f"Test {'PASSED' if success else 'FAILED'}")
