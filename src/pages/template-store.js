/**
 * UI Template Store - Browse and install frontend UI templates
 * 
 * Templates are CSS/HTML themes that modify the visual appearance of Tailor
 * without changing backend functionality.
 */

// Sample template data (would be fetched from GitHub API in production)
const SAMPLE_TEMPLATES = [
    {
        id: 'dark-minimal',
        name: 'Dark Minimal',
        description: 'A clean, minimalist dark theme with subtle accents',
        author: 'Tailor Team',
        version: '1.0.0',
        category: 'themes',
        downloads: 1250,
        preview: null,
        repo: 'https://github.com/tailor-dev/ui-dark-minimal'
    },
    {
        id: 'light-modern',
        name: 'Light Modern',
        description: 'A bright, modern light theme with smooth gradients',
        author: 'Community',
        version: '1.2.0',
        category: 'themes',
        downloads: 890,
        preview: null,
        repo: 'https://github.com/tailor-dev/ui-light-modern'
    },
    {
        id: 'cyberpunk-neon',
        name: 'Cyberpunk Neon',
        description: 'Vibrant neon colors with a futuristic feel',
        author: 'NeonDev',
        version: '0.9.0',
        category: 'themes',
        downloads: 2100,
        preview: null,
        repo: 'https://github.com/neondev/tailor-cyberpunk'
    },
    {
        id: 'sidebar-compact',
        name: 'Compact Sidebar',
        description: 'A more compact sidebar layout for smaller screens',
        author: 'UI Labs',
        version: '1.0.0',
        category: 'layouts',
        downloads: 450,
        preview: null,
        repo: 'https://github.com/uilabs/tailor-compact-sidebar'
    },
    {
        id: 'chat-bubble',
        name: 'Bubble Chat UI',
        description: 'Chat messages displayed as bubbles like messaging apps',
        author: 'ChatUI',
        version: '1.1.0',
        category: 'components',
        downloads: 780,
        preview: null,
        repo: 'https://github.com/chatui/tailor-bubble-chat'
    },
    {
        id: 'monaco-editor',
        name: 'Monaco Editor Theme',
        description: 'Code editor styling matching VS Code Monaco theme',
        author: 'DevThemes',
        version: '2.0.0',
        category: 'components',
        downloads: 1500,
        preview: null,
        repo: 'https://github.com/devthemes/tailor-monaco'
    }
];

const CATEGORIES = [
    { id: 'all', name: 'All Templates', icon: 'grid' },
    { id: 'themes', name: 'Color Themes', icon: 'palette' },
    { id: 'layouts', name: 'Layouts', icon: 'layout' },
    { id: 'components', name: 'Components', icon: 'box' }
];

/**
 * Initialize the UI template store page
 */
export function initTemplateStore() {
    const container = document.getElementById('template-store-container');
    if (!container) {
        console.warn('Template store container not found');
        return;
    }

    renderTemplateStore(container);
}

/**
 * Render the template store UI
 */
function renderTemplateStore(container) {
    container.innerHTML = `
        <div class="template-store">
            <header class="store-header">
                <h1>
                    <i data-lucide="brush"></i>
                    UI Template Store
                </h1>
                <p class="subtitle">Browse and install visual themes and UI components</p>
            </header>

            <div class="store-controls">
                <div class="search-box">
                    <i data-lucide="search"></i>
                    <input type="text" id="template-search" placeholder="Search templates..." />
                </div>
                <div class="category-filters" id="category-filters">
                    ${CATEGORIES.map(cat => `
                        <button class="filter-btn ${cat.id === 'all' ? 'active' : ''}" data-category="${cat.id}">
                            <i data-lucide="${cat.icon}"></i>
                            ${cat.name}
                        </button>
                    `).join('')}
                </div>
            </div>

            <div class="template-grid" id="template-grid">
                <!-- Templates rendered here -->
            </div>
        </div>
    `;

    // Initialize icons
    if (window.lucide) {
        window.lucide.createIcons();
    }

    // Render initial templates
    renderTemplates(container, SAMPLE_TEMPLATES);

    // Setup event handlers
    setupEventHandlers(container);
}

/**
 * Render template cards
 */
