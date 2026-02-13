/**
 * Vault Settings Modal Module
 * 
 * Handles the settings button and modal for vault configuration.
 * Includes API key management and model category selection.
 */

import { autoConnect, request } from './connection.js';
import { settingsApi } from '../services/api.js';

// State for settings
let providersStatus = {};
let availableModels = {};
let categoryConfig = {};
let categoriesInfo = {};
let cachedSettings = null;

// Navigation items configuration
// Fixed items that are not in settings.toml
const FIXED_NAV_ITEMS = [
    { id: 'api-keys', label: 'API Keys', icon: 'key' },
    { id: 'models', label: 'Model Categories', icon: 'brain-circuit' }
];

// Import theme functions
import { applyTheme, loadSavedTheme, initThemes } from '../pages/themes.js';

/**
 * Initialize the settings button
 */
/**
 * Load settings from backend and apply them to the UI on startup
 */
export async function loadAndApplySettings() {
    try {
        const params = new URLSearchParams(window.location.search);
        const vaultPath = params.get('vault') || params.get('path') || '';
        const settings = await settingsApi.getEffectiveSettings(vaultPath);
        if (settings) {
            cachedSettings = settings;
            applySettings(settings);
        }
    } catch (e) {
        console.warn('[Settings] Could not load settings on startup:', e);
    }
}

export function initSettings() {
    if (window.lucide) window.lucide.createIcons();

    // Listen for settings changes to apply them live
    window.addEventListener('settings-changed', (e) => {
        applySettings(e.detail.settings);
    });

    const settingsBtn = document.getElementById('vault-settings-btn');
    if (!settingsBtn) return;

    settingsBtn.addEventListener('click', async () => {
        console.log('[Settings] Opening vault settings');
        cachedSettings = null; // Reset cache on open to fetch fresh

        const params = new URLSearchParams(window.location.search);
        const vaultPath = params.get('vault') || params.get('path') || '';

        // Fetch settings first to generate tabs
        try {
            cachedSettings = await settingsApi.getEffectiveSettings(vaultPath);
        } catch (e) {
            console.error("Failed to load settings for menu generation", e);
            cachedSettings = {};
        }

        // Generate Dynamic Tabs
        const dynamicTabs = [];

        Object.keys(cachedSettings).forEach(key => {
            const val = cachedSettings[key];
            if (val && typeof val === 'object' && !Array.isArray(val) && key !== 'settings') {
                // Capitalize label
                const label = key.charAt(0).toUpperCase() + key.slice(1);
                let icon = 'box';
                if (key === 'editor') icon = 'edit-3';
                if (key === 'plugins') icon = 'package';
                if (key === 'appearance') icon = 'palette';

                dynamicTabs.push({ id: key, label, icon, isDynamic: true });
            }
        });

        // Always ensure General is first
        const allNavItems = [
            { id: 'general', label: 'General', icon: 'settings', isDynamic: true },
            ...dynamicTabs.sort((a, b) => a.label.localeCompare(b.label)), // Sort dynamic tabs
            ...FIXED_NAV_ITEMS
        ];

        if (window.ui && window.ui.showModal) {
            const navItemsHtml = allNavItems.map((item, idx) => `
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
                        <!-- Content loaded dynamically -->
                    </div>
                </div>
            `;

            window.ui.showModal('Vault Settings', settingsHtml, '70%', '70vh');

            setTimeout(() => {
                if (window.lucide) window.lucide.createIcons();
                setupSettingsNavigation(allNavItems, vaultPath);
                // Load default
                renderSettingsSection(document.getElementById('settings-modal-content'), 'general', cachedSettings, vaultPath);
            }, 50);
        } else {
            alert('Vault settings are being loaded...');
        }
    });
}

/**
 * Setup settings navigation
 */
function setupSettingsNavigation(navItemsList, vaultPath) {
    const navItems = document.querySelectorAll('.settings-nav-item-modal');
    const contentEl = document.getElementById('settings-modal-content');

    if (!navItems.length || !contentEl) return;

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            navItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            renderSettingsSection(contentEl, item.dataset.section, cachedSettings, vaultPath);
        });
    });
}

/**
 * Render settings section content
 */
