from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
import logging
import os
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Firebase configuration (you'll get these from Firebase console)
FIREBASE_API_KEY = os.environ.get('FIREBASE_API_KEY', 'AIzaSyC7-xHHI-ip1uThgqc67DRh8ZgWPQZuVgI')
FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID', 'lp-optimization-97f9f')
FIREBASE_AUTH_DOMAIN = f"{FIREBASE_PROJECT_ID}.firebaseapp.com"

# Firebase Authentication Class
class FirebaseAuth:
    def __init__(self):
        self.api_key = FIREBASE_API_KEY
        self.firestore_url = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents"
    
    def store_user_data(self, username, password, uid):
        """Store username, password and uid in Firestore"""
        try:
            # Log the attempt for debugging
            logger.info(f"Attempting to store user data for UID: {uid}, Username: {username}")
            
            result = self._store_user_in_firestore(username, password, uid)
            
            if 'error' in result:
                logger.error(f"Failed to store user data: {result}")
                return result
            
            logger.info(f"Successfully stored user data for UID: {uid}")
            return {
                'success': True,
                'uid': uid,
                'username': username,
                'message': 'User data stored successfully in Firebase'
            }
            
        except Exception as e:
            logger.error(f"Store user data error: {str(e)}")
            return {'error': 'Failed to store user data', 'details': str(e)}
    
    def authenticate_user(self, username, password):
        """Authenticate user with stored username and password"""
        try:
            # Get user data from Firestore by username
            user_data = self._get_user_by_username(username)
            
            if 'error' in user_data:
                return user_data
            
            # Verify password
            stored_password = user_data.get('password')
            if stored_password != password:
                return {'error': 'Invalid username or password'}
            
            return {
                'success': True,
                'uid': user_data['uid'],
                'username': username,
                'message': 'Authentication successful'
            }
            
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return {'error': 'Authentication failed', 'details': str(e)}
    
    def _store_user_in_firestore(self, username, password, uid):
        """Store user data in Firestore using the UID as document ID"""
        # For Firestore REST API with API key authentication
        url = f"{self.firestore_url}/users/{uid}?key={self.api_key}"
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        payload = {
            "fields": {
                "username": {"stringValue": username},
                "password": {"stringValue": password},
                "uid": {"stringValue": uid},
                "created_at": {"timestampValue": datetime.utcnow().isoformat() + "Z"},
                "updated_at": {"timestampValue": datetime.utcnow().isoformat() + "Z"}
            }
        }
        
        response = requests.patch(url, json=payload, headers=headers)
        
        if response.status_code not in [200, 201]:
            logger.error(f"Firestore error: Status {response.status_code}, Response: {response.text}")
            return {'error': f'Failed to store user data in Firestore: {response.text}'}
        
        return {'success': True}
    
    def _get_user_by_username(self, username):
        """Get user data from Firestore by username"""
        # Use API key for authentication
        url = f"{self.firestore_url}/users?key={self.api_key}"
        
        response = requests.get(url)
        
        if response.status_code != 200:
            logger.error(f"Firestore query error: Status {response.status_code}, Response: {response.text}")
            return {'error': f'Failed to query user data from Firestore: {response.text}'}
        
        data = response.json()
        documents = data.get('documents', [])
        
        # Search through documents to find matching username
        for doc in documents:
            fields = doc.get('fields', {})
            stored_username = fields.get('username', {}).get('stringValue', '')
            
            if stored_username == username:
                return {
                    'uid': fields.get('uid', {}).get('stringValue', ''),
                    'username': stored_username,
                    'password': fields.get('password', {}).get('stringValue', '')
                }
        
        return {'error': 'User not found'}

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

# Initialize scraper and Firebase auth
scraper = WebScraper()
firebase_auth = FirebaseAuth()

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'success',
        'message': 'Web Scraper API with Firebase Storage is running',
        'version': '2.0.0',
        'endpoints': {
            'store_user': '/auth/store-user',
            'login': '/auth/login',
            'scrape': '/scrape-batch'
        }
    })

@app.route('/auth/store-user', methods=['POST'])
def store_user():
    """
    Store user data in Firebase Firestore
    Expects JSON: {"username": "john_doe", "password": "password123", "uid": "user123"}
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Request body is required'
            }), 400
        
        username = data.get('username')
        password = data.get('password')
        uid = data.get('uid')
        
        if not username or not password or not uid:
            return jsonify({
                'status': 'error',
                'message': 'Username, password, and uid are required'
            }), 400
        
        # Validate inputs
        if len(username) < 3:
            return jsonify({
                'status': 'error',
                'message': 'Username must be at least 3 characters long'
            }), 400
        
        if len(password) < 6:
            return jsonify({
                'status': 'error',
                'message': 'Password must be at least 6 characters long'
            }), 400
        
        if len(uid) < 1:
            return jsonify({
                'status': 'error',
                'message': 'UID cannot be empty'
            }), 400
        
        # Store user data in Firebase
        result = firebase_auth.store_user_data(username, password, uid)
        
        if 'error' in result:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 400
        
        return jsonify({
            'status': 'success',
            'message': 'User data stored successfully',
            'data': {
                'uid': result['uid'],
                'username': result['username']
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Store user endpoint error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

@app.route('/auth/login', methods=['POST'])
def login():
    """
    Login user with username and password
    Expects JSON: {"username": "john_doe", "password": "password123"}
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Request body is required'
            }), 400
        
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({
                'status': 'error',
                'message': 'Username and password are required'
            }), 400
        
        # Authenticate user
        result = firebase_auth.authenticate_user(username, password)
        
        if 'error' in result:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 401
        
        return jsonify({
            'status': 'success',
            'message': 'Login successful',
            'data': {
                'uid': result['uid'],
                'username': result['username']
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Login endpoint error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

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
