use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::Mutex;
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(dead_code)]
pub struct Event {
    pub event_type: String,
    pub scope: EventScope,
    pub data: serde_json::Value,
    pub timestamp: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
#[allow(dead_code)]
pub enum EventScope {
    Window,
    Global,
    Vault(String),
}

pub struct EventBus {
    // Map window labels to their vault IDs
    #[allow(dead_code)]
    window_vaults: Arc<Mutex<HashMap<String, String>>>,
}

impl Default for EventBus {
    fn default() -> Self {
        Self::new()
    }
}

#[allow(dead_code)]
impl EventBus {
    pub fn new() -> Self {
        Self {
            window_vaults: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    /// Register a window with its vault ID
    pub async fn register_window(&self, window_label: String, vault_id: String) {
        self.window_vaults.lock().await.insert(window_label, vault_id);
    }

    /// Route event from sidecar to appropriate window(s)
    pub async fn route_from_sidecar(
        &self,
        app: &AppHandle,
        source_window: String,
        event: Event,
    ) -> anyhow::Result<()> {
        match &event.scope {
            EventScope::Window => {
                // Route to source window only
                self.send_to_window(app, &source_window, &event).await?;
            }
            EventScope::Global => {
                // Broadcast to all windows
                let window_vaults = self.window_vaults.lock().await;
                for window_label in window_vaults.keys() {
                    self.send_to_window(app, window_label, &event).await?;
                }
            }
            EventScope::Vault(vault_id) => {
                // Send to all windows with matching vault
                let window_vaults = self.window_vaults.lock().await;
                for (window_label, vid) in window_vaults.iter() {
                    if vid == vault_id {
                        self.send_to_window(app, window_label, &event).await?;
                    }
                }
            }
        }

        Ok(())
    }

    /// Send event to a specific window
    async fn send_to_window(
        &self,
        app: &AppHandle,
        window_label: &str,
        event: &Event,
    ) -> anyhow::Result<()> {
        if let Some(window) = app.get_webview_window(window_label) {
            // Use Emitter trait method
            use tauri::Emitter;
            window.emit("sidecar-event", event)
                .map_err(|e| anyhow::anyhow!("Failed to emit event: {}", e))?;
            println!("Sent event '{}' to window '{}'", event.event_type, window_label);
        } else {
            eprintln!("Window '{}' not found", window_label);
        }

        Ok(())
    }

    /// Unregister a window
    #[allow(dead_code)]
    pub async fn unregister_window(&self, window_label: &str) {
        self.window_vaults.lock().await.remove(window_label);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_event_bus_registration() {
        let bus = EventBus::new();
        
        bus.register_window("main".to_string(), "vault_123".to_string()).await;
        
        {
            let map = bus.window_vaults.lock().await;
            assert_eq!(map.get("main"), Some(&"vault_123".to_string()));
            assert_eq!(map.len(), 1);
        } // Drop lock
        
        bus.unregister_window("main").await;
        
        {
            let map = bus.window_vaults.lock().await;
            assert!(map.is_empty());
        } // Drop lock
    }
}

