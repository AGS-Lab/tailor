import { describe, it, expect, beforeEach, vi } from 'vitest';
import toolbarModule from '../vault/chat/MessageActionToolbar.js';

// Access methods from the default export since it was exported as default
const { createToolbar, createComposerToolbar, registerAction, unregisterAction } = toolbarModule;

global.ResizeObserver = class {
    observe() { }
    unobserve() { }
    disconnect() { }
};

describe('MessageActionToolbar.js', () => {
    beforeEach(() => {
        window.lucide = { createIcons: vi.fn() };
    });

    it('registers and renders core actions in message toolbar', () => {
        const message = { id: 'msg-1', role: 'assistant', content: 'Test info' };
        const context = { index: 0 };

        const toolbar = createToolbar(message, context);

        // Should contain buttons
        const textContent = toolbar.innerHTML;
        // The icons use data-lucide
        expect(textContent).toContain('data-lucide="copy"');
        expect(textContent).toContain('data-lucide="bookmark"');
    });

    it('allows custom plugin actions', () => {
        registerAction({
            id: 'my-custom-action',
            icon: 'star',
            label: 'Star',
            position: 50,
            type: 'button',
            location: 'message-actionbar',
            handler: vi.fn()
        });

        const message = { id: 'msg-2', role: 'assistant', content: 'Test' };
        const toolbar = createToolbar(message, {});

        expect(toolbar.innerHTML).toContain('data-lucide="star"');

        // Cleanup
        unregisterAction('my-custom-action');
    });
});
