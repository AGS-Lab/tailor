use std::collections::HashMap;
use std::process::{Child, Command, Stdio};
use std::sync::Arc;
use tokio::sync::Mutex;
use anyhow::{Result, Context};

pub struct SidecarProcess {
    pub child: Child,
    #[allow(dead_code)]
    pub vault_path: String,
    pub ws_port: u16,
}

pub struct SidecarManager {
    processes: Arc<Mutex<HashMap<String, SidecarProcess>>>,
    next_port: Arc<Mutex<u16>>,
}

impl Default for SidecarManager {
    fn default() -> Self {
        Self::new()
    }
}

impl SidecarManager {
    pub fn new() -> Self {
        Self {
            processes: Arc::new(Mutex::new(HashMap::new())),
            next_port: Arc::new(Mutex::new(9000)),
        }
    }

    /// Spawn a Python sidecar process for a vault
    pub async fn spawn_sidecar(
        &self,
        window_label: String,
        vault_path: String,
    ) -> Result<u16> {
        // Allocate port
        let ws_port = self.allocate_port().await;

        // Get Python executable path
        let python_exe = self.get_python_executable()?;
        
        // Get project root (parent of src-tauri) to set as CWD
        let project_root = std::env::current_dir()?
            .parent()
            .context("Failed to get parent directory")?
            .to_path_buf();

        println!("Spawning sidecar for window '{}': vault={}, port={}", 
                 window_label, vault_path, ws_port);
        println!("Python executable: {}", python_exe);
        println!("Project root: {}", project_root.display());

        // Spawn Python process with unbuffered output
        let mut child = Command::new(&python_exe)
            .arg("-u")  // Unbuffered output
            .arg("-m")
            .arg("sidecar")
            .arg("--vault")
            .arg(&vault_path)
            .arg("--ws-port")
            .arg(ws_port.to_string())
            .current_dir(&project_root)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .context("Failed to spawn Python sidecar")?;

        let pid = child.id();
        println!("Sidecar spawned with PID: {}", pid);

        // Capture stdout for debugging
        if let Some(stdout) = child.stdout.take() {
            use std::io::BufRead;
            std::thread::spawn(move || {
                let reader = std::io::BufReader::new(stdout);
                for line in reader.lines() {
                    if let Ok(line) = line {
                        println!("[Sidecar] {}", line);
                    }
                }
            });
        }

        // Capture stderr for debugging
        if let Some(stderr) = child.stderr.take() {
            use std::io::BufRead;
            std::thread::spawn(move || {
                let reader = std::io::BufReader::new(stderr);
                for line in reader.lines() {
                    if let Ok(line) = line {
                        eprintln!("[Sidecar Error] {}", line);
                    }
                }
            });
        }

        // Store process
        let process = SidecarProcess {
            child,
            vault_path: vault_path.clone(),
            ws_port,
        };

        self.processes.lock().await.insert(window_label.clone(), process);

        Ok(ws_port)
    }

    /// Terminate a sidecar process
    pub async fn terminate_sidecar(&self, window_label: &str) -> Result<()> {
        let mut processes = self.processes.lock().await;
        
        if let Some(mut process) = processes.remove(window_label) {
            println!("Terminating sidecar for window '{}'", window_label);
            
            // Try graceful shutdown first
            if let Err(e) = process.child.kill() {
                eprintln!("Failed to kill sidecar process: {}", e);
            }
            
            // Wait for process to exit
            if let Err(e) = process.child.wait() {
                eprintln!("Failed to wait for sidecar exit: {}", e);
            }
            
            println!("Sidecar terminated for window '{}'", window_label);
        }

        Ok(())
    }

    /// Terminate ALL sidecar processes (used for app shutdown)
    pub fn shutdown_all(&self) {
        println!("Shutting down all sidecars...");
        // Use blocking lock for shutdown
        if let Ok(mut processes) = self.processes.try_lock() {
             for (label, mut process) in processes.drain() {
                println!("Killing sidecar for window '{}' (PID: {})", label, process.child.id());
                if let Err(e) = process.child.kill() {
                    eprintln!("Failed to kill sidecar {}: {}", label, e);
                } else {
                     let _ = process.child.wait(); // Best effort wait
                }
             }
        } else {
            // Fallback: If we can't lock (unlikely in shutdown), we might leak. 
            // Better to force lock if possible, but try_lock avoids deadlock potential in panic paths.
            eprintln!("Failed to acquire lock for shutdown cleanup!");
        }
    }
    
    /// Get WebSocket port for a sidecar
    pub async fn get_ws_port(&self, window_label: &str) -> Option<u16> {
        self.processes.lock().await
            .get(window_label)
            .map(|p| p.ws_port)
    }

    /// Check if sidecar is still running
    #[allow(dead_code)]
    pub async fn is_running(&self, window_label: &str) -> bool {
        self.processes.lock().await.contains_key(window_label)
    }

    /// Allocate next available port by actually checking port availability
    async fn allocate_port(&self) -> u16 {
        let mut port = self.next_port.lock().await;
        
        // Try to find an available port starting from current port
        loop {
            if Self::is_port_available(*port) {
                let allocated = *port;
                *port += 1;
                return allocated;
            }
            *port += 1;
            
            // Wrap around if we exceed reasonable ports
            if *port > 19000 {
                *port = 9000;
            }
        }
    }
    
    /// Check if a port is available
    fn is_port_available(port: u16) -> bool {
        use std::net::TcpListener;
        TcpListener::bind(("127.0.0.1", port)).is_ok()
    }

    /// Get Python executable path
    fn get_python_executable(&self) -> Result<String> {
        // Try to find Python in PATH
        #[cfg(target_os = "windows")]
        let python_candidates = vec!["python.exe", "python3.exe"];
        
        #[cfg(not(target_os = "windows"))]
        let python_candidates = vec!["python3", "python"];

        for candidate in python_candidates {
            if let Ok(output) = Command::new(candidate)
                .arg("--version")
                .output()
            {
                if output.status.success() {
                    return Ok(candidate.to_string());
                }
            }
        }

        anyhow::bail!("Python not found in PATH")
    }
}

impl Drop for SidecarManager {
    fn drop(&mut self) {
        // Ensure all processes are terminated when manager is dropped
        // Note: This is a blocking operation in async context
        // In production, consider using a shutdown signal
        println!("SidecarManager dropping - cleaning up processes");
    }
}
