use crate::{AppState, dependency_checker::DependencyChecker};
use tauri::{AppHandle, State, Manager};
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


#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VaultListItem {
    pub name: String,
    pub path: String,
    pub created: Option<String>,
}

/// List all known vaults
#[tauri::command]
pub async fn list_vaults(app: AppHandle) -> Result<Vec<VaultListItem>, String> {
    let mut vaults = Vec::new();
    
    // Get app data directory
    let app_data_dir = app.path().app_data_dir()
        .map_err(|e| format!("Failed to get app data directory: {}", e))?;
    
    // Create app data directory if it doesn't exist
    fs::create_dir_all(&app_data_dir)
        .map_err(|e| format!("Failed to create app data directory: {}", e))?;
    
    let registry_path = app_data_dir.join("vaults.json");
    
    // If registry exists, load it
    if registry_path.exists() {
        if let Ok(contents) = fs::read_to_string(&registry_path) {
                if let Ok(registry) = serde_json::from_str::<Vec<VaultListItem>>(&contents) {
                    // Validate that vaults still exist and load info from .vault.json
                    for mut vault in registry {
                        let vault_path = PathBuf::from(&vault.path);
                        if vault_path.exists() {
                            // Try to load vault info from .vault.json
                            let config_path = vault_path.join(".vault.json");
                            if config_path.exists() {
                                if let Ok(config_contents) = fs::read_to_string(&config_path) {
                                    if let Ok(config) = serde_json::from_str::<serde_json::Value>(&config_contents) {
                                        if let Some(name) = config.get("name").and_then(|v| v.as_str()) {
                                            vault.name = name.to_string();
                                        }
                                        if let Some(created) = config.get("created").and_then(|v| v.as_str()) {
                                            vault.created = Some(created.to_string());
                                        }
                                    }
                                }
                            }
                            vaults.push(vault);
                        }
                    }
                }
        }
    }
    
    Ok(vaults)
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

/// Update plugin configuration in .vault.json
#[tauri::command]
pub async fn update_plugin_config(
    vault_path: String,
    plugin_id: String,
    config: serde_json::Value,
) -> Result<(), String> {
    let path = PathBuf::from(&vault_path);
    let config_path = path.join(".vault.json");
    
    // Read existing config
    let contents = if config_path.exists() {
        fs::read_to_string(&config_path)
            .map_err(|e| format!("Failed to read vault config: {}", e))?
    } else {
        r#"{"plugins": {}}"#.to_string()
    };
    
    let mut vault_config: serde_json::Value = serde_json::from_str(&contents)
        .map_err(|e| format!("Failed to parse vault config: {}", e))?;
    
    // Ensure plugins object exists
    if vault_config.get("plugins").is_none() {
        vault_config["plugins"] = serde_json::json!({});
    }
    
    // Get or create plugin config
    if vault_config["plugins"].get(&plugin_id).is_none() {
        vault_config["plugins"][&plugin_id] = serde_json::json!({});
    }
    
    // Merge config values
    if let Some(plugin_config) = vault_config["plugins"].get_mut(&plugin_id) {
        if let serde_json::Value::Object(plugin_obj) = plugin_config {
            if let serde_json::Value::Object(new_config) = config {
                for (key, value) in new_config {
                    plugin_obj.insert(key, value);
                }
            }
        }
    }
    
    // Write back
    let updated = serde_json::to_string_pretty(&vault_config)
        .map_err(|e| format!("Failed to serialize config: {}", e))?;
    
    fs::write(&config_path, updated)
        .map_err(|e| format!("Failed to write vault config: {}", e))?;
    
    println!("Updated plugin config for '{}' in {}", plugin_id, vault_path);
    
    Ok(())
}

/// Create a new vault
#[tauri::command]
pub async fn create_vault(
    name: String,
    path: String,
    app: AppHandle,
) -> Result<VaultListItem, String> {
    // Validate that path is provided
    if path.is_empty() {
        return Err("Vault path is required".to_string());
    }
    
    let vault_path = PathBuf::from(&path);
    
    // Check if vault already exists
    if vault_path.exists() {
        return Err(format!("Directory already exists: {}", path));
    }
    
    // Create vault directory
    fs::create_dir_all(&vault_path)
        .map_err(|e| format!("Failed to create vault directory: {}", e))?;
    
    // Create subdirectories
    let plugins_dir = vault_path.join("plugins");
    let lib_dir = vault_path.join("lib");
    let memory_dir = vault_path.join(".memory");
    let configs_dir = vault_path.join("configs");
    
    fs::create_dir_all(&plugins_dir)
        .map_err(|e| format!("Failed to create plugins directory: {}", e))?;
    fs::create_dir_all(&lib_dir)
        .map_err(|e| format!("Failed to create lib directory: {}", e))?;
    fs::create_dir_all(&memory_dir)
        .map_err(|e| format!("Failed to create memory directory: {}", e))?;
    fs::create_dir_all(&configs_dir)
        .map_err(|e| format!("Failed to create configs directory: {}", e))?;
    
    // Create empty requirements.txt in plugins directory
    let requirements_file = plugins_dir.join("requirements.txt");
    if !requirements_file.exists() {
        fs::write(&requirements_file, "# Shared plugin dependencies\n")
            .map_err(|e| format!("Failed to create requirements.txt: {}", e))?;
    }
    
    // Generate vault ID
    let vault_id = format!("vault_{}", uuid::Uuid::new_v4().to_string().replace("-", ""));
    
    // Get current timestamp in ISO 8601 format
    let created_iso = chrono::Utc::now().to_rfc3339();
    
    // Create .vault.json file
    let vault_config = serde_json::json!({
        "id": vault_id,
        "name": name,
        "version": "1.0.0",
        "description": format!("Vault: {}", name),
        "created": created_iso
    });
    
    let config_path = vault_path.join(".vault.json");
    let config_json = serde_json::to_string_pretty(&vault_config)
        .map_err(|e| format!("Failed to serialize vault config: {}", e))?;
    
    fs::write(&config_path, config_json)
        .map_err(|e| format!("Failed to write vault config: {}", e))?;
    
    println!("Created vault: {} at {}", name, path);
    
    let vault_item = VaultListItem {
        name: name.clone(),
        path: path.clone(),
        created: Some(created_iso.clone()),
    };
    
    // Register vault in registry
    register_vault_in_registry(&app, &vault_item).await?;
    
    Ok(vault_item)
}

/// Register a vault in the registry
async fn register_vault_in_registry(
    app: &AppHandle,
    vault: &VaultListItem,
) -> Result<(), String> {
    // Get app data directory
    let app_data_dir = app.path().app_data_dir()
        .map_err(|e| format!("Failed to get app data directory: {}", e))?;
    
    // Create app data directory if it doesn't exist
    fs::create_dir_all(&app_data_dir)
        .map_err(|e| format!("Failed to create app data directory: {}", e))?;
    
    let registry_path = app_data_dir.join("vaults.json");
    
    // Load existing registry
    let mut vaults = if registry_path.exists() {
        if let Ok(contents) = fs::read_to_string(&registry_path) {
            serde_json::from_str::<Vec<VaultListItem>>(&contents).unwrap_or_default()
        } else {
            Vec::new()
        }
    } else {
        Vec::new()
    };
    
    // Check if vault already exists in registry
    if !vaults.iter().any(|v| v.path == vault.path) {
        vaults.push(vault.clone());
        
        // Write registry back
        let registry_json = serde_json::to_string_pretty(&vaults)
            .map_err(|e| format!("Failed to serialize registry: {}", e))?;
        fs::write(&registry_path, registry_json)
            .map_err(|e| format!("Failed to write registry: {}", e))?;
    }
    
    Ok(())
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

