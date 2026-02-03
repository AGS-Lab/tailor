/**
 * Vault Settings Modal Module
 * 
 * Handles the settings button and modal for vault configuration.
 * Includes API key management and model category selection.
 */

import { request } from './connection.js';

// State for settings
let providersStatus = {};
let availableModels = {};
let categoryConfig = {};
let categoriesInfo = {};

// Navigation items configuration
const NAV_ITEMS = [
    { id: 'general', icon: 'settings', label: 'General' },
    { id: 'plugins', icon: 'puzzle', label: 'Plugins' },
    { id: 'api-keys', icon: 'key', label: 'API Keys' },
    { id: 'models', icon: 'brain', label: 'Model Categories' }
];

/**
 * Initialize the settings button
 */
export function initSettings() {
    if (window.lucide) window.lucide.createIcons();

    const settingsBtn = document.getElementById('vault-settings-btn');
    if (!settingsBtn) return;

    settingsBtn.addEventListener('click', async () => {
        console.log('[Settings] Opening vault settings');

        const params = new URLSearchParams(window.location.search);
        const vaultPath = params.get('vault') || params.get('path') || '';

        if (window.ui && window.ui.showModal) {
            const navItemsHtml = NAV_ITEMS.map((item, idx) => `
                <button class="settings-nav-item-modal ${idx === 0 ? 'active' : ''}" data-section="${item.id}">
                    <i data-lucide="${item.icon}"></i>
                    <span>${item.label}</span>
                </button>
            `).join('');

            const settingsHtml = `
                <div class="vault-settings-modal">
                    <div class="settings-nav-modal">
                        <div class="settings-nav-header">Configuration</div>
                        ${navItemsHtml}
                    </div>
                    <div id="settings-modal-content" class="settings-modal-content">
                        <h3>General Settings</h3>
                        <p>Configure your vault settings and preferences.</p>
                        <div class="setting-item">
                            <label>Vault Path</label>
                            <div class="setting-value">
                                <i data-lucide="folder"></i>
                                ${vaultPath}
                            </div>
                        </div>
                        <button class="btn btn-secondary" onclick="window.request('system.client_ready', {}); window.ui.closeModal();">
                            <i data-lucide="refresh-cw"></i>
                            Reload Application
                        </button>
                    </div>
                </div>
            `;
            window.ui.showModal('Vault Settings', settingsHtml, '850px');

            setTimeout(() => {
                if (window.lucide) window.lucide.createIcons();
                setupSettingsNavigation();
            }, 50);
        } else {
            if (window.log) window.log('Settings modal not available', 'info');
            alert('Vault settings are being loaded...');
        }
    });
}

/**
 * Setup settings navigation between sections
 */
function setupSettingsNavigation() {
    const navItems = document.querySelectorAll('.settings-nav-item-modal');
    const contentEl = document.getElementById('settings-modal-content');

    if (!navItems.length || !contentEl) return;

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            navItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            renderSettingsSection(contentEl, item.dataset.section);
        });
    });
}

/**
 * Render settings section content
 */
async function renderSettingsSection(container, section) {
    const params = new URLSearchParams(window.location.search);
    const vaultPath = params.get('vault') || params.get('path') || '';

    switch (section) {
        case 'general':
            container.innerHTML = `
                <h3>General Settings</h3>
                <p style="color: var(--text-secondary); margin-bottom: 20px;">
                    Configure your vault settings here.
                </p>
                <div style="display: flex; flex-direction: column; gap: 12px;">
                    <div class="setting-item">
                        <strong>Vault Path:</strong>
                        <code style="background: var(--surface-color); padding: 4px 8px; border-radius: 4px;">${vaultPath}</code>
                    </div>
                    <button class="btn btn-secondary" onclick="window.request('system.client_ready', {}); window.ui.closeModal();">
                        <i data-lucide="refresh-cw"></i>
                        Reload
                    </button>
                </div>
            `;
            break;

        case 'plugins':
            container.innerHTML = `
                <h3>Plugins</h3>
                <p style="color: var(--text-secondary); margin-bottom: 20px;">
                    Manage your installed plugins. Click the Plugin Store button in the activity bar for the full plugin manager.
                </p>
                <button class="btn btn-primary" onclick="document.getElementById('plugin-store-btn').click(); window.ui.closeModal();">
                    <i data-lucide="package-plus"></i>
                    Open Plugin Manager
                </button>
            `;
            break;

        case 'api-keys':
            await renderApiKeysSection(container);
            break;

        case 'models':
            await renderModelsSection(container);
            break;

        default:
            container.innerHTML = '<p>Section not found.</p>';
    }

    if (window.lucide) window.lucide.createIcons();
}

/**
 * Render API Keys section
 */