async function renderSettingsSection(container, section, settings, vaultPath) {
    if (!container) return;

    // Handle Fixed Sections
    if (section === 'api-keys') {
        await renderApiKeysSection(container);
        return;
    }
    if (section === 'models') {
        await renderModelsSection(container);
        return;
    }

    // Handle Dynamic Sections
    container.innerHTML = `
        <div class="settings-header">
            <h3>${section.charAt(0).toUpperCase() + section.slice(1)} Settings</h3>
            <p class="settings-description">
                Configure your ${section} settings.
            </p>
        </div>
        <div id="dynamic-settings-form" style="display: flex; flex-direction: column; gap: 24px; margin-top: 20px;"></div>
    `;

    const formContainer = container.querySelector('#dynamic-settings-form');

    // Determine data to render
    let sectionData = {};
    if (section === 'general') {
        // Filter functionality primitives
        Object.keys(settings).forEach(key => {
            const val = settings[key];
            if (typeof val !== 'object' || val === null || Array.isArray(val)) {
                sectionData[key] = val;
            }
        });

        // Add Vault Path as read-only
        formContainer.innerHTML += `
             <div class="setting-item">
                <label>Vault Path</label>
                <div class="setting-value">
                    <code style="background: var(--surface-color); padding: 4px 8px; border-radius: 4px;">${vaultPath}</code>
                </div>
            </div>
        `;
    } else {
        sectionData = settings[section] || {};
    }

    renderDynamicForm(formContainer, sectionData, [section], settings);

    if (window.lucide) window.lucide.createIcons();
}

/**
 * Recursively render form fields
 * path: Array of keys to reach current level (e.g. ['editor'])
 */
function renderDynamicForm(container, data, path, fullSettings) {
    if (!data || Object.keys(data).length === 0) {
        container.innerHTML += `<p class="text-secondary">No settings available.</p>`;
        return;
    }

    Object.keys(data).forEach(key => {
        const val = data[key];
        const currentPath = [...path, key]; // Full path for updates
        const fieldId = currentPath.join('.');

        const itemDiv = document.createElement('div');
        itemDiv.className = 'settings-group'; // Wrapper

        if (typeof val === 'boolean') {
            itemDiv.innerHTML = `
                <div class="settings-item">
                    <label>${formatLabel(key)}</label>
                    <label class="toggle-switch">
                        <input type="checkbox" id="${fieldId}" ${val ? 'checked' : ''}>
                        <span class="slider round"></span>
                    </label>
                </div>
            `;
            // Bind
            setTimeout(() => {
                const el = document.getElementById(fieldId);
                if (el) el.addEventListener('change', (e) => updateSetting(fullSettings, currentPath, e.target.checked));
            }, 0);

        } else if (typeof val === 'number') {
            itemDiv.innerHTML = `
                 <div class="settings-item">
                    <label>${formatLabel(key)}</label>
                    <input type="number" class="filter-select" id="${fieldId}" value="${val}">
                </div>
            `;
            setTimeout(() => {
                const el = document.getElementById(fieldId);
                if (el) el.addEventListener('change', (e) => updateSetting(fullSettings, currentPath, Number(e.target.value)));
            }, 0);

        } else if (typeof val === 'string') {
            // Heuristic for Themes or Enums?
            // If key is 'theme', force a dropdown
            if (key === 'theme') {
                // Hardcoded theme options for now, or fetch?
                // Let's stick to system/light/dark
                itemDiv.innerHTML = `
                    <div class="settings-item">
                        <label>Theme</label>
                        <select class="filter-select" id="${fieldId}">
                            <option value="system" ${val === 'system' ? 'selected' : ''}>System Default</option>
                            <option value="light" ${val === 'light' ? 'selected' : ''}>Light</option>
                            <option value="dark" ${val === 'dark' ? 'selected' : ''}>Dark</option>
                        </select>
                    </div>
                `;
                setTimeout(() => {
                    const el = document.getElementById(fieldId);
                    if (el) el.addEventListener('change', (e) => updateSetting(fullSettings, currentPath, e.target.value));
                }, 0);
            } else {
                itemDiv.innerHTML = `
                     <div class="settings-item">
                        <label>${formatLabel(key)}</label>
                        <input type="text" class="filter-select" id="${fieldId}" value="${val}">
                    </div>
                `;
                setTimeout(() => {
                    const el = document.getElementById(fieldId);
                    if (el) el.addEventListener('change', (e) => updateSetting(fullSettings, currentPath, e.target.value));
                }, 0);
            }
        } else if (typeof val === 'object' && val !== null) {
            // Nested object (subsection)
            itemDiv.className = 'settings-subsection';
            itemDiv.style.marginLeft = '10px';
            itemDiv.style.borderLeft = '2px solid var(--border-subtle)';
            itemDiv.style.paddingLeft = '10px';

            itemDiv.innerHTML = `<h4 style="margin: 10px 0;">${formatLabel(key)}</h4>`;

            // Recurse
            const subContainer = document.createElement('div');
            renderDynamicForm(subContainer, val, currentPath, fullSettings);
            itemDiv.appendChild(subContainer);
        }

        container.appendChild(itemDiv);
    });
}

