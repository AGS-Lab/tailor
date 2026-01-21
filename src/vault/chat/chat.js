/**
 * Core Chat Module - Main Entry Point
 * 
 * Built-in chat interface that replaces the LLM plugin.
 * Uses LiteLLM backend for provider-agnostic LLM access.
 */

import { request } from '../connection.js';
import { createToolbar, registerAction, refreshComposerToolbar } from './MessageActionToolbar.js';

// Chat state
let conversationHistory = [];
let isWaitingForResponse = false;
let currentCategory = 'fast';
let messageIdCounter = 0;
let activeChatId = null;

// Streaming state
let activeStreamId = null;
let activeStreamElement = null;
let enableStreaming = true; // Toggle streaming mode

/**
 * Initialize the chat module
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

    // Setup chat event listeners for toolbar actions
    setupToolbarEventListeners();

    // Setup streaming event listeners
    setupStreamEventListeners();

    // Initialize composer toolbar with registered actions
    refreshComposerToolbar();

    // Add welcome message with a specific class for removal later
    addSystemMessage('Welcome! Type a message to start chatting.', 'welcome-message');

    // Initialize icons after a short delay
    setTimeout(() => {
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }, 50);

    console.log('[Chat] Core chat module initialized');
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
                            <!-- Plugin actions will be inserted here -->
                        </div>
                        <div class="toolbar-send">
                            <button class="chat-send-btn" id="chat-send" title="Send Message">
                                <i data-lucide="arrow-up"></i>
                            </button>
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
    addMessage('user', message);

    // Add to history
    conversationHistory.push({ role: 'user', content: message });

    // Show loading state
    setStatus(enableStreaming ? 'Streaming...' : 'Thinking...');
    isWaitingForResponse = true;

    // Create assistant message placeholder
    const assistantMsgEl = addMessage('assistant', '', true);

    // Generate stream ID for this request
    const streamId = `stream_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    // Store active stream info (for streaming mode)
    if (enableStreaming) {
        activeStreamId = streamId;
        activeStreamElement = assistantMsgEl;
    }

    // Ensure we have a chat ID for this conversation
    if (!activeChatId) {
        activeChatId = `chat_${Math.floor(Date.now() / 1000)}`;
    }

    try {
        const res = await request('execute_command', {
            command: 'chat.send',
            args: {
                message: message,
                history: conversationHistory.slice(0, -1), // Exclude the just-added message
                category: currentCategory,
                stream: enableStreaming,
                stream_id: streamId,
                chat_id: activeChatId
            }
        });

        const result = res.result?.result || res.result || {};

        if (result.status === 'success') {
            const response = result.response || 'No response';

            // For streaming, the response is already shown via events
            // For non-streaming, update the message now
            if (!enableStreaming || !result.streaming) {
                updateMessage(assistantMsgEl, response);
                conversationHistory.push({ role: 'assistant', content: response });
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
        isWaitingForResponse = false;
        // Clear streaming state if this stream matches
        if (activeStreamId === streamId) {
            activeStreamId = null;
            activeStreamElement = null;
        }
    }
}

/**
 * Add a message to the chat
 */
function addMessage(role, content, isLoading = false) {
    const messagesEl = document.getElementById('chat-messages');
    if (!messagesEl) return null;

    const messageId = `msg-${++messageIdCounter}`;
    const messageIndex = conversationHistory.length;

    const msgEl = document.createElement('div');
    msgEl.className = `chat-message chat-message-${role}`;
    msgEl.dataset.messageId = messageId;
    msgEl.dataset.messageIndex = messageIndex;

    const iconName = role === 'user' ? 'user' : 'bot';

    msgEl.innerHTML = `
        <div class="message-avatar">
            <i data-lucide="${iconName}"></i>
        </div>
        <div class="message-content-wrapper">
            <div class="message-content">
                ${isLoading ? '<div class="message-loading"><span></span><span></span><span></span></div>' : escapeHtml(content)}
            </div>
            <div class="message-toolbar-container"></div>
        </div>
    `;

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
function addSystemMessage(content, className = '') {
    const messagesEl = document.getElementById('chat-messages');
    if (!messagesEl) return;

    const msgEl = document.createElement('div');
    msgEl.className = 'chat-message chat-message-system';
    if (className) {
        msgEl.classList.add(className);
    }
    msgEl.innerHTML = `<div class="message-content">${escapeHtml(content)}</div>`;

    messagesEl.appendChild(msgEl);
}

/**
 * Clear the chat
 */
function clearChat() {
    conversationHistory = [];
    activeChatId = null;

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

    // Handle create branch
    window.addEventListener('chat:createBranch', (e) => {
        const { branchFrom, history } = e.detail;

        // Clear current chat and start with branched history
        conversationHistory = [...history];

        const messagesEl = document.getElementById('chat-messages');
        if (messagesEl) {
            messagesEl.innerHTML = '';
        }

        // Re-render messages from history
        addSystemMessage(`Chat branched from: "${branchFrom.content.slice(0, 50)}..."`);

        history.forEach((msg, idx) => {
            const msgEl = addMessage(msg.role, msg.content);
            if (msgEl) {
                msgEl.dataset.messageIndex = idx;
            }
        });

        setStatus('Ready');
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
            const res = await request('execute_command', {
                command: 'chat.send',
                args: {
                    message: userMessage,
                    history: conversationHistory.slice(0, -1),
                    category: currentCategory,
                    model: model, // Override model if specified
                    chat_id: activeChatId
                }
            });

            const result = res.result?.result || res.result || {};

            if (result.status === 'success') {
                const response = result.response || 'No response';
                updateMessage(assistantMsgEl, response);
                conversationHistory.push({ role: 'assistant', content: response });
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
        const { stream_id } = e.detail || {};
        console.log(`[Chat] Stream started: ${stream_id}`);
        setStatus('Streaming...');
    });

    // Handle stream end event
    window.addEventListener('CHAT_STREAM_END', (e) => {
        const { stream_id, response, status, error } = e.detail || {};

        // Verify this is for the active stream
        if (stream_id !== activeStreamId || !activeStreamElement) {
            return;
        }

        console.log(`[Chat] Stream ended: ${stream_id}, status: ${status}`);

        if (status === 'success') {
            // Final update with full response
            updateMessage(activeStreamElement, response);

            // Add to conversation history
            conversationHistory.push({ role: 'assistant', content: response });

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
 * Export for global access
 */
export default {
    initChat,
    setCategory,
    getHistory,
    setStreaming,
    clearChat: () => clearChat(),
    registerAction // Expose for plugins
};
