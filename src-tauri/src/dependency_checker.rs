use std::path::PathBuf;
use std::process::Command;
use anyhow::{Result, Context};

pub struct DependencyChecker;

impl DependencyChecker {
    /// Check and install dependencies for a vault
    pub async fn check_and_install(vault_path: &str) -> Result<()> {
        let vault_path = PathBuf::from(vault_path);
        
        // Check if plugins directory exists
        let plugins_dir = vault_path.join("plugins");
        if !plugins_dir.exists() {
            println!("No plugins directory found in vault, skipping dependency check");
            return Ok(());
        }

        // Check for requirements.txt
        let requirements_file = plugins_dir.join("requirements.txt");
        if !requirements_file.exists() {
            println!("No requirements.txt found, skipping dependency installation");
            return Ok(());
        }

        // Create lib directory if it doesn't exist
        let lib_dir = vault_path.join("lib");
        std::fs::create_dir_all(&lib_dir)
            .context("Failed to create lib directory")?;

        println!("Installing dependencies for vault: {}", vault_path.display());
        println!("Requirements file: {}", requirements_file.display());
        println!("Target directory: {}", lib_dir.display());

        // Run pip install
        let output = Command::new(Self::get_pip_executable()?)
            .arg("install")
            .arg("-t")
            .arg(&lib_dir)
            .arg("-r")
            .arg(&requirements_file)
            .arg("--upgrade")
            .output()
            .context("Failed to run pip install")?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            eprintln!("pip install failed: {}", stderr);
            anyhow::bail!("Failed to install dependencies");
        }

        let stdout = String::from_utf8_lossy(&output.stdout);
        println!("Dependencies installed:\n{}", stdout);

        Ok(())
    }

    /// Get pip executable
    fn get_pip_executable() -> Result<String> {
        #[cfg(target_os = "windows")]
        let pip_candidates = vec!["pip.exe", "pip3.exe"];
        
        #[cfg(not(target_os = "windows"))]
        let pip_candidates = vec!["pip3", "pip"];

        for candidate in pip_candidates {
            if let Ok(output) = Command::new(candidate)
                .arg("--version")
                .output()
            {
                if output.status.success() {
                    return Ok(candidate.to_string());
                }
            }
        }

        anyhow::bail!("pip not found in PATH")
    }

    /// Check if dependencies need updating
    #[allow(dead_code)]
    pub async fn needs_update(vault_path: &str) -> Result<bool> {
        let vault_path = PathBuf::from(vault_path);
        let requirements_file = vault_path.join("plugins").join("requirements.txt");
        let lib_dir = vault_path.join("lib");

        // If requirements.txt doesn't exist, no update needed
        if !requirements_file.exists() {
            return Ok(false);
        }

        // If lib directory doesn't exist, update needed
        if !lib_dir.exists() {
            return Ok(true);
        }

        // Check modification times (simplified check)
        // In production, you'd want to parse requirements.txt and check installed versions
        Ok(false)
    }
}