function renderTemplates(container, templates) {
    const grid = container.querySelector('#template-grid');
    if (!grid) return;

    if (templates.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <i data-lucide="search-x"></i>
                <p>No templates found</p>
            </div>
        `;
        if (window.lucide) window.lucide.createIcons();
        return;
    }

    grid.innerHTML = templates.map(template => `
        <div class="template-card" data-id="${template.id}">
            <div class="template-preview">
                ${template.preview
            ? `<img src="${template.preview}" alt="${template.name}" />`
            : `<div class="preview-placeholder"><i data-lucide="image"></i></div>`
        }
            </div>
            <div class="template-info">
                <h3>${template.name}</h3>
                <p class="template-desc">${template.description}</p>
                <div class="template-meta">
                    <span class="author"><i data-lucide="user"></i> ${template.author}</span>
                    <span class="version">v${template.version}</span>
                    <span class="downloads"><i data-lucide="download"></i> ${template.downloads}</span>
                </div>
                <div class="template-actions">
                    <button class="btn btn-secondary preview-btn" data-id="${template.id}">
                        <i data-lucide="eye"></i> Preview
                    </button>
                    <button class="btn btn-primary install-btn" data-id="${template.id}" data-repo="${template.repo}">
                        <i data-lucide="download"></i> Install
                    </button>
                </div>
            </div>
        </div>
    `).join('');

    if (window.lucide) window.lucide.createIcons();
}

/**
 * Setup event handlers for search and filters
 */
function setupEventHandlers(container) {
    // Search
    const searchInput = container.querySelector('#template-search');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            filterTemplates(container, query);
        });
    }

    // Category filters
    const filterBtns = container.querySelectorAll('.filter-btn');
    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            filterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            filterTemplates(container);
        });
    });

    // Install buttons
    container.addEventListener('click', async (e) => {
        const installBtn = e.target.closest('.install-btn');
        if (installBtn) {
            const templateId = installBtn.dataset.id;
            const templateRepo = installBtn.dataset.repo;
            await installTemplate(templateId, templateRepo, installBtn);
        }

        const previewBtn = e.target.closest('.preview-btn');
        if (previewBtn) {
            const templateId = previewBtn.dataset.id;
            previewTemplate(templateId);
        }
    });
}

/**
 * Filter templates by search query and category
 */
function filterTemplates(container, query = '') {
    const activeCategory = container.querySelector('.filter-btn.active')?.dataset.category || 'all';

    let filtered = SAMPLE_TEMPLATES;

    // Filter by category
    if (activeCategory !== 'all') {
        filtered = filtered.filter(t => t.category === activeCategory);
    }

    // Filter by search query
    if (query) {
        filtered = filtered.filter(t =>
            t.name.toLowerCase().includes(query) ||
            t.description.toLowerCase().includes(query) ||
            t.author.toLowerCase().includes(query)
        );
    }

    renderTemplates(container, filtered);
}

/**
 * Install a UI template
 */
async function installTemplate(templateId, templateRepo, btn) {
    const originalContent = btn.innerHTML;

    try {
        btn.disabled = true;
        btn.innerHTML = '<i data-lucide="loader" class="spinning"></i> Installing...';
        if (window.lucide) window.lucide.createIcons();

        // Templates are installed to vault/ui-templates/ directory
        // For now, show instructions since we need to copy CSS files

        const template = SAMPLE_TEMPLATES.find(t => t.id === templateId);
        if (!template) {
            throw new Error('Template not found');
        }

        // In the future, this would clone the repo and apply CSS
        // For now, show installation instructions
        alert(
            `To install "${template.name}":\n\n` +
            `1. Open terminal in your vault's ui-templates folder\n` +
            `2. Run: git clone ${templateRepo}\n` +
            `3. Update .vault.json to use the template:\n` +
            `   "ui": { "template": "${templateId}" }\n` +
            `4. Restart Tailor to apply the theme`
        );

        btn.innerHTML = '<i data-lucide="check"></i> Instructions Shown';
        btn.classList.add('btn-success');
        if (window.lucide) window.lucide.createIcons();

    } catch (error) {
        console.error('Template install error:', error);
        btn.innerHTML = originalContent;
        btn.disabled = false;
        if (window.lucide) window.lucide.createIcons();
        alert('Failed to install template: ' + error.message);
    }
}

/**
 * Preview a template (show in modal)
 */
function previewTemplate(templateId) {
    const template = SAMPLE_TEMPLATES.find(t => t.id === templateId);
    if (!template) return;

    alert(`Preview for "${template.name}" coming soon!\n\nThis would show a live preview of the template applied to a sample vault.`);
}

// Auto-initialize if container exists
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('template-store-container')) {
        initTemplateStore();
    }
});