function formatLabel(key) {
    // camelCase to Words
    return key.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase());
}

async function updateSetting(settings, path, value) {
    // Deep set
    let current = settings;
    for (let i = 0; i < path.length - 1; i++) {
        const key = path[i];
        if (key === 'general') continue; // Virtual root
        if (!current[key]) current[key] = {};
        current = current[key];
    }

    // Handle 'general' stripping
    const lastKey = path[path.length - 1];

    // Correct way:
    // path is ['general', 'theme'] -> settings['theme']
    // path is ['editor', 'fontSize'] -> settings['editor']['fontSize']

    let target = settings;
    if (path[0] === 'general') {
        // Root primitives
        target[lastKey] = value;
    } else {
        // Follow path
        let c = settings;
        for (let i = 0; i < path.length - 1; i++) {
            c = c[path[i]];
        }
        c[lastKey] = value;
    }

    // Save
    try {
        const params = new URLSearchParams(window.location.search);
        const vaultPath = params.get('vault') || params.get('path') || '';
        await settingsApi.saveVaultSettings(settings);

        // Notify app
        window.dispatchEvent(new CustomEvent('settings-changed', { detail: { settings } }));
        console.log('[Settings] Saved:', path.join('.'), value);

    } catch (e) {
        console.error('Failed to save settings:', e);
        alert('Failed to save settings');
    }
}

/**
 * Apply settings to the UI
 */
function applySettings(settings) {
    if (!settings) return;

    // Apply theme
    if (settings.theme) {
        // theme logic is handled by pages/themes.js via event listener?
        // or we call applyTheme here if imported?
        // settings.js imports applyTheme from themes.js
        applyTheme(settings.theme);
    }
}

