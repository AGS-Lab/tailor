/**
 * Core Chat Module - Main Entry Point
 * 
 * Built-in chat interface that replaces the LLM plugin.
 * Uses LiteLLM backend for provider-agnostic LLM access.
 */

import { request } from '../connection.js';
import { createToolbar, registerAction, refreshComposerToolbar } from './MessageActionToolbar.js';
import { getModelSelector } from './ModelSelector.js';
import { settingsApi } from '../../services/api.js';

// Chat state
let conversationHistory = [];
let isWaitingForResponse = false;
let currentCategory = 'fast';
let messageIdCounter = 0;
let activeChatId = null;
let modelSelector = null;  // Model selector instance

// Streaming state
let activeStreamId = null;
let activeStreamElement = null;
let enableStreaming = true; // Toggle streaming mode

/**
 * Initialize global chat listeners (run once)
 */
export function initChatGlobals() {
    if (window.__chatGlobalsInitialized) return;

    // Setup chat event listeners for toolbar actions
    setupToolbarEventListeners();

    // Setup streaming event listeners
    setupStreamEventListeners();

    // Setup Smart Context highlight event listeners
    setupSmartContextEventListeners();

    window.__chatGlobalsInitialized = true;
    console.log('[Chat] Global listeners initialized');
}

/**
 * Initialize the chat module (DOM encapsulation)
 */
export function initChat(containerEl) {
    if (!containerEl) {
        console.error('[Chat] Container element not provided');
        return;
    }

    // Render chat UI
    containerEl.innerHTML = getChatHTML();

    // Bind events
    bindEvents(containerEl);

    // Initialize composer toolbar with registered actions
    refreshComposerToolbar();

    // Initialize model selector
    initializeModelSelector();

    // Add welcome message with a specific class for removal later
    addSystemMessage('Welcome! Type a message to start chatting.', 'welcome-message');

    // Initialize icons after a short delay
    setTimeout(() => {
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }, 50);

    if (window.activeChatId || activeChatId) {
        if (!activeChatId) activeChatId = window.activeChatId;
        loadHistory(activeChatId);
    }

    // Load settings from vault config
    loadSettings();

    console.log('[Chat] Core chat module initialized');
}

/**
 * Load settings from vault configuration
 */
async function loadSettings() {
    try {
        const vaultPath = getCurrentVault();
        if (!vaultPath || vaultPath === 'default') return;

        const settings = await settingsApi.getEffectiveSettings(vaultPath);
        if (settings) {
            // Apply streaming setting
            if (typeof settings.streaming === 'boolean') {
                enableStreaming = settings.streaming;
            }

            // Apply default category for new chats
            if (settings.default_category && !activeChatId && !window.activeChatId) {
                setCategory(settings.default_category);
            }
        }
    } catch (e) {
        console.warn('[Chat] Failed to load settings:', e);
    }
}

/**
 * Load history from backend
 */
async function loadHistory(chatId) {
    if (!chatId) return;

    try {
        setStatus('Loading history...');
        const res = await request('chat.get_history', {
            chat_id: chatId
        });

        // Update activeChatId to ensure we are sending to the correct chat
        if (chatId) {
            activeChatId = chatId;
            window.activeChatId = chatId;
        }

        const result = res.result || {};
        if (result.status === 'success') {
            conversationHistory = result.history || [];

            // Dispatch event so plugins can see the raw data (including branches)
            window.dispatchEvent(new CustomEvent('chat:historyLoaded', {
                detail: { chatId, result }
            }));

            // Clear current messages
            const messagesEl = document.getElementById('chat-messages');
            if (messagesEl) messagesEl.innerHTML = ''; // Redundant but safe

            renderConversation(conversationHistory);

            setStatus('Ready');
        } else {
            console.warn('[Chat] Failed to load history:', result.error);
            setStatus('Ready');
        }
    } catch (e) {
        console.error('[Chat] History load error:', e);
        setStatus('Error loading history');
    }
}

