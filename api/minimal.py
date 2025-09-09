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

# Initialize AI
cerebras_ai = CerebrasAI()

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'success',
        'message': 'Web Scraper API with AI Enhancement is working!',
        'version': '4.0.0',
        'endpoints': {
            'health': '/health',
            'test': '/test',
            'scrape': '/scrape',
            'scrape-complete': '/scrape-complete',
            'scrape-ai': '/scrape-ai'
        },
        'ai_features': {
            'headline_optimization': True,
            'subheadline_optimization': True,
            'description_optimization': True,
            'cta_optimization': True,
            'model': 'cerebras-llama3.1-8b'
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

if __name__ == '__main__':
    app.run(debug=False)
