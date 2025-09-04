import requests
import json

try:
    # Test WordPress config endpoint
    response = requests.get('http://127.0.0.1:5000/wordpress/config')
    print(f"WordPress Config Status: {response.status_code}")
    print("Response:")
    print(json.dumps(response.json(), indent=2))
    print("\n" + "="*50 + "\n")
    
    # Test WordPress connection
    test_data = {
        "site_url": "https://royalblue-worm-557866.hostingersite.com",
        "username": "zainiqbal.35201@gmail.com",
        "password": "Zain@AiceXpert1"
    }
    
    response = requests.post('http://127.0.0.1:5000/wordpress/test-connection', json=test_data)
    print(f"WordPress Connection Test Status: {response.status_code}")
    print("Response:")
    print(json.dumps(response.json(), indent=2))
    
except Exception as e:
    print(f"Error: {e}")
