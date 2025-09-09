from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import logging
import os

app = Flask(__name__)
CORS(app, origins=['*'], allow_headers=['*'], methods=['*'])

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "message": "Simple API is running"})

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'success',
        'message': 'Simple Web Scraper API is running',
        'version': '1.0.0',
        'endpoints': {
            'health': '/health',
            'scrape': '/scrape'
        }
    })

@app.route('/scrape', methods=['POST'])
def scrape_endpoint():
    """
    Simple scraping endpoint
    Expects JSON: {"url": "https://example.com"}
    """
    try:
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({
                'status': 'error',
                'message': 'URL is required in request body'
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
        
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        description = meta_desc.get('content', '') if meta_desc else ''
        
        return jsonify({
            'status': 'success',
            'data': {
                'url': url,
                'title': title_text,
                'headings': headings,
                'description': description,
                'html_length': len(str(soup))
            }
        })
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to fetch URL: {str(e)}'
        }), 400
    except Exception as e:
        logger.error(f"Scraping error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'status': 'error',
        'message': 'Endpoint not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'status': 'error',
        'message': 'Internal server error'
    }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
