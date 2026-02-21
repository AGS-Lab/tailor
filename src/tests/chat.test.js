import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { initChatGlobals, initChat, setCategory, getHistory } from '../vault/chat/chat.js';
import { request } from '../vault/connection.js';

vi.mock('../vault/connection.js', () => ({
    request: vi.fn()
}));

vi.mock('../services/api.js', () => ({
    settingsApi: {
        getEffectiveSettings: vi.fn().mockResolvedValue({ streaming: false })
    }
}));

vi.mock('../vault/chat/ModelSelector.js', () => ({
    getModelSelector: vi.fn().mockReturnValue({
        init: vi.fn(),
        getCurrentSelection: vi.fn().mockReturnValue({ type: 'category', value: 'thinking' })
    })
}));

global.ResizeObserver = class {
    observe() { }
    unobserve() { }
    disconnect() { }
};

describe('chat.js', () => {
    let container;

    beforeEach(() => {
        container = document.createElement('div');
        container.id = 'chat-container';
        document.body.appendChild(container);

        vi.clearAllMocks();
        window.lucide = { createIcons: vi.fn() };
        window.__chatGlobalsInitialized = false;

        // Mock prompt
        window.prompt = vi.fn();
    });

    afterEach(() => {
        document.body.innerHTML = '';
        window.dispatchEvent(new CustomEvent('CHAT_STREAM_END', { detail: { stream_id: null, status: 'success' } }));
    });

    it('initializes chat globals once', () => {
        initChatGlobals();
        expect(window.__chatGlobalsInitialized).toBe(true);
        initChatGlobals(); // Should not throw or double-register
    });

    it('renders chat layout', () => {
        initChat(container);
        expect(container.innerHTML).toContain('Tailor');
        expect(container.innerHTML).toContain('Type your message...');

        const input = container.querySelector('#chat-input');
        expect(input).not.toBeNull();
    });

    it('handles sending a message non-streaming', async () => {
        initChat(container);

        const input = container.querySelector('#chat-input');
        const sendBtn = container.querySelector('#chat-send');

        request.mockResolvedValue({
            result: {
                status: 'success',
                message_ids: { user_message_id: 'u1', assistant_message_id: 'a1' },
                response: 'Test response'
            }
        });

        input.value = 'Hello world';
        await sendBtn.click();

        // Wait for async request
        await new Promise(resolve => setTimeout(resolve, 0));

        expect(request).toHaveBeenCalledWith('chat.send', expect.objectContaining({
            message: 'Hello world'
        }));

        const messages = container.querySelectorAll('.chat-message');
        expect(messages.length).toBeGreaterThan(0);

        // At least one user message and one assistant
        const history = getHistory();
        expect(history.length).toBe(2);
        expect(history[0].role).toBe('user');
        expect(history[1].content).toBe('Test response');
    });

    it('changes category using setCategory', async () => {
        initChat(container);

        // The header might not have chat-model exactly if we changed HTML, but the function should still run
        setCategory('thinking');

        // Mock a send to see if category is used
        request.mockResolvedValue({ result: { status: 'success', response: 'Ok' } });
        const input = container.querySelector('#chat-input');
        input.value = 'Test';
        const sendBtn = container.querySelector('#chat-send');
        sendBtn.click();

        await new Promise(resolve => setTimeout(resolve, 0));

        expect(request).toHaveBeenCalledWith('chat.send', expect.objectContaining({
            category: 'thinking'
        }));
    });
});
