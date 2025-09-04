/**
 * WordPress Page Duplication Service - Node.js Implementation
 * ===========================================================
 * 
 * Alternative Node.js implementation for WordPress A/B testing integration.
 * This provides the same functionality as the Python version but for Node.js environments.
 * 
 * Requirements:
 * - Node.js 14+
 * - axios for HTTP requests
 * - WordPress site with REST API enabled
 * 
 * Usage:
 *   const wordpress = new WordPressPageDuplicator(config);
 *   const result = await wordpress.shipChangesToWordPress(pageUrl, changes);
 */

const axios = require('axios');

class WordPressConfig {
    constructor(siteUrl, username, password) {
        this.siteUrl = siteUrl.replace(/\/$/, ''); // Remove trailing slash
        this.username = username;
        this.password = password;
        this.apiBase = 'wp-json/wp/v2';
        this.apiUrl = `${this.siteUrl}/${this.apiBase}`;
    }
}

class ContentChange {
    constructor(elementId, originalText, modifiedText, elementType = 'text') {
        this.elementId = elementId;
        this.originalText = originalText;
        this.modifiedText = modifiedText;
        this.elementType = elementType;
    }
}

class WordPressPageDuplicator {
    constructor(config) {
        this.config = config;
        
        // Create axios instance with authentication
        this.client = axios.create({
            auth: {
                username: config.username,
                password: config.password
            },
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        });
    }

    /**
     * Find a WordPress page by its URL
     * @param {string} pageUrl - The full URL of the page to find
     * @returns {Promise<Object|null>} Page object if found, null otherwise
     */
    async findPageByUrl(pageUrl) {
        try {
            // Extract slug from URL
            const url = new URL(pageUrl);
            const pathParts = url.pathname.split('/').filter(part => part);
            const slug = pathParts[pathParts.length - 1];

            console.log(`🔍 Searching for page with slug: ${slug}`);

            // Search for pages with this slug
            const response = await this.client.get(`${this.config.apiUrl}/pages`, {
                params: {
                    slug: slug,
                    status: 'publish'
                }
            });

            if (response.data && response.data.length > 0) {
                console.log(`✅ Found page: ${response.data[0].title.rendered}`);
                return response.data[0];
            }

            // If slug search fails, try searching by URL
            const searchResponse = await this.client.get(`${this.config.apiUrl}/pages`, {
                params: {
                    search: pageUrl,
                    status: 'publish'
                }
            });

            const pages = searchResponse.data;
            for (const page of pages) {
                if (pageUrl.includes(page.link) || page.link.includes(pageUrl)) {
                    console.log(`✅ Found page by URL search: ${page.title.rendered}`);
                    return page;
                }
            }

            console.warn(`⚠️ No page found for URL: ${pageUrl}`);
            return null;

        } catch (error) {
            console.error(`❌ Error finding page: ${error.message}`);
            return null;
        }
    }

    /**
     * Create a duplicate of a WordPress page
     * @param {Object} originalPage - The original page object from WordPress API
     * @param {string} suffix - Optional suffix for the new page title/slug
     * @returns {Promise<Object|null>} New page object if successful, null otherwise
     */
    async duplicatePage(originalPage, suffix = null) {
        try {
            if (!suffix) {
                suffix = `ab-test-${new Date().toISOString().slice(0, 16).replace(/[:-]/g, '')}`;
            }

            console.log(`📄 Creating duplicate page with suffix: ${suffix}`);

            // Prepare new page data
            const newPageData = {
                title: `${originalPage.title.rendered} - ${suffix}`,
                content: originalPage.content.rendered,
                excerpt: originalPage.excerpt.rendered,
                status: 'draft', // Start as draft for review
                parent: originalPage.parent || 0,
                template: originalPage.template || '',
                meta: originalPage.meta || {},
                featured_media: originalPage.featured_media || 0
            };

            // Create the new page
            const response = await this.client.post(`${this.config.apiUrl}/pages`, newPageData);
            
            console.log(`✅ Successfully created duplicate page: ${response.data.title.rendered}`);
            return response.data;

        } catch (error) {
            console.error(`❌ Error duplicating page: ${error.message}`);
            return null;
        }
    }

