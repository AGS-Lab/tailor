/**
 * Tests for PanelManager
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PanelManager } from '../vault/managers/PanelManager';

// Mock window and GoldenLayout globals
global.window = {
    myLayout: {
        registerComponent: vi.fn(),
        root: {
            contentItems: []
        },
        init: vi.fn()
    },
    lucide: {
        createIcons: vi.fn()
    }
};

global.document = {
    getElementById: vi.fn(),
    createElement: vi.fn(),
};

describe('PanelManager', () => {
    let panelManager;
    let mockLayout;
    let mockStack;

    beforeEach(() => {
        panelManager = new PanelManager();
        mockStack = {
            type: 'stack',
            contentItems: [],
            addChild: vi.fn(),
            addComponent: vi.fn()
        };

        mockLayout = {
            registerComponent: vi.fn(),
            root: {
                contentItems: [
                    {
                        contentItems: [
                            {}, // Left column
                            {   // Right column
                                contentItems: [
                                    mockStack // The stack we want to add to
                                ]
                            }
                        ]
                    }
                ],
                getItemsById: vi.fn().mockReturnValue([])
            }
        };

        window.myLayout = mockLayout;
        vi.clearAllMocks();
    });

    it('should register a new panel', () => {
        panelManager.registerPanel('test-panel', 'Test Title', 'icon');

        expect(panelManager.panels.has('test-panel')).toBe(true);
        expect(mockLayout.registerComponent).toHaveBeenCalledWith('plugin_test-panel', expect.any(Function));
    });

    it('should use addComponent if available (GL 2.x)', () => {
        panelManager.registerPanel('test-panel', 'Test Title', 'icon');

        expect(mockStack.addComponent).toHaveBeenCalledWith(
            'plugin_test-panel',
            {},
            'Test Title'
        );
        expect(mockStack.addChild).not.toHaveBeenCalled();
    });

    it('should fallback to addChild if addComponent is missing', () => {
        // Remove addComponent from mock
        mockStack.addComponent = undefined;

        panelManager.registerPanel('test-panel', 'Test Title', 'icon');

        expect(mockStack.addChild).toHaveBeenCalledWith(expect.objectContaining({
            type: 'component',
            componentName: 'plugin_test-panel',
            title: 'Test Title'
        }));
    });

    it('should not register duplicate panels', () => {
        panelManager.registerPanel('test-panel', 'Test Title');
        panelManager.registerPanel('test-panel', 'Test Title');

        expect(mockLayout.registerComponent).toHaveBeenCalledTimes(1);
    });

    it('should remove panel', () => {
        panelManager.registerPanel('test-panel', 'Test Title');
        panelManager.removePanel('test-panel');

        expect(panelManager.panels.has('test-panel')).toBe(false);
        expect(mockLayout.root.getItemsById).toHaveBeenCalledWith('test-panel');
    });
});
