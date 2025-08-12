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

# Cerebras AI configuration
CEREBRAS_API_KEY = os.environ.get('CEREBRAS_API_KEY', 'csk-t5dtmc52cd435fke365yh26np2fmryhwxwdfkc9mjn236vvp')
CEREBRAS_API_URL = 'https://api.cerebras.ai/v1/chat/completions'

# Firebase Authentication Class
class FirebaseAuth:
    def __init__(self):
        self.api_key = FIREBASE_API_KEY
        self.auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts"
        self.firestore_url = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents"
    
    def register_user(self, email, password, username):
        """Register a new user with Firebase Auth and store username in Firestore"""
        try:
            # Step 1: Create user with Firebase Auth
            auth_response = self._create_firebase_user(email, password)
            if 'error' in auth_response:
                return auth_response
            
            user_id = auth_response['localId']
            id_token = auth_response['idToken']
            
            # Step 2: Store username and email in Firestore
            firestore_response = self._store_user_data_in_firestore(user_id, username, email, id_token)
            if 'error' in firestore_response:
                return firestore_response
            
            return {
                'success': True,
                'user_id': user_id,
                'username': username,
                'email': email,
                'token': id_token
            }
            
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return {'error': 'Registration failed', 'details': str(e)}
    
    def login_user(self, email, password):
        """Login user with Firebase Auth and get username from Firestore"""
        try:
            # Step 1: Authenticate with Firebase Auth
            auth_response = self._authenticate_firebase_user(email, password)
            if 'error' in auth_response:
                return auth_response
            
            user_id = auth_response['localId']
            id_token = auth_response['idToken']
            
            # Step 2: Get username from Firestore
            username_response = self._get_username_from_firestore(user_id, id_token)
            if 'error' in username_response:
                return username_response
            
            return {
                'success': True,
                'user_id': user_id,
                'username': username_response['username'],
                'email': email,
                'token': id_token
            }
            
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return {'error': 'Login failed', 'details': str(e)}
    
    def _create_firebase_user(self, email, password):
        """Create user with Firebase Authentication"""
        url = f"{self.auth_url}:signUp?key={self.api_key}"
        
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }
        
        response = requests.post(url, json=payload)
        data = response.json()
        
        if response.status_code != 200:
            error_message = data.get('error', {}).get('message', 'Unknown error')
            return {'error': f'Firebase Auth error: {error_message}'}
        
        return data
    
    def _authenticate_firebase_user(self, email, password):
        """Authenticate user with Firebase Authentication"""
        url = f"{self.auth_url}:signInWithPassword?key={self.api_key}"
        
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }
        
        response = requests.post(url, json=payload)
        data = response.json()
        
        if response.status_code != 200:
            error_message = data.get('error', {}).get('message', 'Unknown error')
            return {'error': f'Firebase Auth error: {error_message}'}
        
        return data
    
    def _store_user_data_in_firestore(self, user_id, username, email, id_token):
        """Store username and email in Firestore"""
        url = f"{self.firestore_url}/users/{user_id}"
        
        headers = {
            'Authorization': f'Bearer {id_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            "fields": {
                "username": {"stringValue": username},
                "email": {"stringValue": email},
                "created_at": {"timestampValue": datetime.utcnow().isoformat() + "Z"}
            }
        }
        
        response = requests.patch(url, json=payload, headers=headers)
        
        if response.status_code not in [200, 201]:
            return {'error': 'Failed to store user data in Firestore'}
        
        return {'success': True}
    
    def _get_username_from_firestore(self, user_id, id_token):
        """Get username from Firestore"""
        url = f"{self.firestore_url}/users/{user_id}"
        
        headers = {
            'Authorization': f'Bearer {id_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            return {'error': 'Failed to get username from Firestore'}
        
        data = response.json()
        username = data.get('fields', {}).get('username', {}).get('stringValue', '')
        
        if not username:
            return {'error': 'Username not found'}
        
        return {'username': username}
    
    def change_password(self, email, old_password, new_password):
        """Change user password after verifying old password"""
        try:
            # Step 1: Verify old password by attempting authentication
            auth_response = self._authenticate_firebase_user(email, old_password)
            if 'error' in auth_response:
                return {'error': 'Old password is incorrect'}
            
            # Step 2: Change password using Firebase Auth API
            id_token = auth_response['idToken']
            password_change_response = self._update_firebase_password(id_token, new_password)
            if 'error' in password_change_response:
                return password_change_response
            
            return {
                'success': True,
                'message': 'Password changed successfully'
            }
            
        except Exception as e:
            logger.error(f"Change password error: {str(e)}")
            return {'error': 'Password change failed', 'details': str(e)}
    
    def forgot_password(self, email):
        """Send password reset email using Firebase Auth"""
        try:
            # Send password reset email using Firebase Auth API
            reset_response = self._send_password_reset_email(email)
            if 'error' in reset_response:
                return reset_response
            
            return {
                'success': True,
                'message': 'Password reset email sent successfully'
            }
            
        except Exception as e:
            logger.error(f"Forgot password error: {str(e)}")
            return {'error': 'Failed to send password reset email', 'details': str(e)}
    
    def _send_password_reset_email(self, email):
        """Send password reset email using Firebase Auth API"""
        url = f"{self.auth_url}:sendOobCode?key={self.api_key}"
        
        payload = {
            "requestType": "PASSWORD_RESET",
            "email": email
        }
        
        response = requests.post(url, json=payload)
        data = response.json()
        
        if response.status_code != 200:
            error_message = data.get('error', {}).get('message', 'Unknown error')
            
            # Handle specific Firebase error cases
            if 'EMAIL_NOT_FOUND' in error_message:
                return {'error': 'Email address not found'}
            elif 'INVALID_EMAIL' in error_message:
                return {'error': 'Invalid email address format'}
            elif 'USER_DISABLED' in error_message:
                return {'error': 'This account has been disabled'}
            elif 'TOO_MANY_ATTEMPTS_TRY_LATER' in error_message:
                return {'error': 'Too many requests. Please try again later'}
            else:
                return {'error': f'Unable to send password reset email: {error_message}'}
        
        return {'success': True}
    
    def _get_user_info_by_uid(self, uid):
        """Get user info from Firebase Auth using getAccountInfo API"""
        url = f"{self.auth_url}:lookup?key={self.api_key}"
        
        payload = {
            "localId": [uid]
        }
        
        try:
            response = requests.post(url, json=payload)
            data = response.json()
            
            if response.status_code != 200:
                # If lookup fails, try alternative approach using Firestore
                return self._get_email_from_firestore(uid)
            
            users = data.get('users', [])
            if not users:
                return self._get_email_from_firestore(uid)
            
            user = users[0]
            email = user.get('email', '')
            if not email:
                return self._get_email_from_firestore(uid)
                
            return {'email': email}
            
        except Exception as e:
            logger.error(f"Get user info error: {str(e)}")
            return self._get_email_from_firestore(uid)
    
    def _get_email_from_firestore(self, uid):
        """Fallback method to get email from Firestore"""
        url = f"{self.firestore_url}/users/{uid}"
        
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                email = data.get('fields', {}).get('email', {}).get('stringValue', '')
                if email:
                    return {'email': email}
            
            # If still no email found, we'll need to ask user to provide email
            return {'error': 'User email not found. Please provide email for password change.'}
            
        except Exception as e:
            logger.error(f"Firestore lookup error: {str(e)}")
            return {'error': 'Unable to retrieve user information'}
    
    def _update_firebase_password(self, id_token, new_password):
        """Update user password using Firebase Auth API"""
        url = f"{self.auth_url}:update?key={self.api_key}"
        
        payload = {
            "idToken": id_token,
            "password": new_password,
            "returnSecureToken": True
        }
        
        response = requests.post(url, json=payload)
        data = response.json()
        
        if response.status_code != 200:
            error_message = data.get('error', {}).get('message', 'Unknown error')
            return {'error': f'Firebase password update error: {error_message}'}
        
        return {'success': True}

# Cerebras AI Integration Class
class CerebrasAI:
    def __init__(self):
        self.api_key = CEREBRAS_API_KEY
        self.api_url = CEREBRAS_API_URL
    
    def generate_headline_suggestions(self, original_headline, context=""):
        """Generate 10 SEO-optimized headline suggestions using Cerebras AI"""
        try:
            prompt = self._create_headline_optimization_prompt(original_headline, context)
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "model": "llama3.1-8b",  # Cerebras model
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert SEO copywriter and digital marketing specialist. Your job is to create compelling, SEO-optimized headlines that increase click-through rates and conversions."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                "max_tokens": 1000,
                "temperature": 0.8,
                "stream": False
            }
            
            response = requests.post(self.api_url, json=payload, headers=headers)
            data = response.json()
            
            if response.status_code == 200:
                ai_response = data['choices'][0]['message']['content']
                suggestions = self._parse_suggestions(ai_response)
                return {'success': True, 'suggestions': suggestions}
            else:
                logger.error(f"Cerebras AI error: {response.status_code} - {response.text}")
                return {'error': f'AI service error: {response.status_code}'}
                
        except Exception as e:
            logger.error(f"Cerebras AI integration error: {str(e)}")
            return {'error': 'Failed to generate AI suggestions'}
    
    def _create_headline_optimization_prompt(self, headline, context):
        """Create an optimized prompt for headline suggestions"""
        return f"""
Analyze this website headline and provide 10 improved, SEO-optimized alternatives:

Original Headline: "{headline}"
Website Context: {context if context else "General website"}

Requirements for suggestions:
1. More engaging and click-worthy
2. SEO-optimized with relevant keywords
3. Clear value proposition
4. Emotional appeal or urgency
5. Different styles (question-based, benefit-focused, curiosity-driven, etc.)
6. Maintain the core message but improve conversion potential
7. Suitable for different audiences (B2B, B2C, professional, casual)
8. Include power words that drive action
9. Consider current digital marketing trends
10. Each suggestion should be unique and distinct

Format your response as a numbered list (1-10) with just the headline suggestions, no additional explanation.

Example format:
1. [First suggestion]
2. [Second suggestion]
...
10. [Tenth suggestion]
"""
    
    def _parse_suggestions(self, ai_response):
        """Parse AI response to extract clean suggestions list"""
        try:
            lines = ai_response.strip().split('\n')
            suggestions = []
            
            for line in lines:
                line = line.strip()
                # Look for numbered lines (1., 2., etc.)
                if re.match(r'^\d+\.', line):
                    # Remove the number and clean the suggestion
                    suggestion = re.sub(r'^\d+\.\s*', '', line).strip()
                    if suggestion:
                        suggestions.append(suggestion)
            
            # If we don't have exactly 10, try a different parsing approach
            if len(suggestions) != 10:
                # Try to extract any text that looks like headlines
                all_text = ai_response.replace('\n', ' ')
                # This is a fallback - in practice, the AI should follow the format
                suggestions = [s.strip() for s in suggestions if s.strip()][:10]
            
            return suggestions[:10]  # Ensure we return max 10 suggestions
            
        except Exception as e:
            logger.error(f"Error parsing AI suggestions: {str(e)}")
            return []

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
    
    def scrape_website_with_ai(self, url, cerebras_ai):
        """
        Scrape a website and enhance headlines with AI suggestions
        """
        try:
            # First, do the regular scraping
            scraped_data = self.scrape_website(url)
            if 'error' in scraped_data:
                return scraped_data
            
            # Enhance headlines with AI suggestions
            enhanced_data = scraped_data.copy()
            
            # Process headlines
            if scraped_data.get('headline'):
                enhanced_headlines = []
                for headline in scraped_data['headline']:
                    ai_result = cerebras_ai.generate_headline_suggestions(
                        headline, 
                        context=f"Website: {url}"
                    )
                    
                    headline_data = {
                        'original': headline,
                        'ai_suggestions': ai_result.get('suggestions', []) if 'success' in ai_result else [],
                        'ai_error': ai_result.get('error') if 'error' in ai_result else None
                    }
                    enhanced_headlines.append(headline_data)
                
                enhanced_data['headline'] = enhanced_headlines
            
            # Process subheadlines
            if scraped_data.get('subheadline'):
                enhanced_subheadlines = []
                for subheadline in scraped_data['subheadline']:
                    ai_result = cerebras_ai.generate_headline_suggestions(
                        subheadline,
                        context=f"Subheadline from: {url}"
                    )
                    
                    subheadline_data = {
                        'original': subheadline,
                        'ai_suggestions': ai_result.get('suggestions', []) if 'success' in ai_result else [],
                        'ai_error': ai_result.get('error') if 'error' in ai_result else None
                    }
                    enhanced_subheadlines.append(subheadline_data)
                
                enhanced_data['subheadline'] = enhanced_subheadlines
            
            # Add metadata
            enhanced_data['ai_enhanced'] = True
            enhanced_data['processing_timestamp'] = datetime.utcnow().isoformat() + "Z"
            
            return enhanced_data
            
        except Exception as e:
            logger.error(f"AI-enhanced scraping error for {url}: {str(e)}")
            return {'error': f'Failed to scrape website with AI enhancement: {str(e)}'}
    
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

