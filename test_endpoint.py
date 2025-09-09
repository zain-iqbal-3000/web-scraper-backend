#!/usr/bin/env python3

import requests
import json

def test_self_contained_endpoint():
    url = "http://127.0.0.1:5000/scrape-self-contained"
    data = {"url": "https://httpbin.org/html"}
    
    try:
        print("Testing self-contained scraping endpoint...")
        response = requests.post(url, json=data, timeout=60)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Response: {result.get('status', 'unknown')}")
            print(f"HTML size: {len(result.get('html', ''))} characters")
            print("CORS-safe:", result.get('processing_info', {}).get('cors_safe', False))
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_self_contained_endpoint()
