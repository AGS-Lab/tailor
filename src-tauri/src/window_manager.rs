use std::collections::HashMap;
use tauri::{AppHandle, WebviewWindowBuilder};
use anyhow::Result;

pub struct WindowManager {
    windows: HashMap<String, String>, // window_label -> vault_path
}

impl Default for WindowManager {
    fn default() -> Self {
        Self::new()
    }
}

impl WindowManager {
    pub fn new() -> Self {
        Self {
            windows: HashMap::new(),
        }
    }

    /// Create a new vault window
    pub fn create_vault_window(
        &mut self,
        app: &AppHandle,
        vault_path: String,
    ) -> Result<String> {
        // Generate unique window label
        let window_label = format!("vault_{}", uuid::Uuid::new_v4());

        // Create the window
        let _window = WebviewWindowBuilder::new(
            app,
            &window_label,
            tauri::WebviewUrl::App("vault.html".into()),
        )
        .title(format!("Tailor - {}", Self::extract_vault_name(&vault_path)))
        .inner_size(1200.0, 800.0)
        .resizable(true)
        .decorations(false)
        .build()?;

        // Store window reference
        self.windows.insert(window_label.clone(), vault_path.clone());

        println!("Created window '{}' for vault: {}", window_label, vault_path);

        Ok(window_label)
    }

    /// Get vault path for a window
    pub fn get_vault_path(&self, window_label: &str) -> Option<&String> {
        self.windows.get(window_label)
    }

    /// Remove window from tracking
    pub fn remove_window(&mut self, window_label: &str) {
        self.windows.remove(window_label);
        println!("Removed window: {}", window_label);
    }

    /// Get all active window labels
    pub fn get_active_windows(&self) -> Vec<String> {
        self.windows.keys().cloned().collect()
    }

    /// Extract vault name from path
    fn extract_vault_name(vault_path: &str) -> String {
        std::path::Path::new(vault_path)
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("Vault")
            .to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_window_manager_registry() {
        let mut manager = WindowManager::new();
        
        let vault_path = "/tmp/my_vault".to_string();
        
        // Test manual insertion for internal state checks
        manager.windows.insert("test_window".to_string(), vault_path.clone());
        
        assert_eq!(manager.get_vault_path("test_window"), Some(&vault_path));
        assert!(manager.get_active_windows().contains(&"test_window".to_string()));
        
        manager.remove_window("test_window");
        assert_eq!(manager.get_vault_path("test_window"), None);
    }

    #[test]
    fn test_extract_vault_name() {
        assert_eq!(WindowManager::extract_vault_name("/path/to/my_vault"), "my_vault");
        assert_eq!(WindowManager::extract_vault_name("my_vault"), "my_vault");
    }
}
