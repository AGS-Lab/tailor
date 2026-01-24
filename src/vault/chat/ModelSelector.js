/**
 * Model Selector Component
 * 
 * Handles model selection UI for the chat composer toolbar.
 * Supports both category-based selection and specific model selection.
 */

import { request } from '../connection.js';

// Category icon mapping
const CATEGORY_ICONS = {
    'fast': 'zap',
    'thinking': 'brain',
    'code': 'code',
    'vision': 'eye',
    'embedding': 'hash',
    'audio': 'mic'
};

/**
 * ModelSelector class - manages model selection state and UI
 */
export class ModelSelector {
    constructor() {
        this.currentSelection = {
            type: 'category',  // 'category' or 'specific'
            value: 'fast',     // category name or model ID
            displayName: 'Fast',
            actualModel: null,  // The actual model ID being used
            modelInfo: null     // Cached model info for tooltips
        };

        this.categories = {};
        this.availableModels = {};
        this.categoryConfig = {};

        this.container = null;
        this.dropdown = null;
    }

    /**
     * Initialize the model selector
     */
    async init(containerElement) {
        this.container = containerElement;

        // Load categories and models
        await this.loadCategoriesAndModels();

        // Render UI
        this.render();

        // Setup event listeners
        this.setupEventListeners();

        // Listen for settings changes to keep in sync
        this.setupSettingsListener();
    }

