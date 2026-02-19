import { describe, it, expect, vi, beforeEach } from 'vitest';
import { loadPlugins, handleEvent } from '../vault/plugins.js';
import * as connection from '../vault/connection.js';

// Mock dependencies
vi.mock('../vault/connection.js');
vi.mock('../vault/chat/index.js', () => ({
    initChat: vi.fn(),
    initChatGlobals: vi.fn()
}));

describe('Plugins Module', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        window.log = vi.fn();
        window.ui = {
            registerPanel: vi.fn(),
            showToast: vi.fn()
        };
        document.body.innerHTML = '<div id="chat-area"></div>';
    });

    it('loadPlugins initializes correctly', async () => {
        connection.request.mockResolvedValueOnce({}); // client_ready
        connection.request.mockResolvedValueOnce({ result: { commands: { 'cmd1': {} } } }); // list_commands

        await loadPlugins();

        expect(connection.request).toHaveBeenCalledWith('system.client_ready', {});
        expect(connection.request).toHaveBeenCalledWith('system.list_commands');
    });

    it('handleEvent dispatches custom event', () => {
        const dispatchSpy = vi.spyOn(window, 'dispatchEvent');
        const evt = { event_type: 'my-event', data: { foo: 'bar' } };

        handleEvent(evt);

        expect(dispatchSpy).toHaveBeenCalledWith(expect.objectContaining({
            type: 'my-event',
            detail: { foo: 'bar' }
        }));
    });

    it('handleEvent processes UI_COMMAND register_panel', () => {
        const evt = {
            event_type: 'UI_COMMAND',
            data: {
                action: 'register_panel',
                id: 'p1',
                title: 'Panel 1'
            }
        };

        handleEvent(evt);

        expect(window.ui.registerPanel).toHaveBeenCalledWith('p1', 'Panel 1', undefined, undefined);
    });
});
