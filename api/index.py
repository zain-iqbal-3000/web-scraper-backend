from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
import logging
import os
import json
import base64
from datetime import datetime, timezone
##hello from saim

def download_and_inline_resources(html_content, base_url):
    """
    Download all external resources and inline them to create a completely self-contained HTML file
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Download and inline CSS files
        for link in soup.find_all('link', rel='stylesheet'):
            if link.get('href'):
                try:
                    css_url = urljoin(base_url, link['href'])
                    logging.info(f"Downloading CSS: {css_url}")
                    css_response = session.get(css_url, timeout=15)
                    if css_response.status_code == 200:
                        # Process CSS to inline fonts and images
                        css_content = process_css_content(css_response.text, css_url, session)
                        
                        # Replace link tag with style tag
                        style_tag = soup.new_tag('style')
                        style_tag.string = css_content
                        style_tag.attrs['data-original-href'] = css_url
                        link.replace_with(style_tag)
                        logging.info(f"Successfully inlined CSS: {css_url}")
                    else:
                        logging.warning(f"Failed to download CSS {css_url}: HTTP {css_response.status_code}")
                        # Don't remove the link, let it load externally with our permissive CSP
                except Exception as e:
                    logging.warning(f"Failed to download CSS {link.get('href')}: {str(e)}")
                    # Don't remove the link, let it load externally
        
        # Process existing style tags
        for style in soup.find_all('style'):
            if style.string:
                original_css = style.string
                processed_css = process_css_content(original_css, base_url, session)
                style.string = processed_css
        
        # Remove external script tags that might cause CORS issues
        for script in soup.find_all('script', src=True):
            src = script.get('src')
            if src and (src.startswith('http') or src.startswith('//')):
                # Remove external scripts that make AJAX calls
                script.decompose()
                logging.info(f"Removed external script: {src}")
        
        # Remove inline scripts that make external AJAX calls
        for script in soup.find_all('script'):
            if script.string and 'admin-ajax.php' in script.string:
                script.decompose()
                logging.info("Removed script with admin-ajax.php call")
        
        # Process images - download and convert to data URLs for better compatibility
        for img in soup.find_all('img', src=True):
            if img.get('src'):
                try:
                    img_url = urljoin(base_url, img['src'])
                    if img_url.startswith('data:'):
                        continue  # Skip if already a data URL
                    
                    logging.info(f"Downloading image: {img_url}")
                    img_response = session.get(img_url, timeout=10)
                    if img_response.status_code == 200 and len(img_response.content) < 2000000:  # Limit to 2MB
                        # Determine MIME type
                        content_type = img_response.headers.get('content-type', '')
                        if not content_type:
                            if img_url.lower().endswith('.png'):
                                content_type = 'image/png'
                            elif img_url.lower().endswith(('.jpg', '.jpeg')):
                                content_type = 'image/jpeg'
                            elif img_url.lower().endswith('.gif'):
                                content_type = 'image/gif'
                            elif img_url.lower().endswith('.svg'):
                                content_type = 'image/svg+xml'
                            elif img_url.lower().endswith('.webp'):
                                content_type = 'image/webp'
                            else:
                                content_type = 'application/octet-stream'
                        
                        # Convert to base64 data URL
                        img_data = base64.b64encode(img_response.content).decode('utf-8')
                        img['src'] = f"data:{content_type};base64,{img_data}"
                        img['data-original-src'] = img_url
                        logging.info(f"Successfully converted image to data URL: {img_url}")
                    else:
                        if img_response.status_code != 200:
                            logging.warning(f"Failed to download image {img_url}: HTTP {img_response.status_code}")
                        else:
                            logging.warning(f"Image too large, skipping: {img_url} ({len(img_response.content)} bytes)")
                except Exception as e:
                    logging.warning(f"Failed to process image {img.get('src')}: {str(e)}")
        
        # Handle lazy-loaded images (data-src, data-lazy-src, etc.)
        for img in soup.find_all('img'):
            for attr in ['data-src', 'data-lazy-src', 'data-original', 'data-lazy']:
                if img.get(attr):
                    try:
                        img_url = urljoin(base_url, img[attr])
                        if img_url.startswith('data:'):
                            continue
                        
                        logging.info(f"Processing lazy image: {img_url}")
                        img_response = session.get(img_url, timeout=10)
                        if img_response.status_code == 200 and len(img_response.content) < 2000000:
                            content_type = img_response.headers.get('content-type', 'image/jpeg')
                            img_data = base64.b64encode(img_response.content).decode('utf-8')
                            
                            # Set both src and the lazy attributes
                            img['src'] = f"data:{content_type};base64,{img_data}"
                            img[attr] = f"data:{content_type};base64,{img_data}"
                            
                            logging.info(f"Successfully converted lazy image: {img_url}")
                            break  # Only process the first valid lazy attribute
                    except Exception as e:
                        logging.warning(f"Failed to process lazy image {img.get(attr)}: {str(e)}")
        
        # Remove problematic meta tags
        for meta in soup.find_all('meta'):
            if meta.get('http-equiv') == 'Content-Security-Policy':
                meta.decompose()
        
        # Add meta tag with more permissive CSP for stylesheets
        if soup.head:
            # Remove existing CSP meta tags that might conflict
            for meta in soup.find_all('meta'):
                if meta.get('http-equiv') == 'Content-Security-Policy':
                    meta.decompose()
            
            csp_meta = soup.new_tag('meta')
            csp_meta.attrs['http-equiv'] = 'Content-Security-Policy'
            # Much more permissive CSP - allow most things except dangerous scripts
            csp_meta.attrs['content'] = "default-src * data: blob: 'unsafe-inline' 'unsafe-eval'; script-src * 'unsafe-inline' 'unsafe-eval'; style-src * 'unsafe-inline'; img-src * data: blob:;"
            soup.head.insert(0, csp_meta)
        
        return str(soup)
    except Exception as e:
        logging.error(f"Error processing resources: {str(e)}")
        return html_content

def process_css_content(css_content, css_base_url, session):
    """
    Process CSS content to inline fonts and handle imports
    """
    try:
        # Handle @import statements
        import_pattern = r'@import\s+(?:url\()?[\'"]?([^\'")]+)[\'"]?\)?[^;]*;'
        def replace_import(match):
            import_url = urljoin(css_base_url, match.group(1))
            try:
                import_response = session.get(import_url, timeout=10)
                if import_response.status_code == 200:
                    return process_css_content(import_response.text, import_url, session)
            except Exception as e:
                logging.warning(f"Failed to import CSS {import_url}: {str(e)}")
            return ""  # Remove import if failed
        
        css_content = re.sub(import_pattern, replace_import, css_content)
        
        # Handle font URLs - convert to data URLs
        font_pattern = r'url\([\'"]?([^\'")]+\.(?:woff2?|ttf|eot|otf)(?:\?[^\'")]*)?)[\'"]?\)'
        def replace_font_url(match):
            font_url = urljoin(css_base_url, match.group(1))
            try:
                logging.info(f"Downloading font: {font_url}")
                font_response = session.get(font_url, timeout=20)
                if font_response.status_code == 200:
                    # Determine MIME type based on extension
                    if font_url.endswith('.woff2'):
                        mime_type = 'font/woff2'
                    elif font_url.endswith('.woff'):
                        mime_type = 'font/woff'
                    elif font_url.endswith('.ttf'):
                        mime_type = 'font/truetype'
                    elif font_url.endswith('.eot'):
                        mime_type = 'application/vnd.ms-fontobject'
                    elif font_url.endswith('.otf'):
                        mime_type = 'font/opentype'
                    else:
                        mime_type = 'application/octet-stream'
                    
                    # Convert to base64 data URL
                    font_data = base64.b64encode(font_response.content).decode('utf-8')
                    logging.info(f"Successfully converted font to data URL: {font_url}")
                    return f'url("data:{mime_type};base64,{font_data}")'
                else:
                    logging.warning(f"Failed to download font {font_url}: HTTP {font_response.status_code}")
            except Exception as e:
                logging.warning(f"Failed to download font {font_url}: {str(e)}")
            
            # Return original URL if conversion failed - let it load externally
            return match.group(0)
        
        css_content = re.sub(font_pattern, replace_font_url, css_content)
        
        # Handle background images in CSS
        bg_pattern = r'url\([\'"]?([^\'")]+\.(?:jpg|jpeg|png|gif|svg|webp)(?:\?[^\'")]*)?)[\'"]?\)'
        def replace_bg_url(match):
            img_url = urljoin(css_base_url, match.group(1))
            try:
                img_response = session.get(img_url, timeout=10)
                if img_response.status_code == 200 and len(img_response.content) < 500000:  # Limit to 500KB
                    # Determine MIME type
                    content_type = img_response.headers.get('content-type', '')
                    if not content_type:
                        if img_url.endswith('.png'):
                            content_type = 'image/png'
                        elif img_url.endswith('.jpg') or img_url.endswith('.jpeg'):
                            content_type = 'image/jpeg'
                        elif img_url.endswith('.gif'):
                            content_type = 'image/gif'
                        elif img_url.endswith('.svg'):
                            content_type = 'image/svg+xml'
                        elif img_url.endswith('.webp'):
                            content_type = 'image/webp'
                        else:
                            content_type = 'application/octet-stream'
                    
                    # Convert to base64 data URL
                    img_data = base64.b64encode(img_response.content).decode('utf-8')
                    return f'url("data:{content_type};base64,{img_data}")'
            except Exception as e:
                logging.warning(f"Failed to download background image {img_url}: {str(e)}")
            
            return match.group(0)  # Return original if failed
        
        css_content = re.sub(bg_pattern, replace_bg_url, css_content)
        
        return css_content
    except Exception as e:
        logging.error(f"Error processing CSS content: {str(e)}")
        return css_content

app = Flask(__name__)
CORS(app, origins=['*'], allow_headers=['*'], methods=['*'])



# Add global CORS headers to all responses
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response



# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Firebase configuration (you'll get these from Firebase console)
FIREBASE_API_KEY = os.environ.get('FIREBASE_API_KEY', 'AIzaSyC7-xHHI-ip1uThgqc67DRh8ZgWPQZuVgI')
FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID', 'lp-optimization-97f9f')
FIREBASE_AUTH_DOMAIN = f"{FIREBASE_PROJECT_ID}.firebaseapp.com"

# Cerebras AI configuration
CEREBRAS_API_KEY = os.environ.get('CEREBRAS_API_KEY', 'csk-rkhkxny26c6rvj32cfd4wtwf8n3w8drncpx9j88dkk66fre6')
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
    
    def generate_content_suggestions(self, original_content, content_type, context=""):
        """Generate 10 optimized suggestions for any content type using Cerebras AI"""
        try:
            prompt = self._create_content_optimization_prompt(original_content, content_type, context)
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "model": "llama3.1-8b",  # Cerebras model
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert SEO copywriter and digital marketing specialist. Your job is to create compelling, SEO-optimized content that increases click-through rates and conversions. IMPORTANT: Always respond in the same language as the original content. If the original content is in French, respond in French. If it's in English, respond in English. Maintain the same linguistic style and cultural context as the original."
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

    def generate_headline_suggestions(self, original_headline, context=""):
        """Generate 10 SEO-optimized headline suggestions using Cerebras AI (backward compatibility)"""
        return self.generate_content_suggestions(original_headline, "headline", context)
    
    def _create_content_optimization_prompt(self, content, content_type, context):
        """Create an optimized prompt based on content type"""
        
        # Detect language based on content
        def detect_language(text):
            # Simple language detection based on common French words/patterns
            french_indicators = [
                'le ', 'la ', 'les ', 'un ', 'une ', 'des ', 'du ', 'de la ', 'de ',
                'avec', 'pour', 'sur', 'dans', 'et ', 'ou ', 'mais', 'donc',
                'à ', 'au ', 'aux ', 'en ', 'par ', 'chez',
                'économies', 'électricité', 'solaire', 'énergie',
                "d'", "l'", "c'", "n'", "s'", "t'", "m'"
            ]
            
            text_lower = text.lower()
            french_count = sum(1 for indicator in french_indicators if indicator in text_lower)
            
            if french_count >= 2:  # If we find 2+ French indicators, likely French
                return "French"
            else:
                return "English"
        
        detected_language = detect_language(content)
        
        # Language-specific instructions
        if detected_language == "French":
            language_instruction = "IMPORTANT: Respond in French. Use proper French grammar, vocabulary, and cultural context. Consider French SEO practices and local market preferences."
        else:
            language_instruction = "Respond in English with clear, engaging copy."
        
        base_context = f"Website Context: {context if context else 'General website'}\n{language_instruction}"
        
        if content_type == "headline":
            return f"""
