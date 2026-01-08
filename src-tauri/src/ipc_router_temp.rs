use crate::{AppState, window_manager::WindowManager, sidecar_manager::SidecarManager, dependency_checker::DependencyChecker};
use tauri::{AppHandle, Manager, State};
use serde::{Deserialize, Serialize};
use anyhow::Result;
use std::path::PathBuf;
use std::fs;

#[derive(Debug, Serialize, Deserialize)]
pub struct VaultInfo {
    pub window_label: String,
    pub vault_path: String,
    pub ws_port: u16,
}

/// Open a new vault window
#[tauri::command]
pub async fn open_vault(
    app: AppHandle,
    vault_path: String,
    state: State<'_, AppState>,
) -> Result<VaultInfo, String> {
    println!("Opening vault: {}", vault_path);

    // Step 1: Check and install dependencies
    DependencyChecker::check_and_install(&vault_path)
        .await
        .map_err(|e| format!("Failed to install dependencies: {}", e))?;

    // Step 2: Create window
    let window_label = state.window_manager
        .lock()
        .await
        .create_vault_window(&app, vault_path.clone())
        .map_err(|e| format!("Failed to create window: {}", e))?;

    // Step 3: Spawn sidecar
    let ws_port = state.sidecar_manager
        .spawn_sidecar(window_label.clone(), vault_path.clone())
        .await
        .map_err(|e| format!("Failed to spawn sidecar: {}", e))?;

    println!("Vault opened successfully: window={}, port={}", window_label, ws_port);

    Ok(VaultInfo {
        window_label,
        vault_path,
        ws_port,
    })
}

/// Send command to sidecar
#[tauri::command]
pub async fn send_to_sidecar(
    window_label: String,
    command: serde_json::Value,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    println!("Sending command to sidecar '{}': {:?}", window_label, command);

    // Get WebSocket port
    let ws_port = state.sidecar_manager
        .get_ws_port(&window_label)
        .await
        .ok_or_else(|| format!("Sidecar not found for window: {}", window_label))?;

    // In a full implementation, you would:
    // 1. Connect to WebSocket at ws://localhost:{ws_port}
    // 2. Send JSON-RPC command
    // 3. Wait for response
    // For now, return a placeholder

    // TODO: Implement WebSocket client communication
    println!("Would send to ws://localhost:{}", ws_port);

    Ok(serde_json::json!({
        "status": "pending",
        "message": "WebSocket communication not yet implemented"
    }))
}

/// Close a vault window and terminate its sidecar
#[tauri::command]
pub async fn close_vault(
    window_label: String,
    state: State<'_, AppState>,
) -> Result<(), String> {
    println!("Closing vault window: {}", window_label);

    // Step 1: Terminate sidecar
    state.sidecar_manager
        .terminate_sidecar(&window_label)
        .await
        .map_err(|e| format!("Failed to terminate sidecar: {}", e))?;

    // Step 2: Remove window from tracking
    state.window_manager
        .lock()
        .await
        .remove_window(&window_label);

    println!("Vault closed successfully: {}", window_label);

    Ok(())
}

/// Get the current window's vault information
#[tauri::command]
pub async fn get_current_vault_info(
    window: tauri::Window,
    state: State<'_, AppState>,
) -> Result<VaultInfo, String> {
    let window_label = window.label().to_string();
    
    // Get vault path
    let vault_path = state.window_manager
        .lock()
        .await
        .get_vault_path(&window_label)
        .ok_or_else(|| "Vault not found for this window".to_string())?
        .clone();
    
    // Get WebSocket port
    let ws_port = state.sidecar_manager
        .get_ws_port(&window_label)
        .await
        .ok_or_else(|| "Sidecar not found for this window".to_string())?;
    
    Ok(VaultInfo {
        window_label,
        vault_path,
        ws_port,
    })
}


#[derive(Debug, Serialize, Deserialize)]
pub struct VaultListItem {
    pub name: String,
    pub path: String,
    pub created: Option<String>,
}

/// List all known vaults
#[tauri::command]
pub async fn list_vaults() -> Result<Vec<VaultListItem>, String> {
    // TODO: Implement vault discovery
    Ok(vec![])
}

/// Get vault information
#[tauri::command]
pub async fn get_vault_info(vault_path: String) -> Result<serde_json::Value, String> {
    let path = PathBuf::from(&vault_path);
    let config_path = path.join(".vault.json");
    
    if !config_path.exists() {
        return Err("Vault config file not found".to_string());
    }
    
    let contents = fs::read_to_string(&config_path)
        .map_err(|e| format!("Failed to read vault config: {}", e))?;
    
    let config: serde_json::Value = serde_json::from_str(&contents)
        .map_err(|e| format!("Failed to parse vault config: {}", e))?;
    
    Ok(config)
}

