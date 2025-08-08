# Web Scraper API Documentation

## Base URL
```
http://localhost:5000
```

## Endpoints

### 1. Health Check
**GET** `/`

**Respons    if (result.status === 'success') {
      console.log('Headlines:', result.data.headline);
      console.log('Subheadlines:', result.data.subheadline);
      console.log('CTAs:', result.data.call_to_action);
      console.log('Description/Credibility:', result.data.description_credibility);
    }
```json
{
  "status": "success",
  "message": "Web Scraper API is running",
  "version": "1.0.0"
}
```

### 2. Scrape Single Website
**POST** `/scrape`

**Request Body:**
```json
{
  "url": "https://example.com"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "html": "<html>...</html>",
    "headline": [
      "Main Website Headline",
      "Secondary Headline"
    ],
    "subheadline": [
      "Subheadline text",
      "Additional subheadline"
    ],
    "call_to_action": [
      "Sign up today",
      "Get started now",
      "Join us",
      "Try it free"
    ],
    "description_credibility": [
      "Website description or about text",
      "Customer testimonial text",
      "Award or certification mention",
      "Company credentials and experience"
    ]
  }
}
```

### 3. Batch Scrape Multiple Websites
**POST** `/scrape-batch`

**Request Body:**
```json
{
  "urls": [
    "https://example1.com",
    "https://example2.com"
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
      "headline": ["Headline 1"],
      "subheadline": ["Subheadline 1"],
      "call_to_action": ["Sign up now", "Get started"],
      "description_credibility": ["Description 1", "Testimonial 1"]
    },
    {
      "html": "<html>...</html>",
      "headline": ["Headline 2"],
      "subheadline": ["Subheadline 2"],
      "call_to_action": ["Join today"],
      "description_credibility": ["Description 2", "Award mention"]
    }
  ]
}
```

## Error Responses

### 400 Bad Request
```json
{
  "status": "error",
  "message": "URL is required in request body"
}
```

### 404 Not Found
```json
{
  "status": "error",
  "message": "Endpoint not found"
}
```

### 500 Internal Server Error
```json
{
  "status": "error",
  "message": "Internal server error"
}
```

## Frontend Integration Examples

### JavaScript/Fetch
```javascript
// Single website scraping
async function scrapeWebsite(url) {
  const response = await fetch('http://localhost:5000/scrape', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ url: url })
  });
  
  const data = await response.json();
  return data;
}

// Usage
scrapeWebsite('https://example.com')
  .then(result => {
    if (result.status === 'success') {
      console.log('Headlines:', result.data.headline);
      console.log('CTAs:', result.data.call_to_action);
      console.log('Descriptions:', result.data.description);
    }
  });
```

### React Component
```jsx
import React, { useState } from 'react';

function WebsiteScraper() {
  const [url, setUrl] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleScrape = async () => {
    setLoading(true);
    try {
      const response = await fetch('http://localhost:5000/scrape', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url })
      });
      
      const data = await response.json();
      setResults(data);
    } catch (error) {
      console.error('Error:', error);
    }
    setLoading(false);
  };

  return (
    <div>
      <input
        type="url"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="Enter website URL"
      />
      <button onClick={handleScrape} disabled={loading}>
        {loading ? 'Scraping...' : 'Scrape Website'}
      </button>
      
      {results && results.status === 'success' && (
        <div>
          <h3>Headlines</h3>
          {results.data.headline.map((h, i) => <p key={i}>{h}</p>)}
          
          <h3>Subheadlines</h3>
          {results.data.subheadline.map((sub, i) => <p key={i}>{sub}</p>)}
          
          <h3>Call to Actions</h3>
          {results.data.call_to_action.map((cta, i) => (
            <div key={i}>{cta}</div>
          ))}
          
          <h3>Description & Credibility</h3>
          {results.data.description_credibility.map((desc, i) => <p key={i}>{desc}</p>)}
        </div>
      )}
    </div>
  );
}
```

### cURL Examples
```bash
# Health check
curl http://localhost:5000/

# Single scrape
curl -X POST http://localhost:5000/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'

# Batch scrape
curl -X POST http://localhost:5000/scrape-batch \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://example1.com", "https://example2.com"]}'
```

## Data Extraction Details

### Headlines
- Extracts from `h1` tags
- Elements with classes containing "headline", "title"
- Hero section headings
- Header section headings

### Subheadlines
- Extracts from `h2`, `h3` tags
- Elements with classes containing "subheadline", "subtitle", "tagline"
- Hero section subheadings

### Call-to-Action (Textual)
- Textual phrases containing action words like "sign up", "join", "get started"
- Action-oriented text with words like "try free", "download", "learn more"
- Urgency phrases like "don't wait", "limited time", "act now"
- Text from buttons and CTA elements (content only, not HTML structure)

### Description & Credibility (Combined)
- Website descriptions and about text
- Meta descriptions
- Customer testimonials and reviews
- Awards and certifications
- Trust indicators and security badges
- Company experience and expertise mentions
- Success stories and case studies

## Limitations
- Maximum 10 URLs per batch request
- 10-second timeout per request
- JavaScript-rendered content not supported (static HTML only)
- Some websites may block scraping attempts
- Rate limiting may apply for frequent requests
