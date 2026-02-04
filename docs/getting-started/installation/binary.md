# Binary Installation

Download and run pre-built qBitrr binaries for Linux, macOS, or Windows. No Python installation required!

!!! info "Binary Releases"
    Pre-built binaries are generated for each release using PyInstaller. They include Python and all dependencies in a single executable file.

## Prerequisites

- 64-bit operating system (Linux, macOS, or Windows)
- qBittorrent running and accessible
- At least one Arr instance (Radarr, Sonarr, or Lidarr)

## Download

### Latest Release

Visit the [GitHub Releases page](https://github.com/Feramance/qBitrr/releases) and download the binary for your platform:

| Platform | File |
|----------|------|
| Linux | `qbitrr-linux-x64` |
| macOS | `qbitrr-macos-x64` |
| Windows | `qbitrr-windows-x64.exe` |

### Command Line Download

=== "Linux"

    ```bash
    # Download latest release
    curl -L -o qbitrr https://github.com/Feramance/qBitrr/releases/latest/download/qbitrr-linux-x64

    # Make executable
    chmod +x qbitrr

    # Run
    ./qbitrr
    ```

=== "macOS"

    ```bash
    # Download latest release
    curl -L -o qbitrr https://github.com/Feramance/qBitrr/releases/latest/download/qbitrr-macos-x64

    # Make executable
    chmod +x qbitrr

    # Run (you may need to allow in Security settings)
    ./qbitrr
    ```

=== "Windows"

    ```powershell
    # Download with PowerShell
    Invoke-WebRequest -Uri https://github.com/Feramance/qBitrr/releases/latest/download/qbitrr-windows-x64.exe -OutFile qbitrr.exe

    # Run
    .\qbitrr.exe
    ```

## Installation

### Linux

1. **Download and install:**
   ```bash
   sudo curl -L -o /usr/local/bin/qbitrr \
     https://github.com/Feramance/qBitrr/releases/latest/download/qbitrr-linux-x64

   sudo chmod +x /usr/local/bin/qbitrr
   ```

2. **Run:**
   ```bash
   qbitrr
   ```

### macOS

1. **Download:**
   ```bash
   curl -L -o ~/Downloads/qbitrr \
     https://github.com/Feramance/qBitrr/releases/latest/download/qbitrr-macos-x64

   chmod +x ~/Downloads/qbitrr
   ```

2. **Move to Applications (optional):**
   ```bash
   sudo mv ~/Downloads/qbitrr /usr/local/bin/
   ```

3. **First run (security prompt):**
   ```bash
   ./qbitrr
   ```

   If macOS blocks it:
   - Go to System Preferences → Security & Privacy
   - Click "Allow Anyway" next to the qbitrr message
   - Run again

### Windows

1. **Download** `qbitrr-windows-x64.exe` from releases

2. **Move to a permanent location:**
   ```
   C:\Program Files\qBitrr\qbitrr.exe
   ```

3. **Run:**
   - Double-click `qbitrr.exe`
   - Or run from PowerShell: `.\qbitrr.exe`

4. **Add to PATH (optional):**
   - Search for "Environment Variables"
   - Edit "Path" system variable
   - Add `C:\Program Files\qBitrr`

## First Run

1. **Start qBitrr:**
   ```bash
   ./qbitrr  # or qbitrr.exe on Windows
   ```

2. **Configuration file created:**

   Binary installations use these default paths:

   === "Linux/macOS"
       ```
       ~/.config/qbitrr/config.toml
       ~/.local/share/qbitrr/logs/
       ```

   === "Windows"
       ```
       %APPDATA%\qbitrr\config.toml
       %APPDATA%\qbitrr\logs\
       ```

3. **Stop qBitrr:**
   Press ++ctrl+c++

4. **Edit configuration:**
   See [First Run Guide](../quickstart.md)

5. **Start again:**
   ```bash
   ./qbitrr
   ```

## Configuration Location

### Custom Config Path

Set a custom config directory:

=== "Linux/macOS"

    ```bash
    export QBITRR_CONFIG_PATH=/path/to/config
    ./qbitrr
    ```

=== "Windows"

    ```powershell
    $env:QBITRR_CONFIG_PATH = "C:\path\to\config"
    .\qbitrr.exe
    ```

## Running as a Service

### Linux (systemd)

Create `/etc/systemd/system/qbitrr.service`:

```ini
[Unit]
Description=qBitrr
After=network.target

[Service]
Type=simple
User=your-user
ExecStart=/usr/local/bin/qbitrr
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now qbitrr
```

### Windows

Use Task Scheduler:

1. Open Task Scheduler
2. Create Basic Task
3. Name: "qBitrr"
4. Trigger: "When the computer starts"
5. Action: "Start a program"
6. Program: `C:\Program Files\qBitrr\qbitrr.exe`
7. Finish

Or use [NSSM](https://nssm.cc/):

```powershell
nssm install qBitrr "C:\Program Files\qBitrr\qbitrr.exe"
nssm start qBitrr
```

### macOS (LaunchAgent)

Create `~/Library/LaunchAgents/com.qbitrr.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.qbitrr</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/qbitrr</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

Load:

```bash
launchctl load ~/Library/LaunchAgents/com.qbitrr.plist
```

## Updating

Binary installations do not support auto-update. You must manually download and replace the binary.

### Linux/macOS

```bash
# Backup current binary
sudo mv /usr/local/bin/qbitrr /usr/local/bin/qbitrr.bak

# Download latest
sudo curl -L -o /usr/local/bin/qbitrr \
  https://github.com/Feramance/qBitrr/releases/latest/download/qbitrr-linux-x64

sudo chmod +x /usr/local/bin/qbitrr

# Restart service
sudo systemctl restart qbitrr  # if using systemd
```

### Windows

1. Stop qBitrr (or the service)
2. Download new `qbitrr-windows-x64.exe`
3. Replace old file
4. Start qBitrr again

## Troubleshooting

### Binary Won't Run

=== "Linux"

    Check dependencies:
    ```bash
    ldd ./qbitrr
    ```

    Most common issues:
    - Missing `glibc` (too old)
    - Missing `libz` or `libssl`

    Solution: Use [pip installation](pip.md) instead.

=== "macOS"

    If blocked by security:
    ```bash
    # Remove quarantine flag
    xattr -d com.apple.quarantine ./qbitrr
    ```

=== "Windows"

    If blocked by Windows Defender:
    - Add exception in Windows Security
    - Or use [pip installation](pip.md)

### Permission Denied

=== "Linux/macOS"

    ```bash
    chmod +x qbitrr
    ```

=== "Windows"

    Run as Administrator (right-click → Run as administrator)

### Config File Not Found

Check config location:

```bash
./qbitrr --show-config-path
```

Create config directory manually:

=== "Linux/macOS"

    ```bash
    mkdir -p ~/.config/qbitrr
    ```

=== "Windows"

    ```powershell
    New-Item -ItemType Directory -Path "$env:APPDATA\qbitrr"
    ```

### Large Binary Size

Binary files are 50-100MB because they include:
- Python interpreter
- All Python dependencies
- Compiled libraries

This is normal for PyInstaller binaries.

## Advantages & Disadvantages

### ✅ Advantages

- No Python installation required
- Single file distribution
- Easy to deploy
- Consistent across systems
- No dependency conflicts

### ❌ Disadvantages

- Large file size (50-100MB)
- No auto-update support
- Manual updates required
- May trigger antivirus warnings
- Slower startup than native Python

## Building from Source

To build your own binary:

```bash
# Clone repository
git clone https://github.com/Feramance/qBitrr.git
cd qBitrr

# Install dependencies
pip install pyinstaller
pip install -e .[all]

# Build
pyinstaller build.spec

# Binary in dist/
ls dist/
```

See the [Development Guide](../../development/index.md) for more details.

## Next Steps

- [First Run Guide](../quickstart.md)
- [Configure qBittorrent](../../configuration/qbittorrent.md)
- [Configure Arr Instances](../../configuration/arr/index.md)
- [Troubleshooting](../../troubleshooting/index.md)
