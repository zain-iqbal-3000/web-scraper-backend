import requests
import json
import time

def test_font_downloading():
    url = "http://localhost:5000/scrape-complete"
    data = {
        "urls": ["https://maprimerenovsolaire.fr/calculer-aide-v2/"]
    }
    
    # First, test if the server is running
    try:
        print("Checking if server is running...")
        health_response = requests.get("http://localhost:5000/", timeout=5)
        print(f"Server response: {health_response.status_code}")
    except Exception as e:
        print(f"❌ Server not responding: {e}")
        return
    
    try:
        print("Testing font downloading with:", data["urls"][0])
        print("Making request...")
        response = requests.post(url, json=data, timeout=180)
        
        print(f"Response status code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Success!")
            print(f"Status: {result.get('status')}")
            
            if 'data' in result and len(result['data']) > 0:
                page_data = result['data'][0]
                print(f"CSS Files Processed: {page_data.get('css_files_processed', 0)}")
                print(f"Fonts Downloaded: {page_data.get('fonts_downloaded', 0)}")
                print(f"Fonts Failed: {page_data.get('fonts_failed', 0)}")
                
                # Check if fonts are embedded in the HTML
                html_content = page_data.get('complete_html', '')
                if 'data:font/' in html_content:
                    print("✅ Fonts are embedded as base64 data URLs!")
                    font_count = html_content.count('data:font/')
                    print(f"Found {font_count} embedded fonts in the HTML")
                else:
                    print("❌ No embedded fonts found in HTML")
                    
                # Check for external font URLs
                if 'maprimerenovsolaire.fr' in html_content and '.ttf' in html_content:
                    print("⚠️  External font URLs still present")
                    # Count external font references
                    external_fonts = html_content.count('.ttf') + html_content.count('.woff') + html_content.count('.woff2')
                    print(f"Found {external_fonts} external font references")
                else:
                    print("✅ No external font URLs found")
                    
                # Save a sample to check manually
                with open('sample_output.html', 'w', encoding='utf-8') as f:
                    f.write(html_content)
                print("📁 Saved sample output to 'sample_output.html' for manual inspection")
            
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_font_downloading()
