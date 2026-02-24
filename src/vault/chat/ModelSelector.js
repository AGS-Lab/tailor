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

        this.container.innerHTML = '';

        const wrap = document.createElement('div');
        wrap.className = 'model-selector-container';

        const btn = document.createElement('button');
        btn.className = 'model-selector-btn';
        btn.id = 'model-selector-btn';
        btn.title = 'Select model or category';

        const iconEl = document.createElement('i');
        iconEl.dataset.lucide = icon;
        iconEl.className = 'model-icon';
        btn.appendChild(iconEl);

        const nameEl = document.createElement('span');
        nameEl.className = 'model-name';
        nameEl.textContent = displayName;
        btn.appendChild(nameEl);

        if (actualModel) {
            const detailEl = document.createElement('span');
            detailEl.className = 'model-detail';
            detailEl.textContent = `(${actualModel})`;
            btn.appendChild(detailEl);
        }

        const dropIcon = document.createElement('i');
        dropIcon.dataset.lucide = 'chevron-down';
        dropIcon.className = 'dropdown-icon';
        btn.appendChild(dropIcon);

        const dropdown = document.createElement('div');
        dropdown.className = 'model-selector-dropdown hidden';
        dropdown.id = 'model-selector-dropdown';
        dropdown.appendChild(this.renderDropdownContent());

        wrap.appendChild(btn);
        wrap.appendChild(dropdown);
        this.container.appendChild(wrap);

        // Store dropdown reference
        this.dropdown = dropdown;

        // Render icons
        if (window.lucide) {
            setTimeout(() => window.lucide.createIcons(), 0);
        }
    }

    /**
     * Render dropdown content with categories and "More models..." option
     */
    renderDropdownContent() {
        const container = document.createElement('div');
        container.className = 'model-options';

        // Render category options
        for (const [catId, catInfo] of Object.entries(this.categories)) {
            const icon = catInfo.icon || CATEGORY_ICONS[catId] || 'cpu';
            const isSelected = this.currentSelection.type === 'category' && this.currentSelection.value === catId;
            const configuredModel = this.categoryConfig[catId];
            const modelName = this.extractModelName(configuredModel);

            const btn = document.createElement('button');
            btn.className = `model-option model-option-category ${isSelected ? 'selected' : ''}`;
            btn.dataset.category = catId;

            const mainDiv = document.createElement('div');
            mainDiv.className = 'model-option-main';

            const iEl = document.createElement('i');
            iEl.dataset.lucide = icon;
            mainDiv.appendChild(iEl);

            const textDiv = document.createElement('div');
            textDiv.className = 'model-option-text';

            const titleSpan = document.createElement('span');
            titleSpan.className = 'model-option-title';
            titleSpan.textContent = catInfo.name || catId;
            textDiv.appendChild(titleSpan);

            if (modelName) {
                const subSpan = document.createElement('span');
                subSpan.className = 'model-option-subtitle';
                subSpan.textContent = modelName;
                textDiv.appendChild(subSpan);
            }
            mainDiv.appendChild(textDiv);
            btn.appendChild(mainDiv);

            if (isSelected) {
                const chk = document.createElement('i');
                chk.dataset.lucide = 'check';
                chk.className = 'model-option-check';
                btn.appendChild(chk);
            }
            container.appendChild(btn);
        }

        // Add divider
        const div = document.createElement('div');
        div.className = 'model-option-divider';
        container.appendChild(div);

        // Add "More models..." option
        const advBtn = document.createElement('button');
        advBtn.className = 'model-option model-option-advanced';
        advBtn.id = 'model-selector-advanced';

        const advMain = document.createElement('div');
        advMain.className = 'model-option-main';
        const advI = document.createElement('i');
        advI.dataset.lucide = 'list';
        advMain.appendChild(advI);

        const advText = document.createElement('span');
        advText.className = 'model-option-title';
        advText.textContent = 'More models...';
        advMain.appendChild(advText);

        advBtn.appendChild(advMain);
        const rightI = document.createElement('i');
        rightI.dataset.lucide = 'chevron-right';
        advBtn.appendChild(rightI);

        container.appendChild(advBtn);
        return container;
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
        const container = document.createElement('div');
        container.className = 'advanced-model-picker';

        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.id = 'model-search';
        searchInput.className = 'model-search-input';
        searchInput.placeholder = 'Search models...';
        container.appendChild(searchInput);

        const groups = document.createElement('div');
        groups.className = 'model-provider-groups';
        groups.id = 'model-provider-groups';

        for (const [providerId, models] of Object.entries(this.availableModels)) {
            const groupDiv = document.createElement('div');
            groupDiv.className = 'model-provider-group';

            const headerDiv = document.createElement('div');
            headerDiv.className = 'model-provider-header';

            const chevron = document.createElement('i');
            chevron.dataset.lucide = 'chevron-down';
            chevron.className = 'provider-toggle';
            headerDiv.appendChild(chevron);

            const nameEl = document.createElement('span');
            nameEl.className = 'provider-name';
            nameEl.textContent = this.formatProviderName(providerId);
            headerDiv.appendChild(nameEl);

            const countEl = document.createElement('span');
            countEl.className = 'provider-count';
            countEl.textContent = `${models.length} models`;
            headerDiv.appendChild(countEl);
            groupDiv.appendChild(headerDiv);

            const cardsContainer = document.createElement('div');
            cardsContainer.className = 'model-cards';

            for (const model of models) {
                const isSelected = this.currentSelection.actualModel === this.getFullModelId(providerId, model.id);
                const isCategoryDefault = Object.values(this.categoryConfig).includes(this.getFullModelId(providerId, model.id));

                const card = document.createElement('div');
                card.className = `model-card ${isSelected ? 'selected' : ''}`;
                card.dataset.modelId = `${providerId}/${model.id}`;

                const cardHeader = document.createElement('div');
                cardHeader.className = 'model-card-header';

                const radioDiv = document.createElement('div');
                radioDiv.className = 'model-card-radio';
                const radioInput = document.createElement('input');
                radioInput.type = 'radio';
                radioInput.name = 'model-selection';
                radioInput.value = `${providerId}/${model.id}`;
                if (isSelected) radioInput.checked = true;
                radioDiv.appendChild(radioInput);
                cardHeader.appendChild(radioDiv);

                const cardInfo = document.createElement('div');
                cardInfo.className = 'model-card-info';
                const cardName = document.createElement('div');
                cardName.className = 'model-card-name';
                cardName.textContent = model.name;
                cardInfo.appendChild(cardName);
                if (isCategoryDefault) {
                    const badge = document.createElement('span');
                    badge.className = 'model-badge';
                    badge.textContent = 'Category default';
                    cardInfo.appendChild(badge);
                }
                cardHeader.appendChild(cardInfo);
                card.appendChild(cardHeader);

                const cardDetails = document.createElement('div');
                cardDetails.className = 'model-card-details';
                if (model.context_window) {
                    const ctxSpan = document.createElement('span');
                    ctxSpan.textContent = `Context: ${this.formatNumber(model.context_window)} tokens`;
                    cardDetails.appendChild(ctxSpan);
                }
                const priceSpan = document.createElement('span');
                if (model.is_local) {
                    priceSpan.className = 'model-local';
                    priceSpan.textContent = 'Free (Local)';
                } else {
                    priceSpan.className = 'model-pricing-placeholder';
                    priceSpan.textContent = 'Loading pricing...';
                }
                cardDetails.appendChild(priceSpan);
                card.appendChild(cardDetails);

                cardsContainer.appendChild(card);
            }
            groupDiv.appendChild(cardsContainer);
            groups.appendChild(groupDiv);
        }
        container.appendChild(groups);

        // Custom Model Input
        const customWrapper = document.createElement('div');
        customWrapper.innerHTML = `
            <div class="custom-model-section">
                <div class="model-provider-group">
                        <div class="model-provider-header expanded">
                        <i data-lucide="plus" class="provider-icon"></i>
                        <span class="provider-name">Custom Model</span>
                    </div>
                    <div class="custom-model-input-container">
                        <p class="text-sm text-gray-500 mb-2">Enter full model ID (e.g., <code>openrouter/anthropic/claude-3-opus</code> or <code>groq/llama3-70b-8192</code>)</p>
                        <div class="flex gap-2" style="display:flex;gap:0.5rem">
                            <input 
                                type="text" 
                                id="custom-model-input" 
                                class="model-search-input flex-1" style="flex:1" 
                                placeholder="provider/model-id" 
                            />
                            <button id="btn-use-custom-model" class="btn btn-primary">Use</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        container.appendChild(customWrapper.firstElementChild);
        return container;
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
        const contentElem = this.renderTooltipContent(modelInfo);
        tooltip.innerHTML = '';
        tooltip.appendChild(contentElem);

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
        const wrapper = document.createElement('div');
        wrapper.innerHTML = `
            <div class="model-tooltip-header"></div>
            <div class="model-tooltip-body"></div>
        `;
        const header = wrapper.querySelector('.model-tooltip-header');
        header.textContent = modelInfo.name || '';
        const body = wrapper.querySelector('.model-tooltip-body');

        const mkRow = (label, value) => {
            const div = document.createElement('div');
            div.className = 'tooltip-row';
            const lab = document.createElement('span');
            lab.className = 'tooltip-label';
            lab.textContent = label;
            const val = document.createElement('span');
            val.textContent = value;
            div.appendChild(lab);
            div.appendChild(val);
            return div;
        };

        body.appendChild(mkRow('Provider:', this.formatProviderName(modelInfo.provider)));
        if (modelInfo.context_window) {
            body.appendChild(mkRow('Context:', `${this.formatNumber(modelInfo.context_window)} tokens`));
        }

        if (!modelInfo.is_local && (modelInfo.pricing?.input || modelInfo.pricing?.output)) {
            const pricingDiv = document.createElement('div');
            pricingDiv.className = 'tooltip-section';
            const pricingTitle = document.createElement('div');
            pricingTitle.className = 'tooltip-section-title';
            pricingTitle.textContent = 'Pricing (per 1M tokens):';
            pricingDiv.appendChild(pricingTitle);
            pricingDiv.appendChild(mkRow('Input:', `$${(modelInfo.pricing.input || 0).toFixed(2)}`));
            pricingDiv.appendChild(mkRow('Output:', `$${(modelInfo.pricing.output || 0).toFixed(2)}`));
            body.appendChild(pricingDiv);
        }

        if (modelInfo.is_local) {
            const loc = document.createElement('div');
            loc.className = 'tooltip-local';
            loc.textContent = 'Free (Local)';
            body.appendChild(loc);
        }

        if (modelInfo.capabilities?.length) {
            body.appendChild(mkRow('Capabilities:', modelInfo.capabilities.join(', ')));
        }

        if (modelInfo.categories?.length) {
            body.appendChild(mkRow('Categories:', modelInfo.categories.map(c => this.categories[c]?.name || c).join(', ')));
        }

        return wrapper;
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
