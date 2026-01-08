# Tailor Setup Guide

## Quick Start (Windows)

### Step 1: Install Rust

Rust is required to compile the Tauri backend.

```powershell
# Option A: Using winget (Windows 11/10)
winget install --id Rustlang.Rustup

# Option B: Manual download
# Visit https://rustup.rs/ and run the installer
```

**Important**: After installation, restart your terminal or run:
```powershell
refreshenv
```

Verify installation:
```powershell
cargo --version
# Should output: cargo 1.xx.x
```

### Step 2: Install Node.js Dependencies

```powershell
cd c:\Users\ARC\Dev\tailor
npm install
```

### Step 3: Install Python Sidecar Dependencies

```powershell
cd sidecar
pip install -r requirements.txt
cd ..
```

### Step 4: Run Development Server

```powershell
npm run tauri:dev
```

This will:
1. ✅ Start Vite frontend dev server (port 5173)
2. ✅ Compile Rust backend
3. ✅ Launch Tauri application window

## Testing the Implementation

### Test 1: Open Example Vault

1. Click "Open Vault" button
2. Navigate to `c:\Users\ARC\Dev\tailor\example-vault`
3. Select the folder

**Expected Behavior**:
- Status shows: "✅ Vault opened: vault_xxx (Port: 9000)"
- Console shows sidecar initialization
- Python process spawned

### Test 2: Verify Plugin Events

Wait 15 seconds after opening the vault.

**Expected Behavior**:
- Alert popup appears: "INFO: Heartbeat #1 from example_plugin"
- This repeats every 15 seconds
- Console shows tick events every 5 seconds

### Test 3: Open Multiple Vaults

1. Create a copy of `example-vault` named `test-vault`
2. Open both vaults in separate windows
3. Observe separate Python processes

**Expected Behavior**:
- Two vault windows open
- Two Python processes running
- Independent notifications from each

## Troubleshooting

### "Rust not found"

```powershell
# Ensure Rust is installed
cargo --version

# If not found, restart terminal after Rust installation
```

### "Python not found"

```powershell
# Verify Python is in PATH
python --version

# If not, install Python 3.10+ from python.org
```

### "Failed to spawn sidecar"

Check:
- Python is accessible via `python` command
- Sidecar dependencies are installed: `pip list | grep websockets`
- Path to `sidecar/main.py` is correct

### "WebSocket connection failed"

- Ensure port 9000+ are not blocked by firewall
- Check sidecar process is running: `tasklist | findstr python`

## Next Steps

### Create Your Own Plugin

1. Copy `example-vault` to a new location
2. Create a new file in `plugins/` directory:

```python
# plugins/my_plugin.py
class Plugin:
    def __init__(self, emitter):
        self.emitter = emitter
        self.name = "my_plugin"
    
    async def on_tick(self, emitter):
        # Your logic here
        pass
```

3. Open your vault in Tailor

### Add Dependencies

Edit `plugins/requirements.txt`:
```
requests==2.31.0
beautifulsoup4==4.12.0
```

Tailor will auto-install when you open the vault.

## Architecture Reference

- **Rust Code**: `src-tauri/src/*.rs`
- **Python Code**: `sidecar/*.py`
- **Frontend**: `src/index.html`
- **Example Vault**: `example-vault/`

## Development Commands

```powershell
# Run in dev mode
npm run tauri:dev

# Build for production
npm run tauri:build

# Run Rust tests
cd src-tauri
cargo test

# Run Python sidecar standalone
cd sidecar
python main.py --vault ../example-vault --ws-port 9000
```

## Support

See documentation in:
- [README.md](../README.md)
- Architecture docs in `.gemini/antigravity/brain/...`