    /**
     * Apply content changes to page HTML content
     * @param {string} pageContent - Original HTML content
     * @param {Array<ContentChange>} changes - List of content changes to apply
     * @returns {string} Modified HTML content
     */
    applyContentChanges(pageContent, changes) {
        let modifiedContent = pageContent;

        for (const change of changes) {
            try {
                // Escape special regex characters in original text
                const escapedOriginal = change.originalText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                
                // Replace the content (case-insensitive, first occurrence only)
                const regex = new RegExp(escapedOriginal, 'i');
                modifiedContent = modifiedContent.replace(regex, change.modifiedText);
                
                console.log(`✅ Applied change: '${change.originalText.substring(0, 50)}...' → '${change.modifiedText.substring(0, 50)}...'`);

            } catch (error) {
                console.warn(`⚠️ Failed to apply change for element ${change.elementId}: ${error.message}`);
                continue;
            }
        }

        return modifiedContent;
    }

    /**
     * Update a WordPress page's content
     * @param {number} pageId - WordPress page ID
     * @param {string} newContent - New HTML content
     * @param {string} newTitle - Optional new title
     * @returns {Promise<Object|null>} Updated page object if successful, null otherwise
     */
    async updatePageContent(pageId, newContent, newTitle = null) {
        try {
            const updateData = { content: newContent };
            if (newTitle) {
                updateData.title = newTitle;
            }

            const response = await this.client.post(`${this.config.apiUrl}/pages/${pageId}`, updateData);
            
            console.log(`✅ Successfully updated page content: ${response.data.title.rendered}`);
            return response.data;

        } catch (error) {
            console.error(`❌ Error updating page content: ${error.message}`);
            return null;
        }
    }

    /**
     * Main method to ship changes to WordPress
     * Creates a duplicate page with modified content for A/B testing
     * @param {string} pageUrl - URL of the original WordPress page
     * @param {Array<ContentChange>} changes - List of content changes to apply
     * @param {string} testName - Optional name for the A/B test
     * @returns {Promise<Object>} Result object with success/error information
     */
    async shipChangesToWordPress(pageUrl, changes, testName = null) {
        try {
            console.log(`🚀 Starting WordPress shipping process for: ${pageUrl}`);

            // Step 1: Find the original page
            const originalPage = await this.findPageByUrl(pageUrl);
            if (!originalPage) {
                return {
                    success: false,
                    error: `Original page not found for URL: ${pageUrl}`
                };
            }

            // Step 2: Create duplicate page
            const suffix = testName || `AB-Test-${new Date().toISOString().slice(0, 13).replace(/[:-]/g, '')}`;
            const duplicatePage = await this.duplicatePage(originalPage, suffix);
            if (!duplicatePage) {
                return {
                    success: false,
                    error: 'Failed to create duplicate page'
                };
            }

            // Step 3: Apply content changes
            const modifiedContent = this.applyContentChanges(
                originalPage.content.rendered,
                changes
            );

            // Step 4: Update duplicate page with new content
            const updatedPage = await this.updatePageContent(
                duplicatePage.id,
                modifiedContent
            );

            if (!updatedPage) {
                return {
                    success: false,
                    error: 'Failed to update duplicate page content'
                };
            }

            // Step 5: Return success result
            return {
                success: true,
                original_page: {
                    id: originalPage.id,
                    title: originalPage.title.rendered,
                    url: originalPage.link
                },
                duplicate_page: {
                    id: updatedPage.id,
                    title: updatedPage.title.rendered,
                    url: updatedPage.link,
                    edit_url: `${this.config.siteUrl}/wp-admin/post.php?post=${updatedPage.id}&action=edit`
                },
                changes_applied: changes.length,
                test_name: suffix
            };

        } catch (error) {
            console.error(`❌ Error in shipChangesToWordPress: ${error.message}`);
            return {
                success: false,
                error: `Unexpected error: ${error.message}`
            };
        }
    }