    /**
     * Listen for settings changes and refresh
     */
    setupSettingsListener() {
        // Listen for custom event that vault settings emits when categories change
        window.addEventListener('model-categories-updated', async () => {
            console.log('[ModelSelector] Detected settings change, refreshing');
            await this.refresh();
        });

        // Also listen for WebSocket events
        if (window.ws) {
            const originalOnMessage = window.ws.onmessage;
            window.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.event === 'settings.model_category_changed') {
                        this.refresh();
                    }
                } catch (e) { }
                if (originalOnMessage) originalOnMessage(event);
            };
        }
    }

    /**
     * Refresh categories and models from backend
     */
    async refresh() {
        await this.loadCategoriesAndModels();
        this.render();
        this.setupEventListeners();
    }

    /**
     * Load categories and available models from backend
     */
    async loadCategoriesAndModels() {
        try {
            // Get category info
            const catRes = await request('settings.get_model_categories', {});
            if (catRes.result?.status === 'success') {
                this.categories = catRes.result.categories_info || {};
                this.categoryConfig = catRes.result.configured || {};
            }

            // Get available models
            const modelsRes = await request('settings.get_available_models', {});
            if (modelsRes.result?.status === 'success') {
                this.availableModels = modelsRes.result.models || {};
            }
        } catch (e) {
            console.error('[ModelSelector] Failed to load categories/models:', e);
        }
    }

    /**
     * Render the model selector UI
     */
    render() {
        if (!this.container) return;

        const icon = CATEGORY_ICONS[this.currentSelection.value] || 'cpu';
        const displayName = this.currentSelection.displayName;
        const actualModel = this.getActualModelName();

        this.container.innerHTML = `
            <div class="model-selector-container">
                <button class="model-selector-btn" id="model-selector-btn" title="Select model or category">
                    <i data-lucide="${icon}" class="model-icon"></i>
                    <span class="model-name">${displayName}</span>
                    ${actualModel ? `<span class="model-detail">(${actualModel})</span>` : ''}
                    <i data-lucide="chevron-down" class="dropdown-icon"></i>
                </button>
                <div class="model-selector-dropdown hidden" id="model-selector-dropdown">
                    ${this.renderDropdownContent()}
                </div>
            </div>
        `;

        // Store dropdown reference
        this.dropdown = this.container.querySelector('#model-selector-dropdown');

        // Render icons
        if (window.lucide) {
            setTimeout(() => window.lucide.createIcons(), 0);
        }
    }

    /**
     * Render dropdown content with categories and "More models..." option
     */
    renderDropdownContent() {
        let html = '<div class="model-options">';

        // Render category options
        for (const [catId, catInfo] of Object.entries(this.categories)) {
            const icon = catInfo.icon || CATEGORY_ICONS[catId] || 'cpu';
            const isSelected = this.currentSelection.type === 'category' && this.currentSelection.value === catId;
            const configuredModel = this.categoryConfig[catId];
            const modelName = this.extractModelName(configuredModel);

            html += `
                <button class="model-option model-option-category ${isSelected ? 'selected' : ''}" data-category="${catId}">
                    <div class="model-option-main">
                        <i data-lucide="${icon}"></i>
                        <div class="model-option-text">
                            <span class="model-option-title">${catInfo.name || catId}</span>
                            ${modelName ? `<span class="model-option-subtitle">${modelName}</span>` : ''}
                        </div>
                    </div>
                    ${isSelected ? '<i data-lucide="check" class="model-option-check"></i>' : ''}
                </button>
            `;
        }

        // Add divider
        html += '<div class="model-option-divider"></div>';

        // Add "More models..." option
        html += `
            <button class="model-option model-option-advanced" id="model-selector-advanced">
                <div class="model-option-main">
                    <i data-lucide="list"></i>
                    <span class="model-option-title">More models...</span>
                </div>
                <i data-lucide="chevron-right"></i>
            </button>
        `;

        html += '</div>';
        return html;
    }

    /**
     * Setup event listeners for the model selector
     */
    setupEventListeners() {
        const btn = this.container.querySelector('#model-selector-btn');
        const dropdown = this.dropdown;

        // Toggle dropdown
        btn?.addEventListener('click', (e) => {
            e.stopPropagation();
            dropdown?.classList.toggle('hidden');
        });

        // Close dropdown on click outside
        document.addEventListener('click', () => {
            dropdown?.classList.add('hidden');
        });

        // Prevent dropdown from closing when clicking inside
        dropdown?.addEventListener('click', (e) => {
            e.stopPropagation();
        });

        // Category selection
        dropdown?.querySelectorAll('.model-option-category').forEach(option => {
            option.addEventListener('click', async () => {
                const category = option.dataset.category;
                await this.selectCategory(category);
                dropdown.classList.add('hidden');
            });
        });

        // Advanced model picker
        const advancedBtn = dropdown?.querySelector('#model-selector-advanced');
        advancedBtn?.addEventListener('click', () => {
            this.openAdvancedPicker();
            dropdown.classList.add('hidden');
        });

        // Hover tooltip
        btn?.addEventListener('mouseenter', async () => {
            await this.showTooltip(btn);
        });

        btn?.addEventListener('mouseleave', () => {
            this.hideTooltip();
        });
    }

    /**
     * Select a category
     */
    async selectCategory(category) {
        const catInfo = this.categories[category];
        if (!catInfo) return;

        this.currentSelection = {
            type: 'category',
            value: category,
            displayName: catInfo.name || category,
            actualModel: this.categoryConfig[category] || null,
            modelInfo: null
        };

        // Persist to backend
        const chatId = window.activeChatId;
        if (chatId) {
            try {
                await request('chat.set_model', {
                    chat_id: chatId,
                    category: category,
                    model_id: ''
                });
            } catch (e) {
                console.error('[ModelSelector] Failed to persist category:', e);
            }
        }

        // Re-render
        this.render();
        this.setupEventListeners();

        // Show brief notification
        this.showToast(`Switched to ${this.currentSelection.displayName}`);
    }

    /**
     * Select a specific model
     */
    async selectSpecificModel(modelId, modelName) {
        this.currentSelection = {
            type: 'specific',
            value: modelId,
            displayName: modelName || this.extractModelName(modelId),
            actualModel: modelId,
            modelInfo: null
        };

        // Persist to backend
        const chatId = window.activeChatId;
        if (chatId) {
            try {
                await request('chat.set_model', {
                    chat_id: chatId,
                    model_id: modelId,
                    category: ''
                });
            } catch (e) {
                console.error('[ModelSelector] Failed to persist model:', e);
            }
        }

        // Re-render
        this.render();
        this.setupEventListeners();

        // Show brief notification
        this.showToast(`Switched to ${this.currentSelection.displayName}`);
    }

    /**
     * Open advanced model picker modal
     */
    openAdvancedPicker() {
        const modalHtml = this.renderAdvancedPicker();

        if (window.ui && window.ui.showModal) {
            window.ui.showModal('Select Model', modalHtml, '700px');

            setTimeout(() => {
                if (window.lucide) window.lucide.createIcons();
                this.setupAdvancedPickerListeners();
            }, 50);
        }
    }

    /**
     * Render advanced model picker modal content
     */
    renderAdvancedPicker() {
        let html = `
            <div class="advanced-model-picker">
                <input 
                    type="text" 
                    id="model-search" 
                    class="model-search-input" 
                    placeholder="Search models..." 
                />
                <div class="model-provider-groups" id="model-provider-groups">
        `;

        for (const [providerId, models] of Object.entries(this.availableModels)) {
            html += `
                <div class="model-provider-group">
                    <div class="model-provider-header">
                        <i data-lucide="chevron-down" class="provider-toggle"></i>
                        <span class="provider-name">${this.formatProviderName(providerId)}</span>
                        <span class="provider-count">${models.length} models</span>
                    </div>
                    <div class="model-cards">
            `;

            for (const model of models) {
                const isSelected = this.currentSelection.actualModel === this.getFullModelId(providerId, model.id);
                const isCategoryDefault = Object.values(this.categoryConfig).includes(this.getFullModelId(providerId, model.id));

                html += `
                    <div class="model-card ${isSelected ? 'selected' : ''}" data-model-id="${providerId}/${model.id}">
                        <div class="model-card-header">
                            <div class="model-card-radio">
                                <input 
                                    type="radio" 
                                    name="model-selection" 
                                    value="${providerId}/${model.id}"
                                    ${isSelected ? 'checked' : ''}
                                />
                            </div>
                            <div class="model-card-info">
                                <div class="model-card-name">${model.name}</div>
                                ${isCategoryDefault ? '<span class="model-badge">Category default</span>' : ''}
                            </div>
                        </div>
                        <div class="model-card-details">
                            ${model.context_window ? `<span>Context: ${this.formatNumber(model.context_window)} tokens</span>` : ''}
                            ${model.is_local ? '<span class="model-local">Free (Local)</span>' : '<span class="model-pricing-placeholder">Loading pricing...</span>'}
                        </div>
                    </div>
                `;
            }

            html += `
                    </div>
                </div>
            `;
        }

        html += `
                </div>
                
                <!-- Custom Model Input -->
                <div class="custom-model-section">
                    <div class="model-provider-group">
                         <div class="model-provider-header expanded">
                            <i data-lucide="plus" class="provider-icon"></i>
                            <span class="provider-name">Custom Model</span>
                        </div>
                        <div class="custom-model-input-container">
                            <p class="text-sm text-gray-500 mb-2">Enter full model ID (e.g., <code>openrouter/anthropic/claude-3-opus</code> or <code>groq/llama3-70b-8192</code>)</p>
                            <div class="flex gap-2">
                                <input 
                                    type="text" 
                                    id="custom-model-input" 
                                    class="model-search-input flex-1" 
                                    placeholder="provider/model-id" 
                                />
                                <button id="btn-use-custom-model" class="btn btn-primary">Use</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        return html;
    }

    /**
     * Setup listeners for advanced picker
     */
    setupAdvancedPickerListeners() {
        // Search functionality
        const searchInput = document.getElementById('model-search');
        searchInput?.addEventListener('input', (e) => {
            this.filterModels(e.target.value);
        });

        // Provider toggle
        document.querySelectorAll('.model-provider-header').forEach(header => {
            header.addEventListener('click', () => {
                header.parentElement.classList.toggle('collapsed');
            });
        });

        // Model selection
        document.querySelectorAll('.model-card').forEach(card => {
            card.addEventListener('click', async () => {
                const modelId = card.dataset.modelId;
                const radio = card.querySelector('input[type="radio"]');
                if (radio) radio.checked = true;

                // Select model and close modal
                await this.selectSpecificModel(modelId);
                if (window.ui && window.ui.closeModal) {
                    window.ui.closeModal();
                }
            });
        });

        // Load pricing for non-local models
        this.loadModelPricing();

        // Custom model listener
        const customBtn = document.getElementById('btn-use-custom-model');
        const customInput = document.getElementById('custom-model-input');

        customBtn?.addEventListener('click', async () => {
            const modelId = customInput.value.trim();
            if (modelId) {
                await this.selectSpecificModel(modelId, modelId); // Use ID as name for custom
                if (window.ui && window.ui.closeModal) {
                    window.ui.closeModal();
                }
            }
        });
    }

    /**
     * Load pricing for models in advanced picker
     */
    async loadModelPricing() {
        const cards = document.querySelectorAll('.model-card:not(.is-local)');

        for (const card of cards) {
            const modelId = card.dataset.modelId;
            const pricingEl = card.querySelector('.model-pricing-placeholder');

            if (pricingEl) {
                try {
                    const res = await request('settings.get_model_info', { model_id: modelId });
                    if (res.result?.status === 'success') {
                        const modelInfo = res.result.model;
                        const pricing = modelInfo.pricing;

                        if (pricing && (pricing.input || pricing.output)) {
                            pricingEl.innerHTML = `$${pricing.input?.toFixed(2) || '?'} / $${pricing.output?.toFixed(2) || '?'} per 1M`;
                            pricingEl.classList.remove('model-pricing-placeholder');
                            pricingEl.classList.add('model-pricing');
                        } else {
                            pricingEl.textContent = 'Pricing unavailable';
                        }
                    }
                } catch (e) {
                    pricingEl.textContent = 'Error loading pricing';
                }
            }
        }
    }

    /**
     * Filter models in advanced picker
     */
    filterModels(query) {
        const lowerQuery = query.toLowerCase();
        const cards = document.querySelectorAll('.model-card');

        cards.forEach(card => {
            const text = card.textContent.toLowerCase();
            if (text.includes(lowerQuery)) {
                card.style.display = 'block';
            } else {
                card.style.display = 'none';
            }
        });
    }

    /**
     * Show hover tooltip with model info
     */
    async showTooltip(element) {
        // Get or fetch model info
        if (!this.currentSelection.modelInfo && this.currentSelection.actualModel) {
            try {
                const res = await request('settings.get_model_info', {
                    model_id: this.currentSelection.actualModel
                });

                if (res.result?.status === 'success') {
                    this.currentSelection.modelInfo = res.result.model;
                }
            } catch (e) {
                console.error('[ModelSelector] Failed to load model info:', e);
                return;
            }
        }

        const modelInfo = this.currentSelection.modelInfo;
        if (!modelInfo) return;

        // Create tooltip
        const tooltip = document.createElement('div');
        tooltip.className = 'model-tooltip';
        tooltip.innerHTML = this.renderTooltipContent(modelInfo);

        document.body.appendChild(tooltip);

        // Position tooltip
        const rect = element.getBoundingClientRect();
        tooltip.style.top = `${rect.bottom + 8}px`;
        tooltip.style.left = `${rect.left}px`;

        this.activeTooltip = tooltip;
    }

    /**
     * Hide tooltip
     */
    hideTooltip() {
        if (this.activeTooltip) {
            this.activeTooltip.remove();
            this.activeTooltip = null;
        }
    }

    /**
     * Render tooltip content
     */
    renderTooltipContent(modelInfo) {
        return `
            <div class="model-tooltip-header">${modelInfo.name}</div>
            <div class="model-tooltip-body">
                <div class="tooltip-row">
                    <span class="tooltip-label">Provider:</span>
                    <span>${this.formatProviderName(modelInfo.provider)}</span>
                </div>
                ${modelInfo.context_window ? `
                <div class="tooltip-row">
                    <span class="tooltip-label">Context:</span>
                    <span>${this.formatNumber(modelInfo.context_window)} tokens</span>
                </div>
                ` : ''}
                ${!modelInfo.is_local && (modelInfo.pricing?.input || modelInfo.pricing?.output) ? `
                <div class="tooltip-section">
                    <div class="tooltip-section-title">Pricing (per 1M tokens):</div>
                    <div class="tooltip-row">
                        <span class="tooltip-label">Input:</span>
                        <span>$${modelInfo.pricing.input?.toFixed(2) || 'N/A'}</span>
                    </div>
                    <div class="tooltip-row">
                        <span class="tooltip-label">Output:</span>
                        <span>$${modelInfo.pricing.output?.toFixed(2) || 'N/A'}</span>
                    </div>
                </div>
                ` : ''}
                ${modelInfo.is_local ? '<div class="tooltip-local">Free (Local)</div>' : ''}
                ${modelInfo.capabilities?.length ? `
                <div class="tooltip-row">
                    <span class="tooltip-label">Capabilities:</span>
                    <span>${modelInfo.capabilities.join(', ')}</span>
                </div>
                ` : ''}
                ${modelInfo.categories?.length ? `
                <div class="tooltip-row">
                    <span class="tooltip-label">Categories:</span>
                    <span>${modelInfo.categories.map(c => this.categories[c]?.name || c).join(', ')}</span>
                </div>
                ` : ''}
            </div>
        `;
    }

    /**
     * Helper: Extract model name from full ID
     */
    extractModelName(fullId) {
        if (!fullId) return '';
        const idx = fullId.indexOf('/');
        if (idx !== -1) {
            return fullId.substring(idx + 1);
        }
        return fullId;
    }

    /**
     * Helper: Get full model ID
     */
    getFullModelId(provider, modelId) {
        return `${provider}/${modelId}`;
    }

    /**
     * Helper: Get actual model name for display
     */
    getActualModelName() {
        if (this.currentSelection.type === 'specific') {
            return this.extractModelName(this.currentSelection.actualModel);
        }

        const configured = this.categoryConfig[this.currentSelection.value];
        return this.extractModelName(configured);
    }

    /**
     * Helper: Format provider name
     */
    formatProviderName(providerId) {
        const names = {
            'openai': 'OpenAI',
            'anthropic': 'Anthropic',
            'google': 'Google',
            'ollama': 'Ollama',
            'mistral': 'Mistral',
            'groq': 'Groq'
        };
        return names[providerId] || providerId.charAt(0).toUpperCase() + providerId.slice(1);
    }

    /**
     * Helper: Format large numbers
     */
    formatNumber(num) {
        if (!num) return '';
        return num.toLocaleString();
    }

    /**
     * Helper: Show toast notification
     */
    showToast(message) {
        // Use existing toast system if available
        if (window.showToast) {
            window.showToast(message, 'success');
        } else {
            console.log(`[ModelSelector] ${message}`);
        }
    }

    /**
     * Get current selection
     */
    getCurrentSelection() {
        return this.currentSelection;
    }

    /**
     * Set selection from chat metadata (when switching chats)
     */
    setFromMetadata(metadata) {
        if (!metadata) return;

        if (metadata.model_id) {
            this.selectSpecificModel(metadata.model_id);
        } else if (metadata.category) {
            this.selectCategory(metadata.category);
        }
    }
}

// Create singleton instance
let modelSelectorInstance = null;

export function getModelSelector() {
    if (!modelSelectorInstance) {
        modelSelectorInstance = new ModelSelector();
    }
    return modelSelectorInstance;
}
