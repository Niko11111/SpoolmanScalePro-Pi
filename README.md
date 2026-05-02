# SpoolmanScalePro-Pi

> Self-hosted filament management server for SpoolmanScale Pro — runs Spoolman or FilaMan on a Raspberry Pi with a built-in web UI for setup and management.

Part of the [SpoolmanScale](https://github.com/Niko11111/SpoolmanScale) ecosystem.

---

## What is this?

SpoolmanScalePro-Pi turns a Raspberry Pi into a self-contained filament management server. It runs either [Spoolman](https://github.com/Donkie/Spoolman) or [FilaMan](https://filaman.app) — switchable at any time — and provides a built-in web UI for setup, monitoring, backup and management.

Designed to run inside the **SpoolmanScale Pro** enclosure (Pi Zero 2W), but works on any Raspberry Pi with Docker.

## Features

- 🔄 **Switch between Spoolman and FilaMan** — only one runs at a time for stability
- 🌐 **Built-in Web UI** — setup, status, backup, WiFi, update and more
- 💾 **Backup & Restore** — generate and download database backups with one click
- 🔁 **Auto-start** — last active backend starts automatically on boot
- 📡 **mDNS** — reachable via `http://spoolmanscale.local`

## Requirements

- Raspberry Pi (Zero 2W, 3, 4 or 5)
- Raspberry Pi OS Lite (64-bit, Debian Trixie or later)
- Docker

## Installation

### 1. Flash Pi OS

Flash **Raspberry Pi OS Lite (64-bit)** with Pi Imager. In the pre-configuration:

| Setting | Value |
|---|---|
| Hostname | `spoolmanscale` |
| SSH | Enable, public key auth |
| WiFi | 2.4 GHz only (Pi Zero 2W has no 5 GHz) |
| Locale | Your region |

### 2. First boot

```bash
ssh pi@spoolmanscale.local
```

### 3. Passwordless sudo (optional but recommended)

```bash
echo "pi ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/010_pi-nopasswd
sudo chmod 440 /etc/sudoers.d/010_pi-nopasswd
```

### 4. GPU RAM reduction (headless, saves ~48 MB)

```bash
echo "gpu_mem=16" | sudo tee -a /boot/firmware/config.txt
sudo reboot
```

### 5. Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker pi
```

Log out and back in, then verify:

```bash
docker --version
docker compose version
```

### 6. Clone and start

```bash
mkdir -p ~/spoolmanscale/spoolmanscale-ui/templates
mkdir -p ~/spoolmanscale/spoolmanscale-ui/static
cd ~/spoolmanscale

# Clone repo
git clone https://github.com/Niko11111/SpoolmanScalePro-Pi.git .

# Fix permissions
chmod +x switch-backend.sh

# Start Setup UI
docker compose up -d --build
```

### 7. Auto-start on boot

```bash
sudo nano /etc/systemd/system/spoolmanscale-backend.service
```

Paste:

```ini
[Unit]
Description=SpoolmanScale Backend Auto-Start
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=root
WorkingDirectory=/home/pi/spoolmanscale
ExecStart=/home/pi/spoolmanscale/switch-backend.sh auto

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable spoolmanscale-backend.service
```

### 8. Open Web UI

```
http://spoolmanscale.local
```

or use the Pi's IP address directly.

From the Web UI, select and activate Spoolman or FilaMan — the backend will be downloaded and started automatically.

---

## Backends

| | Spoolman | FilaMan |
|---|---|---|
| Port | 7912 | 8002 |
| Community | Large, established | Growing |
| UI | Functional | Modern |
| App | — | iOS & Android |
| Recommendation | Most users | App integration |

Both backends **cannot run simultaneously** on the Pi Zero 2W (512 MB RAM). Switch anytime from the Web UI — your data is always kept separately.

---

## Web UI

| Tab | Features |
|---|---|
| **Backend** | Switch Spoolman ↔ FilaMan, status, update, logs |
| **System** | RAM/SD/Temp/Uptime, Pi update, WiFi, reboot, shutdown |
| **Backup** | Generate, download, restore database backups |

---

## Part of SpoolmanScale

- 🔧 [SpoolmanScale](https://github.com/Niko11111/SpoolmanScale) — ESP32 filament scale with NFC
- ☕ [Ko-fi](https://ko-fi.com/formfollowsfunction) — Support the project
- 💬 [Discord](https://discord.gg/GzQzGa5pBG) — Community
- 🖨️ [MakerWorld](https://makerworld.com/de/@FormFollowsF) — 3D printable enclosure

---

© 2026 Nikolai Herrmann. All rights reserved.
