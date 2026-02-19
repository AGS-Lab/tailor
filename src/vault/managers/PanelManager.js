/**
 * PanelManager - Manages GoldenLayout panels/tabs
 * 
 * Handles panel registration, content updates, and layout integration.
 */
export class PanelManager {
    constructor() {
        this.panels = new Map(); // id -> { title, content, component }
    }

    registerPanel(id, title, icon = null, position = 'right') {
        console.log(`[PanelManager] Registering panel: ${id}, title: ${title}, position: ${position}`);

        if (this.panels.has(id)) {
            console.log(`[PanelManager] Panel ${id} already registered`);
            return;
        }

        this.panels.set(id, { title, icon, content: '', position });

        // Register component with GoldenLayout
        if (window.myLayout) {
            // Register the component type if not already registered
            try {
                window.myLayout.registerComponent(`plugin_${id}`, (container, state) => {
                    container.element.innerHTML = `
                        <div class="panel-container" id="panel-${id}">
                            <div class="scrollable" style="padding: 12px;">
                                <div style="color:var(--text-disabled); text-align:center;">
                                    Loading ${title}...
                                </div>
                            </div>
                        </div>
                    `;
                });
            } catch (e) {
                // Component already registered, which is fine
            }

            // Find target stack based on position
            const root = window.myLayout.root;
            if (root && root.contentItems && root.contentItems.length > 0) {
                // Add to existing layout - find appropriate stack
                const newItem = {
                    type: 'component',
                    componentName: `plugin_${id}`,
                    title: title,
                    id: id
                };

                // Try to add to existing right column stack
                try {
                    const rightColumn = root.contentItems[0]?.contentItems?.[1];
                    if (rightColumn && rightColumn.contentItems) {
                        const stack = rightColumn.contentItems[0]; // First stack in right column
                        if (stack) {
                            // Use addComponent if available (GL 2.x) or fallback to addChild
                            if (stack.addComponent) {
                                stack.addComponent(`plugin_${id}`, {}, title);
                                console.log(`[PanelManager] Added panel ${id} to layout via addComponent`);
                            } else if (stack.addChild) {
                                stack.addChild(newItem);
                                console.log(`[PanelManager] Added panel ${id} to layout via addChild`);
                            }
                        }
                    }
                } catch (e) {
                    console.warn(`[PanelManager] Could not add panel to layout:`, e);
                }
            }
        }
    }

    setPanelContent(id, html) {
        console.log(`[PanelManager] Setting content for panel: ${id}`);
        if (this.panels.has(id)) {
            this.panels.get(id).content = html;
        }

        // Update DOM if panel exists
        const panelEl = document.getElementById(`panel-${id}`);
        if (panelEl) {
            panelEl.innerHTML = `<div class="scrollable" style="padding: 12px;">${html}</div>`;
            // Re-init icons
            if (window.lucide) window.lucide.createIcons();
        }
    }

    removePanel(id) {
        console.log(`[PanelManager] Removing panel: ${id}`);
        this.panels.delete(id);

        // Remove from GoldenLayout
        if (window.myLayout) {
            const items = window.myLayout.root.getItemsById(id);
            items.forEach(item => item.remove());
        }
    }
}
