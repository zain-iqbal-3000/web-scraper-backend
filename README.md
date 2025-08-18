  # Web Scraper Batch API

A Flask-based web scraper API that extracts headlines, subheadlines, call-to-action text, and credibility information from websites. Optimized for Vercel deployment.

## 🚀 Features

- **Batch Processing**: Scrape up to 10 websites in a single request
- **Smart Extraction**: Extracts headlines, subheadlines, textual CTAs, and credibility content
- **Production Ready**: Configured for Vercel serverless deployment
- **CORS Enabled**: Ready for frontend integration

## 📡 API Endpoint

### POST `/api/scrape-batch`

**Request:**
```json
{
  "urls": [
    "https://example.com",
    "https://another-site.com"
  ]
}
```

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "html": "<html>...</html>",
      "headline": ["Main Headline"],
      "subheadline": ["Subheadline text"],
      "call_to_action": ["Sign up now", "Get started"],
      "description_credibility": ["About text", "Testimonial"]
    }
  ]
}
```

## 🛠 Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run locally:**
   ```bash
   python app.py
   ```

3. **Test the API:**
   ```bash
   curl -X POST http://localhost:5000/api/scrape-batch \
     -H "Content-Type: application/json" \
     -d '{"urls": ["https://example.com"]}'
   ```

## 🌐 Deployment

See [VERCEL_DEPLOYMENT.md](VERCEL_DEPLOYMENT.md) for detailed deployment instructions.

**Quick Deploy:**
```bash
vercel
```

## 🔧 Configuration

- **Maximum URLs**: 10 per batch request
- **Timeout**: 10 seconds per URL
- **Response Limit**: Optimized for serverless functions

## 📝 Usage Examples

### JavaScript/Fetch
```javascript
const response = await fetch('https://your-app.vercel.app/api/scrape-batch', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    urls: ['https://example.com', 'https://another-site.com']
  })
});

const data = await response.json();
console.log(data.data); // Array of scraped results
```

### Python
```python
import requests

response = requests.post('https://your-app.vercel.app/api/scrape-batch', 
  json={'urls': ['https://example.com']})

data = response.json()
print(data['data'])
```

## 📄 License

MIT License - Feel free to use for personal and commercial projects.
