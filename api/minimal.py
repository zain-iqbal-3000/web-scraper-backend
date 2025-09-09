from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import requests
from bs4 import BeautifulSoup
import logging
import os
import re
from datetime import datetime, timezone

app = Flask(__name__)
CORS(app, origins=['*'], allow_headers=['*'], methods=['*'])

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cerebras AI configuration
CEREBRAS_API_KEY = os.environ.get('CEREBRAS_API_KEY', 'csk-rkhkxny26c6rvj32cfd4wtwf8n3w8drncpx9j88dkk66fre6')
CEREBRAS_API_URL = 'https://api.cerebras.ai/v1/chat/completions'

# Firebase configuration
FIREBASE_API_KEY = os.environ.get('FIREBASE_API_KEY', 'AIzaSyC7-xHHI-ip1uThgqc67DRh8ZgWPQZuVgI')
FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID', 'lp-optimization-97f9f')
FIREBASE_AUTH_DOMAIN = f"{FIREBASE_PROJECT_ID}.firebaseapp.com"

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
                # If username not found in Firestore, return basic info
                return {
                    'success': True,
                    'user_id': user_id,
                    'username': email.split('@')[0],  # Fallback username
                    'email': auth_response.get('email', email),
                    'token': id_token
                }
            
            return {
                'success': True,
                'user_id': user_id,
                'username': username_response['username'],
                'email': auth_response.get('email', email),
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
                "created_at": {"timestampValue": datetime.now(timezone.utc).isoformat()}
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
            return {'error': 'Username not found in Firestore'}
        
        return {'username': username}

# Cerebras AI Integration Class
class CerebrasAI:
    def __init__(self):
        self.api_key = CEREBRAS_API_KEY
        self.api_url = CEREBRAS_API_URL
    
    def generate_content_suggestions(self, original_content, content_type, context=""):
        """Generate 10 optimized suggestions for any content type using Cerebras AI"""
        try:
            prompt = self._create_content_optimization_prompt(original_content, content_type, context)
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "model": "llama3.1-8b",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert SEO copywriter and digital marketing specialist. Your job is to create compelling, SEO-optimized content that increases click-through rates and conversions. IMPORTANT: Always respond in the same language as the original content."
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
    
    def _create_content_optimization_prompt(self, content, content_type, context):
        """Create an optimized prompt based on content type"""
        
        def detect_language(text):
            # Simple language detection
            french_words = ['le', 'la', 'les', 'de', 'des', 'du', 'et', 'pour', 'avec', 'sur', 'dans']
            english_words = ['the', 'and', 'for', 'with', 'on', 'in', 'to', 'of', 'a', 'an']
            
            text_lower = text.lower()
            french_count = sum(1 for word in french_words if word in text_lower)
            english_count = sum(1 for word in english_words if word in text_lower)
            
            return "French" if french_count > english_count else "English"
        
        detected_language = detect_language(content)
        
        if detected_language == "French":
            language_instruction = "IMPORTANT: Répondez UNIQUEMENT en français. Utilisez un style français naturel."
        else:
            language_instruction = "IMPORTANT: Respond ONLY in English. Use natural English style."
        
        base_context = f"Website Context: {context if context else 'General website'}\n{language_instruction}"
        
        if content_type == "headline":
            return f"""{base_context}

Original headline: "{content}"

Generate 10 SEO-optimized headline variations that:
1. Are compelling and click-worthy
2. Include relevant keywords
3. Are 50-60 characters for optimal SEO
4. Create urgency or curiosity
5. Match the tone of the original

Format as a numbered list (1-10) with just the headlines."""
        
        elif content_type == "subheadline":
            return f"""{base_context}

Original subheadline: "{content}"

Generate 10 improved subheadline variations that:
1. Support the main headline
2. Add value and clarity
3. Are 80-120 characters
4. Include benefits or features
5. Maintain consistent tone

Format as a numbered list (1-10) with just the subheadlines."""
        
        elif content_type == "description":
            return f"""{base_context}

Original description: "{content}"

Generate 10 enhanced description variations that:
1. Clearly explain the value proposition
2. Include social proof elements
3. Are 120-160 characters for meta descriptions
4. Use action-oriented language
5. Build credibility and trust

Format as a numbered list (1-10) with just the descriptions."""
        
        elif content_type == "cta":
            return f"""{base_context}

Original CTA: "{content}"

Generate 10 high-converting CTA variations that:
1. Create urgency and action
2. Are clear and specific
3. Use power words
4. Are 2-6 words long
5. Focus on benefits

Format as a numbered list (1-10) with just the CTAs."""
        
        else:
            return f"""{base_context}

Original content: "{content}"

Generate 10 optimized variations of this {content_type} that improve engagement and conversion.
Format as a numbered list (1-10)."""
    
    def _parse_suggestions(self, ai_response):
        """Parse AI response to extract clean suggestions list"""
        try:
            lines = ai_response.strip().split('\n')
            suggestions = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Remove numbered list formatting
                if re.match(r'^\d+\.?\s*', line):
                    suggestion = re.sub(r'^\d+\.?\s*', '', line).strip()
                    if suggestion and len(suggestion) > 5:
                        # Remove quotes if present
                        suggestion = suggestion.strip('"').strip("'")
                        suggestions.append(suggestion)
                
                if len(suggestions) >= 10:
                    break
            
            return suggestions[:10] if suggestions else ["No suggestions generated"]
            
        except Exception as e:
            logger.error(f"Error parsing AI suggestions: {str(e)}")
            return ["Error parsing suggestions"]

# Initialize AI and Firebase
cerebras_ai = CerebrasAI()
firebase_auth = FirebaseAuth()

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'success',
        'message': 'Web Scraper API with AI Enhancement and Firebase Auth is working!',
        'version': '5.0.0',
        'endpoints': {
            'health': '/health',
            'test': '/test',
            'scrape': '/scrape',
            'scrape-complete': '/scrape-complete',
            'scrape-ai': '/scrape-ai',
            'register': '/auth/register',
            'login': '/auth/login'
        },
        'ai_features': {
            'headline_optimization': True,
            'subheadline_optimization': True,
            'description_optimization': True,
            'cta_optimization': True,
            'model': 'cerebras-llama3.1-8b'
        },
        'auth_features': {
            'firebase_auth': True,
            'user_registration': True,
            'user_login': True,
            'firestore_storage': True
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

@app.route('/scrape-ai', methods=['POST'])
def scrape_ai():
    """AI-enhanced scraping endpoint with content optimization"""
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
        
        if len(urls) > 3:  # Limit for AI processing
            return jsonify({
                'status': 'error',
                'message': 'Maximum 3 URLs allowed for AI-enhanced scraping'
            }), 400
        
        results = []
        
        for url in urls:
            try:
                # First do regular scraping
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract data
                title = soup.find('title')
                title_text = title.text.strip() if title else ""
                
                h1_tags = soup.find_all('h1')
                headlines = [h1.get_text().strip() for h1 in h1_tags[:3] if h1.get_text().strip()]
                
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
                
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                description = meta_desc.get('content', '').strip() if meta_desc else ''
                
                paragraphs = soup.find_all('p')
                descriptions = [description] if description else []
                for p in paragraphs[:3]:
                    text = p.get_text().strip()
                    if text and len(text) > 20 and len(text) < 300:
                        descriptions.append(text)
                
                cta_elements = []
                buttons = soup.find_all(['button', 'a'], string=True)
                for btn in buttons[:5]:
                    text = btn.get_text().strip()
                    if text and len(text) > 2 and len(text) < 50:
                        cta_elements.append(text)
                
                # Now enhance with AI
                enhanced_data = {
                    'url': url,
                    'title': title_text,
                    'ai_enhanced': True,
                    'processing_timestamp': datetime.now(timezone.utc).isoformat()
                }
                
                # Process headlines with AI
                if headlines:
                    enhanced_headlines = []
                    for headline in headlines[:2]:  # Limit to 2 headlines for performance
                        ai_result = cerebras_ai.generate_content_suggestions(
                            headline, 
                            "headline",
                            context=f"Website: {url}"
                        )
                        
                        headline_data = {
                            'original': headline,
                            'ai_suggestions': ai_result.get('suggestions', []) if 'success' in ai_result else [],
                            'ai_error': ai_result.get('error') if 'error' in ai_result else None
                        }
                        enhanced_headlines.append(headline_data)
                    
                    enhanced_data['headline'] = enhanced_headlines
                
                # Process subheadlines with AI
                if subheadlines:
                    enhanced_subheadlines = []
                    for subheadline in subheadlines[:2]:  # Limit to 2 for performance
                        ai_result = cerebras_ai.generate_content_suggestions(
                            subheadline,
                            "subheadline",
                            context=f"Website: {url}"
                        )
                        
                        subheadline_data = {
                            'original': subheadline,
                            'ai_suggestions': ai_result.get('suggestions', []) if 'success' in ai_result else [],
                            'ai_error': ai_result.get('error') if 'error' in ai_result else None
                        }
                        enhanced_subheadlines.append(subheadline_data)
                    
                    enhanced_data['subheadline'] = enhanced_subheadlines
                
                # Process descriptions with AI
                if descriptions:
                    enhanced_descriptions = []
                    for description in descriptions[:2]:  # Limit to 2 for performance
                        ai_result = cerebras_ai.generate_content_suggestions(
                            description,
                            "description",
                            context=f"Website: {url}"
                        )
                        
                        description_data = {
                            'original': description,
                            'ai_suggestions': ai_result.get('suggestions', []) if 'success' in ai_result else [],
                            'ai_error': ai_result.get('error') if 'error' in ai_result else None
                        }
                        enhanced_descriptions.append(description_data)
                    
                    enhanced_data['description_credibility'] = enhanced_descriptions
                
                # Process CTAs with AI
                if cta_elements:
                    enhanced_ctas = []
                    for cta in cta_elements[:2]:  # Limit to 2 for performance
                        ai_result = cerebras_ai.generate_content_suggestions(
                            cta,
                            "cta",
                            context=f"Website: {url}"
                        )
                        
                        cta_data = {
                            'original': cta,
                            'ai_suggestions': ai_result.get('suggestions', []) if 'success' in ai_result else [],
                            'ai_error': ai_result.get('error') if 'error' in ai_result else None
                        }
                        enhanced_ctas.append(cta_data)
                    
                    enhanced_data['call_to_action'] = enhanced_ctas
                
                results.append(enhanced_data)
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error for {url}: {str(e)}")
                results.append({
                    'url': url,
                    'error': f'Failed to fetch URL: {str(e)}'
                })
            except Exception as e:
                logger.error(f"AI scraping error for {url}: {str(e)}")
                results.append({
                    'url': url,
                    'error': f'AI scraping error: {str(e)}'
                })
        
        return jsonify({
            'status': 'success',
            'data': results if len(results) > 1 else results[0],
            'ai_enhanced': True,
            'processing_info': {
                'total_urls': len(results),
                'ai_model': 'cerebras-llama3.1-8b',
                'suggestions_per_item': 10
            }
        })
        
    except Exception as e:
        logger.error(f"AI scraping API error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'AI scraping error: {str(e)}'
        }), 500

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
        
        if not all([email, password, username]):
            return jsonify({
                'status': 'error',
                'message': 'Email, password, and username are required'
            }), 400
        
        # Basic validation
        if len(password) < 6:
            return jsonify({
                'status': 'error',
                'message': 'Password must be at least 6 characters'
            }), 400
        
        if '@' not in email or '.' not in email:
            return jsonify({
                'status': 'error',
                'message': 'Invalid email format'
            }), 400
        
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
                'email': result['email']
            },
            'token': result['token']
        })
        
    except Exception as e:
        logger.error(f"Registration endpoint error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Registration failed'
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
        
        if not all([email, password]):
            return jsonify({
                'status': 'error',
                'message': 'Email and password are required'
            }), 400
        
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
                'email': result['email']
            },
            'token': result['token']
        })
        
    except Exception as e:
        logger.error(f"Login endpoint error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Login failed'
        }), 500

if __name__ == '__main__':
    app.run(debug=False)
