/**
 * API service for communicating with Tauri backend
 * Provides typed functions for all IPC commands
 */

import { invoke } from '@tauri-apps/api/core';
import { open } from '@tauri-apps/plugin-dialog';

/**
 * Vault Management
 */
export const vaultApi = {
    /**
     * Open a vault by selecting a directory
     */
    async openVault() {
        const selected = await open({
            directory: true,
            multiple: false,
        });
        if (selected) {
            return await invoke('open_vault', { vaultPath: selected });
        }
        return null;
    },

    /**
     * Open a vault by path
     */
    async openVaultByPath(vaultPath) {
        return await invoke('open_vault', { vaultPath });
    },

    /**
     * Get list of known vaults
     */
    async listVaults() {
        return await invoke('list_vaults', {});
    },

    /**
     * Get vault information
     */
    async getVaultInfo(vaultPath) {
        return await invoke('get_vault_info', { vaultPath });
    },

    /**
     * Create a new vault
     */
    async createVault(name, path) {
        return await invoke('create_vault', { name, path });
    },

    /**
     * Select a parent directory for vault creation
     */
    async selectDirectory() {
        return await open({
            directory: true,
            multiple: false,
        });
    },

    /**
     * Close a vault window
     */
    async closeVault(windowLabel) {
        return await invoke('close_vault', { windowLabel });
    },

    /**
     * Update plugin configuration in .vault.toml
     */
    async updatePluginConfig(vaultPath, pluginId, config) {
        return await invoke('update_plugin_config', { vaultPath, pluginId, config });
    },
};

/**
 * Plugin Store API
 */
export const pluginStoreApi = {
    /**
     * Search plugins
     */
    async searchPlugins(query, category = null) {
        return await invoke('search_plugins', { query, category });
    },

    /**
     * Get plugin details
     */
    async getPluginDetails(pluginId) {
        return await invoke('get_plugin_details', { pluginId });
    },

    /**
     * Install plugin to vault
     */
    async installPlugin(vaultPath, pluginRepo, pluginName) {
        return await invoke('install_plugin', { vaultPath, pluginRepo, pluginName });
    },

    /**
     * Get installed plugins for a vault
     */
    async getInstalledPlugins(vaultPath) {
        return await invoke('get_installed_plugins', { vaultPath });
    },
};

/**
 * Settings API
 */
export const settingsApi = {
    /**
     * Get global settings
     */
    async getGlobalSettings() {
        return await invoke('get_global_settings', {});
    },

    /**
     * Save global settings
     */
    async saveGlobalSettings(settings) {
        return await invoke('save_global_settings', { settings });
    },

    /**
     * Get vault settings
     */
    async getVaultSettings(vaultPath) {
        return await invoke('get_vault_settings', { vaultPath });
    },

    /**
     * Save vault settings
     */
    async saveVaultSettings(vaultPath, settings) {
        return await invoke('save_vault_settings', { vaultPath, settings });
    },

    /**
     * Get effective settings (Global + Vault)
     */
    async getEffectiveSettings(vaultPath) {
        return await invoke('get_effective_settings', { vaultPath });
    },

    /**
     * Get settings schema
     */
    async getSettingsSchema() {
        return await invoke('get_settings_schema', {});
    },

    /**
     * Get API keys
     */
    async getApiKeys() {
        return await invoke('get_api_keys', {});
    },

    /**
     * Save API key
     */
    async saveApiKey(keyName, keyValue) {
        return await invoke('save_api_key', { keyName, keyValue });
    },

    /**
     * Delete API key
     */
    async deleteApiKey(keyName) {
        return await invoke('delete_api_key', { keyName });
    },
};

/**
 * Developer Mode API
 */
export const developerApi = {
    /**
     * Get plugin template
     */
    async getPluginTemplate() {
        return await invoke('get_plugin_template', {});
    },

    /**
     * Validate plugin structure
     */
    async validatePlugin(vaultPath, pluginPath) {
        return await invoke('validate_plugin', { vaultPath, pluginPath });
    },
};

