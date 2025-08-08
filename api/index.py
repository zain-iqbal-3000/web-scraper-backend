from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
import logging
import os

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def scrape_website(self, url):
        """
        Scrape a website and extract specific elements
        """
        try:
            # Validate URL
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                return {'error': 'Invalid URL provided'}
            
            # Make request
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract data
            scraped_data = {
                'html': str(soup),
                'headline': self._extract_headline(soup),
                'subheadline': self._extract_subheadline(soup),
                'call_to_action': self._extract_call_to_action(soup),
                'description_credibility': self._extract_description_credibility(soup)
            }
            
            return scraped_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for {url}: {str(e)}")
            return {'error': f'Failed to fetch URL: {str(e)}'}
        except Exception as e:
            logger.error(f"Scraping error for {url}: {str(e)}")
            return {'error': f'Failed to scrape website: {str(e)}'}
    
    def _extract_headline(self, soup):
        """Extract main headline from the page"""
        headlines = []
        
        # Try different selectors for headlines
        selectors = [
            'h1',
            '[class*="headline"]',
            '[class*="title"]',
            '[id*="headline"]',
            '[id*="title"]',
            '.hero h1',
            '.hero h2',
            'header h1',
            'header h2'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                if text and len(text) > 10:  # Filter out very short text
                    headlines.append(text)
        
        return headlines[:3] if headlines else []
    
    def _extract_subheadline(self, soup):
        """Extract subheadlines from the page"""
        subheadlines = []
        
        # Try different selectors for subheadlines
        selectors = [
            'h2',
            'h3',
            '[class*="subheadline"]',
            '[class*="subtitle"]',
            '[class*="tagline"]',
            '.hero h2',
            '.hero h3',
            '.hero p:first-of-type'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                if text and len(text) > 5:
                    subheadlines.append(text)
        
        return subheadlines[:5] if subheadlines else []
    
    def _extract_description_credibility(self, soup):
        """Extract description/credibility content combined"""
        descriptions = []
        
        # Try different selectors for descriptions and credibility
        selectors = [
            # Description selectors
            '[class*="description"]',
            '[class*="about"]',
            '[class*="intro"]',
            '[class*="summary"]',
            'meta[name="description"]',
            '.hero p',
            'main p',
            'article p',
            # Credibility selectors
            '[class*="testimonial"]',
            '[class*="review"]',
            '[class*="award"]',
            '[class*="certification"]',
            '[class*="trust"]',
            '[class*="security"]',
            '[class*="guarantee"]',
            '[class*="client"]',
            '[class*="customer"]',
            '.social-proof',
            '[class*="experience"]',
            '[class*="expertise"]',
            '[class*="proven"]',
            '[class*="success"]'
        ]
        
        for selector in selectors:
            if selector.startswith('meta'):
                elements = soup.select(selector)
                for element in elements:
                    content = element.get('content', '')
                    if content and len(content) > 20:
                        descriptions.append(content)
            else:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text(strip=True)
                    if text and len(text) > 20 and len(text) < 500:
                        # Clean the text
                        clean_text = re.sub(r'\s+', ' ', text).strip()
                        if clean_text not in descriptions:
                            descriptions.append(clean_text)
        
        return descriptions[:8] if descriptions else []
    
    def _extract_call_to_action(self, soup):
        """Extract textual call-to-action phrases and compelling text"""
        ctas = []
        
        # Common CTA phrases to look for
        cta_patterns = [
            r'\b(?:sign up|join|register|subscribe|get started|start now|try free|free trial|learn more|discover|explore|find out|click here|read more|download|get|book now|contact us|call now|shop now|buy now|order now|get quote|request)\b',
            r'\b(?:unlock|access|claim|grab|secure|reserve|activate|enable|upgrade|optimize|transform|boost|improve|enhance|maximize)\b',
            r'\b(?:don\'t wait|limited time|act now|hurry|exclusive|special offer|save|discount|deal)\b'
        ]
        
        # Look for text containing CTA phrases
        all_text_elements = soup.find_all(text=True)
        
        for text in all_text_elements:
            text = text.strip()
            if len(text) > 5 and len(text) < 200:  # Filter reasonable length text
                text_lower = text.lower()
                
                # Check if text contains CTA patterns
                for pattern in cta_patterns:
                    if re.search(pattern, text_lower, re.IGNORECASE):
                        # Clean the text and add to CTAs
                        clean_text = re.sub(r'\s+', ' ', text).strip()
                        if clean_text not in ctas and len(clean_text) > 3:
                            ctas.append(clean_text)
                        break
        
        # Also look for text in specific CTA-related elements
        cta_selectors = [
            'a[class*="cta"]',
            'button',
            'input[type="submit"]',
            '[class*="call-to-action"]',
            '[class*="action"]',
            'a[class*="btn"]',
            'a[class*="button"]'
        ]
        
        for selector in cta_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                if text and len(text) > 2 and len(text) < 100:
                    clean_text = re.sub(r'\s+', ' ', text).strip()
                    if clean_text not in ctas:
                        ctas.append(clean_text)
        
        return ctas[:10] if ctas else []

# Initialize scraper
scraper = WebScraper()

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'success',
        'message': 'Web Scraper Batch API is running',
        'version': '1.0.0',
        'endpoint': '/scrape-batch'
    })

@app.route('/scrape-batch', methods=['POST'])
def scrape_batch_endpoint():
    """
    Batch scraping endpoint
    Expects JSON: {"urls": ["https://example1.com", "https://example2.com"]}
    """
    try:
        data = request.get_json()
        
        if not data or 'urls' not in data:
            return jsonify({
                'status': 'error',
                'message': 'URLs array is required in request body'
            }), 400
        
        urls = data['urls']
        
        if not isinstance(urls, list) or len(urls) == 0:
            return jsonify({
                'status': 'error',
                'message': 'URLs must be a non-empty array'
            }), 400
        
        if len(urls) > 10:  # Limit batch size
            return jsonify({
                'status': 'error',
                'message': 'Maximum 10 URLs allowed per batch'
            }), 400
        
        results = []
        for url in urls:
            result = scraper.scrape_website(url)
            results.append(result)
        
        return jsonify({
            'status': 'success',
            'data': results
        })
    
    except Exception as e:
        logger.error(f"Batch API error: {str(e)}")
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
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    app.run(host='0.0.0.0', port=port, debug=debug)
