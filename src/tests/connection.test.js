import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { connect, request, autoConnect } from '../vault/connection.js';

// Mock WebSocket
class MockWebSocket {
    constructor(url) {
        this.url = url;
        this.readyState = WebSocket.CONNECTING;
        setTimeout(() => {
            this.readyState = WebSocket.OPEN;
            if (this.onopen) this.onopen();
        }, 10);
    }
    send(data) {
        // Echo back for testing if needed, or just spy on it
        const parsed = JSON.parse(data);
        if (this.onmessage) {
            // Simulate response
            setTimeout(() => {
                this.onmessage({
                    data: JSON.stringify({
                        jsonrpc: '2.0',
                        result: 'success',
                        id: parsed.id
                    })
                });
            }, 10);
        }
    }
    close() { }
}

global.WebSocket = MockWebSocket;

// Mock window globals
global.window = {
    location: { search: '' },
    log: vi.fn(),
    console: { log: vi.fn(), warn: vi.fn(), error: vi.fn() }
};

describe('Connection Module', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        global.window.log.mockClear();
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    it('connects to default port 9002', () => {
        connect(null, vi.fn(), vi.fn());
        expect(global.window.log).toHaveBeenCalledWith(expect.stringContaining('9002'));
    });

    it('connects to explicit port', () => {
        connect('8080', vi.fn(), vi.fn());
        expect(global.window.log).toHaveBeenCalledWith(expect.stringContaining('8080'));
    });

    it('sends request and receives response', async () => {
        connect('9002');
        vi.runAllTimers(); // Wait for open

        const promise = request('test.method', { foo: 'bar' });
        vi.runAllTimers(); // Wait for response mock

        const result = await promise;
        expect(result).toEqual({ jsonrpc: '2.0', result: 'success', id: expect.any(Number) });
    });

    it('handles autoConnect via URL param', async () => {
        global.window.location.search = '?port=1234';
        await autoConnect();
        vi.runAllTimers();
        expect(global.window.log).toHaveBeenCalledWith(expect.stringContaining('1234'));
    });
});
