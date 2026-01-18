/**
 * Vault Main Entry Point
 * 
 * Initializes all vault components: managers, layout, connection, and plugins.
 */

import { SidebarManager, PanelManager, ToolbarManager, ModalManager, ToolboxManager } from './managers/index.js';
import { initLayout, initResize, log } from './layout.js';
import { autoConnect } from './connection.js';
import { loadPlugins, handleEvent } from './plugins.js';
import { initSettings } from './settings.js';
import { initPluginStore } from './plugin-store.js';


/**
 * Initialize the vault application
 */
export function initVault() {
    // Initialize managers
    const sidebar = new SidebarManager();
    const panels = new PanelManager();
    const toolbar = new ToolbarManager();
    const modal = new ModalManager();
    const toolbox = new ToolboxManager();

    // Expose logging function globally
    window.log = log;

    // Public API for Plugins
    window.ui = {
        // Sidebar
        registerSidebarView: (id, icon, title) => sidebar.registerView(id, icon, title),
        setSidebarContent: (id, html) => sidebar.setContent(id, html),
        toggleSidebar: (id) => sidebar.toggle(id),

        // Panels (GoldenLayout tabs)
        registerPanel: (id, title, icon, position) => panels.registerPanel(id, title, icon, position),
        setPanelContent: (id, html) => panels.setPanelContent(id, html),
        removePanel: (id) => panels.removePanel(id),

        // Toolbar buttons
        registerToolbarButton: (id, icon, title, command) => toolbar.registerButton(id, icon, title, command),

        // Toolbox/Stage content
        setToolboxContent: (html) => toolbox.setContent(html),
        addToolboxItem: (html) => toolbox.addItem(html),
        setStageContent: (html) => toolbox.setContent(html), // Back-compat

        // Modal dialogs
        showModal: (title, html, width) => modal.show(title, html, width),
        closeModal: () => modal.close()
    };

    // Initialize GoldenLayout
    initLayout();

    // Initialize resize functionality
    initResize();

    // Initialize UI buttons
    initSettings();
    initPluginStore();

    // Auto-connect to WebSocket and load plugins
    autoConnect(loadPlugins, handleEvent);

    console.log('[Vault] Initialization complete');
}
