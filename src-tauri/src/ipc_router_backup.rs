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
