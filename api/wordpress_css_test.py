import requests
import json

# FINAL FIX TEST
wp_url = 'https://royalblue-worm-557866.hostingersite.com'
wp_user = 'zain'
wp_pass = 'eGq1 WrOF EFOI nJOK mR0Q aDDh'

print('🚨 FINAL CSS TEST: Getting original page...')
response = requests.get(f'{wp_url}/wp-json/wp/v2/pages/22?context=edit', auth=(wp_user, wp_pass))
if response.status_code != 200:
    print(f'❌ Failed to get original: {response.status_code}')
    exit()

original = response.json()
print(f'✅ Original has {len(original.get("meta", {}))} meta fields')

# Show critical meta fields
critical_fields = ['_elementor_data', '_elementor_css', '_wp_page_template']
for field in critical_fields:
    if field in original.get('meta', {}):
        print(f'   ✅ Has {field}')
    else:
        print(f'   ❌ Missing {field}')

# Create duplicate with ALL data
duplicate_data = {
    'title': f"{original['title']['raw']} - FINAL_CSS_TEST",
    'content': original['content']['raw'],
    'status': 'publish',
    'meta': original.get('meta', {})
}

print(f'🚀 Creating duplicate with {len(duplicate_data.get("meta", {}))} meta fields...')
create_response = requests.post(f'{wp_url}/wp-json/wp/v2/pages', json=duplicate_data, auth=(wp_user, wp_pass))

if create_response.status_code in [200, 201]:
    new_page = create_response.json()
    print(f'✅ SUCCESS: Created page {new_page["id"]} - {new_page["title"]["rendered"]}')
    print(f'🔗 URL: {new_page.get("link")}')
    
    # Verify meta fields were copied
    verify_response = requests.get(f'{wp_url}/wp-json/wp/v2/pages/{new_page["id"]}?context=edit', auth=(wp_user, wp_pass))
    if verify_response.status_code == 200:
        verify_page = verify_response.json()
        verify_meta = verify_page.get('meta', {})
        print(f'🔍 Verification: New page has {len(verify_meta)} meta fields')
        
        for field in critical_fields:
            if field in verify_meta:
                print(f'   ✅ Copied {field}')
            else:
                print(f'   ❌ LOST {field}')
    
    print(f'\n🎯 TEST COMPLETE! Check if CSS is preserved at: {new_page.get("link")}')
else:
    print(f'❌ FAILED: {create_response.status_code} - {create_response.text[:200]}')
