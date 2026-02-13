/**
 * ModalManager - Manages modal dialogs
 * 
 * Provides show/close functionality for plugin modals.
 */
export class ModalManager {
    constructor() {
        this.isOpen = false;
        this._ensureModal();
    }

    _ensureModal() {
        if (!document.getElementById('plugin-modal-overlay')) {
            const overlay = document.createElement('div');
            overlay.id = 'plugin-modal-overlay';
            overlay.className = 'modal-overlay';
            overlay.style.cssText = `
                display: none;
                position: fixed;
                top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(0,0,0,0.5);
                backdrop-filter: blur(4px);
                z-index: 1000;
                justify-content: center;
                align-items: center;
            `;
            overlay.innerHTML = `
                <div id="plugin-modal" class="modal-dialog" style="
                    background: var(--bg-card);
                    border: 1px solid var(--border-subtle);
                    border-radius: var(--border-radius, 12px);
                    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
                    max-height: 85vh;
                    overflow: hidden;
                    display: flex;
                    flex-direction: column;
                    color: var(--text-primary);
                ">
                    <div class="modal-header" style="
                        padding: 20px 24px;
                        border-bottom: 1px solid var(--border-subtle);
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        background: var(--bg-card);
                    ">
                        <h3 id="modal-title" style="margin:0; font-size:1.1rem; font-weight:600; color:var(--text-primary);"></h3>
                        <button id="modal-close-btn" class="icon-btn" style="
                            background: transparent; border: none; cursor: pointer;
                            color: var(--text-secondary); width: 32px; height: 32px;
                            display: flex; align-items: center; justify-content: center;
                            border-radius: 6px; transition: background 0.2s;
                        ">
                            <i data-lucide="x" style="width:20px; height:20px;"></i>
                        </button>
                    </div>
                    <div id="modal-content" class="modal-body" style="
                        padding: 0;
                        overflow-y: auto;
                        flex: 1;
                        background: var(--bg-app);
                    "></div>
                </div>
            `;

            document.body.appendChild(overlay);

            // Close handlers
            overlay.onclick = (e) => {
                if (e.target === overlay) this.close();
            };
            document.getElementById('modal-close-btn').onclick = () => this.close();
        }
    }

    show(title, html, width = '500px', height = null) {
        console.log(`[ModalManager] Showing modal: ${title}`);
        this._ensureModal();

        const overlay = document.getElementById('plugin-modal-overlay');
        const modal = document.getElementById('plugin-modal');
        const titleEl = document.getElementById('modal-title');
        const contentEl = document.getElementById('modal-content');

        titleEl.textContent = title;
        contentEl.innerHTML = html;
        modal.style.width = width;
        if (height) {
            modal.style.height = height;
        } else {
            modal.style.height = 'auto';
        }
        overlay.style.display = 'flex';
        this.isOpen = true;

        if (window.lucide) window.lucide.createIcons();
    }

    close() {
        console.log(`[ModalManager] Closing modal`);
        const overlay = document.getElementById('plugin-modal-overlay');
        if (overlay) {
            overlay.style.display = 'none';
        }
        this.isOpen = false;
    }
}