async function renderApiKeysSection(container) {
    container.innerHTML = `
        <h3>API Keys</h3>
        <p style="color: var(--text-secondary); margin-bottom: 20px;">
            Configure API keys for LLM providers. Keys are stored securely in your system's credential manager.
        </p>
        <div id="api-keys-loading" style="text-align: center; padding: 20px;">
            <p>Loading providers...</p>
        </div>
        <div id="api-keys-list" style="display: none;"></div>
    `;

    // Load providers status
    try {
        const res = await request('settings.list_providers', {});

        const result = res.result?.result || res.result || {};
        providersStatus = result.providers || {};

        renderApiKeysList();
    } catch (e) {
        container.querySelector('#api-keys-loading').innerHTML = `
            <p style="color: var(--error-color);">Error loading providers: ${e.message}</p>
        `;
    }
}

/**
 * Render the API keys list
 */
function renderApiKeysList() {
    const loadingEl = document.getElementById('api-keys-loading');
    const listEl = document.getElementById('api-keys-list');

    if (!listEl) return;

    loadingEl.style.display = 'none';
    listEl.style.display = 'block';

    let html = '<div class="api-keys-grid">';

    for (const [providerId, info] of Object.entries(providersStatus)) {
        const isConfigured = info.configured;
        const statusClass = isConfigured ? 'status-configured' : 'status-not-configured';
        const statusText = isConfigured ? 'Configured' : 'Not configured';

        html += `
            <div class="api-key-card">
                <div class="api-key-header">
                    <span class="provider-name">${info.name}</span>
                    <span class="provider-status ${statusClass}">${statusText}</span>
                </div>
                <div class="api-key-body">
                    ${isConfigured ? `
                        <div class="api-key-actions">
                            <button class="btn btn-sm btn-secondary" onclick="verifyApiKey('${providerId}')">
                                <i data-lucide="check-circle"></i> Verify
                            </button>
                            <button class="btn btn-sm btn-danger" onclick="deleteApiKey('${providerId}')">
                                <i data-lucide="trash-2"></i> Remove
                            </button>
                        </div>
                    ` : `
                        <div class="api-key-input-group">
                            <input type="password" id="api-key-${providerId}" placeholder="Enter API key..." class="api-key-input">
                            <button class="btn btn-sm btn-primary" onclick="saveApiKey('${providerId}')">
                                <i data-lucide="save"></i> Save
                            </button>
                        </div>
                    `}
                </div>
            </div>
        `;
    }

    // Add Ollama detection card
    html += `
        <div class="api-key-card ollama-card">
            <div class="api-key-header">
                <span class="provider-name">Ollama (Local)</span>
                <span class="provider-status" id="ollama-status">Checking...</span>
            </div>
            <div class="api-key-body">
                <button class="btn btn-sm btn-secondary" onclick="detectOllama()">
                    <i data-lucide="search"></i> Detect Ollama
                </button>
                <div id="ollama-models" style="margin-top: 10px; display: none;"></div>
            </div>
        </div>
    `;

    html += '</div>';
    listEl.innerHTML = html;

    if (window.lucide) window.lucide.createIcons();

    // Check Ollama status
    detectOllama();
}

// Global functions for button handlers
window.saveApiKey = async function (provider) {
    const input = document.getElementById(`api-key-${provider}`);
    const apiKey = input?.value?.trim();

    if (!apiKey) {
        alert('Please enter an API key');
        return;
    }

    try {
        const res = await request('settings.store_api_key', { provider, api_key: apiKey });

        const result = res.result?.result || res.result || {};

        if (result.status === 'success') {
            providersStatus[provider] = { ...providersStatus[provider], configured: true };
            renderApiKeysList();
        } else {
            alert('Error: ' + (result.error || 'Failed to save API key'));
        }
    } catch (e) {
        alert('Error: ' + e.message);
    }
};

window.deleteApiKey = async function (provider) {
    if (!confirm(`Remove API key for ${providersStatus[provider]?.name || provider}?`)) {
        return;
    }

    try {
        const res = await request('settings.delete_api_key', { provider });

        const result = res.result?.result || res.result || {};

        if (result.status === 'success') {
            providersStatus[provider] = { ...providersStatus[provider], configured: false };
            renderApiKeysList();
        } else {
            alert('Error: ' + (result.error || 'Failed to delete API key'));
        }
    } catch (e) {
        alert('Error: ' + e.message);
    }
};

window.verifyApiKey = async function (provider) {
    const card = document.querySelector(`.api-key-card`);

    try {
        const res = await request('settings.verify_api_key', { provider });

        const result = res.result?.result || res.result || {};

        if (result.valid) {
            alert(`✅ ${providersStatus[provider]?.name} API key is valid!`);
        } else {
            alert(`❌ ${providersStatus[provider]?.name} API key verification failed: ${result.error || 'Invalid key'}`);
        }
    } catch (e) {
        alert('Error: ' + e.message);
    }
};

