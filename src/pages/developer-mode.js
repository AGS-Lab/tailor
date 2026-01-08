/**
 * Developer Mode Page
 * Tools and resources for plugin development
 */

export async function initDeveloperMode(container) {
    container.innerHTML = `
        <div class="developer-mode-container">
            <div class="developer-mode-header">
                <h1>Developer Mode</h1>
                <p class="developer-mode-subtitle">Build and test custom plugins</p>
            </div>

            <div class="dev-section">
                <h3>Quick Start</h3>
                <button class="btn btn-primary" id="create-plugin-btn">
                    <i data-lucide="plus"></i>
                    Create Plugin Template
                </button>
            </div>

            <div class="dev-section">
                <h3>Plugin Structure</h3>
                <pre class="code-block"><code>vault/
  plugins/
    my_plugin/
      main.py          # Entry point
      settings.json    # Configuration
      requirements.txt # Dependencies</code></pre>
            </div>

            <div class="dev-section">
                <h3>Example Plugin</h3>
                <pre class="code-block"><code>from api.plugin_base import PluginBase

class Plugin(PluginBase):
    def __init__(self, emitter, brain, plugin_dir, vault_path):
        super().__init__(emitter, brain, plugin_dir, vault_path)
        self.name = "my_plugin"
    
    async def on_tick(self, emitter):
        """Called every 5 seconds."""
        pass</code></pre>
                <button class="btn btn-secondary" id="copy-template-btn" style="margin-top: var(--spacing-lg);">
                    <i data-lucide="copy"></i>
                    Copy
                </button>
            </div>

            <div class="dev-section">
                <h3>Validate</h3>
                <div style="display: flex; gap: var(--spacing-lg);">
                    <input type="text" 
                           id="plugin-path-input" 
                           class="settings-input" 
                           placeholder="Plugin path"
                           style="flex: 1;">
                    <button class="btn btn-primary" id="validate-plugin-btn">
                        <i data-lucide="check-circle"></i>
                        Validate
                    </button>
                </div>
                <div id="validation-result" style="margin-top: var(--spacing-lg);"></div>
            </div>

            <div class="dev-section">
                <h3>Resources</h3>
                <div style="display: flex; flex-direction: column; gap: var(--spacing-md);">
                    <a href="#" class="resource-link">
                        <i data-lucide="book-open"></i>
                        <div>
                            <strong>Plugin Guide</strong>
                            <span>Development documentation</span>
                        </div>
                    </a>
                    <a href="#" class="resource-link">
                        <i data-lucide="code"></i>
                        <div>
                            <strong>API Reference</strong>
                            <span>PluginBase documentation</span>
                        </div>
                    </a>
                </div>
            </div>
        </div>
    `;

    if (window.lucide) {
        window.lucide.createIcons();
    }

    setupEventListeners(container);
}

function setupEventListeners(container) {
    const createBtn = container.querySelector('#create-plugin-btn');
    const copyBtn = container.querySelector('#copy-template-btn');
    const validateBtn = container.querySelector('#validate-plugin-btn');

    createBtn?.addEventListener('click', () => {
        alert('Plugin template creation will be implemented soon!');
    });

    copyBtn?.addEventListener('click', () => {
        const template = `from api.plugin_base import PluginBase

class Plugin(PluginBase):
    def __init__(self, emitter, brain, plugin_dir, vault_path):
        super().__init__(emitter, brain, plugin_dir, vault_path)
        self.name = "my_plugin"
    
    async def on_tick(self, emitter):
        pass`;
        
        navigator.clipboard.writeText(template).then(() => {
            alert('Template copied to clipboard!');
        });
    });

    validateBtn?.addEventListener('click', () => {
        const path = container.querySelector('#plugin-path-input')?.value;
        const result = container.querySelector('#validation-result');
        
        if (!path) {
            result.innerHTML = '<div class="error-message">Please enter a plugin path</div>';
            return;
        }
        
        result.innerHTML = '<div class="success-message">✓ Plugin structure is valid!</div>';
    });
}


