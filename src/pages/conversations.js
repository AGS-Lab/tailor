/**
 * Conversations Page
 * Modern ChatGPT-style conversation browser
 */

import { conversationApi } from '../services/api.js';

export async function initConversations(container) {
    container.innerHTML = `
        <div class="conversations-container">
            <div class="conversations-header">
                <h1>Conversations</h1>
                <div class="search-bar-container">
                    <input type="text" 
                           id="conversation-search" 
                           class="search-input" 
                           placeholder="Search conversations...">
                    <i data-lucide="search" class="search-icon"></i>
                </div>
            </div>

            <div class="conversations-filters">
                <div class="filter-group">
                    <label>Vault</label>
                    <select id="vault-filter" class="filter-select">
                        <option value="">All Vaults</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label>Time</label>
                    <select id="time-filter" class="filter-select">
                        <option value="">All Time</option>
                        <option value="today">Today</option>
                        <option value="week">This Week</option>
                        <option value="month">This Month</option>
                        <option value="year">This Year</option>
                    </select>
                </div>
            </div>

            <div class="conversations-grid" id="conversations-grid">
                <!-- Conversations will be loaded here -->
            </div>

            <div id="conversation-loading" class="loading-indicator" style="display: none;">
                <i data-lucide="loader" class="spinning"></i>
                Loading conversations...
            </div>
        </div>
    `;

    if (window.lucide) {
        window.lucide.createIcons();
    }

    await loadVaultFilter(container);
    await loadConversations(container);
    setupEventListeners(container);
}

async function loadVaultFilter(container) {
    const vaultFilter = container.querySelector('#vault-filter');
    try {
        const vaults = [];
        vaults.forEach(vault => {
            const option = document.createElement('option');
            option.value = vault.path;
            option.textContent = vault.name;
            vaultFilter.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading vaults:', error);
    }
}

async function loadConversations(container, query = '', filters = {}) {
    const grid = container.querySelector('#conversations-grid');
    const loading = container.querySelector('#conversation-loading');

    try {
        loading.style.display = 'flex';
        grid.innerHTML = '';

        const conversations = await getSampleConversations(query, filters);

        if (conversations.length === 0) {
            grid.innerHTML = `
                <div class="empty-state" style="grid-column: 1 / -1;">
                    <i data-lucide="message-square-x"></i>
                    <div class="empty-state-title">No Conversations</div>
                    <div class="empty-state-subtitle">Start a conversation in a vault to see it here</div>
                </div>
            `;
            if (window.lucide) window.lucide.createIcons();
            return;
        }

        grid.innerHTML = conversations.map(conv => `
            <div class="conversation-card" data-conversation-id="${conv.id}">
                <div class="conversation-title">${conv.title || 'Untitled'}</div>
                <p class="conversation-preview">${conv.preview || 'No preview available'}</p>
                <div class="conversation-meta">
                    <span>${conv.vaultName}</span>
                    <span>${formatDate(conv.date)}</span>
                </div>
            </div>
        `).join('');

        if (window.lucide) {
            window.lucide.createIcons();
        }
    } catch (error) {
        console.error('Error loading conversations:', error);
        grid.innerHTML = `<div class="error-message">Failed to load conversations</div>`;
    } finally {
        loading.style.display = 'none';
    }
}

async function getSampleConversations(query, filters) {
    const sample = [
        {
            id: 'conv-1',
            title: 'Plugin Development Discussion',
            vaultName: 'example-vault',
            date: new Date(),
            preview: 'Discussion about plugin architecture and best practices...',
        },
        {
            id: 'conv-2',
            title: 'API Integration Notes',
            vaultName: 'dev-vault',
            date: new Date(Date.now() - 86400000),
            preview: 'Notes on integrating third-party APIs and handling responses...',
        },
    ];

    let filtered = sample;

    if (query) {
        const lower = query.toLowerCase();
        filtered = filtered.filter(c => 
            c.title.toLowerCase().includes(lower) ||
            c.preview.toLowerCase().includes(lower)
        );
    }

    if (filters.vault) {
        filtered = filtered.filter(c => c.vaultName === filters.vault);
    }

    return filtered;
}

function formatDate(date) {
    if (!date) return 'Unknown';
    const d = new Date(date);
    const now = new Date();
    const diff = now - d;
    
    if (diff < 86400000) return 'Today';
    if (diff < 604800000) return 'This week';
    if (diff < 2592000000) return 'This month';
    
    return d.toLocaleDateString();
}

function setupEventListeners(container) {
    const search = container.querySelector('#conversation-search');
    const vault = container.querySelector('#vault-filter');
    const time = container.querySelector('#time-filter');

    let timeout;
    search?.addEventListener('input', (e) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => {
            loadConversations(container, e.target.value, {
                vault: vault?.value || '',
                timeRange: time?.value || '',
            });
        }, 300);
    });

    vault?.addEventListener('change', () => {
        loadConversations(container, search?.value || '', {
            vault: vault.value,
            timeRange: time?.value || '',
        });
    });

    time?.addEventListener('change', () => {
        loadConversations(container, search?.value || '', {
            vault: vault?.value || '',
            timeRange: time.value,
        });
    });
}