window.detectOllama = async function () {
    const statusEl = document.getElementById('ollama-status');
    const modelsEl = document.getElementById('ollama-models');

    if (!statusEl) return;

    statusEl.textContent = 'Checking...';
    statusEl.className = 'provider-status';

    try {
        const res = await request('settings.detect_ollama', {});

        const result = res.result?.result || res.result || {};

        if (result.available) {
            statusEl.textContent = 'Running';
            statusEl.className = 'provider-status status-configured';

            if (modelsEl && result.models?.length) {
                modelsEl.style.display = 'block';
                modelsEl.innerHTML = `
                    <p style="font-size: 0.85rem; color: var(--text-secondary);">
                        ${result.models.length} model(s) available:
                    </p>
                    <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px;">
                        ${result.models.map(m => `
                            <span class="tag">${m.name}</span>
                        `).join('')}
                    </div>
                `;
            }
        } else {
            statusEl.textContent = 'Not running';
            statusEl.className = 'provider-status status-not-configured';
            if (modelsEl) modelsEl.style.display = 'none';
        }
    } catch (e) {
        statusEl.textContent = 'Error';
        statusEl.className = 'provider-status status-not-configured';
    }
};

/**
 * Render Model Categories section
 */
async function renderModelsSection(container) {
    container.innerHTML = `
        <h3>Model Categories</h3>
        <p style="color: var(--text-secondary); margin-bottom: 20px;">
            Assign models to each category. Plugins use these categories to access the appropriate model.
        </p>
        <div id="models-loading" style="text-align: center; padding: 20px;">
            <p>Loading models...</p>
        </div>
        <div id="models-config" style="display: none;"></div>
    `;

    try {
        // Load available models
        const modelsRes = await request('settings.get_available_models', {});
        availableModels = modelsRes.result?.result?.models || modelsRes.result?.models || {};

        // Load category config
        const catRes = await request('settings.get_model_categories', {});
        const catResult = catRes.result?.result || catRes.result || {};
        categoriesInfo = catResult.categories_info || {};
        categoryConfig = catResult.configured || {};

        renderModelsCategoryConfig();
    } catch (e) {
        container.querySelector('#models-loading').innerHTML = `
            <p style="color: var(--error-color);">Error loading models: ${e.message}</p>
        `;
    }
}

/**
 * Render model category configuration
 */
function renderModelsCategoryConfig() {
    const loadingEl = document.getElementById('models-loading');
    const configEl = document.getElementById('models-config');

    if (!configEl) return;

    loadingEl.style.display = 'none';
    configEl.style.display = 'block';

    // Build flat list of all available models
    const allModels = [];
    for (const [providerId, models] of Object.entries(availableModels)) {
        for (const model of models) {
            allModels.push({
                ...model,
                provider: providerId,
                fullId: `${providerId}/${model.id}`
            });
        }
    }

    let html = '<div class="category-config-grid">';

    for (const [categoryId, info] of Object.entries(categoriesInfo)) {
        const currentModel = categoryConfig[categoryId] || '';
        const categoryModels = allModels.filter(m => m.categories.includes(categoryId));

        html += `
            <div class="category-config-card">
                <div class="category-header">
                    <div class="category-title">
                        <i data-lucide="${info.icon || 'cpu'}"></i>
                        <span>${info.name || categoryId}</span>
                    </div>
                    <span class="category-description">${info.description || ''}</span>
                </div>
                <div class="category-body">
                    <select id="category-${categoryId}" class="category-select" onchange="setCategoryModel('${categoryId}', this.value)">
                        <option value="">Not configured</option>
                        ${categoryModels.map(m => `
                            <option value="${m.fullId}" ${currentModel === m.fullId ? 'selected' : ''}>
                                ${m.name} (${m.provider})
                            </option>
                        `).join('')}
                    </select>
                </div>
            </div>
        `;
    }

    html += '</div>';

    if (Object.keys(availableModels).length === 0) {
        html = `
            <div class="empty-state">
                <i data-lucide="alert-circle"></i>
                <p>No models available. Configure API keys first.</p>
            </div>
        `;
    }

    configEl.innerHTML = html;

    if (window.lucide) window.lucide.createIcons();
}

window.setCategoryModel = async function (category, model) {
    if (!model) return;

    try {
        const res = await request('settings.set_model_category', { category, model });

        const result = res.result?.result || res.result || {};

        if (result.status === 'success') {
            categoryConfig[category] = model;
            console.log(`[Settings] Set ${category} model to ${model}`);

            // Emit event so model selector can refresh
            window.dispatchEvent(new CustomEvent('model-categories-updated', {
                detail: { category, model }
            }));
        } else {
            alert('Error: ' + (result.error || 'Failed to save model configuration'));
        }
    } catch (e) {
        alert('Error: ' + e.message);
    }
};

