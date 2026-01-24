/**
 * Chat Branches Plugin - Frontend Module
 * 
 * Handles branch UI rendering and event management.
 * Uses Tailor design system tokens from theme.css.
 */
(function () {
    'use strict';

    console.log('[ChatBranches] Frontend module loading...');

    // State
    let lastMetadata = null;
    let isRendering = false;

    /**
     * Cache metadata when history is loaded
     */
    window.addEventListener('chat:historyLoaded', (e) => {
        const { result } = e.detail;
        if (result && result.branches) {
            // Transform metadata to include ID in the object for easier sorting/filtering
            const transformed = {};
            Object.entries(result.branches).forEach(([id, meta]) => {
                transformed[id] = { ...meta, id };
            });
            lastMetadata = transformed;
            console.log('[ChatBranches] Metadata cached:', Object.keys(lastMetadata).length, 'branches');
        }
    });

    /**
     * Inject UI after core chat has rendered
     */
    window.addEventListener('chat:rendered', (e) => {
        if (isRendering || !lastMetadata) return;

        const { history } = e.detail;

        try {
            isRendering = true;
            injectBranchUI(history, lastMetadata);
        } catch (err) {
            console.error('[ChatBranches] Injection error:', err);
        } finally {
            isRendering = false;
        }
    });

    /**
     * Inject branch dividers and tabs into the chat messages
     */
    function injectBranchUI(history, branchesMetadata) {
        const messagesEl = document.getElementById('chat-messages');
        if (!messagesEl) return;

        let lastBranchId = history[0]?.source_branch || null;

        history.forEach((msg, idx) => {
            const currentBranchId = msg.source_branch || null;

            // Detect branch transitions
            if (idx > 0 && currentBranchId !== lastBranchId) {
                const targetBranchId = currentBranchId || lastBranchId;
                const branchToRender = branchesMetadata[targetBranchId];

                if (branchToRender) {
                    const parentId = branchToRender.parent_branch;
                    const siblings = Object.values(branchesMetadata).filter(b =>
                        b.parent_branch === parentId
                    );

                    siblings.sort((a, b) => (a.id || '').localeCompare(b.id || ''));

                    if (siblings.length > 1 || currentBranchId) {
                        const msgEl = messagesEl.querySelector(`[data-message-index="${idx}"]`);
                        if (msgEl) {
                            const divider = createBranchTabsElement(siblings, currentBranchId);
                            messagesEl.insertBefore(divider, msgEl);
                        }
                    }
                }
            }
            lastBranchId = currentBranchId;
        });

        // Forward navigation at the end
        if (lastBranchId && branchesMetadata[lastBranchId]) {
            const children = Object.values(branchesMetadata).filter(b =>
                b.parent_branch === lastBranchId
            );

            if (children.length > 0) {
                children.sort((a, b) => (a.id || '').localeCompare(b.id || ''));
                const forwardTabs = createBranchTabsElement(children, null, true);
                messagesEl.appendChild(forwardTabs);
                messagesEl.scrollTop = messagesEl.scrollHeight;
            }
        }

        if (window.lucide) window.lucide.createIcons();
    }

    /**
     * Create a row of branch tabs
     */
    function createBranchTabsElement(siblings, activeBranchId, isForward = false) {
        const div = document.createElement('div');
        div.className = 'chat-message chat-message-system branch-divider';

        // Use theme variables for styling
        div.style.margin = isForward ? 'var(--spacing-md) 0' : 'var(--spacing-sm) 0';
        div.style.padding = 'var(--spacing-sm) 0';
        div.style.borderTop = isForward ? 'none' : '1px solid var(--border-subtle)';

        const tabsHtml = siblings.map(b => {
            const isActive = b.id === activeBranchId;
            const name = b.display_name || (b.id ? b.id.substring(0, 8) : 'branch');

            // Theming based on active state
            const bg = isActive ? 'var(--accent-primary)' : 'var(--bg-input)';
            const color = isActive ? '#ffffff' : 'var(--text-secondary)';
            const border = isActive ? 'none' : '1px solid var(--border-subtle)';

            return `
                <button 
                    class="branch-tab-btn"
                    data-branch-id="${b.id || ''}"
                    style="
                        background: ${bg};
                        color: ${color};
                        border: ${border};
                        border-radius: 100px;
                        padding: 4px 12px;
                        margin: 4px;
                        font-size: 12px;
                        font-weight: 500;
                        font-family: var(--font-main);
                        cursor: ${isActive ? 'default' : 'pointer'};
                        display: inline-flex;
                        align-items: center;
                        gap: 6px;
                        transition: all 0.2s;
                    "
                    ${isActive ? 'disabled' : ''}
                >
                    <i data-lucide="git-branch" style="width:14px; height:14px;"></i>
                    <span>${escapeHtml(name)}</span>
                </button>
            `;
        }).join('');

        div.innerHTML = `<div class="message-content" style="display: flex; flex-wrap: wrap; align-items: center; justify-content: center; opacity: 0.9;">${tabsHtml}</div>`;

        div.querySelectorAll('.branch-tab-btn').forEach(btn => {
            if (!btn.disabled && btn.dataset.branchId) {
                btn.addEventListener('click', (e) => {
                    e.preventDefault();
                    window.dispatchEvent(new CustomEvent('chat:switchBranch', {
                        detail: { branchId: btn.dataset.branchId }
                    }));
                });

                // Add hover effect via JS since we are injecting style
                btn.addEventListener('mouseenter', () => {
                    if (!btn.disabled) {
                        btn.style.background = 'var(--bg-hover)';
                        btn.style.borderColor = 'var(--accent-primary)';
                    }
                });
                btn.addEventListener('mouseleave', () => {
                    if (!btn.disabled) {
                        btn.style.background = 'var(--bg-input)';
                        btn.style.borderColor = 'var(--border-subtle)';
                    }
                });
            }
        });

        return div;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Event Listeners for API calls
     */
    window.addEventListener('chat:createBranch', async (e) => {
        const { messageId } = e.detail;
        const activeChatId = window.chatModule?.activeChatId;

        if (!activeChatId) return;

        try {
            const res = await window.request('branch.create', {
                chat_id: activeChatId,
                message_id: messageId
            });
            const result = res.result || res;
            if (result.status === 'success') {
                window.chatModule.loadHistory(activeChatId);
            } else {
                console.error('[ChatBranches] Branch creation failed:', result.error);
            }
        } catch (err) { console.error(err); }
    });

    window.addEventListener('chat:switchBranch', async (e) => {
        const { branchId } = e.detail;
        const activeChatId = window.chatModule?.activeChatId;

        if (!activeChatId) return;

        try {
            const res = await window.request('branch.switch', {
                chat_id: activeChatId,
                branch: branchId
            });
            const result = res.result || res;
            if (result.status === 'success') {
                window.chatModule.loadHistory(activeChatId);
            }
        } catch (err) { console.error(err); }
    });

    console.log('[ChatBranches] Plugin ready. Theme variables applied.');
})();
