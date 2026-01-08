/**
 * Plugin Store Page
 * Modern ChatGPT-style plugin store for browsing and installing plugins
 */

import { pluginStoreApi } from '../services/api.js';

export async function initPluginStore(container) {
    container.innerHTML = `
        <div class="plugin-store-container">
            <div class="plugin-store-header">
                <h1>Plugin Store</h1>
                <div class="search-bar-container">
                    <input type="text" 
                           id="plugin-search" 
                           class="search-input" 
                           placeholder="Search plugins...">
                    <i data-lucide="search" class="search-icon"></i>
                </div>
            </div>

            <div class="plugin-store-filters">
                <div class="filter-group">
                    <label>Category</label>
                    <select id="category-filter" class="filter-select">
                        <option value="">All Categories</option>
                        <option value="memory">Memory</option>
                        <option value="tools">Tools</option>
                        <option value="integrations">Integrations</option>
                        <option value="ui-themes">UI Themes</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label>Sort</label>
                    <select id="sort-filter" class="filter-select">
                        <option value="stars">Most Stars</option>
                        <option value="installs">Most Installs</option>
                        <option value="recent">Recently Updated</option>
                        <option value="name">Name (A-Z)</option>
                    </select>
                </div>
            </div>

            <div class="plugins-grid" id="plugins-grid">
                <!-- Plugins will be loaded here -->
            </div>

            <div id="plugin-loading" class="loading-indicator" style="display: none;">
                <i data-lucide="loader" class="spinning"></i>
                Loading plugins...
            </div>
        </div>
    `;

    // Initialize icons
    if (window.lucide) {
        window.lucide.createIcons();
    }

    // Load plugins
    await loadPlugins(container);

    // Setup event listeners
    setupEventListeners(container);
}

async function loadPlugins(container, query = '', category = '') {
    const pluginsGrid = container.querySelector('#plugins-grid');
    const loadingIndicator = container.querySelector('#plugin-loading');

    try {
        loadingIndicator.style.display = 'flex';
        pluginsGrid.innerHTML = '';

        const plugins = await getSamplePlugins(query, category);

        if (plugins.length === 0) {
            pluginsGrid.innerHTML = `
                <div class="empty-state" style="grid-column: 1 / -1;">
                    <i data-lucide="package-x"></i>
                    <div class="empty-state-title">No Plugins Found</div>
                    <div class="empty-state-subtitle">Try adjusting your search or filters</div>
                </div>
            `;
            if (window.lucide) window.lucide.createIcons();
            return;
        }

        pluginsGrid.innerHTML = plugins.map(plugin => `
            <div class="plugin-card" data-plugin-id="${plugin.id}">
                <div class="plugin-card-header">
                    <div class="plugin-icon">
                        <i data-lucide="${plugin.icon || 'package'}"></i>
                    </div>
                    <div class="plugin-info">
                        <h3>${plugin.name}</h3>
                        <p class="plugin-author">by ${plugin.author}</p>
                    </div>
                </div>
                <p class="plugin-description">${plugin.description}</p>
                <div class="plugin-stats">
                    <span class="plugin-stat">
                        <i data-lucide="star"></i>
                        ${plugin.stars}
                    </span>
                    <span class="plugin-stat">
                        <i data-lucide="download"></i>
                        ${plugin.installs}
                    </span>
                </div>
                <div class="plugin-card-footer">
                    <span class="plugin-version">v${plugin.version}</span>
                    <button class="btn btn-primary plugin-install-btn" data-plugin-id="${plugin.id}" data-plugin-repo="${plugin.repo}">
                        <i data-lucide="download"></i>
                        Install
                    </button>
                </div>
            </div>
        `).join('');

        if (window.lucide) {
            window.lucide.createIcons();
        }

        setupInstallListeners(container);
    } catch (error) {
        console.error('Error loading plugins:', error);
        pluginsGrid.innerHTML = `
            <div class="error-message">
                Failed to load plugins: ${error.message}
            </div>
        `;
    } finally {
        loadingIndicator.style.display = 'none';
    }
}

