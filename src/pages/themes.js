/**
 * Themes Page
 * 
 * Theme store where users can browse, preview, and apply visual themes.
 */

// Theme state
let themes = [];
let currentThemeId = localStorage.getItem('tailor-theme') || 'default';

import { settingsApi } from '../services/api.js';
import { listen } from '@tauri-apps/api/event';

/**
 * Initialize the themes page
 */
export async function initThemes(container) {
    container.innerHTML = `
        <div class="themes-container">
            <div class="themes-header">
                <div class="themes-header-content">
                    <h1>Theme Store</h1>
                    <p class="themes-tagline">Personalize your Tailor experience</p>
                </div>
                <button class="btn btn-secondary" id="reset-theme-btn">
                    <i data-lucide="rotate-ccw"></i>
                    Reset to Default
                </button>
            </div>

            <div class="themes-grid" id="themes-grid">
                <div class="loading-state">
                    <i data-lucide="loader" class="spinning"></i>
                    <span>Loading themes...</span>
                </div>
            </div>
        </div>
    `;

    // Initialize icons
    if (window.lucide) {
        window.lucide.createIcons();
    }

    // Load themes
    await loadThemes(container);

    // Setup event listeners
    setupEventListeners(container);
}

/**
 * Load themes from registry
 */
async function loadThemes(container) {
    const grid = container.querySelector('#themes-grid');

    try {
        const response = await fetch('/theme-registry.json');
        const data = await response.json();
        themes = data.themes || [];

        renderThemes(grid);
    } catch (error) {
        console.error('[Themes] Failed to load themes:', error);
        grid.innerHTML = `
            <div class="error-message">
                Failed to load themes. Please try again later.
            </div>
        `;
    }
}

/**
 * Render theme cards
 */