/**
 * Get the chat HTML template
 */
function getChatHTML() {
    return `
        <div class="chat-container">
            <div class="chat-header">
                <div class="chat-title">
                    <div class="tailor-logo">
                        <i data-lucide="sparkles"></i>
                    </div>
                    <span>Tailor</span>
                </div>
                <div class="chat-actions">
                    <div class="header-dropdown-container">
                        <button class="icon-btn" id="header-menu-btn" title="Chat Options">
                            <i data-lucide="more-horizontal"></i>
                        </button>
                        <div class="header-dropdown-menu" id="header-dropdown">
                            <button class="dropdown-item" data-action="move">
                                <i data-lucide="folder-output"></i>
                                <span>Move to project</span>
                            </button>
                            <button class="dropdown-item" data-action="pin">
                                <i data-lucide="pin"></i>
                                <span>Pin this chat</span>
                            </button>
                            <button class="dropdown-item" data-action="archive">
                                <i data-lucide="archive"></i>
                                <span>Archive</span>
                            </button>
                            <div class="dropdown-divider"></div>
                            <button class="dropdown-item text-error" data-action="clear" id="chat-clear">
                                <i data-lucide="trash-2"></i>
                                <span>Clear Chat</span>
                            </button>
                            <button class="dropdown-item text-error" data-action="delete">
                                <i data-lucide="trash"></i>
                                <span>Delete</span>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            <div class="chat-messages" id="chat-messages">
                <!-- Messages will be inserted here -->
            </div>
            <div class="chat-input-area">
                <div class="chat-input-wrapper">
                    <textarea 
                        id="chat-input" 
                        class="chat-input" 
                        placeholder="Type your message..." 
                        rows="1"
                    ></textarea>
                    <div id="composer-toolbar" class="composer-action-toolbar">
                        <div class="toolbar-actions">
                            <!-- Plugin actions will be inserted here (far left) -->
                        </div>
                        <div class="toolbar-right">
                            <div id="model-selector-wrapper" class="model-selector-wrapper"></div>
                            <div class="toolbar-send">
                                <button class="chat-send-btn" id="chat-send" title="Send Message">
                                    <i data-lucide="arrow-up"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

/**
 * Bind event listeners
 */
function bindEvents(container) {
    const input = container.querySelector('#chat-input');
    const sendBtn = container.querySelector('#chat-send');
    const clearBtn = container.querySelector('#chat-clear');

    // Send on button click
    sendBtn?.addEventListener('click', () => sendMessage());

    // Send on Enter (Shift+Enter for newline)
    input?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Auto-resize textarea
    input?.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 150) + 'px';
    });

    // Toggle header dropdown
    const menuBtn = container.querySelector('#header-menu-btn');
    const dropdown = container.querySelector('#header-dropdown');

    menuBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        dropdown?.classList.toggle('active');
    });

    // Close dropdown on click outside
    document.addEventListener('click', () => {
        dropdown?.classList.remove('active');
    });

    // Menu actions
    dropdown?.addEventListener('click', (e) => {
        const item = e.target.closest('.dropdown-item');
        if (!item) return;

        const action = item.dataset.action;
        console.log(`[Chat] Action triggered: ${action}`);

        if (action === 'clear') {
            clearChat();
        } else {
            // Placeholder for other actions
            window.ui.showModal('Action', `Feature "${action}" is coming soon!`);
        }
        dropdown.classList.remove('active');
    });

    // Clear chat (fallback if needed, though handled in dropdown above)
    // clearBtn is now part of the dropdown
    const clearBtnInMenu = dropdown?.querySelector('#chat-clear');
    clearBtnInMenu?.addEventListener('click', () => clearChat());

    // Initialize Lucide icons
    if (window.lucide) {
        setTimeout(() => window.lucide.createIcons(), 0);
    }
}


/**
 * Send a message (supports both streaming and non-streaming modes)
 */
async function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input?.value?.trim();

    if (!message || isWaitingForResponse) return;

    // Clear input
    input.value = '';
    input.style.height = 'auto';

    // Remove welcome message if it exists (only on first message)
    const welcomeMsg = document.querySelector('.welcome-message');
    if (welcomeMsg) {
        welcomeMsg.remove();
    }

    // Add user message to UI
    const userMsgEl = addMessage('user', message);

    // Add to history
    conversationHistory.push({ role: 'user', content: message });

    // Show loading state
    setStatus(enableStreaming ? 'Streaming...' : 'Thinking...');
    isWaitingForResponse = true;

    // Create assistant message placeholder
    const assistantMsgEl = addMessage('assistant', '', true);

    // Generate stream ID for this request (Backend authority, but we can pass null to let backend generate)
    const streamId = null; // Let backend generate it

    // Store active stream info (for streaming mode)
    if (enableStreaming) {
        // We don't have stream_id yet, will get it from START event
        activeStreamElement = assistantMsgEl;
        // activeStreamId will be set in CHAT_STREAM_START
    }

    // Ensure we have a chat ID for this conversation
    // Backend Authority: Send null if new chat, backend will generate and return it
    if (!activeChatId) {
        // activeChatId = `chat_${Math.floor(Date.now() / 1000)}`;
        // Don't generate locally
    }
    // Expose globally for plugins
    // window.activeChatId = activeChatId; // Will update after response

    // Get current model selection from model selector
    let selectedModel = null;
    let selectedCategory = currentCategory;

    if (modelSelector) {
        const selection = modelSelector.getCurrentSelection();
        if (selection.type === 'specific' && selection.actualModel) {
            selectedModel = selection.actualModel;
        } else if (selection.type === 'category') {
            selectedCategory = selection.value;
        }
    }

    try {
        const res = await request('chat.send', {
            message: message,
            history: [], // Backend manages history now
            category: selectedCategory,
            model: selectedModel,  // Pass specific model if selected
            stream: enableStreaming,
            stream_id: streamId,
            chat_id: activeChatId
        });

        const result = res.result?.result || res.result || {};

        if (result.status === 'success') {
            if (result.chat_id) {
                activeChatId = result.chat_id;
                window.activeChatId = activeChatId;
            }

            // For streaming, the response is already shown via events
            // For non-streaming, update the message now
            // For non-streaming, update the message now
            // For non-streaming, update the message now
            if (!enableStreaming || !result.streaming) {
                // Update IDs from backend response FIRST
                if (result.message_ids) {
                    const { user_message_id, assistant_message_id } = result.message_ids;

                    // Update DOM
                    if (userMsgEl) userMsgEl.dataset.messageId = user_message_id;
                    if (assistantMsgEl) assistantMsgEl.dataset.messageId = assistant_message_id;

                    // Update History
                    const histLen = conversationHistory.length;
                    if (histLen >= 2) {
                        conversationHistory[histLen - 2].id = user_message_id;
                        conversationHistory[histLen - 1].id = assistant_message_id;
                    }
                }

                // Then update content (which creates toolbar with correct ID)
                const responseText = result.response || '';
                updateMessage(assistantMsgEl, responseText);
                conversationHistory.push({ role: 'assistant', content: responseText });
            }
            // Note: For streaming mode, history is updated in handleStreamEnd

            setStatus('Ready');
        } else {
            const error = result.error || 'Unknown error';
            // Only update if streaming hasn't already shown the error
            if (!enableStreaming || activeStreamId === streamId) {
                updateMessage(assistantMsgEl, `Error: ${error}`, true);
            }
            setStatus('Error');
        }
    } catch (e) {
        console.error('[Chat] Send error:', e);
        updateMessage(assistantMsgEl, `Error: ${e.message || e}`, true);
        setStatus('Error');
    } finally {
        // For non-streaming mode, we can clean up immediately
        // For streaming mode, the CHAT_STREAM_END event handler will clean up
        if (!enableStreaming) {
            isWaitingForResponse = false;
            activeStreamId = null;
            activeStreamElement = null;
        }
        // Note: For streaming, isWaitingForResponse and activeStream* are cleared in the CHAT_STREAM_END handler
    }
}

/**
 * Add a message to the chat
 */
function addMessage(role, content, isLoading = false, id = null) {
    const messagesEl = document.getElementById('chat-messages');
    if (!messagesEl) return null;

    const messageId = id || `msg-${++messageIdCounter}`;
    const messageIndex = conversationHistory.length;

    const msgEl = document.createElement('div');
    msgEl.className = `chat-message chat-message-${role}`;
    msgEl.dataset.messageId = messageId;
    msgEl.dataset.messageIndex = messageIndex;

    const iconName = role === 'user' ? 'user' : 'bot';

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    const icon = document.createElement('i');
    icon.dataset.lucide = iconName;
    avatar.appendChild(icon);
    msgEl.appendChild(avatar);

    const wrapper = document.createElement('div');
    wrapper.className = 'message-content-wrapper';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    if (isLoading) {
        const loading = document.createElement('div');
        loading.className = 'message-loading';
        loading.appendChild(document.createElement('span'));
        loading.appendChild(document.createElement('span'));
        loading.appendChild(document.createElement('span'));
        contentDiv.appendChild(loading);
    } else {
        contentDiv.innerHTML = escapeHtml(content);
    }

    const tbContainer = document.createElement('div');
    tbContainer.className = 'message-toolbar-container';

    wrapper.appendChild(contentDiv);
    wrapper.appendChild(tbContainer);
    msgEl.appendChild(wrapper);

    // Add toolbar for assistant messages only (not user, not system, not loading)
    if (role === 'assistant' && !isLoading) {
        const toolbarContainer = msgEl.querySelector('.message-toolbar-container');
        const message = { id: messageId, role, content };
        const context = {
            index: messageIndex,
            history: conversationHistory,
            vault: getCurrentVault()
        };
        const toolbar = createToolbar(message, context);
        toolbarContainer.appendChild(toolbar);
    }

    messagesEl.appendChild(msgEl);
    messagesEl.scrollTop = messagesEl.scrollHeight;

    // Render icons
    if (window.lucide) {
        setTimeout(() => window.lucide.createIcons(), 0);
    }

    return msgEl;
}

/**
 * Update an existing message element
 */
function updateMessage(msgEl, content, isError = false) {
    if (!msgEl) return;

    const contentEl = msgEl.querySelector('.message-content');
    if (contentEl) {
        contentEl.innerHTML = isError
            ? `<span class="message-error">${escapeHtml(content)}</span>`
            : escapeHtml(content);

        if (isError) {
            msgEl.classList.add('chat-message-error');
        }
    }

    // Add toolbar if not present (for assistant messages after loading completes)
    const toolbarContainer = msgEl.querySelector('.message-toolbar-container');
    const isAssistant = msgEl.classList.contains('chat-message-assistant');
    if (toolbarContainer && !toolbarContainer.querySelector('.message-action-toolbar') && !isError && isAssistant) {
        const messageId = msgEl.dataset.messageId;
        const messageIndex = parseInt(msgEl.dataset.messageIndex || '0', 10);

        const message = { id: messageId, role: 'assistant', content };
        const context = {
            index: messageIndex,
            history: conversationHistory,
            vault: getCurrentVault()
        };
        const toolbar = createToolbar(message, context);
        toolbarContainer.appendChild(toolbar);

        if (window.lucide) {
            setTimeout(() => window.lucide.createIcons(), 0);
        }
    }

    // Scroll to bottom
    const messagesEl = document.getElementById('chat-messages');
    if (messagesEl) {
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }
}

/**
 * Add a system message
 */
function addSystemMessage(content, className = '', allowHtml = false) {
    const messagesEl = document.getElementById('chat-messages');
    if (!messagesEl) return;

    const msgEl = document.createElement('div');
    msgEl.className = 'chat-message chat-message-system';
    if (className) {
        msgEl.classList.add(className);
    }

    // Check if content is already escaped/safe or needs escaping
    const innerContent = allowHtml ? content : escapeHtml(content);
    msgEl.innerHTML = `<div class="message-content">${innerContent}</div>`;

    messagesEl.appendChild(msgEl);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

/**
 * Clear the chat
 */
function clearChat() {
    conversationHistory = [];
    activeChatId = null;
    window.activeChatId = null;  // Also clear global so sidebar sync doesn't re-highlight

    const messagesEl = document.getElementById('chat-messages');
    if (messagesEl) {
        messagesEl.innerHTML = '';
    }

    addSystemMessage('Chat cleared. Start a new conversation.');
    setStatus('Ready');
}

/**
 * Set the status text
 */
function setStatus(status) {
    const statusEl = document.getElementById('chat-status');
    if (statusEl) {
        statusEl.textContent = status;
    }
}

/**
 * Set the current model category
 */
export function setCategory(category) {
    currentCategory = category;
    const modelEl = document.getElementById('chat-model');
    if (modelEl) {
        modelEl.textContent = category;
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/\n/g, '<br>');
}

/**
 * Initialize the model selector component
 */
async function initializeModelSelector() {
    const wrapper = document.getElementById('model-selector-wrapper');
    if (!wrapper) {
        console.warn('[Chat] Model selector wrapper not found');
        return;
    }

    modelSelector = getModelSelector();
    await modelSelector.init(wrapper);

    // Setup keyboard shortcut for cycling categories (Cmd/Ctrl + M)
    document.addEventListener('keydown', handleModelSelectorKeyboard);
}

/**
 * Handle keyboard shortcuts for model selector
 */
function handleModelSelectorKeyboard(e) {
    // Cmd/Ctrl + M: Cycle through categories
    if ((e.metaKey || e.ctrlKey) && e.key === 'm') {
        e.preventDefault();
        cycleModelCategory();
    }
}

/**
 * Cycle through model categories
 */
async function cycleModelCategory() {
    if (!modelSelector) return;

    const categories = ['fast', 'thinking', 'code', 'vision'];
    const current = modelSelector.getCurrentSelection();

    // Only cycle if currently on a category (not a specific model)
    if (current.type !== 'category') return;

    const currentIndex = categories.indexOf(current.value);
    const nextIndex = (currentIndex + 1) % categories.length;
    const nextCategory = categories[nextIndex];

    await modelSelector.selectCategory(nextCategory);

    // Briefly highlight the selector for visual feedback
    const selector = document.querySelector('.model-selector-btn');
    if (selector) {
        selector.classList.add('highlight-pulse');
        setTimeout(() => selector.classList.remove('highlight-pulse'), 500);
    }
}

/**
 * Get conversation history
 */
export function getHistory() {
    return conversationHistory;
}

/**
 * Get current vault name
 */
function getCurrentVault() {
    // Try to get vault from URL or global
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('vault') || window.currentVault || 'default';
}

/**
 * Setup event listeners for toolbar actions
 */
function setupToolbarEventListeners() {
    // Handle delete message
    window.addEventListener('chat:deleteMessage', (e) => {
        const { messageId, index } = e.detail;

        // Remove from conversation history
        if (typeof index === 'number' && index >= 0 && index < conversationHistory.length) {
            conversationHistory.splice(index, 1);
        }

        // Remove from DOM
        const msgEl = document.querySelector(`[data-message-id="${messageId}"]`);
        if (msgEl) {
            msgEl.remove();
        }

        // Re-index remaining messages
        reindexMessages();
    });

    // Handle regenerate
    window.addEventListener('chat:regenerate', async (e) => {
        const { messageIndex, model } = e.detail;

        if (typeof messageIndex !== 'number' || messageIndex < 0) return;

        // Get the user message before this assistant message
        const userMsgIndex = messageIndex - 1;
        if (userMsgIndex < 0 || conversationHistory[userMsgIndex]?.role !== 'user') {
            console.error('[Chat] Cannot regenerate: no user message found');
            return;
        }

        const userMessage = conversationHistory[userMsgIndex].content;

        // Remove the current assistant response
        conversationHistory.splice(messageIndex);

        // Remove from DOM
        const msgEl = document.querySelector(`[data-message-index="${messageIndex}"]`);
        if (msgEl) {
            msgEl.remove();
        }

        // Re-index
        reindexMessages();

        // Show loading state
        setStatus('Regenerating...');
        isWaitingForResponse = true;

        const assistantMsgEl = addMessage('assistant', '', true);

        try {
            const res = await request('chat.send', {
                message: userMessage,
                history: conversationHistory.slice(0, -1),
                category: currentCategory,
                model: model, // Override model if specified
                chat_id: activeChatId
            });

            const result = res.result?.result || res.result || {};

            if (result.status === 'success') {
                const response = result.response || 'No response';
                updateMessage(assistantMsgEl, response);

                // Reload history to ensure we have valid UUIDs from backend
                await loadHistory(activeChatId);

                setStatus('Ready');
            } else {
                const error = result.error || 'Unknown error';
                updateMessage(assistantMsgEl, `Error: ${error}`, true);
                setStatus('Error');
            }
        } catch (err) {
            console.error('[Chat] Regenerate error:', err);
            updateMessage(assistantMsgEl, `Error: ${err.message || err}`, true);
            setStatus('Error');
        } finally {
            isWaitingForResponse = false;
        }
    });
}

/**
 * Setup event listeners for streaming responses
 */
function setupStreamEventListeners() {
    // Handle streaming token events
    window.addEventListener('CHAT_TOKEN', (e) => {
        const { stream_id, token, accumulated } = e.detail || {};

        // Verify this is for the active stream
        if (stream_id !== activeStreamId || !activeStreamElement) {
            return;
        }

        // Update the message content with accumulated text
        updateStreamingContent(activeStreamElement, accumulated);
    });

    // Handle stream start event
    window.addEventListener('CHAT_STREAM_START', (e) => {
        const { stream_id, message } = e.detail || {};
        if (stream_id) {
            activeStreamId = stream_id;
        }
        setStatus('Streaming...');
    });

    // Handle stream end event
    window.addEventListener('CHAT_STREAM_END', async (e) => {
        const { stream_id, response, status, error, chat_id } = e.detail || {};

        // Verify this is for the active stream
        if (stream_id !== activeStreamId || !activeStreamElement) {
            return;
        }

        // Update activeChatId from backend (fixes duplicate chat creation)
        if (chat_id) {
            activeChatId = chat_id;
            window.activeChatId = chat_id;
        }

        if (status === 'success') {
            // Update IDs if provided FIRST
            const messageIds = e.detail?.message_ids;
            if (messageIds) {
                const { user_message_id, assistant_message_id } = messageIds;

                // Update Assistant DOM
                if (activeStreamElement) activeStreamElement.dataset.messageId = assistant_message_id;

                // Update User DOM (find last user message)
                const allUserMsgs = document.querySelectorAll('.chat-message-user');
                const lastUserMsg = allUserMsgs[allUserMsgs.length - 1];
                if (lastUserMsg) lastUserMsg.dataset.messageId = user_message_id;

                // Update History (Push assistant msg, update user msg ID)
                const lastUserIdx = conversationHistory.length - 1; // User message is last in history currently
                if (lastUserIdx >= 0 && conversationHistory[lastUserIdx].role === 'user') {
                    conversationHistory[lastUserIdx].id = user_message_id;
                }

                conversationHistory.push({
                    role: 'assistant',
                    content: response,
                    id: assistant_message_id
                });
            }

            // Final update with full response (creates toolbar)
            updateMessage(activeStreamElement, response);

            if (!messageIds) {
                // Fallback: Reload history to ensure we have valid UUIDs from backend
                await loadHistory(activeChatId);
            }
            setStatus('Ready');
        } else if (status === 'error') {
            updateMessage(activeStreamElement, `Error: ${error}`, true);
            setStatus('Error');
        }

        // Clear streaming state
        isWaitingForResponse = false;
        activeStreamId = null;
        activeStreamElement = null;
    });
}

/**
 * Setup event listeners for Smart Context chat highlighting
 */
function setupSmartContextEventListeners() {
    // Highlight messages included in the current Smart Context filter
    window.addEventListener('smart_context.highlight_applied', function(e) {
        var messageIds = (e.detail && e.detail.message_ids) ? e.detail.message_ids : [];

        // Remove all existing highlights
        document.querySelectorAll('[data-message-id].sc-highlight')
            .forEach(function(el) { el.classList.remove('sc-highlight'); });

        // Apply to matching elements
        messageIds.forEach(function(id) {
            var el = document.querySelector('[data-message-id="' + id + '"]');
            if (el) el.classList.add('sc-highlight');
        });
    });

    // Clear all highlights when filter is cleared
    window.addEventListener('smart_context.filter_changed', function(e) {
        var active = (e.detail && e.detail.active_topics) ? e.detail.active_topics : [];
        if (active.length === 0) {
            document.querySelectorAll('[data-message-id].sc-highlight')
                .forEach(function(el) { el.classList.remove('sc-highlight'); });
        }
    });
}

/**
 * Update streaming content without adding toolbar (for in-progress streaming)
 */
function updateStreamingContent(msgEl, content) {
    if (!msgEl) return;

    const contentEl = msgEl.querySelector('.message-content');
    if (contentEl) {
        // Replace loading indicator with streamed content
        contentEl.innerHTML = escapeHtml(content);
    }

    // Scroll to bottom
    const messagesEl = document.getElementById('chat-messages');
    if (messagesEl) {
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }
}

/**
 * Re-index message elements after deletion
 */
function reindexMessages() {
    const messagesEl = document.getElementById('chat-messages');
    if (!messagesEl) return;

    const messages = messagesEl.querySelectorAll('.chat-message:not(.chat-message-system)');
    messages.forEach((msgEl, idx) => {
        msgEl.dataset.messageIndex = idx;
    });
}

/**
 * Set streaming mode
 */
export function setStreaming(enabled) {
    enableStreaming = enabled;
    console.log(`[Chat] Streaming mode: ${enabled ? 'enabled' : 'disabled'}`);
}

/**
 * Render conversation history
 */
function renderConversation(history) {
    const messagesEl = document.getElementById('chat-messages');
    if (messagesEl) {
        messagesEl.innerHTML = '';
    }

    if (!history || history.length === 0) {
        addSystemMessage('Welcome! Type a message to start chatting.', 'welcome-message');
        return;
    }

    history.forEach((msg, idx) => {
        const msgEl = addMessage(msg.role, msg.content, false, msg.id);
        if (msgEl) {
            msgEl.dataset.messageIndex = idx;
            if (msg.id) msgEl.dataset.messageId = msg.id;
        }
    });

    // Notify plugins that rendering is complete
    window.dispatchEvent(new CustomEvent('chat:rendered', {
        detail: { history }
    }));
}


/**
 * Export for global access
 */
export default {
    initChat,
    setCategory,
    getHistory,
    setStreaming,
    clearChat: () => clearChat(),
    loadHistory,
    registerAction // Expose for plugins
};

// Also attach to window for easier plugin access
window.chatModule = {
    loadHistory,
    addMessage,
    addSystemMessage,
    renderConversation,
    clearChat: () => clearChat(),
    get activeChatId() { return activeChatId; },
    set activeChatId(id) { activeChatId = id; window.activeChatId = id; }
};