# Initialize scraper, Firebase auth, and AI
scraper = WebScraper()
firebase_auth = FirebaseAuth()
cerebras_ai = CerebrasAI()

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'success',
        'message': 'Web Scraper API with Firebase Auth and AI Enhancement is running',
        'version': '3.0.0',
        'endpoints': {
            'register': '/auth/register',
            'add_user': '/auth/add-user',
            'login': '/auth/login',
            'change_password': '/auth/change-password',
            'forgot_password': '/auth/forgot-password',
            'scrape': '/scrape-batch',
            'scrape_ai': '/scrape-batch-ai'
        },
        'ai_features': {
            'headline_optimization': True,
            'model': 'cerebras-llama3.1-8b',
            'suggestions_per_headline': 10
        }
    })

@app.route('/auth/register', methods=['POST'])
def register():
    """
    Register a new user
    Expects JSON: {"email": "user@example.com", "password": "password123", "username": "john_doe"}
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Request body is required'
            }), 400
        
        email = data.get('email')
        password = data.get('password')
        username = data.get('username')
        
        if not email or not password or not username:
            return jsonify({
                'status': 'error',
                'message': 'Email, password, and username are required'
            }), 400
        
        # Validate email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return jsonify({
                'status': 'error',
                'message': 'Invalid email format'
            }), 400
        
        # Validate password length
        if len(password) < 6:
            return jsonify({
                'status': 'error',
                'message': 'Password must be at least 6 characters long'
            }), 400
        
        # Register user
        result = firebase_auth.register_user(email, password, username)
        
        if 'error' in result:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 400
        
        return jsonify({
            'status': 'success',
            'message': 'User registered successfully',
            'data': {
                'user_id': result['user_id'],
                'username': result['username'],
                'email': result['email'],
                'token': result['token']
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Registration endpoint error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

@app.route('/auth/login', methods=['POST'])
def login():
    """
    Login user
    Expects JSON: {"email": "user@example.com", "password": "password123"}
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Request body is required'
            }), 400
        
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({
                'status': 'error',
                'message': 'Email and password are required'
            }), 400
        
        # Login user
        result = firebase_auth.login_user(email, password)
        
        if 'error' in result:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 401
        
        return jsonify({
            'status': 'success',
            'message': 'Login successful',
            'data': {
                'user_id': result['user_id'],
                'username': result['username'],
                'email': result['email'],
                'token': result['token']
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Login endpoint error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

@app.route('/auth/change-password', methods=['POST'])
def change_password():
    """
    Change user password
    Expects JSON: {"uid": "user_uid", "email": "user@example.com", "old_password": "current_password", "new_password": "new_password"}
    Note: Both UID and email are required for security verification
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Request body is required'
            }), 400
        
        uid = data.get('uid')
        email = data.get('email')
        old_password = data.get('old_password')
        new_password = data.get('new_password')
        
        # Validate required fields
        if not uid or not email or not old_password or not new_password:
            return jsonify({
                'status': 'error',
                'message': 'UID, email, old password, and new password are required'
            }), 400
        
        # Validate new password length
        if len(new_password) < 6:
            return jsonify({
                'status': 'error',
                'message': 'New password must be at least 6 characters long'
            }), 400
        
        # Change password using email
        result = firebase_auth.change_password(email, old_password, new_password)
        
        if 'error' in result:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 400
        
        return jsonify({
            'status': 'success',
            'message': 'Password changed successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Change password endpoint error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

@app.route('/auth/forgot-password', methods=['POST'])
def forgot_password():
    """
    Send password reset email
    Expects JSON: {"email": "user@example.com"}
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Request body is required'
            }), 400
        
        email = data.get('email')
        
        # Validate required fields
        if not email:
            return jsonify({
                'status': 'error',
                'message': 'Email is required'
            }), 400
        
        # Validate email format
        if '@' not in email or '.' not in email.split('@')[-1]:
            return jsonify({
                'status': 'error',
                'message': 'Please provide a valid email address'
            }), 400
        
        # Send password reset email
        result = firebase_auth.forgot_password(email)
        
        if 'error' in result:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 400
        
        return jsonify({
            'status': 'success',
            'message': 'Password reset email sent successfully. Please check your email.'
        }), 200
        
    except Exception as e:
        logger.error(f"Forgot password endpoint error: {str(e)}")
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

@app.route('/scrape-batch-ai', methods=['POST'])
def scrape_batch_ai_endpoint():
    """
    AI-enhanced batch scraping endpoint with headline optimization
    Expects JSON: {"urls": ["https://example1.com", "https://example2.com"]}
    Returns scraped data with AI-generated headline suggestions
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
        
        if len(urls) > 5:  # Limit batch size for AI processing
            return jsonify({
                'status': 'error',
                'message': 'Maximum 5 URLs allowed per AI-enhanced batch due to processing time'
            }), 400
        
        results = []
        for url in urls:
            logger.info(f"Processing URL with AI enhancement: {url}")
            result = scraper.scrape_website_with_ai(url, cerebras_ai)
            results.append(result)
        
        return jsonify({
            'status': 'success',
            'data': results,
            'ai_enhanced': True,
            'processing_info': {
                'total_urls': len(urls),
                'ai_model': 'cerebras-llama3.1-8b',
                'suggestions_per_headline': 10
            }
        })
    
    except Exception as e:
        logger.error(f"AI-enhanced batch API error: {str(e)}")
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
