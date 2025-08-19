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
                        "content": "You are an expert SEO copywriter and digital marketing specialist. Your job is to create compelling, SEO-optimized content that increases click-through rates and conversions."
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
        base_context = f"Website Context: {context if context else 'General website'}"
        
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
            
            # CORS fix: Remove problematic @font-face rules that cause CORS errors
            processed_css = self._fix_cors_fonts(processed_css)
            
            return processed_css
            
        except Exception as e:
            logger.warning(f"Error processing CSS URLs: {str(e)}")
            return css_content
    
    def _fix_cors_fonts(self, css_content):
        """Fix CORS font issues by replacing external font URLs with system fonts"""
        try:
            # Remove or modify @font-face rules that cause CORS issues
            font_face_pattern = r'@font-face\s*\{[^}]*\}'
            
            def replace_font_face(match):
                font_face_rule = match.group(0)
                # If it contains external URLs that cause CORS issues, comment it out
                if 'wp-content/themes' in font_face_rule or 'fontawesome' in font_face_rule:
                    return f'/* CORS blocked font: {font_face_rule} */'
                return font_face_rule
            
            # Replace problematic @font-face rules
            processed_css = re.sub(font_face_pattern, replace_font_face, css_content, flags=re.IGNORECASE | re.DOTALL)
            
            # Add fallback font declarations
            fallback_fonts = '''
            
            /* CORS-safe system font fallbacks */
            body, html, * {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen-Sans, Ubuntu, Cantarell, "Helvetica Neue", sans-serif !important;
            }
            
            .fa, .fas, .far, .fab, .fal, .fontawesome {
                font-family: "Font Awesome 5 Free", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
                font-weight: 900 !important;
            }
            '''
            
            processed_css += fallback_fonts
            
            return processed_css
            
        except Exception as e:
            logger.warning(f"Error fixing CORS fonts: {str(e)}")
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
                
                # Add CORS fix for external fonts
                cors_style = soup.new_tag('style', type='text/css')
                cors_style.string = '''
                /* CORS fix for external fonts */
                @font-face {
                    font-display: optional;
                }
                /* Override external font loading with system fonts as fallback */
                * {
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen-Sans, Ubuntu, Cantarell, "Helvetica Neue", sans-serif !important;
                }
                '''
                soup.head.append(cors_style)
                
                # Add script to handle CORS font loading issues
                cors_script = soup.new_tag('script')
                cors_script.string = '''
                // Handle CORS font loading errors gracefully
                (function() {
                    // Catch and suppress font loading errors
                    window.addEventListener('error', function(e) {
                        if (e.target && (e.target.tagName === 'LINK' || e.target.src)) {
                            var src = e.target.href || e.target.src || '';
                            if (src.includes('.woff') || src.includes('.ttf') || src.includes('.otf') || src.includes('.eot')) {
                                console.log('Font loading blocked by CORS, using system fonts');
                                e.preventDefault();
                                return false;
                            }
                        }
                    }, true);
                    
                    // Remove @font-face rules that cause CORS issues
                    document.addEventListener('DOMContentLoaded', function() {
                        try {
                            var sheets = document.styleSheets;
                            for (var i = 0; i < sheets.length; i++) {
                                try {
                                    var rules = sheets[i].cssRules || sheets[i].rules;
                                    for (var j = rules.length - 1; j >= 0; j--) {
                                        if (rules[j].type === CSSRule.FONT_FACE_RULE) {
                                            var src = rules[j].style.src;
                                            if (src && (src.includes('maprimerenovsolaire.fr') || src.includes('wp-content/themes'))) {
                                                sheets[i].deleteRule(j);
                                            }
                                        }
                                    }
                                } catch (e) {
                                    // CORS blocked, skip this stylesheet
                                }
                            }
                        } catch (e) {
                            console.log('Font cleanup completed');
                        }
                    });
                })();
                '''
                soup.head.append(cors_script)
            
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
        all_text_elements = soup.find_all(text=True)
        
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
            enhanced_data['processing_timestamp'] = datetime.utcnow().isoformat() + "Z"
            
            return enhanced_data
            
        except Exception as e:
            logger.error(f"AI-enhanced scraping error for {url}: {str(e)}")
            return {'error': f'Failed to scrape website with AI enhancement: {str(e)}'}

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
            'scrape': '/scrape',
            'scrape_complete': '/scrape-complete'
        },
        'ai_features': {
            'headline_optimization': True,
            'subheadline_optimization': True,
            'description_optimization': True,
            'cta_optimization': True,
            'model': 'cerebras-llama3.1-8b',
            'suggestions_per_item': 10,
            'content_types_supported': ['headline', 'subheadline', 'description', 'cta']
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