    /**
     * Test WordPress API connection
     * @returns {Promise<Object>} Connection test result
     */
    async testConnection() {
        try {
            const response = await this.client.get(`${this.config.apiUrl}/pages`, {
                params: { per_page: 1 }
            });

            return {
                success: true,
                message: 'WordPress connection successful',
                data: {
                    api_url: this.config.apiUrl,
                    connection_verified: true,
                    pages_accessible: true
                }
            };

        } catch (error) {
            return {
                success: false,
                message: 'Failed to connect to WordPress API',
                error: error.message
            };
        }
    }
}

/**
 * Parse frontend changes data into ContentChange objects
 * @param {Object} savedChangesData - Dictionary containing the saved changes from frontend
 * @returns {Array<ContentChange>} List of ContentChange objects
 */
function parseFrontendChanges(savedChangesData) {
    const changes = [];

    for (const [elementId, changeData] of Object.entries(savedChangesData)) {
        // Determine element type based on element_id or content
        let elementType = 'text'; // default

        if (elementId.toLowerCase().includes('headline') || elementId.toLowerCase().includes('h1')) {
            elementType = 'headline';
        } else if (elementId.toLowerCase().includes('subheadline') || 
                   ['h2', 'h3', 'subtitle'].some(tag => elementId.toLowerCase().includes(tag))) {
            elementType = 'subheadline';
        } else if (['cta', 'button', 'btn', 'call-to-action'].some(term => elementId.toLowerCase().includes(term))) {
            elementType = 'cta';
        } else if (['description', 'desc', 'paragraph', 'p'].some(term => elementId.toLowerCase().includes(term))) {
            elementType = 'description';
        }

        changes.push(new ContentChange(
            elementId,
            changeData.original,
            changeData.modified,
            elementType
        ));
    }

    return changes;
}

// Export for use as module
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        WordPressPageDuplicator,
        WordPressConfig,
        ContentChange,
        parseFrontendChanges
    };
}

// Example usage function
async function exampleUsage() {
    // Configuration
    const config = new WordPressConfig(
        'https://your-wordpress-site.com',
        'your-username',
        'your-application-password'
    );

    // Sample changes data (from frontend)
    const sampleChanges = {
        'headline-1': {
            original: 'Original Headline Text',
            modified: 'AI-Optimized Headline Text'
        },
        'cta-button-1': {
            original: 'Sign Up Now',
            modified: 'Get Started Today'
        },
        'description-1': {
            original: 'Original description text here',
            modified: 'Improved description with better conversion copy'
        }
    };

    // Parse changes
    const changes = parseFrontendChanges(sampleChanges);

    // Initialize duplicator and ship changes
    const duplicator = new WordPressPageDuplicator(config);

    try {
        // Test connection first
        console.log('🔗 Testing WordPress connection...');
        const connectionTest = await duplicator.testConnection();
        
        if (!connectionTest.success) {
            console.error('❌ Connection test failed:', connectionTest.message);
            return;
        }

        console.log('✅ Connection test passed!');

        // Ship changes
        console.log('🚀 Shipping changes to WordPress...');
        const result = await duplicator.shipChangesToWordPress(
            'https://your-wordpress-site.com/landing-page',
            changes,
            'Homepage-Optimization-Test'
        );

        if (result.success) {
            console.log('🎉 Successfully shipped to WordPress!');
            console.log('Original page:', result.original_page.title);
            console.log('Duplicate page:', result.duplicate_page.title);
            console.log('View new page:', result.duplicate_page.url);
            console.log('Edit in WordPress:', result.duplicate_page.edit_url);
        } else {
            console.error('❌ Failed to ship changes:', result.error);
        }

    } catch (error) {
        console.error('❌ Unexpected error:', error.message);
    }
}

// Run example if script is executed directly
if (require.main === module) {
    console.log('🚀 WordPress Integration - Node.js Version');
    console.log('=========================================');
    console.log('');
    console.log('This is an example. To use:');
    console.log('1. Update the config with your WordPress details');
    console.log('2. Update the page URL to match your site');
    console.log('3. Run: node wordpress_integration.js');
    console.log('');
    
    // Uncomment to run the example
    // exampleUsage();
}
