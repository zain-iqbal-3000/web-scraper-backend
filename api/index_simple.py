from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=['*'], allow_headers=['*'], methods=['*'])

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'success',
        'message': 'Web Scraper API is running',
        'version': '1.0.0',
        'endpoints': {
            'health': '/',
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
                'success': False,
                'error': 'URL is required'
            }), 400
        
        url = data['url']
        
        # Basic URL validation
        if not url.startswith(('http://', 'https://')):
            return jsonify({
                'success': False,
                'error': 'Invalid URL format'
            }), 400
        
        # Make request to scrape the website
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract basic information
        title = soup.find('title')
        title_text = title.text.strip() if title else 'No title found'
        
        # Extract headings
        headings = []
        for h in soup.find_all(['h1', 'h2', 'h3']):
            if h.text.strip():
                headings.append({
                    'tag': h.name,
                    'text': h.text.strip()
                })
        
        # Extract meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        description = meta_desc.get('content', '') if meta_desc else ''
        
        # Extract links
        links = []
        for link in soup.find_all('a', href=True):
            if link.text.strip():
                links.append({
                    'text': link.text.strip(),
                    'href': link['href']
                })
        
        result = {
            'success': True,
            'url': url,
            'data': {
                'title': title_text,
                'description': description,
                'headings': headings[:10],  # Limit to first 10
                'links': links[:20]  # Limit to first 20
            }
        }
        
        return jsonify(result)
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error for {url}: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Failed to fetch URL: {str(e)}'
        }), 400
    
    except Exception as e:
        logger.error(f"Scraping error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@app.route('/scrape-complete', methods=['POST'])
def scrape_complete_endpoint():
    """
    Complete HTML scraping endpoint
    Expects JSON: {"url": "https://example.com"}
    """
    try:
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({
                'success': False,
                'error': 'URL is required'
            }), 400
        
        url = data['url']
        
        # Basic URL validation
        if not url.startswith(('http://', 'https://')):
            return jsonify({
                'success': False,
                'error': 'Invalid URL format'
            }), 400
        
        # Make request to scrape the website
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Return raw HTML
        result = {
            'success': True,
            'url': url,
            'html': response.text,
            'status_code': response.status_code
        }
        
        return jsonify(result)
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error for {url}: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Failed to fetch URL: {str(e)}'
        }), 400
    
    except Exception as e:
        logger.error(f"Scraping error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