/// Create a new vault
#[tauri::command]
pub async fn create_vault(name: String, _path: String) -> Result<VaultListItem, String> {
    Err("Vault creation not yet implemented".to_string())
}

/// Search plugins in the community store
#[tauri::command]
pub async fn search_plugins(_query: String, _category: Option<String>) -> Result<Vec<serde_json::Value>, String> {
    Ok(vec![])
}

/// Get plugin details
#[tauri::command]
pub async fn get_plugin_details(_plugin_id: String) -> Result<serde_json::Value, String> {
    Err("Plugin details not yet implemented".to_string())
}

/// Install plugin to vault
#[tauri::command]
pub async fn install_plugin(_vault_path: String, _plugin_repo: String, _plugin_name: String) -> Result<(), String> {
    Err("Plugin installation not yet implemented".to_string())
}

/// Get installed plugins for a vault
#[tauri::command]
pub async fn get_installed_plugins(vault_path: String) -> Result<Vec<serde_json::Value>, String> {
    let path = PathBuf::from(&vault_path).join("plugins");
    
    if !path.exists() {
        return Ok(vec![]);
    }
    
    let mut plugins = vec![];
    
    if let Ok(entries) = fs::read_dir(&path) {
        for entry in entries.flatten() {
            if entry.path().is_dir() {
                let plugin_name = entry.file_name().to_string_lossy().to_string();
                plugins.push(serde_json::json!({
                    "name": plugin_name,
                    "path": entry.path().to_string_lossy().to_string(),
                }));
            }
        }
    }
    
    Ok(plugins)
}

/// Get global settings
#[tauri::command]
pub async fn get_global_settings() -> Result<serde_json::Value, String> {
    Ok(serde_json::json!({
        "theme": "dark",
        "autoUpdate": false,
    }))
}

/// Save global settings
#[tauri::command]
pub async fn save_global_settings(settings: serde_json::Value) -> Result<(), String> {
    println!("Saving global settings: {:?}", settings);
    Ok(())
}

/// Get vault settings
#[tauri::command]
pub async fn get_vault_settings(_vault_path: String) -> Result<serde_json::Value, String> {
    Ok(serde_json::json!({}))
}

/// Save vault settings
#[tauri::command]
pub async fn save_vault_settings(vault_path: String, settings: serde_json::Value) -> Result<(), String> {
    println!("Saving vault settings for {}: {:?}", vault_path, settings);
    Ok(())
}

/// Get API keys
#[tauri::command]
pub async fn get_api_keys() -> Result<serde_json::Value, String> {
    Ok(serde_json::json!({}))
}

/// Save API key
#[tauri::command]
pub async fn save_api_key(key_name: String, _key_value: String) -> Result<(), String> {
    println!("Saving API key: {}", key_name);
    Ok(())
}

/// Delete API key
#[tauri::command]
pub async fn delete_api_key(key_name: String) -> Result<(), String> {
    println!("Deleting API key: {}", key_name);
    Ok(())
}

/// Search conversations
#[tauri::command]
pub async fn search_conversations(_query: String, _filters: serde_json::Value) -> Result<Vec<serde_json::Value>, String> {
    Ok(vec![])
}

/// Get conversation details
#[tauri::command]
pub async fn get_conversation(_vault_path: String, _conversation_id: String) -> Result<serde_json::Value, String> {
    Err("Conversation loading not yet implemented".to_string())
}

/// Delete conversation
#[tauri::command]
pub async fn delete_conversation(vault_path: String, conversation_id: String) -> Result<(), String> {
    println!("Deleting conversation {} from {}", conversation_id, vault_path);
    Ok(())
}

/// Get plugin template
#[tauri::command]
pub async fn get_plugin_template() -> Result<String, String> {
    Ok(r#"# plugins/my_plugin/main.py
import sys
from pathlib import Path

# Add sidecar to path
sidecar_path = Path(__file__).parent.parent.parent.parent / "sidecar"
sys.path.insert(0, str(sidecar_path))

from api.plugin_base import PluginBase

class Plugin(PluginBase):
    """My custom plugin."""
    
    def __init__(self, emitter, brain, plugin_dir, vault_path):
        super().__init__(emitter, brain, plugin_dir, vault_path)
        self.name = "my_plugin"
    
    async def on_tick(self, emitter):
        """Called every 5 seconds."""
        pass
    
    async def custom_method(self, **kwargs):
        """Call via: execute_command('my_plugin.custom_method', {...})"""
        return {"status": "ok"}"#.to_string())
}

/// Validate plugin structure
#[tauri::command]
pub async fn validate_plugin(_vault_path: String, plugin_path: String) -> Result<serde_json::Value, String> {
    let path = PathBuf::from(&plugin_path);
    let main_py = path.join("main.py");
    
    if !main_py.exists() {
        return Err("Plugin missing main.py file".to_string());
    }
    
    Ok(serde_json::json!({
        "valid": true,
        "message": "Plugin structure is valid",
    }))
}