function renderThemes(grid) {
    if (!themes.length) {
        grid.innerHTML = `
            <div class="empty-state">
                <i data-lucide="palette"></i>
                <p>No themes available</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = themes.map((theme, index) => `
        <div class="theme-card ${theme.id === currentThemeId ? 'active' : ''}" 
             data-theme-id="${theme.id}"
             style="animation-delay: ${index * 0.05}s">
            <div class="theme-preview" style="
                --preview-bg: ${theme.variables['--bg-app']};
                --preview-card: ${theme.variables['--bg-card']};
                --preview-sidebar: ${theme.variables['--bg-sidebar']};
                --preview-text: ${theme.variables['--text-primary']};
                --preview-accent: ${theme.variables['--accent-primary']};
                --preview-border: ${theme.variables['--border-subtle']};
            ">
                <div class="preview-sidebar">
                    <div class="preview-nav-item"></div>
                    <div class="preview-nav-item active"></div>
                    <div class="preview-nav-item"></div>
                </div>
                <div class="preview-content">
                    <div class="preview-header"></div>
                    <div class="preview-card">
                        <div class="preview-line"></div>
                        <div class="preview-line short"></div>
                    </div>
                    <div class="preview-card">
                        <div class="preview-line"></div>
                        <div class="preview-line short"></div>
                    </div>
                </div>
            </div>
            <div class="theme-info">
                <div class="theme-header">
                    <h3>${theme.name}</h3>
                    ${theme.id === currentThemeId ? '<span class="theme-badge">Applied</span>' : ''}
                </div>
                <p class="theme-author">by ${theme.author}</p>
                <p class="theme-description">${theme.description}</p>
                <div class="theme-colors">
                    <div class="color-swatch" style="background: ${theme.variables['--bg-app']}" title="Background"></div>
                    <div class="color-swatch" style="background: ${theme.variables['--bg-card']}" title="Card"></div>
                    <div class="color-swatch" style="background: ${theme.variables['--accent-primary']}" title="Accent"></div>
                    <div class="color-swatch" style="background: ${theme.variables['--text-primary']}" title="Text"></div>
                    <div class="color-swatch" style="background: ${theme.variables['--accent-success']}" title="Success"></div>
                    <div class="color-swatch" style="background: ${theme.variables['--accent-error']}" title="Error"></div>
                </div>
            </div>
            <div class="theme-actions">
                <button class="btn ${theme.id === currentThemeId ? 'btn-secondary' : 'btn-primary'} apply-theme-btn">
                    ${theme.id === currentThemeId ? 'Applied' : 'Apply Theme'}
                </button>
            </div>
        </div>
    `).join('');

    if (window.lucide) {
        window.lucide.createIcons();
    }
}

/**
 * Convert hex color to RGB values
 */
function hexToRgb(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    if (result) {
        return `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}`;
    }
    return '0, 135, 108'; // fallback
}

/**
 * Apply a theme
 */
export async function applyTheme(themeId) {
    if (!themes.length) {
        // Try to load themes if not loaded
        try {
            const response = await fetch('/theme-registry.json');
            const data = await response.json();
            themes = data.themes || [];
        } catch (e) {
            console.error('[Themes] Failed to auto-load themes:', e);
            return;
        }
    }

    const theme = themes.find(t => t.id === themeId);
    if (!theme) return;

    const root = document.documentElement;

    // Apply all CSS variables from theme
    for (const [key, value] of Object.entries(theme.variables)) {
        root.style.setProperty(key, value);
    }

    // Compute and apply derived/compatibility variables
    const accentPrimary = theme.variables['--accent-primary'] || '#00876c';
    const accentRgb = hexToRgb(accentPrimary);

    root.style.setProperty('--primary-rgb', accentRgb);
    root.style.setProperty('--primary-color', accentPrimary);
    root.style.setProperty('--primary-color-alpha', `rgba(${accentRgb}, 0.1)`);
    root.style.setProperty('--border-color', theme.variables['--border-subtle'] || '#eaecf0');
    root.style.setProperty('--hover-color', theme.variables['--bg-hover'] || '#f0f2f5');
    root.style.setProperty('--text-tertiary', theme.variables['--text-disabled'] || '#97a0af');

    const successColor = theme.variables['--accent-success'] || '#2f9e44';
    const successRgb = hexToRgb(successColor);
    root.style.setProperty('--success-color', successColor);
    root.style.setProperty('--success-color-alpha', `rgba(${successRgb}, 0.1)`);

    // Save to localStorage
    localStorage.setItem('tailor-theme', themeId);
    currentThemeId = themeId;

    // Save to Backend (Global Settings)
    try {
        // We need to fetch current global settings first to avoid overwriting other keys?
        // Actually saveGlobalSettings overwrites the file in current impl.
        // Let's fetch first.
        const currentGlobal = await settingsApi.getGlobalSettings();
        currentGlobal.theme = themeId;
        await settingsApi.saveGlobalSettings(currentGlobal);
        console.log(`[Themes] Saved theme to backend: ${themeId}`);
    } catch (e) {
        console.error('[Themes] Failed to save theme to backend:', e);
    }

    // Re-render to update active states
    const grid = document.getElementById('themes-grid');
    if (grid) {
        renderThemes(grid);
    }

    console.log(`[Themes] Applied theme: ${theme.name}`);
}

/**
 * Reset to default theme
 */
export function resetTheme() {
    applyTheme('default');
}

/**
 * Setup event listeners
 */
function setupEventListeners(container) {
    // Theme card clicks
    container.addEventListener('click', (e) => {
        const applyBtn = e.target.closest('.apply-theme-btn');
        if (applyBtn) {
            const card = applyBtn.closest('.theme-card');
            const themeId = card?.dataset.themeId;
            if (themeId && themeId !== currentThemeId) {
                applyTheme(themeId);
            }
            return;
        }

        // Preview on card click (not on button)
        const card = e.target.closest('.theme-card');
        if (card && !e.target.closest('.apply-theme-btn')) {
            const themeId = card.dataset.themeId;
            // Could implement hover preview here
        }
    });

    // Reset button
    const resetBtn = container.querySelector('#reset-theme-btn');
    resetBtn?.addEventListener('click', resetTheme);
}

/**
 * Load saved theme on app startup
 * Call this from the main app initialization
 */
export async function loadSavedTheme() {
    const savedThemeId = localStorage.getItem('tailor-theme');
    if (!savedThemeId || savedThemeId === 'default') return;

    try {
        const response = await fetch('/theme-registry.json');
        const data = await response.json();
        const theme = data.themes?.find(t => t.id === savedThemeId);

        if (theme) {
            const root = document.documentElement;

            // Apply all CSS variables from theme
            for (const [key, value] of Object.entries(theme.variables)) {
                root.style.setProperty(key, value);
            }

            // Compute and apply derived/compatibility variables
            const accentPrimary = theme.variables['--accent-primary'] || '#00876c';
            const accentRgb = hexToRgb(accentPrimary);

            root.style.setProperty('--primary-rgb', accentRgb);
            root.style.setProperty('--primary-color', accentPrimary);
            root.style.setProperty('--primary-color-alpha', `rgba(${accentRgb}, 0.1)`);
            root.style.setProperty('--border-color', theme.variables['--border-subtle'] || '#eaecf0');
            root.style.setProperty('--hover-color', theme.variables['--bg-hover'] || '#f0f2f5');
            root.style.setProperty('--text-tertiary', theme.variables['--text-disabled'] || '#97a0af');

            const successColor = theme.variables['--accent-success'] || '#2f9e44';
            const successRgb = hexToRgb(successColor);
            root.style.setProperty('--success-color', successColor);
            root.style.setProperty('--success-color-alpha', `rgba(${successRgb}, 0.1)`);

            console.log(`[Themes] Loaded saved theme: ${theme.name}`);
        }
    } catch (error) {
        console.error('[Themes] Failed to load saved theme:', error);
    }
}

/**
 * Setup global listener for theme changes across windows 
 */
export async function setupGlobalThemeListener() {
    try {
        await listen('theme-changed', (event) => {
            const settings = event.payload;
            if (settings && settings.theme) {
                if (settings.theme !== currentThemeId) {
                    if (settings.theme === 'system') {
                        // system means clear localStorage and revert to default styling logic
                        localStorage.removeItem('tailor-theme');
                        applyTheme('default');
                    } else {
                        applyTheme(settings.theme);
                    }
                }
            }
        });
        console.log('[Themes] Global theme listener initialized');
    } catch (err) {
        console.error('[Themes] Failed to setup global theme listener:', err);
    }
}