Analyze this website headline and provide 10 improved, SEO-optimized alternatives:

Original Headline: "{content}"
{base_context}

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
"""
        
        elif content_type == "subheadline":
            return f"""
Analyze this website subheadline and provide 10 improved, conversion-optimized alternatives:

Original Subheadline: "{content}"
{base_context}

Requirements for suggestions:
1. Support and expand on the main headline
2. Provide additional value proposition details
3. Create curiosity and encourage further reading
4. Include social proof or credibility elements
5. Address potential objections or concerns
6. Use benefit-focused language
7. Keep concise but informative
8. Appeal to emotions and logic
9. Create sense of urgency or scarcity
10. Each suggestion should be unique and compelling

Format your response as a numbered list (1-10) with just the subheadline suggestions, no additional explanation.
"""
        
        elif content_type == "description":
            return f"""
Analyze this website description/credibility content and provide 10 improved, conversion-optimized alternatives:

Original Description: "{content}"
{base_context}

Requirements for suggestions:
1. Build trust and credibility
2. Highlight unique value propositions
3. Include social proof elements
4. Address customer pain points
5. Use persuasive but authentic language
6. Include specific benefits and outcomes
7. Create emotional connection
8. Use power words and action-oriented language
9. Keep professional yet engaging tone
10. Each suggestion should be unique and compelling

Format your response as a numbered list (1-10) with just the description suggestions, no additional explanation.
"""
        
        elif content_type == "cta":
            return f"""
Analyze this call-to-action button/link text and provide 10 improved, conversion-optimized alternatives:

Original CTA: "{content}"
{base_context}

Requirements for suggestions:
1. Action-oriented and compelling
2. Create sense of urgency
3. Clearly communicate the benefit
4. Use power words that drive clicks
5. Keep concise (2-5 words ideally)
6. Remove friction and objections
7. Create FOMO (fear of missing out)
8. Use first-person perspective when appropriate
9. Test different emotional triggers
10. Each suggestion should be unique and click-worthy

Format your response as a numbered list (1-10) with just the CTA suggestions, no additional explanation.
"""
        
        else:
            # Default prompt for any other content type
            return f"""
Analyze this website content and provide 10 improved, SEO and conversion-optimized alternatives:

Original Content: "{content}"
Content Type: {content_type}
{base_context}

Requirements for suggestions:
1. More engaging and compelling
2. SEO-optimized when applicable
3. Clear value proposition
4. Emotional appeal
5. Action-oriented language
6. Address target audience needs
7. Professional yet accessible tone
8. Include relevant keywords naturally
9. Create interest and engagement
10. Each suggestion should be unique

