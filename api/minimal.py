from flask import Flask, jsonify, request
import json
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'success',
        'message': 'Web Scraper API is working!',
        'version': '2.0.0',
        'endpoints': {
            'health': '/health',
            'test': '/test',
            'scrape': '/scrape'
        }
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'message': 'API is running'
    })

@app.route('/test', methods=['POST'])
def test():
    try:
        data = request.get_json()
        return jsonify({
            'status': 'success',
            'received': data,
            'message': 'Test endpoint working'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/scrape', methods=['POST'])
def scrape():
    try:
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({
                'status': 'error',
                'message': 'URL is required'
            }), 400
        
        url = data['url']
        
        # Make request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract basic data
        title = soup.find('title')
        title_text = title.text.strip() if title else ""
        
        h1_tags = soup.find_all('h1')
        headings = [h1.get_text().strip() for h1 in h1_tags[:3]]
        
        return jsonify({
            'status': 'success',
            'data': {
                'url': url,
                'title': title_text,
                'headings': headings,
                'html_length': len(str(soup))
            }
        })
        
    except requests.exceptions.RequestException as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to fetch URL: {str(e)}'
        }), 400
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Scraping error: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(debug=False)