// -------------------------------------------------------------------------
// Existing Fixed Sections (API Keys, Models) - Reserved
// -------------------------------------------------------------------------

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

    if (loadingEl) loadingEl.style.display = 'none';
    listEl.style.display = 'block';

    const providers = Object.entries(providersStatus);

    if (providers.length === 0) {
        listEl.innerHTML = '<p>No providers found.</p>';
        return;
    }

    listEl.innerHTML = `
        <div class="models-grid" style="grid-template-columns: 1fr;">
            ${providers.map(([id, info]) => `
                <div class="model-card">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
                        <div style="display: flex; align-items: center; gap: 12px;">
                            <div style="
                                width: 40px; 
                                height: 40px; 
                                border-radius: 8px; 
                                background: ${info.configured ? 'rgba(76, 175, 80, 0.1)' : 'var(--surface-color)'}; 
                                display: flex; 
                                align-items: center; 
                                justify-content: center;
                                color: ${info.configured ? '#4caf50' : 'var(--text-secondary)'};
                            ">
                                <i data-lucide="${info.configured ? 'check-circle' : 'key'}"></i>
                            </div>
                            <div>
                                <h4 style="margin: 0 0 4px 0;">${info.name || id}</h4>
                                <span class="badge ${info.configured ? 'badge-primary' : 'badge-secondary'}">
                                    ${info.configured ? 'Configured' : 'Not Configured'}
                                </span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-value" style="display: flex; gap: 8px;">
                            <input type="password" 
                                id="key-${id}" 
                                placeholder="Enter API Key" 
                                value="${info.configured ? '••••••••••••••••' : ''}"
                                style="flex: 1; font-family: monospace;"
                            >
                            <button class="btn btn-secondary" onclick="saveApiKey('${id}')">
                                <i data-lucide="save"></i>
                                Save
                            </button>
                            ${info.configured ? `
                                <button class="btn btn-icon danger" onclick="deleteApiKey('${id}')" title="Delete Key">
                                    <i data-lucide="trash-2"></i>
                                </button>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `).join('')}
        </div>
    `;

    // Expose functions globally for onclick
    window.saveApiKey = async (providerId) => {
        const input = document.getElementById(`key-${providerId}`);
        const key = input.value;

        if (!key) {
            alert('Please enter an API key');
            return;
        }

        try {
            await request('settings.set_provider_key', {
                provider: providerId,
                key: key
            });

            // Reload status
            await renderApiKeysSection(document.getElementById('settings-modal-content'));
            alert('API key saved successfully');
        } catch (e) {
            alert(`Failed to save key: ${e.message}`);
        }
    };

    window.deleteApiKey = async (providerId) => {
        if (!confirm('Are you sure you want to delete this API key?')) return;

        try {
            await request('settings.delete_provider_key', {
                provider: providerId
            });

            // Reload status
            await renderApiKeysSection(document.getElementById('settings-modal-content'));
        } catch (e) {
            alert(`Failed to delete key: ${e.message}`);
        }
    };

    if (window.lucide) window.lucide.createIcons();
}

/**
 * Render Models Config Section
 */
async function renderModelsSection(container) {
    container.innerHTML = `
        <h3>Model Categories</h3>
        <p style="color: var(--text-secondary); margin-bottom: 20px;">
            Select which models to use for different tasks.
        </p>
        <div id="models-loading" style="text-align: center; padding: 20px;">
            <p>Loading configuration...</p>
        </div>
        <div id="models-config-form" style="display: none;"></div>
    `;

    try {
        // Fetch config and available models
        const [configRes, modelsRes] = await Promise.all([
            request('settings.get_model_config', {}),
            request('settings.list_models', {})
        ]);

        categoryConfig = configRes.result || {};
        const modelsData = modelsRes.result || {};
        availableModels = modelsData.models || {};
        categoriesInfo = modelsData.categories || {};

        renderModelsForm();

    } catch (e) {
        container.querySelector('#models-loading').innerHTML = `
            <p style="color: var(--error-color);">Error loading model config: ${e.message}</p>
        `;
    }
}

function renderModelsForm() {
    const loadingEl = document.getElementById('models-loading');
    const formEl = document.getElementById('models-config-form');

    if (!formEl) return;

    if (loadingEl) loadingEl.style.display = 'none';
    formEl.style.display = 'flex';
    formEl.style.flexDirection = 'column';
    formEl.style.gap = '20px';

    // Group models by provider for select options
    const modelOptions = Object.entries(availableModels).map(([id, info]) => {
        return `<option value="${id}">${info.name} (${info.provider})</option>`;
    }).join('');

    const categories = [
        { id: 'chat_model', label: 'Chat & Reasoning', desc: 'Main model used for conversation and planning' },
        { id: 'fast_model', label: 'Fast / Tool Use', desc: 'Smaller model for quick tasks and tool execution' },
        { id: 'embedding_model', label: 'Embeddings', desc: 'Model used for semantic search and memory' }
    ];

    formEl.innerHTML = categories.map(cat => {
        const currentVal = categoryConfig[cat.id];

        return `
            <div class="setting-item">
                <label>
                    ${cat.label}
                    <span style="font-weight: normal; color: var(--text-secondary); font-size: 0.9em; display: block; margin-top: 4px;">
                        ${cat.desc}
                    </span>
                </label>
                <div class="setting-value">
                    <select id="cat-${cat.id}" class="filter-select" onchange="updateModelCategory('${cat.id}', this.value)">
                        <option value="">Select a model...</option>
                        ${Object.entries(availableModels).map(([id, info]) => `
                            <option value="${id}" ${currentVal === id ? 'selected' : ''}>
                                ${info.name} (${info.provider})
                            </option>
                        `).join('')}
                    </select>
                </div>
            </div>
        `;
    }).join('');

    // Expose update function
    window.updateModelCategory = async (category, modelId) => {
        if (!modelId) return;

        try {
            await request('settings.set_model_category', {
                category: category,
                model_id: modelId
            });
            console.log(`Updated ${category} to ${modelId}`);
        } catch (e) {
            console.error('Failed to update model category:', e);
            alert('Failed to update model setting');
        }
    };
}
