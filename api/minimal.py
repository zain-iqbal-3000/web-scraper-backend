from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import requests
from bs4 import BeautifulSoup
import logging

app = Flask(__name__)
CORS(app, origins=['*'], allow_headers=['*'], methods=['*'])

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'success',
        'message': 'Web Scraper API is working!',
        'version': '3.0.0',
        'endpoints': {
            'health': '/health',
            'test': '/test',
            'scrape': '/scrape',
            'scrape-complete': '/scrape-complete'
        }
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'message': 'API is running with CORS support'
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
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Request body is required'
            }), 400
        
        # Support both single URL and multiple URLs
        if 'url' in data:
            urls = [data['url']]
        elif 'urls' in data:
            urls = data['urls']
            if not isinstance(urls, list):
                return jsonify({
                    'status': 'error',
                    'message': 'URLs must be an array'
                }), 400
        else:
            return jsonify({
                'status': 'error',
                'message': 'URL or URLs array is required'
            }), 400
        
        if len(urls) > 5:
            return jsonify({
                'status': 'error',
                'message': 'Maximum 5 URLs allowed per request'
            }), 400
        
        results = []
        
        for url in urls:
            try:
                # Make request
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                
                # Parse HTML
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract data using your original logic
                title = soup.find('title')
                title_text = title.text.strip() if title else ""
                
                # Extract headlines (h1 tags)
                h1_tags = soup.find_all('h1')
                headlines = [h1.get_text().strip() for h1 in h1_tags[:3] if h1.get_text().strip()]
                
                # Extract subheadlines (h2, h3 tags)
                h2_tags = soup.find_all('h2')
                h3_tags = soup.find_all('h3')
                subheadlines = []
                for h in h2_tags[:3]:
                    text = h.get_text().strip()
                    if text and len(text) > 5:
                        subheadlines.append(text)
                for h in h3_tags[:2]:
                    text = h.get_text().strip()
                    if text and len(text) > 5:
                        subheadlines.append(text)
                
                # Extract meta description
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                description = meta_desc.get('content', '').strip() if meta_desc else ''
                
                # Extract some paragraph text
                paragraphs = soup.find_all('p')
                descriptions = [description] if description else []
                for p in paragraphs[:3]:
                    text = p.get_text().strip()
                    if text and len(text) > 20 and len(text) < 300:
                        descriptions.append(text)
                
                # Extract call-to-action elements
                cta_elements = []
                buttons = soup.find_all(['button', 'a'], string=True)
                for btn in buttons[:5]:
                    text = btn.get_text().strip()
                    if text and len(text) > 2 and len(text) < 50:
                        cta_elements.append(text)
                
                result = {
                    'url': url,
                    'title': title_text,
                    'headline': headlines,
                    'subheadline': subheadlines[:5],
                    'description_credibility': descriptions[:8],
                    'call_to_action': cta_elements[:10],
                    'html_length': len(str(soup))
                }
                
                results.append(result)
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error for {url}: {str(e)}")
                results.append({
                    'url': url,
                    'error': f'Failed to fetch URL: {str(e)}'
                })
            except Exception as e:
                logger.error(f"Scraping error for {url}: {str(e)}")
                results.append({
                    'url': url,
                    'error': f'Scraping error: {str(e)}'
                })
        
        return jsonify({
            'status': 'success',
            'data': results if len(results) > 1 else results[0],
            'total_processed': len(results)
        })
        
    except Exception as e:
        logger.error(f"API error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Internal server error: {str(e)}'
        }), 500

@app.route('/scrape-complete', methods=['POST'])
def scrape_complete():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Request body is required'
            }), 400
        
        # Support both single URL and multiple URLs
        if 'url' in data:
            urls = [data['url']]
        elif 'urls' in data:
            urls = data['urls']
        else:
            return jsonify({
                'status': 'error',
                'message': 'URL or URLs array is required'
            }), 400
        
        results = []
        
        for url in urls:
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                
                # Return complete HTML
                result = {
                    'url': url,
                    'html': response.text,
                    'status_code': response.status_code,
                    'content_type': response.headers.get('content-type', ''),
                    'html_length': len(response.text)
                }
                
                results.append(result)
                
            except Exception as e:
                logger.error(f"Complete scraping error for {url}: {str(e)}")
                results.append({
                    'url': url,
                    'error': str(e)
                })
        
        return jsonify({
            'status': 'success',
            'data': results if len(results) > 1 else results[0],
            'total_processed': len(results)
        })
        
    except Exception as e:
        logger.error(f"Complete scraping API error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=False)