async function getSamplePlugins(query, category) {
    const samplePlugins = [
        {
            id: 'memory-plugin',
            name: 'Memory Management',
            author: 'Tailor Team',
            description: 'Advanced conversation history and context retention for longer interactions',
            stars: 128,
            installs: 1200,
            category: 'memory',
            icon: 'brain',
            version: '1.2.0',
            repo: 'https://github.com/tailor-dev/memory-plugin',
        },
        {
            id: 'web-search',
            name: 'Web Search',
            author: 'Community',
            description: 'Search the web and bring results into your conversations',
            stars: 95,
            installs: 890,
            category: 'tools',
            icon: 'search',
            version: '2.0.1',
            repo: 'https://github.com/tailor-community/web-search',
        },
        {
            id: 'code-runner',
            name: 'Code Runner',
            author: 'Tailor Team',
            description: 'Execute Python and JavaScript code directly from conversations',
            stars: 212,
            installs: 2150,
            category: 'tools',
            icon: 'code',
            version: '3.1.0',
            repo: 'https://github.com/tailor-dev/code-runner',
        },
        {
            id: 'db-connector',
            name: 'Database Connector',
            author: 'Community',
            description: 'Connect and query your databases from Tailor',
            stars: 76,
            installs: 640,
            category: 'integrations',
            icon: 'database',
            version: '1.5.2',
            repo: 'https://github.com/tailor-community/db-connector',
        },
        {
            id: 'dark-theme',
            name: 'Dark Theme Pro',
            author: 'Design Team',
            description: 'Beautiful dark theme with custom color schemes',
            stars: 342,
            installs: 3200,
            category: 'ui-themes',
            icon: 'palette',
            version: '2.3.0',
            repo: 'https://github.com/tailor-design/dark-theme-pro',
        },
        {
            id: 'notion-sync',
            name: 'Notion Sync',
            author: 'Community',
            description: 'Sync conversations and notes with Notion automatically',
            stars: 154,
            installs: 1340,
            category: 'integrations',
            icon: 'book',
            version: '1.0.5',
            repo: 'https://github.com/tailor-community/notion-sync',
        },
    ];

    let filtered = samplePlugins;

    if (query) {
        const lowerQuery = query.toLowerCase();
        filtered = filtered.filter(p =>
            p.name.toLowerCase().includes(lowerQuery) ||
            p.description.toLowerCase().includes(lowerQuery) ||
            p.author.toLowerCase().includes(lowerQuery)
        );
    }

    if (category) {
        filtered = filtered.filter(p => p.category === category);
    }

    return filtered;
}

function setupEventListeners(container) {
    const searchInput = container.querySelector('#plugin-search');
    const categoryFilter = container.querySelector('#category-filter');
    const sortFilter = container.querySelector('#sort-filter');

    let searchTimeout;
    searchInput?.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            const query = e.target.value;
            const category = categoryFilter?.value || '';
            loadPlugins(container, query, category);
        }, 300);
    });

    categoryFilter?.addEventListener('change', (e) => {
        const query = searchInput?.value || '';
        const category = e.target.value;
        loadPlugins(container, query, category);
    });

    sortFilter?.addEventListener('change', (e) => {
        console.log('Sort by:', e.target.value);
    });
}

function setupInstallListeners(container) {
    const installButtons = container.querySelectorAll('.plugin-install-btn');
    installButtons.forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const pluginId = btn.dataset.pluginId;
            const pluginRepo = btn.dataset.pluginRepo;
            await installPlugin(pluginId, pluginRepo, container);
        });
    });
}

async function installPlugin(pluginId, pluginRepo, container) {
    const btn = container.querySelector(`[data-plugin-id="${pluginId}"]`);
    const originalText = btn?.innerHTML;

    try {
        // Update button to show loading state
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = `<i data-lucide="loader" class="spinning"></i> Installing...`;
            if (window.lucide) window.lucide.createIcons();
        }

        // Call the WebSocket API to install plugin
        // This uses the request() helper defined in vault.html
        if (typeof window.request === 'function') {
            const result = await window.request('plugins.install', {
                repo_url: pluginRepo,
                plugin_id: pluginId
            });

            if (result.status === 'success') {
                // Update button to show installed state
                if (btn) {
                    btn.innerHTML = `<i data-lucide="check"></i> Installed`;
                    btn.classList.remove('btn-primary');
                    btn.classList.add('btn-success');
                    if (window.lucide) window.lucide.createIcons();
                }

                // Show success notification
                if (window.showNotification) {
                    window.showNotification(`Plugin "${pluginId}" installed successfully!`, 'success');
                } else {
                    alert(`Plugin "${pluginId}" installed successfully! Restart the vault to activate.`);
                }
            } else if (result.status === 'already_exists') {
                if (btn) {
                    btn.innerHTML = `<i data-lucide="check"></i> Already Installed`;
                    btn.disabled = true;
                    if (window.lucide) window.lucide.createIcons();
                }
            } else {
                throw new Error(result.message || 'Installation failed');
            }
        } else {
            // Fallback: WebSocket not available, show instructions
            alert(
                `To install "${pluginId}":\n\n` +
                `1. Open a terminal in your vault's plugins folder\n` +
                `2. Run: git clone ${pluginRepo}\n` +
                `3. Restart Tailor to load the plugin`
            );
            if (btn) {
                btn.innerHTML = originalText;
                btn.disabled = false;
            }
        }
    } catch (error) {
        console.error('Error installing plugin:', error);

        // Restore button state
        if (btn) {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }

        if (window.showNotification) {
            window.showNotification(`Failed to install plugin: ${error.message}`, 'error');
        } else {
            alert(`Failed to install plugin: ${error.message}`);
        }
    }
}

