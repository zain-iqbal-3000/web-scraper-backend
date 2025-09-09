import requests
import sys

# Test basic server connectivity
try:
    response = requests.get('http://127.0.0.1:5000/')
    print(f"Server response: {response.status_code}")
    print(f"Content: {response.text[:200]}...")
except Exception as e:
    print(f"Server test failed: {e}")
    sys.exit(1)

# Test our new endpoint with a simple URL
try:
    response = requests.post(
        'http://127.0.0.1:5000/scrape-self-contained',
        json={'url': 'https://httpbin.org/html'},
        timeout=30
    )
    print(f"Endpoint response: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Success: {result.get('status')}")
        print(f"HTML size: {len(result.get('html', ''))}")
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Endpoint test failed: {e}")
