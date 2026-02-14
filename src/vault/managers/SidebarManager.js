/**
 * SidebarManager - Manages the sidebar views in the activity bar
 * 
 * Handles registration, toggle, and content updates for sidebar panels.
 */
export class SidebarManager {
    constructor() {
        this.views = new Map(); // id -> { icon, title, content }
        this.activeViewId = null;

        this.barEl = document.getElementById('activity-bar-top');
        this.panelEl = document.getElementById('side-panel');
        this.titleEl = document.getElementById('side-panel-title');
        this.contentEl = document.getElementById('side-panel-content');
    }

    registerView(id, iconData, title) {
        console.log(`[SidebarManager] Registering view: ${id}, icon: ${iconData}, title: ${title}`);

        if (this.views.has(id)) {
            console.log(`[SidebarManager] View ${id} already registered, skipping`);
            return;
        }

        this.views.set(id, { icon: iconData, title: title, content: '' });

        // Create Icon Button
        const btn = document.createElement('div');
        btn.className = 'activity-action';
        btn.title = title;
        btn.onclick = () => this.toggle(id);
        btn.dataset.id = id;

        // Check if iconData looks like an SVG string, otherwise assume it's a Lucide name
        if (iconData.trim().startsWith('<')) {
            btn.innerHTML = iconData;
            console.log(`[SidebarManager] Using raw SVG for ${id}`);
        } else {
            // Lucide Icon name
            btn.innerHTML = `<i data-lucide="${iconData}"></i>`;
            console.log(`[SidebarManager] Using Lucide icon "${iconData}" for ${id}`);
        }

        this.barEl.appendChild(btn);
        console.log(`[SidebarManager] Button appended to activity bar top`);

        // Initialize icons if Lucide is available
        if (window.lucide) {
            window.lucide.createIcons();
            console.log(`[SidebarManager] Lucide icons initialized`);
        } else {
            console.warn(`[SidebarManager] Lucide not available!`);
        }
    }

    setContent(id, html) {
        if (this.views.has(id)) {
            this.views.get(id).content = html;
            // Update if active
            if (this.activeViewId === id) {
                this.contentEl.innerHTML = html;
                this._executeScripts(this.contentEl);
            }
        }
    }

    toggle(id) {
        if (this.activeViewId === id) {
            // Close
            this.activeViewId = null;
            this.panelEl.classList.remove('open');
            this._updateIcons();
        } else {
            // Open
            this.activeViewId = id;
            const view = this.views.get(id);
            this.titleEl.textContent = view.title;
            this.contentEl.innerHTML = view.content || '<div style="padding:20px; text-align:center; color:var(--text-disabled)">Loading...</div>';
            this._executeScripts(this.contentEl);
            this.panelEl.classList.add('open');
            this._updateIcons();
        }

        // Resize GoldenLayout after transition
        setTimeout(() => {
            if (window.myLayout) window.myLayout.updateSize();
        }, 150);
    }

    /**
     * Execute <script> tags within an element.
     * innerHTML doesn't run scripts, so we re-create them as DOM nodes.
     */
    _executeScripts(container) {
        const scripts = container.querySelectorAll('script');
        scripts.forEach(oldScript => {
            const newScript = document.createElement('script');
            // Copy attributes
            Array.from(oldScript.attributes).forEach(attr => {
                newScript.setAttribute(attr.name, attr.value);
            });
            // Copy content
            newScript.textContent = oldScript.textContent;
            oldScript.parentNode.replaceChild(newScript, oldScript);
        });
    }

    _updateIcons() {
        const btns = this.barEl.querySelectorAll('.activity-action');
        btns.forEach(btn => {
            if (btn.dataset.id === this.activeViewId) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }
}