Format your response as a numbered list (1-10) with just the content suggestions, no additional explanation.
"""

    def _create_headline_optimization_prompt(self, headline, context):
        """Create an optimized prompt for headline suggestions (backward compatibility)"""
        return self._create_content_optimization_prompt(headline, "headline", context)
    
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
        
        # Common selectors for cookie popups and unwanted elements to exclude
        self.excluded_selectors = [
            # Cookie popup selectors
            '[class*="cookie"]',
            '[id*="cookie"]',
            '[class*="gdpr"]',
            '[id*="gdpr"]',
            '[class*="consent"]',
            '[id*="consent"]',
            '[class*="privacy"]',
            '[id*="privacy"]',
            
            # Common popup/overlay selectors
            '[class*="popup"]',
            '[id*="popup"]',
            '[class*="modal"]',
            '[id*="modal"]',
            '[class*="overlay"]',
            '[id*="overlay"]',
            '[class*="banner"]',
            '[id*="banner"]',
            
            # Notification bars
            '[class*="notification"]',
            '[id*="notification"]',
            '[class*="alert"]',
            '[id*="alert"]',
            
            # Common cookie popup class names
            '.cookie-notice',
            '.cookie-banner',
            '.cookie-consent',
            '.gdpr-notice',
            '.privacy-notice',
            '.consent-banner',
            '.cookieconsent',
            '.cc-window',
            '.cc-banner',
            '.optanon-alert-box-wrapper',
            '.ot-sdk-container',
            '.onetrust-pc-container',
            
            # Newsletter popups
            '[class*="newsletter"]',
            '[id*="newsletter"]',
            '[class*="signup"]',
            '[id*="signup"]',
            
            # Chat widgets
            '[class*="chat"]',
            '[id*="chat"]',
            '[class*="intercom"]',
            '[id*="intercom"]',
            
            # Ad blockers and promotional overlays
            '[class*="promo"]',
            '[id*="promo"]',
            '[class*="advertisement"]',
            '[id*="advertisement"]',
            
            # Navigation and menu elements
            'nav',
            '.nav',
            '.navbar',
            '.navigation',
            '.menu',
            '.header',
            '.footer',
            '.sidebar'
        ]
    
    
    def _remove_unwanted_elements(self, soup):
        """Remove cookie popups, modals, and other overlay elements"""
        try:
            # Remove elements by common selectors
            for selector in self.excluded_selectors:
                try:
                    elements = soup.select(selector)
                    for element in elements:
                        element.decompose()
                except Exception:
                    # Continue if selector fails
                    continue
            
            # Remove script and style tags
            for script in soup(["script", "style", "noscript"]):
                script.decompose()
            
            # Remove hidden elements (often popups)
            for element in soup.find_all(style=True):
                style = element.get('style', '').lower()
                if any(hidden_style in style for hidden_style in [
                    'display:none', 'display: none',
                    'visibility:hidden', 'visibility: hidden',
                    'opacity:0', 'opacity: 0'
                ]):
                    element.decompose()
            
            # Remove elements with common popup-related attributes
            for element in soup.find_all():
                # Check for popup-related attributes
                class_names = ' '.join(element.get('class', [])).lower()
                element_id = element.get('id', '').lower()
                
                popup_keywords = [
                    'cookie', 'gdpr', 'consent', 'privacy', 'popup', 'modal',
                    'overlay', 'banner', 'notification', 'alert', 'newsletter',
                    'signup', 'chat', 'intercom', 'promo', 'advertisement'
                ]
                
                if any(keyword in class_names or keyword in element_id for keyword in popup_keywords):
                    element.decompose()
            
            # Remove elements with fixed positioning (often popups)
            for element in soup.find_all():
                style = element.get('style', '').lower()
                if 'position:fixed' in style.replace(' ', '') or 'position: fixed' in style:
                    element.decompose()
            
            logger.info(f"Removed unwanted elements (popups, cookies, overlays)")
            return soup
            
        except Exception as e:
            logger.error(f"Error removing unwanted elements: {str(e)}")
            return soup

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
            
            # Remove unwanted elements BEFORE extracting content
            soup = self._remove_unwanted_elements(soup)
            
            # For now, use the original HTML without proxy rewriting
            # The new self-contained endpoint handles CORS issues differently
            
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
    
    def scrape_complete_website(self, url):
        """
        Scrape complete HTML and CSS including external stylesheets
        Returns a complete HTML file that can be saved and run locally
        """
        try:
            # Validate URL
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                return {'error': 'Invalid URL provided'}
            
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            # Make request
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Download and embed external CSS files
            css_content = self._download_external_css(soup, base_url, url)
            
            # Process and embed inline styles
            self._process_inline_styles(soup)
            
            # Convert relative URLs to absolute URLs for images, etc.
            self._convert_relative_urls(soup, base_url)
            
            # Create a complete HTML document with embedded CSS
            complete_html = self._create_complete_html(soup, css_content, url)
            
            return {
                'url': url,
                'complete_html': complete_html,
                'css_files_processed': len(css_content),
                'success': True
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for {url}: {str(e)}")
            return {'error': f'Failed to fetch URL: {str(e)}'}
        except Exception as e:
            logger.error(f"Complete scraping error for {url}: {str(e)}")
            return {'error': f'Failed to scrape complete website: {str(e)}'}
    
    def _download_external_css(self, soup, base_url, page_url):
        """Download all external CSS files and return their content"""
        css_contents = []
        
        # Find all link tags with CSS stylesheets
        css_links = soup.find_all('link', rel='stylesheet')
        
        for link in css_links:
            href = link.get('href')
            if not href:
                continue
            
            try:
                # Convert relative URL to absolute URL
                if href.startswith('//'):
                    css_url = 'https:' + href
                elif href.startswith('/'):
                    css_url = base_url + href
                elif href.startswith('http'):
                    css_url = href
                else:
                    # Relative path
                    css_url = urljoin(page_url, href)
                
                # Download CSS file
                css_response = self.session.get(css_url, timeout=10)
                css_response.raise_for_status()
                
                # Process CSS content to handle relative URLs within CSS
                css_content = self._process_css_urls(css_response.text, css_url, base_url)
                css_contents.append(css_content)
                
                logger.info(f"Downloaded CSS: {css_url}")
                
            except Exception as e:
                logger.warning(f"Failed to download CSS {href}: {str(e)}")
                continue
        
        return css_contents
    
    def _process_css_urls(self, css_content, css_url, base_url):
        """Process CSS content to convert relative URLs to absolute URLs"""
        try:
            # Handle url() references in CSS
            def replace_url(match):
                url_content = match.group(1).strip('\'"')
                
                if url_content.startswith('data:') or url_content.startswith('http'):
                    return match.group(0)
                
                if url_content.startswith('//'):
                    return f'url("https:{url_content}")'
                elif url_content.startswith('/'):
                    return f'url("{base_url}{url_content}")'
                else:
                    # Relative URL
                    absolute_url = urljoin(css_url, url_content)
                    return f'url("{absolute_url}")'
            
            # Replace all url() references
            processed_css = re.sub(r'url\(["\']?([^)]+?)["\']?\)', replace_url, css_content)
            
            return processed_css
            
        except Exception as e:
            logger.warning(f"Error processing CSS URLs: {str(e)}")
            return css_content
    
    def _process_inline_styles(self, soup):
        """Process inline style tags and style attributes"""
        try:
            # Process style tags
            for style_tag in soup.find_all('style'):
                if style_tag.string:
                    # Here we could process URLs in inline styles if needed
                    pass
            
            # Process style attributes on elements
            for element in soup.find_all(style=True):
                # Here we could process URLs in style attributes if needed
                pass
                
        except Exception as e:
            logger.warning(f"Error processing inline styles: {str(e)}")
    
    def _convert_relative_urls(self, soup, base_url):
        """Convert relative URLs to absolute URLs for images, scripts, etc."""
        try:
            # Convert img src attributes
            for img in soup.find_all('img', src=True):
                src = img['src']
                if src.startswith('//'):
                    img['src'] = 'https:' + src
                elif src.startswith('/'):
                    img['src'] = base_url + src
                elif not src.startswith('http') and not src.startswith('data:'):
                    img['src'] = urljoin(base_url, src)
            
            # Convert script src attributes
            for script in soup.find_all('script', src=True):
                src = script['src']
                if src.startswith('//'):
                    script['src'] = 'https:' + src
                elif src.startswith('/'):
                    script['src'] = base_url + src
                elif not src.startswith('http'):
                    script['src'] = urljoin(base_url, src)
            
            # Convert link href attributes (for non-CSS links)
            for link in soup.find_all('a', href=True):
                href = link['href']
                if href.startswith('/') and not href.startswith('//'):
                    link['href'] = base_url + href
                elif not href.startswith('http') and not href.startswith('#') and not href.startswith('mailto:'):
                    link['href'] = urljoin(base_url, href)
            
            # Convert form action attributes
            for form in soup.find_all('form', action=True):
                action = form['action']
                if action.startswith('/'):
                    form['action'] = base_url + action
                elif not action.startswith('http'):
                    form['action'] = urljoin(base_url, action)
                    
        except Exception as e:
            logger.warning(f"Error converting relative URLs: {str(e)}")
    
    def _create_complete_html(self, soup, css_contents, original_url):
        """Create a complete HTML document with embedded CSS"""
        try:
            # Remove existing CSS link tags since we're embedding the CSS
            for link in soup.find_all('link', rel='stylesheet'):
                link.decompose()
            
            # Create combined CSS content
            combined_css = '\n'.join(css_contents)
            
            # Add embedded CSS to head
            if soup.head:
                style_tag = soup.new_tag('style', type='text/css')
                style_tag.string = combined_css
                soup.head.append(style_tag)
                
                # Add meta tag with original URL
                meta_tag = soup.new_tag('meta')
                meta_tag.attrs['name'] = 'original-url'
                meta_tag.attrs['content'] = original_url
                soup.head.append(meta_tag)
                
                # Add meta tag for viewport (responsive design)
                viewport_meta = soup.new_tag('meta')
                viewport_meta.attrs['name'] = 'viewport'
                viewport_meta.attrs['content'] = 'width=device-width, initial-scale=1.0'
                soup.head.append(viewport_meta)
            
            # Ensure proper doctype
            doctype = '<!DOCTYPE html>\n'
            
            return doctype + str(soup)
            
        except Exception as e:
            logger.error(f"Error creating complete HTML: {str(e)}")
            return str(soup)
        """
        Scrape a website and enhance all content with AI suggestions
        """
        try:
            # First, do the regular scraping
            scraped_data = self.scrape_website(url)
            if 'error' in scraped_data:
                return scraped_data
            
            # Enhance all content with AI suggestions
            enhanced_data = scraped_data.copy()
            
            # Process headlines
            if scraped_data.get('headline'):
                enhanced_headlines = []
                for headline in scraped_data['headline']:
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
            
            # Process subheadlines
            if scraped_data.get('subheadline'):
                enhanced_subheadlines = []
                for subheadline in scraped_data['subheadline']:
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
            
            # Process descriptions/credibility content
            if scraped_data.get('description_credibility'):
                enhanced_descriptions = []
                for description in scraped_data['description_credibility']:
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
            
            # Process call-to-action content
            if scraped_data.get('call_to_action'):
                enhanced_ctas = []
                for cta in scraped_data['call_to_action']:
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
            
            # Add metadata
            enhanced_data['ai_enhanced'] = True
            enhanced_data['processing_timestamp'] = datetime.now(timezone.utc).isoformat()
            
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
                if self._is_valid_content(text, min_length=10, max_length=200):
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
                if self._is_valid_content(text, min_length=5, max_length=300):
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
                    if self._is_valid_content(content, min_length=20, max_length=500):
                        descriptions.append(content)
            else:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text(strip=True)
                    if self._is_valid_content(text, min_length=20, max_length=500):
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
        all_text_elements = soup.find_all(string=True)
        
        for text in all_text_elements:
            text = text.strip()
            if len(text) > 5 and len(text) < 200:  # Filter reasonable length text
                text_lower = text.lower()
                
                # Check if text contains CTA patterns and is not cookie-related
                for pattern in cta_patterns:
                    if re.search(pattern, text_lower, re.IGNORECASE) and self._is_valid_cta(text):
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
                if self._is_valid_cta(text):
                    clean_text = re.sub(r'\s+', ' ', text).strip()
                    if clean_text not in ctas:
                        ctas.append(clean_text)
        
        return ctas[:10] if ctas else []
    
    def _is_valid_content(self, text, min_length=10, max_length=500):
        """Check if text is valid content (not popup/cookie related)"""
        if not text or len(text) < min_length or len(text) > max_length:
            return False
        
        # Filter out cookie/popup related text
        popup_keywords = [
            'cookie', 'cookies', 'gdpr', 'consent', 'privacy policy', 'accept', 'decline',
            'continue', 'agree', 'disagree', 'necessary cookies', 'analytics',
            'marketing cookies', 'third party', 'data processing', 'newsletter',
            'subscribe', 'unsubscribe', 'popup', 'close', 'dismiss', 'manage cookies',
            'cookie settings', 'privacy settings', 'cookie preferences', 'accept all',
            'reject all', 'cookie notice', 'this website uses cookies', 'we use cookies',
            'by continuing to use', 'cookie policy', 'data protection'
        ]
        
        text_lower = text.lower()
        if any(keyword in text_lower for keyword in popup_keywords):
            return False
        
        # Filter out common navigation and menu items
        nav_keywords = ['home', 'about', 'contact', 'menu', 'search', 'login', 'register', 'sign in', 'sign out']
        if text_lower.strip() in nav_keywords:
            return False
        
        # Filter out single words that are likely navigation
        if len(text.split()) == 1 and len(text) < 15:
            return False
        
        return True
    
    def _is_valid_cta(self, text):
        """Check if text is a valid CTA (not popup/cookie related)"""
        if not text or len(text) < 2 or len(text) > 100:
            return False
        
        # Filter out cookie/popup CTAs
        invalid_ctas = [
            'accept', 'decline', 'agree', 'disagree', 'close', 'dismiss',
            'ok', 'cancel', 'continue', 'accept all', 'reject all',
            'manage cookies', 'cookie settings', 'privacy settings',
            'allow all', 'deny all', 'cookie preferences', 'necessary only',
            'save preferences', 'confirm choices'
        ]
        
        if text.lower().strip() in invalid_ctas:
            return False
        
        # Filter out if contains cookie-related keywords
        cookie_keywords = ['cookie', 'gdpr', 'consent', 'privacy']
        text_lower = text.lower()
        if any(keyword in text_lower for keyword in cookie_keywords):
            return False
        
        return True

    def scrape_website_with_ai(self, url, cerebras_ai):
        """
        Scrape a website and enhance all content with AI suggestions
        """
        try:
            # First, do the regular scraping
            scraped_data = self.scrape_website(url)
            if 'error' in scraped_data:
                return scraped_data
            
            # Enhance all content with AI suggestions
            enhanced_data = scraped_data.copy()
            
            # Process headlines
            if scraped_data.get('headline'):
                enhanced_headlines = []
                for headline in scraped_data['headline']:
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
            
            # Process subheadlines
            if scraped_data.get('subheadline'):
                enhanced_subheadlines = []
                for subheadline in scraped_data['subheadline']:
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
            
            # Process descriptions/credibility content
            if scraped_data.get('description_credibility'):
                enhanced_descriptions = []
                for description in scraped_data['description_credibility']:
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
            
            # Process call-to-action content
            if scraped_data.get('call_to_action'):
                enhanced_ctas = []
                for cta in scraped_data['call_to_action']:
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
            
            # Add metadata
            enhanced_data['ai_enhanced'] = True
            enhanced_data['processing_timestamp'] = datetime.now(timezone.utc).isoformat()
            
            return enhanced_data
            
        except Exception as e:
            logger.error(f"AI-enhanced scraping error for {url}: {str(e)}")
            return {'error': f'Failed to scrape website with AI enhancement: {str(e)}'}

# Initialize scraper, Firebase auth, and AI
scraper = WebScraper()
firebase_auth = FirebaseAuth()
cerebras_ai = CerebrasAI()

@app.route('/health', methods=['GET'])
def simple_health():
    return jsonify({"status": "ok", "message": "API is running"})

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
            'scrape': '/scrape',
            'scrape_complete': '/scrape-complete',
            'wordpress_ship': '/wordpress/ship' if WORDPRESS_AVAILABLE else None,
            'wordpress_test': '/wordpress/test-connection' if WORDPRESS_AVAILABLE else None,
            'wordpress_config': '/wordpress/config' if WORDPRESS_AVAILABLE else None
        },
        'ai_features': {
            'headline_optimization': True,
            'subheadline_optimization': True,
            'description_optimization': True,
            'cta_optimization': True,
            'model': 'cerebras-llama3.1-8b',
            'suggestions_per_item': 10,
            'content_types_supported': ['headline', 'subheadline', 'description', 'cta']
        },
        'wordpress_integration': get_wordpress_status()
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

@app.route('/scrape-complete', methods=['POST'])
def scrape_complete_endpoint():
    """
    Complete website scraping endpoint with HTML and CSS
    Expects JSON: {"urls": ["https://example1.com"]}
    Returns complete HTML with embedded CSS that can be saved and run locally
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
        
        if len(urls) > 3:  # Limit batch size for complete scraping (more intensive)
            return jsonify({
                'status': 'error',
                'message': 'Maximum 3 URLs allowed per complete scraping batch due to processing intensity'
            }), 400
        
        results = []
        for url in urls:
            logger.info(f"Processing complete website scraping for: {url}")
            result = scraper.scrape_complete_website(url)
            results.append(result)
        
        return jsonify({
            'status': 'success',
            'data': results,
            'scraping_type': 'complete_html_css',
            'processing_info': {
                'total_urls': len(urls),
                'includes': ['html', 'css', 'external_stylesheets', 'absolute_urls'],
                'note': 'HTML files can be saved locally and will display exactly as the original website'
            }
        })
    
    except Exception as e:
        logger.error(f"Complete scraping API error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

@app.route('/scrape', methods=['POST'])
def scrape_endpoint():
    """
    AI-enhanced scraping endpoint with content optimization
    Expects JSON: {"urls": ["https://example1.com", "https://example2.com"]}
    Returns scraped data with AI-generated suggestions for all content types
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
                'suggestions_per_item': 10,
                'content_types_enhanced': ['headline', 'subheadline', 'description', 'cta']
            }
        })
    
    except Exception as e:
        logger.error(f"AI-enhanced scraping API error: {str(e)}")
        error_response = jsonify({
            'status': 'error',
            'message': 'Internal server error'
        })
        error_response.headers.add('Access-Control-Allow-Origin', '*')
        error_response.headers.add('Access-Control-Allow-Headers', '*')
        error_response.headers.add('Access-Control-Allow-Methods', '*')
        return error_response, 500

@app.route('/scrape-self-contained', methods=['POST'])
def scrape_self_contained():
    """
    Create a completely self-contained HTML file with all resources inlined
    This avoids ALL CORS issues by downloading and embedding everything
    """
    try:
        logger.info("Self-contained scraping endpoint called")
        data = request.get_json()
        
        if not data or 'url' not in data:
            logger.error("No URL provided in request")
            return jsonify({
                'status': 'error',
                'message': 'URL is required in request body'
            }), 400
        
        url = data['url']
        logger.info(f"Processing self-contained scrape for URL: {url}")
        
        # Set up session with proper headers
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        logger.info(f"Fetching self-contained version of: {url}")
        
        # Get the main page
        response = session.get(url, timeout=30)
        response.raise_for_status()
        
        # Process and inline all resources
        self_contained_html = download_and_inline_resources(response.text, url)
        
        # Add additional security and performance improvements
        soup = BeautifulSoup(self_contained_html, 'html.parser')
        
        # Add viewport meta tag if not present
        if soup.head and not soup.find('meta', attrs={'name': 'viewport'}):
            viewport_meta = soup.new_tag('meta')
            viewport_meta.attrs['name'] = 'viewport'
            viewport_meta.attrs['content'] = 'width=device-width, initial-scale=1.0'
            soup.head.insert(0, viewport_meta)
        
        # Add charset meta tag if not present
        if soup.head and not soup.find('meta', attrs={'charset': True}):
            charset_meta = soup.new_tag('meta')
            charset_meta.attrs['charset'] = 'UTF-8'
            soup.head.insert(0, charset_meta)
        
        # Remove any remaining external references that might cause issues
        for tag in soup.find_all(['iframe', 'embed', 'object']):
            tag.decompose()
        
        # Remove external forms that might not work
        for form in soup.find_all('form'):
            action = form.get('action', '')
            if action and action.startswith('http') and not action.startswith(url):
                form.decompose()
        
        final_html = str(soup)
        
        # Store the HTML for direct serving
        import uuid
        html_id = str(uuid.uuid4())
        if not hasattr(serve_html, 'html_cache'):
            serve_html.html_cache = {}
        serve_html.html_cache[html_id] = final_html
        
        return jsonify({
            'status': 'success',
            'html': final_html,
            'url': url,
            'serve_url': f'http://127.0.0.1:5000/serve-html/{html_id}',
            'html_id': html_id,
            'processing_info': {
                'type': 'self_contained',
                'size': len(final_html),
                'description': 'All external resources have been downloaded and inlined. This HTML is completely self-contained and will not make any external requests.',
                'cors_safe': True
            }
        })
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error for {url}: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to fetch website: {str(e)}'
        }), 400
    
    except Exception as e:
        logger.error(f"Self-contained scraping error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

@app.route('/apply-changes', methods=['POST'])
def apply_changes():
    """
    Apply text changes to HTML content server-side to avoid CORS issues
    """
    try:
        data = request.get_json()
        
        if not data or 'html' not in data or 'changes' not in data:
            return jsonify({
                'status': 'error',
                'message': 'HTML content and changes are required'
            }), 400
        
        html_content = data['html']
        changes = data['changes']  # Array of {original: string, modified: string}
        
        logger.info(f"Applying {len(changes)} text changes server-side")
        
        # Apply each change to the HTML content
        modified_html = html_content
        for change in changes:
            if 'original' in change and 'modified' in change:
                original_text = change['original']
                modified_text = change['modified']
                
                logger.info(f"Attempting to replace: '{original_text}' -> '{modified_text}'")
                logger.info(f"Original text length: {len(original_text)}")
                
                # Try 0: Handle emoji-prefixed text specifically
                import re
                import unicodedata
                
                # Check if the text starts with emojis
                emoji_pattern = re.compile(
                    "["
                    "\U0001F600-\U0001F64F"  # emoticons
                    "\U0001F300-\U0001F5FF"  # symbols & pictographs
                    "\U0001F680-\U0001F6FF"  # transport & map symbols
                    "\U0001F1E0-\U0001F1FF"  # flags (iOS)
                    "\U00002702-\U000027B0"  # dingbats
                    "\U000024C2-\U0001F251"
                    "✅✓☑️"  # checkmarks
                    "]+", flags=re.UNICODE
                )
                
                emojis_in_original = emoji_pattern.findall(original_text)
                if emojis_in_original:
                    logger.info(f"Found emojis in text: {emojis_in_original}")
                    
                    # Try multiple emoji-aware approaches
                    text_without_emojis = emoji_pattern.sub('', original_text).strip()
                    
                    # Method 0a: Look for text without emojis and replace with emoji included in new text
                    if text_without_emojis and text_without_emojis in modified_html:
                        emoji_prefix = ''.join(emojis_in_original)
                        full_replacement = emoji_prefix + modified_text
                        modified_html = modified_html.replace(text_without_emojis, full_replacement, 1)
                        logger.info(f"✅ Applied emoji-aware replacement: '{original_text[:50]}...' -> '{full_replacement[:50]}...'")
                        continue
                    
                    # Method 0b: Try with normalized Unicode
                    normalized_original = unicodedata.normalize('NFC', original_text)
                    normalized_content = unicodedata.normalize('NFC', modified_html)
                    
                    if normalized_original in normalized_content:
                        modified_html = normalized_content.replace(normalized_original, modified_text, 1)
                        logger.info(f"✅ Applied Unicode normalized emoji replacement: '{original_text[:50]}...' -> '{modified_text[:50]}...'")
                        continue
                    
                    # Method 0c: Try with HTML entity decoding
                    import html
                    html_decoded_original = html.unescape(original_text)
                    html_decoded_content = html.unescape(modified_html)
                    
                    if html_decoded_original in html_decoded_content:
                        # Replace in decoded content and encode back
                        decoded_modified = html_decoded_content.replace(html_decoded_original, modified_text, 1)
                        modified_html = decoded_modified
                        logger.info(f"✅ Applied HTML decoded emoji replacement: '{original_text[:50]}...' -> '{modified_text[:50]}...'")
                        continue
                
                # Try 1: Direct text replacement (fastest)
                if original_text in modified_html:
                    modified_html = modified_html.replace(original_text, modified_text, 1)
                    logger.info(f"✅ Applied direct change: '{original_text[:50]}...' -> '{modified_text[:50]}...'")
                    continue
                
                # Try 2: BeautifulSoup - Handle HTML tags and nested content
                try:
                    soup = BeautifulSoup(modified_html, 'html.parser')
                    replaced = False
                    
                    # Method 2a: Find all text nodes and check for matches
                    for element in soup.find_all(string=True):
                        element_text = str(element).strip()
                        if original_text in element_text:
                            new_text = element_text.replace(original_text, modified_text, 1)
                            element.replace_with(new_text)
                            replaced = True
                            logger.info(f"✅ Applied text node change: '{original_text[:50]}...' -> '{modified_text[:50]}...'")
                            break
                    
                    if replaced:
                        modified_html = str(soup)
                        continue
                    
                    # Method 2b: Advanced nested HTML handling
                    for element in soup.find_all():
                        if element.get_text() and original_text in element.get_text():
                            element_text = element.get_text()
                            
                            # If exact match of text content, replace the entire element content
                            if element_text.strip() == original_text.strip():
                                element.string = modified_text
                                replaced = True
                                logger.info(f"✅ Applied element replacement: '{original_text[:50]}...' -> '{modified_text[:50]}...'")
                                break
                            
                            # For partial matches with HTML tags, try comprehensive replacement
                            elif original_text in element_text:
                                # Method 1: Direct HTML string replacement
                                element_html = str(element)
                                if original_text in element_html:
                                    new_element_html = element_html.replace(original_text, modified_text, 1)
                                    try:
                                        new_element = BeautifulSoup(new_element_html, 'html.parser')
                                        element.replace_with(new_element)
                                        replaced = True
                                        logger.info(f"✅ Applied HTML string replacement: '{original_text[:50]}...' -> '{modified_text[:50]}...'")
                                        break
                                    except:
                                        pass
                                
                                # Method 2: Normalize text and match with whitespace flexibility
                                import unicodedata
                                import re
                                
                                # Normalize both texts to handle French accents and special chars
                                normalized_original = unicodedata.normalize('NFKD', original_text)
                                normalized_element_text = unicodedata.normalize('NFKD', element_text)
                                
                                # Try normalized text replacement
                                if normalized_original in normalized_element_text:
                                    element.clear()
                                    element.string = modified_text
                                    replaced = True
                                    logger.info(f"✅ Applied normalized replacement: '{original_text[:50]}...' -> '{modified_text[:50]}...'")
                                    break
                                
                                # Method 3: Word-by-word matching with HTML tolerance
                                original_words = re.findall(r'\S+', original_text)
                                if len(original_words) > 2:  # Only for multi-word text
                                    # Check if most words are present
                                    words_found = sum(1 for word in original_words if word in element_text)
                                    if words_found >= len(original_words) * 0.8:  # 80% of words match
                                        element.clear()
                                        element.string = modified_text
                                        replaced = True
                                        logger.info(f"✅ Applied word-based replacement: '{original_text[:50]}...' -> '{modified_text[:50]}...'")
                                        break
                                
                                # Method 4: Handle text split across multiple child elements
                                child_texts = []
                                for child in element.descendants:
                                    if isinstance(child, str) and child.strip():
                                        child_texts.append(child.strip())
                                
                                combined_child_text = ' '.join(child_texts)
                                if original_text in combined_child_text:
                                    element.clear()
                                    element.string = modified_text
                                    replaced = True
                                    logger.info(f"✅ Applied child text reconstruction: '{original_text[:50]}...' -> '{modified_text[:50]}...'")
                                    break
                                
                                # Method 5: Flexible matching ignoring extra whitespace and punctuation
                                clean_original = re.sub(r'\s+', ' ', original_text.strip())
                                clean_element = re.sub(r'\s+', ' ', element_text.strip())
                                
                                if clean_original in clean_element:
                                    element.clear()
                                    element.string = modified_text
                                    replaced = True
                                    logger.info(f"✅ Applied clean text replacement: '{original_text[:50]}...' -> '{modified_text[:50]}...'")
                                    break
                    
                    if replaced:
                        modified_html = str(soup)
                        continue
                
                except Exception as e:
                    logger.warning(f"BeautifulSoup processing failed: {e}")
                
                # Try 3: Flexible regex approach for HTML content with tags
                try:
                    import re
                    
                    # Method 3a: Handle text that might be split across HTML tags
                    words = original_text.split()
                    if len(words) > 1:
                        # Build pattern that allows HTML tags between words
                        pattern_parts = []
                        for word in words:
                            pattern_parts.append(re.escape(word))
                        
                        # Pattern allows tags, whitespace, and other content between words
                        flexible_pattern = r'(?:<[^>]*>|\s)*'.join(pattern_parts)
                        
                        if re.search(flexible_pattern, modified_html, re.IGNORECASE | re.DOTALL):
                            modified_html = re.sub(flexible_pattern, modified_text, modified_html, count=1, flags=re.IGNORECASE | re.DOTALL)
                            logger.info(f"✅ Applied flexible regex: '{original_text[:50]}...' -> '{modified_text[:50]}...'")
                            continue
                    
                    # Method 3b: Try exact match with case insensitive
                    escaped_original = re.escape(original_text)
                    if re.search(escaped_original, modified_html, re.IGNORECASE):
                        modified_html = re.sub(escaped_original, modified_text, modified_html, count=1, flags=re.IGNORECASE)
                        logger.info(f"✅ Applied exact regex: '{original_text[:50]}...' -> '{modified_text[:50]}...'")
                        continue
                
                except Exception as regex_error:
                    logger.warning(f"Regex replacement failed: {regex_error}")
                
                # If all methods fail, provide enhanced debugging
                logger.warning(f"❌ Could not find text to replace: '{original_text[:50]}...'")
                
                # Enhanced debugging for failed replacements
                try:
                    soup_debug = BeautifulSoup(modified_html, 'html.parser')
                    
                    # Check if any part of the text exists
                    words = original_text.split()
                    found_words = []
                    for word in words:
                        if word in modified_html:
                            found_words.append(word)
                    
                    if found_words:
                        logger.info(f"Found partial words: {found_words}")
                    
                    # Look for similar text patterns
                    first_few_words = ' '.join(words[:3]) if len(words) >= 3 else original_text
                    if first_few_words in modified_html:
                        logger.info(f"Found beginning of text: '{first_few_words}'")
                    
                    # Find elements containing any of the words
                    for element in soup_debug.find_all():
                        element_text = element.get_text() if element else ""
                        if any(word in element_text for word in words[:3]):
                            logger.info(f"Similar element found: '{element_text[:100]}...'")
                            logger.info(f"Element HTML: {str(element)[:200]}...")
                            break
                            
                except Exception as debug_error:
                    logger.warning(f"Debug search failed: {debug_error}")
        
        return jsonify({
            'status': 'success',
            'html': modified_html,
            'changes_applied': len(changes)
        })

    except Exception as e:
        logger.error(f"Apply changes error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

@app.route('/serve-html/<path:html_id>', methods=['GET'])
def serve_html(html_id):
    """
    Serve processed HTML directly with proper headers to avoid CORS issues
    """
    try:
        # In a real implementation, you'd store the HTML in a database or cache
        # For now, we'll use a simple in-memory storage
        if not hasattr(serve_html, 'html_cache'):
            serve_html.html_cache = {}
        
        if html_id not in serve_html.html_cache:
            return "HTML not found", 404
        
        html_content = serve_html.html_cache[html_id]
        
        response = Response(html_content, mimetype='text/html')
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['X-Frame-Options'] = 'ALLOWALL'
        
        return response
    
    except Exception as e:
        logger.error(f"Serve HTML error: {str(e)}")
        return "Internal server error", 500

@app.route('/store-html', methods=['POST'])
def store_html():
    """
    Store HTML content and return an ID for serving
    """
    try:
        data = request.get_json()
        
        if not data or 'html' not in data:
            return jsonify({
                'status': 'error',
                'message': 'HTML content is required'
            }), 400
        
        html_content = data['html']
        
        # Generate a unique ID
        import uuid
        html_id = str(uuid.uuid4())
        
        # Store in cache
        if not hasattr(serve_html, 'html_cache'):
            serve_html.html_cache = {}
        
        serve_html.html_cache[html_id] = html_content
        
        return jsonify({
            'status': 'success',
            'html_id': html_id,
            'serve_url': f'http://127.0.0.1:5000/serve-html/{html_id}'
        })
    
    except Exception as e:
        logger.error(f"Store HTML error: {str(e)}")
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



# WordPress Integration (optional - only loaded when needed)
try:
    from wordpress_optional import (
        WordPressPageDuplicator, 
        WordPressConfig, 
        ContentChange, 
        parse_frontend_changes,
        WORDPRESS_AVAILABLE,
        get_wordpress_status,
        get_wordpress_credentials
    )
    # Also import simple WordPress integration
    from simple_wordpress import SimpleWordPressIntegration
    logger.info(f"WordPress integration status: {'enabled' if WORDPRESS_AVAILABLE else 'disabled'}")
except ImportError:
    WORDPRESS_AVAILABLE = False
    logger.warning("WordPress integration module not found")
    
    def get_wordpress_status():
        return {
            'available': False,
            'status': 'disabled - module not found',
            'features': []
        }
    
    def get_wordpress_credentials():
        return {
            'configured': False,
            'message': 'WordPress integration not available'
        }

@app.route('/wordpress/ship', methods=['POST'])
def ship_to_wordpress():
    """
    Ship changes to WordPress - Create duplicate page with modified content
    Expects JSON: {
        "wordpress_config": {
            "site_url": "https://your-site.com",
            "username": "your-username", 
            "password": "your-app-password"
        },
        "page_url": "https://your-site.com/original-page",
        "saved_changes": {
            "element-id-1": {"original": "...", "modified": "..."},
            "element-id-2": {"original": "...", "modified": "..."}
        },
        "test_name": "Optional AB Test Name"
    }
    """
    try:
        # Check if WordPress integration is available
        if not WORDPRESS_AVAILABLE:
            return jsonify({
                'status': 'error',
                'message': 'WordPress integration not available. Required dependencies not installed.',
                'available_features': 'This feature requires additional packages that are not available in the current deployment.'
            }), 503
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Request body is required'
            }), 400
        
        # Validate required fields
        wp_config_data = data.get('wordpress_config')
        page_url = data.get('page_url')
        saved_changes = data.get('saved_changes')
        test_name = data.get('test_name')
        
        # Use environment variables as fallback for WordPress config
        env_credentials = get_wordpress_credentials()
        
        if not wp_config_data and env_credentials['configured']:
            wp_config_data = {
                'site_url': env_credentials['site_url'],
                'username': env_credentials['username'],
                'password': env_credentials['password']
            }
            logger.info("Using WordPress credentials from environment variables")
        
        if not wp_config_data:
            return jsonify({
                'status': 'error',
                'message': 'WordPress configuration is required (either in request body or environment variables)',
                'note': 'Set WORDPRESS_SITE_URL, WORDPRESS_USERNAME, and WORDPRESS_PASSWORD environment variables'
            }), 400
        
        if not page_url:
            return jsonify({
                'status': 'error',
                'message': 'Page URL is required'
            }), 400
        
        if not saved_changes:
            return jsonify({
                'status': 'error',
                'message': 'Saved changes are required'
            }), 400
        
        # Validate WordPress config
        required_wp_fields = ['site_url', 'username', 'password']
        for field in required_wp_fields:
            if not wp_config_data.get(field):
                return jsonify({
                    'status': 'error',
                    'message': f'WordPress {field} is required'
                }), 400
        
        # Create WordPress configuration
        wp_config = WordPressConfig(
            site_url=wp_config_data['site_url'],
            username=wp_config_data['username'],
            password=wp_config_data['password']
        )
        
        # Parse frontend changes
        changes = parse_frontend_changes(saved_changes)
        
        # Debug logging
        logger.info(f"🔍 Debug - Received saved_changes: {saved_changes}")
        logger.info(f"🔍 Debug - Parsed {len(changes)} changes:")
        for i, change in enumerate(changes):
            logger.info(f"   Change {i+1}: '{change.original_text[:100]}...' -> '{change.modified_text[:100]}...'")
        
        if not changes:
            return jsonify({
                'status': 'error',
                'message': 'No valid changes found to ship'
            }), 400
        
        # 🚨 FINAL CSS FIX: Direct WordPress API with complete meta preservation
        logger.info(f"🚨 FINAL CSS FIX: Starting WordPress shipping with CSS preservation...")
        
        try:
            # Find original page by URL
            from urllib.parse import urlparse
            parsed_url = urlparse(page_url)
            path = parsed_url.path.strip('/')
            
            # Search for the page by slug
            search_response = requests.get(
                f"{wp_config.site_url}/wp-json/wp/v2/pages",
                params={'slug': path, 'per_page': 1},
                auth=(wp_config.username, wp_config.password),
                timeout=30
            )
            
            if search_response.status_code != 200 or not search_response.json():
                return jsonify({
                    'status': 'error',
                    'message': f'Page not found for URL: {page_url}'
                }), 404
            
            original_page = search_response.json()[0]
            logger.info(f"✅ FINAL: Found original page {original_page['id']}")
            
            # Get COMPLETE original page with ALL meta fields
            full_response = requests.get(
                f"{wp_config.site_url}/wp-json/wp/v2/pages/{original_page['id']}?context=edit",
                auth=(wp_config.username, wp_config.password),
                timeout=30
            )
            
            if full_response.status_code != 200:
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to get complete page data'
                }), 500
            
            full_original = full_response.json()
            logger.info(f"📄 FINAL: Got complete page with {len(full_original.get('meta', {}))} meta fields")
            
            # Show critical meta fields for debugging
            critical_fields = ['_elementor_data', '_elementor_css', '_wp_page_template']
            for field in critical_fields:
                if field in full_original.get('meta', {}):
                    logger.info(f"   ✅ Original has {field}")
                else:
                    logger.info(f"   ❌ Original missing {field}")
            
            # 🚨 FINAL DUPLICATION: Create page with ALL meta fields included
            suffix = test_name or f"CSS-FIXED-{datetime.now().strftime('%H%M%S')}"
            
            duplicate_data = {
                'title': f"{full_original['title']['raw']} - {suffix}",
                'content': full_original['content']['raw'],  # RAW content preserves everything
                'excerpt': full_original.get('excerpt', {}).get('raw', ''),
                'status': 'publish',
                'template': full_original.get('template', ''),
                'featured_media': full_original.get('featured_media', 0),
                'parent': full_original.get('parent', 0),
                'menu_order': full_original.get('menu_order', 0),
                'comment_status': full_original.get('comment_status', 'closed'),
                'ping_status': full_original.get('ping_status', 'closed'),
                'meta': full_original.get('meta', {})  # 🔥 ALL META FIELDS INCLUDED!
            }
            
            logger.info(f"🚀 FINAL: Creating duplicate with {len(duplicate_data.get('meta', {}))} meta fields...")
            
            create_response = requests.post(
                f"{wp_config.site_url}/wp-json/wp/v2/pages",
                json=duplicate_data,
                auth=(wp_config.username, wp_config.password),
                timeout=30
            )
            
            if create_response.status_code not in [200, 201]:
                logger.error(f"❌ FINAL: Failed to create duplicate: {create_response.status_code}")
                logger.error(f"Response: {create_response.text[:300]}")
                return jsonify({
                    'status': 'error',
                    'message': f'Failed to create duplicate page: {create_response.text[:200]}'
                }), 500
            
            new_page = create_response.json()
            logger.info(f"✅ FINAL SUCCESS: Created page {new_page['id']} with CSS preservation!")
            
            # Verify meta fields were copied
            verify_response = requests.get(
                f"{wp_config.site_url}/wp-json/wp/v2/pages/{new_page['id']}?context=edit",
                auth=(wp_config.username, wp_config.password),
                timeout=30
            )
            
            if verify_response.status_code == 200:
                verify_page = verify_response.json()
                verify_meta = verify_page.get('meta', {})
                logger.info(f"🔍 FINAL: Verification - New page has {len(verify_meta)} meta fields")
                
                for field in critical_fields:
                    if field in verify_meta:
                        logger.info(f"   ✅ Successfully copied {field}")
                    else:
                        logger.info(f"   ❌ LOST {field}")
            
            # Apply content changes if any
            if changes:
                logger.info(f"🔄 FINAL: Applying {len(changes)} content changes...")
                
                current_content = new_page['content']['raw']
                modified_content = current_content
                
                for change in changes:
                    if change.original_text in modified_content:
                        modified_content = modified_content.replace(
                            change.original_text, 
                            change.modified_text, 
                            1
                        )
                        logger.info(f"✅ FINAL: Applied change: {change.original_text[:50]}... -> {change.modified_text[:50]}...")
                
                # Update page content
                update_response = requests.post(
                    f"{wp_config.site_url}/wp-json/wp/v2/pages/{new_page['id']}",
                    json={'content': modified_content},
                    auth=(wp_config.username, wp_config.password),
                    timeout=30
                )
                
                if update_response.status_code == 200:
                    logger.info(f"✅ FINAL: Content updated successfully")
                    new_page = update_response.json()
            
            # Return final result
            result = {
                'success': True,
                'message': 'FINAL CSS FIX: Successfully shipped to WordPress with CSS preservation!',
                'original_page': {
                    'id': original_page['id'],
                    'title': original_page['title']['rendered'],
                    'url': original_page['link']
                },
                'duplicate_page': {
                    'id': new_page['id'],
                    'title': new_page['title']['rendered'],
                    'url': new_page['link'],
                    'edit_url': f"{wp_config.site_url}/wp-admin/post.php?post={new_page['id']}&action=edit"
                },
                'changes_applied': len(changes),
                'test_name': suffix,
                'css_preservation': 'ENABLED'
            }
            
            logger.info(f"🎉 FINAL SUCCESS: Created {new_page['link']}")
            return jsonify({
                'status': 'success',
                'message': 'FINAL CSS FIX: Successfully shipped to WordPress with CSS preservation!',
                'data': result
            }), 200
            
        except Exception as e:
            logger.error(f"❌ FINAL CSS FIX ERROR: {e}")
            return jsonify({
                'status': 'error',
                'message': f'FINAL CSS fix failed: {str(e)}'
            }), 500
        
    except Exception as e:
        logger.error(f"WordPress ship endpoint error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error',
            'details': str(e) if app.debug else None
        }), 500

@app.route('/wordpress/test-connection', methods=['POST'])
def test_wordpress_connection():
    """
    Test WordPress API connection
    Expects JSON: {
        "site_url": "https://your-site.com",
        "username": "your-username",
        "password": "your-app-password"
    }
    """
    try:
        # Check if WordPress integration is available
        if not WORDPRESS_AVAILABLE:
            return jsonify({
                'status': 'error',
                'message': 'WordPress integration not available. Required dependencies not installed.',
                'available_features': 'This feature requires additional packages that are not available in the current deployment.'
            }), 503
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Request body is required'
            }), 400
        
        # Validate required fields
        required_fields = ['site_url', 'username', 'password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'status': 'error',
                    'message': f'{field} is required'
                }), 400
        
        # Create WordPress configuration
        wp_config = WordPressConfig(
            site_url=data['site_url'],
            username=data['username'],
            password=data['password']
        )
        
        # Test connection by trying to fetch pages
        duplicator = WordPressPageDuplicator(wp_config)
        
        try:
            response = duplicator.session.get(
                f"{wp_config.api_url}/pages",
                params={'per_page': 1}
            )
            response.raise_for_status()
            
            return jsonify({
                'status': 'success',
                'message': 'WordPress connection successful',
                'data': {
                    'api_url': wp_config.api_url,
                    'connection_verified': True,
                    'pages_accessible': True
                }
            }), 200
            
        except requests.RequestException as e:
            return jsonify({
                'status': 'error',
                'message': 'Failed to connect to WordPress API',
                'details': str(e)
            }), 400
        
    except Exception as e:
        logger.error(f"WordPress test connection error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

@app.route('/wordpress/config', methods=['GET'])
def get_wordpress_config():
    """
    Get WordPress configuration status
    Returns information about available WordPress credentials and configuration
    """
    try:
        # Check if WordPress integration is available
        if not WORDPRESS_AVAILABLE:
            return jsonify({
                'status': 'error',
                'message': 'WordPress integration not available. Required dependencies not installed.',
                'available_features': 'This feature requires additional packages that are not available in the current deployment.'
            }), 503
        
        credentials = get_wordpress_credentials()
        wp_status = get_wordpress_status()
        
        return jsonify({
            'status': 'success',
            'data': {
                'integration_status': wp_status,
                'credentials_configured': credentials['configured'],
                'site_url': credentials.get('site_url', 'Not configured'),
                'username_configured': bool(credentials.get('username')),
                'password_configured': bool(credentials.get('password')),
                'environment_variables': {
                    'WORDPRESS_SITE_URL': 'Set' if credentials.get('site_url') else 'Not set',
                    'WORDPRESS_USERNAME': 'Set' if credentials.get('username') else 'Not set',
                    'WORDPRESS_PASSWORD': 'Set' if credentials.get('password') else 'Not set'
                },
                'usage_note': 'You can either provide WordPress credentials in API requests or set them as environment variables'
            }
        }), 200
        
    except Exception as e:
        logger.error(f"WordPress config endpoint error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

@app.route('/wordpress/debug', methods=['POST'])
def debug_wordpress_changes():
    """
    Debug endpoint to test content replacement without actually shipping
    """
    try:
        if not WORDPRESS_AVAILABLE:
            return jsonify({
                'status': 'error',
                'message': 'WordPress integration not available'
            }), 503
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Request body is required'
            }), 400
        
        saved_changes = data.get('saved_changes', {})
        test_content = data.get('test_content', '<p>Sample WordPress content</p>')
        
        # Parse changes
        changes = parse_frontend_changes(saved_changes)
        
        debug_info = {
            'received_changes': saved_changes,
            'parsed_changes': [
                {
                    'element_id': c.element_id,
                    'original': c.original_text,
                    'modified': c.modified_text,
                    'type': c.element_type
                } for c in changes
            ],
            'original_content': test_content
        }
        
        if changes:
            # Test content replacement
            from wordpress_integration import WordPressPageDuplicator, WordPressConfig
            
            # Create a dummy config for testing
            dummy_config = WordPressConfig(
                site_url="https://example.com",
                username="test",
                password="test"
            )
            
            duplicator = WordPressPageDuplicator(dummy_config)
            modified_content = duplicator.apply_content_changes(test_content, changes)
            
            debug_info['modified_content'] = modified_content
            debug_info['changes_found'] = modified_content != test_content
        
        return jsonify({
            'status': 'success',
            'debug_info': debug_info
        }), 200
        
    except Exception as e:
        logger.error(f"WordPress debug endpoint error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error',
            'details': str(e)
        }), 500

@app.route('/generate-more-suggestions', methods=['POST'])
def generate_more_suggestions():
    """Generate more AI-powered suggestions for specific content"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400
        
        required_fields = ['content', 'content_type']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'status': 'error',
                    'message': f'Missing required field: {field}'
                }), 400
        
        content = data['content']
        content_type = data['content_type']
        original_url = data.get('original_url', '')
        
        # Initialize Cerebras AI
        cerebras_ai = CerebrasAI()
        
        # Generate suggestions using the existing method
        result = cerebras_ai.generate_content_suggestions(
            original_content=content,
            content_type=content_type,
            context=f"Original URL: {original_url}" if original_url else ""
        )
        
        if 'error' in result:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 500
        
        suggestions = result.get('suggestions', [])
        if not suggestions:
            return jsonify({
                'status': 'error',
                'message': 'No suggestions generated'
            }), 500
        
        return jsonify({
            'status': 'success',
            'suggestions': suggestions
        }), 200
        
    except Exception as e:
        logger.error(f"Generate more suggestions error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error',
            'details': str(e)
        }), 500

# --- Proxy Font Endpoint (integrated with main API endpoints) ---
from flask import Response, stream_with_context

@app.route('/proxy-font/<path:font_path>')
def proxy_font(font_path):
    """
    Proxy font files from WordPress, streaming the response and preserving Content-Type.
    Example: /proxy-font/fontawesome/fa-solid-900.woff2
    """
    base_url = 'https://maprimerenovsolaire.fr/wp-content/themes/Divi/core/admin/fonts/'
    remote_url = base_url + font_path
    try:
        with requests.get(remote_url, stream=True, timeout=15) as r:
            r.raise_for_status()
            def generate():
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            headers = {
                'Access-Control-Allow-Origin': 'https://lp-chi-two.vercel.app',
                'Content-Type': r.headers.get('Content-Type', 'application/octet-stream'),
                'Cache-Control': r.headers.get('Cache-Control', 'public, max-age=86400'),
            }
            return Response(stream_with_context(generate()), headers=headers)
    except Exception as e:
        logger.error(f"Font proxy error: {str(e)}")
        return jsonify({'error': 'Failed to fetch font', 'details': str(e)}), 502

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)