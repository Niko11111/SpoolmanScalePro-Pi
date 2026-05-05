# SpoolmanScalePro-Pi

> Self-hosted filament management server for SpoolmanScale Pro — runs Spoolman or FilaMan on a Raspberry Pi with a built-in web UI for setup and management.

Part of the [SpoolmanScale](https://github.com/Niko11111/SpoolmanScale) ecosystem.

---

## What is this?

SpoolmanScalePro-Pi turns a Raspberry Pi into a self-contained filament management server. It runs either [Spoolman](https://github.com/Donkie/Spoolman) or [FilaMan](https://filaman.app) — switchable at any time — and provides a built-in web UI for setup, monitoring, backup and management.

Designed to run inside the **SpoolmanScale Pro** enclosure (Pi Zero 2W), but works on any Raspberry Pi with Docker.

## Features

- 🔄 **Switch between Spoolman and FilaMan** — only one runs at a time for stability on Pi Zero 2W
- 🌐 **Built-in Web UI** — setup, status, backup, WiFi, update and more
- 💾 **Backup & Restore** — generate and download database backups with one click
- 🔁 **Auto-start** — last active backend starts automatically on boot
- 📡 **mDNS** — reachable via http://spoolmanscale.local
- 🔄 **Auto-Backup** — daily scheduled backups, keeps last 7
- ⬆️ **Self-Update** — check and install UI updates directly from the web interface

## Requirements

- Raspberry Pi (Zero 2W, 3, 4 or 5)
- Raspberry Pi OS Lite (64-bit, Debian Trixie or later)
- Docker

## Installation

### 1. Flash Pi OS

Flash **Raspberry Pi OS Lite (64-bit)** with Pi Imager. In the pre-configuration:

| Setting | Value |
|---|---|
| Hostname | spoolmanscale |
| SSH | Enable, public key auth |
| WiFi | 2.4 GHz only (Pi Zero 2W has no 5 GHz) |
| Locale | Your region |

### 2. First boot

ssh pi@spoolmanscale.local

### 3. Passwordless sudo (optional but recommended)

echo "pi ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/010_pi-nopasswd
sudo chmod 440 /etc/sudoers.d/010_pi-nopasswd

### 4. GPU RAM reduction (headless, saves ~48 MB)

echo "gpu_mem=16" | sudo tee -a /boot/firmware/config.txt
sudo reboot

### 5. Docker

curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker pi

Log out and back in, then verify docker --version and docker compose version.

### 6. Clone and start

mkdir -p ~/spoolmanscale
cd ~/spoolmanscale
git clone https://github.com/Niko11111/SpoolmanScalePro-Pi.git .
chmod +x switch-backend.sh auto-backup.sh
docker compose pull
docker compose up -d

### 7. Auto-start on boot

Create /etc/systemd/system/spoolmanscale-backend.service with:

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

Then: sudo systemctl daemon-reload && sudo systemctl enable spoolmanscale-backend.service

### 8. Open Web UI

http://spoolmanscale.local or use the Pi IP directly.
From the Web UI, activate Spoolman or FilaMan — downloaded automatically on first use.

---

## Backends

| | Spoolman | FilaMan |
|---|---|---|
| Port | 7912 | 8002 |
| Community | Large, established | Growing |
| UI | Functional | Modern |
| App | — | iOS & Android |
| RAM usage | ~150 MB | ~250 MB |
| Recommendation | Most users | App integration |

On Pi Zero 2W (512 MB RAM), only one backend runs at a time. On Pi 4 with 2+ GB RAM, parallel mode can be enabled in the Web UI.

FilaMan first login: admin@example.com / admin123 — change after first login.

---

## Web UI

| Tab | Features |
|---|---|
| **Backend** | Switch Spoolman/FilaMan, status, logs, update check, parallel mode |
| **System** | RAM/SD/Temp/Uptime, Pi update, UI self-update, WiFi, reboot, shutdown |
| **Backup** | Generate, download, restore, auto-backup, danger zone |

---

## Part of SpoolmanScale

- SpoolmanScale: https://github.com/Niko11111/SpoolmanScale — ESP32 filament scale with NFC
- Ko-fi: https://ko-fi.com/formfollowsfunction — Support the project
- Discord: https://discord.gg/GzQzGa5pBG — Community
- MakerWorld: https://makerworld.com/de/@FormFollowsF — 3D printable enclosure

---

© 2026 Niko11111. All rights reserved.
