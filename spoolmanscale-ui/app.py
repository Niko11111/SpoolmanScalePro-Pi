#!/usr/bin/env python3
"""
SpoolmanScale Pro — Setup UI
Flask backend for Pi management interface
"""

import os
import json
import subprocess
import shutil
import zipfile
import hashlib
import datetime
import glob
import psutil
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for

app = Flask(__name__)

# Paths
BASE_DIR = Path("/data")
COMPOSE_SPOOLMAN = BASE_DIR / "compose-spoolman.yml"
COMPOSE_FILAMAN  = BASE_DIR / "compose-filaman.yml"
MARKER_FILE      = BASE_DIR / ".active-backend"
SWITCH_SCRIPT    = BASE_DIR / "switch-backend.sh"
BACKUP_DIR       = BASE_DIR / "backups"
SPOOLMAN_DATA    = BASE_DIR / "spoolman-data"
FILAMAN_DATA     = BASE_DIR / "filaman-data"

BACKUP_DIR.mkdir(exist_ok=True)
BACKUP_KEEP = 7

# Links
LINKS = [
    {"name": "Ko-fi",       "url": "https://ko-fi.com/formfollowsfunction",         "icon": "♥"},
    {"name": "GitHub",      "url": "https://github.com/Niko11111/SpoolmanScale",    "icon": "⌥"},
    {"name": "Discord",     "url": "https://discord.gg/GzQzGa5pBG",                "icon": "◈"},
    {"name": "MakerWorld",  "url": "https://makerworld.com/de/@FormFollowsF",       "icon": "◉"},
]

UI_VERSION = "v0.1.0"

# ── Helpers ──────────────────────────────────────────────────────────────────

def run(cmd, timeout=120):
    """Run a shell command, return (success, output)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode == 0, (result.stdout + result.stderr).strip()
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)

def host(cmd, timeout=120):
    """Run command on the host via nsenter."""
    return run(f"nsenter -t 1 -m -u -i -n -p -- sh -c '{cmd}'", timeout=timeout)

def get_active_backend():
    if MARKER_FILE.exists():
        return MARKER_FILE.read_text().strip()
    return "none"

def get_container_status(name):
    ok, out = run(f"docker inspect --format='{{{{.State.Status}}}}' {name} 2>/dev/null")
    if ok and out:
        return out.strip("'")
    return "not installed"

def get_container_uptime(name):
    ok, out = run(
        f"docker inspect --format='{{{{.State.StartedAt}}}}' {name} 2>/dev/null"
    )
    if ok and out and out != "<no value>":
        try:
            started = datetime.datetime.fromisoformat(out.strip("'").replace("Z", "+00:00"))
            now = datetime.datetime.now(datetime.timezone.utc)
            delta = now - started
            h, m = divmod(int(delta.total_seconds()) // 60, 60)
            d, h = divmod(h, 24)
            if d:   return f"{d}d {h}h"
            if h:   return f"{h}h {m}m"
            return f"{m}m"
        except Exception:
            pass
    return "—"

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def cleanup_old_backups():
    files = sorted(BACKUP_DIR.glob("*.zip"), key=lambda p: p.stat().st_mtime)
    while len(files) > BACKUP_KEEP:
        files.pop(0).unlink(missing_ok=True)

@app.route("/api/welcome/dismissed")
def api_welcome_get():
    return jsonify({"dismissed": (BASE_DIR / ".welcome-dismissed").exists()})

@app.route("/api/welcome/dismiss", methods=["POST"])
def api_welcome_dismiss():
    (BASE_DIR / ".welcome-dismissed").touch()
    return jsonify({"ok": True})

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    response = render_template("index.html", links=LINKS, ui_version=UI_VERSION)
    from flask import make_response
    resp = make_response(response)
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp

# ── API: Status ───────────────────────────────────────────────────────────────

@app.route("/api/status")
def api_status():
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    cpu_temp = None
    try:
        temps = psutil.sensors_temperatures()
        if "cpu_thermal" in temps:
            cpu_temp = round(temps["cpu_thermal"][0].current, 1)
    except Exception:
        pass

    boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
    uptime_sec = (datetime.datetime.now() - boot_time).total_seconds()
    h, r = divmod(int(uptime_sec), 3600)
    m = r // 60
    d, h = divmod(h, 24)
    if d:   uptime_str = f"{d}d {h}h {m}m"
    elif h: uptime_str = f"{h}h {m}m"
    else:   uptime_str = f"{m}m"

    active = get_active_backend()
    spoolman_status = get_container_status("spoolman")
    filaman_status  = get_container_status("filaman")

    return jsonify({
        "backend": {
            "active":          active,
            "spoolman_status": spoolman_status,
            "spoolman_uptime": get_container_uptime("spoolman") if spoolman_status == "running" else "—",
            "spoolman_port":   7912,
            "filaman_status":  filaman_status,
            "filaman_uptime":  get_container_uptime("filaman") if filaman_status == "running" else "—",
            "filaman_port":    8002,
        },
        "system": {
            "ram_total_mb":   round(vm.total / 1024 / 1024),
            "ram_used_mb":    round(vm.used  / 1024 / 1024),
            "ram_pct":        vm.percent,
            "disk_total_gb":  round(disk.total / 1024 / 1024 / 1024, 1),
            "disk_used_gb":   round(disk.used  / 1024 / 1024 / 1024, 1),
            "disk_pct":       round(disk.percent, 1),
            "cpu_temp":       cpu_temp,
            "uptime":         uptime_str,
        },
    })

# ── API: Backend switch ───────────────────────────────────────────────────────

@app.route("/api/backend/switch", methods=["POST"])
def api_switch():
    data    = request.get_json(force=True)
    backend = data.get("backend", "")
    if backend not in ("spoolman", "filaman", "off"):
        return jsonify({"ok": False, "msg": "Invalid backend"}), 400
    ok, out = run(f"{SWITCH_SCRIPT} {backend}", timeout=300)
    return jsonify({"ok": ok, "msg": out})

@app.route("/api/backend/update", methods=["POST"])
def api_backend_update():
    active = get_active_backend()
    if active == "none":
        return jsonify({"ok": False, "msg": "No backend active"})
    compose = str(COMPOSE_SPOOLMAN if active == "spoolman" else COMPOSE_FILAMAN)
    ok, out = run(
        f"docker compose -f {compose} pull && docker compose -f {compose} up -d",
        timeout=300
    )
    return jsonify({"ok": ok, "msg": out})

@app.route("/api/backend/check-update")
def api_backend_check_update():
    active = get_active_backend()
    if active == "none":
        return jsonify({"ok": False, "update_available": False, "msg": "No backend active"})

    image = "ghcr.io/donkie/spoolman:latest" if active == "spoolman" else "ghcr.io/fire-devils/filaman-system:latest"

    # Lokalen Image-Digest holen
    ok_local, local_digest = run(f"docker inspect --format='{{{{index .RepoDigests 0}}}}' {image} 2>/dev/null")

    # Remote-Digest holen (ohne zu pullen)
    ok_remote, remote_digest = run(
        f"docker manifest inspect {image} 2>/dev/null | python3 -c \"import sys,json; m=json.load(sys.stdin); print(m.get('config',{{}}).get('digest',''))\" 2>/dev/null",
        timeout=30
    )

    if not ok_local or not local_digest or local_digest == "<no value>":
        return jsonify({"ok": True, "update_available": True, "msg": "Not installed yet"})

    update_available = ok_remote and remote_digest and remote_digest not in local_digest
    return jsonify({
        "ok": True,
        "update_available": update_available,
        "msg": "Update available" if update_available else "Up to date"
    })

@app.route("/api/backend/logs")
def api_backend_logs():
    active = get_active_backend()
    if active == "none":
        return jsonify({"ok": False, "lines": []})
    name = "spoolman" if active == "spoolman" else "filaman"
    ok, out = run(f"docker logs --tail=60 {name} 2>&1")
    lines = out.splitlines() if ok else []
    return jsonify({"ok": ok, "lines": lines})

# ── API: System ───────────────────────────────────────────────────────────────

GITHUB_REPO = "Niko11111/SpoolmanScalePro-Pi"
IMAGE_NAME   = "ghcr.io/niko11111/spoolmanscale-pro-ui"

@app.route("/api/system/check-ui-update")
def api_check_ui_update():
    import urllib.request
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(url, headers={"User-Agent": "SpoolmanScalePro"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        latest = data.get("tag_name", "")
        current = UI_VERSION
        update_available = latest and latest != current
        return jsonify({
            "ok": True,
            "current": current,
            "latest": latest,
            "update_available": update_available,
            "msg": f"Update available: {latest}" if update_available else f"Up to date ({current})"
        })
    except Exception as e:
        return jsonify({"ok": False, "update_available": False, "msg": str(e)})

@app.route("/api/system/update-ui", methods=["POST"])
def api_update_ui():
    ok, out = run(
        f"docker pull {IMAGE_NAME}:latest && docker compose -f /data/docker-compose.yml up -d",
        timeout=300
    )
    return jsonify({"ok": ok, "msg": out})

@app.route("/api/system/update", methods=["POST"])
def api_system_update():
    ok, out = host("apt-get update -qq && apt-get upgrade -y", timeout=600)
    return jsonify({"ok": ok, "msg": out or "Done."})

@app.route("/api/system/reboot", methods=["POST"])
def api_system_reboot():
    run("nsenter -t 1 -m -u -i -n -p -- reboot", timeout=5)
    return jsonify({"ok": True, "msg": "Rebooting..."})

@app.route("/api/system/shutdown", methods=["POST"])
def api_system_shutdown():
    run("nsenter -t 1 -m -u -i -n -p -- shutdown -h now", timeout=5)
    return jsonify({"ok": True, "msg": "Shutting down..."})

@app.route("/api/system/wifi/scan")
def api_system_wifi_scan():
    ok, out = run("iwlist wlan0 scan 2>&1", timeout=15)
    networks = []
    if ok or out:
        current = {}
        for line in out.splitlines():
            line = line.strip()
            if "ESSID:" in line:
                ssid = line.split('ESSID:"')[-1].rstrip('"')
                if ssid and ssid not in [n["ssid"] for n in networks]:
                    networks.append({"ssid": ssid})
            elif "Quality=" in line:
                try:
                    q = line.split("Quality=")[1].split(" ")[0]
                    num, den = q.split("/")
                    pct = int(int(num) / int(den) * 100)
                    if networks:
                        networks[-1]["quality"] = pct
                except Exception:
                    pass
    networks.sort(key=lambda n: n.get("quality", 0), reverse=True)
    return jsonify({"ok": True, "networks": networks})

@app.route("/api/system/wifi", methods=["POST"])
def api_system_wifi():
    data = request.get_json(force=True)
    ssid = data.get("ssid", "").strip()
    pw   = data.get("password", "").strip()
    if not ssid:
        return jsonify({"ok": False, "msg": "SSID required"})
    # Write wpa_supplicant entry
    entry = f'\nnetwork={{\n    ssid="{ssid}"\n    psk="{pw}"\n}}\n'
    try:
        with open("/etc/wpa_supplicant/wpa_supplicant.conf", "a") as f:
            f.write(entry)
        run("sudo wpa_cli -i wlan0 reconfigure")
        return jsonify({"ok": True, "msg": "WiFi updated. Reconnecting..."})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

# ── API: Backup ───────────────────────────────────────────────────────────────

@app.route("/api/backup/list")
def api_backup_list():
    files = sorted(BACKUP_DIR.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    result = []
    for f in files:
        result.append({
            "name":    f.name,
            "size_mb": round(f.stat().st_size / 1024 / 1024, 2),
            "date":    datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
        })
    return jsonify(result)

@app.route("/api/backup/generate", methods=["POST"])
def api_backup_generate():
    active  = get_active_backend()
    ts      = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    zipname = BACKUP_DIR / f"{active}_backup_{ts}.zip"
    meta    = {
        "backend":    active,
        "created_at": ts,
        "ui_version": UI_VERSION,
    }
    try:
        # Stop active container before backup for DB consistency
        if active in ("spoolman", "filaman"):
            run(f"docker stop {active}", timeout=30)

        with zipfile.ZipFile(zipname, "w", zipfile.ZIP_DEFLATED) as zf:
            # Metadata
            zf.writestr("backup_meta.json", json.dumps(meta, indent=2))
            # Spoolman data
            if SPOOLMAN_DATA.exists():
                for fp in SPOOLMAN_DATA.rglob("*"):
                    if fp.is_file():
                        zf.write(fp, fp.relative_to(BASE_DIR))
            # FilaMan data
            if FILAMAN_DATA.exists():
                for fp in FILAMAN_DATA.rglob("*"):
                    if fp.is_file():
                        zf.write(fp, fp.relative_to(BASE_DIR))
            # Compose + switch script
            for f in [COMPOSE_SPOOLMAN, COMPOSE_FILAMAN, SWITCH_SCRIPT]:
                if f.exists():
                    zf.write(f, f.name)

        # Checksum
        checksum = sha256_file(zipname)
        (BACKUP_DIR / f"{zipname.name}.sha256").write_text(checksum)

        return jsonify({"ok": True, "name": zipname.name, "checksum": checksum})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})
    finally:
        # Always restart active container
        if active in ("spoolman", "filaman"):
            run(f"docker start {active}", timeout=30)
        cleanup_old_backups()

@app.route("/api/backup/download/<filename>")
def api_backup_download(filename):
    path = BACKUP_DIR / filename
    if not path.exists() or not path.suffix == ".zip":
        return jsonify({"ok": False, "msg": "Not found"}), 404
    return send_file(path, as_attachment=True)

@app.route("/api/backup/delete/<filename>", methods=["DELETE"])
def api_backup_delete(filename):
    path = BACKUP_DIR / filename
    sha_path = BACKUP_DIR / f"{filename}.sha256"
    if not path.exists():
        return jsonify({"ok": False, "msg": "Not found"}), 404
    path.unlink(missing_ok=True)
    sha_path.unlink(missing_ok=True)
    return jsonify({"ok": True})

@app.route("/api/backup/restore", methods=["POST"])
def api_backup_restore():
    if "file" not in request.files:
        return jsonify({"ok": False, "msg": "No file"}), 400
    f       = request.files["file"]
    tmp_zip = BACKUP_DIR / f"_restore_tmp.zip"
    tmp_dir = BACKUP_DIR / "_restore_tmp"

    try:
        f.save(tmp_zip)

        # Validate zip
        if not zipfile.is_zipfile(tmp_zip):
            return jsonify({"ok": False, "msg": "Invalid zip file"})

        # Stop active backend
        active = get_active_backend()
        if active in ("spoolman", "filaman"):
            run(f"docker stop {active}", timeout=30)

        # Extract to temp
        tmp_dir.mkdir(exist_ok=True)
        with zipfile.ZipFile(tmp_zip) as zf:
            zf.extractall(tmp_dir)

        # Validate metadata
        meta_path = tmp_dir / "backup_meta.json"
        if not meta_path.exists():
            return jsonify({"ok": False, "msg": "Invalid backup: missing metadata"})

        # Rename old data dirs as fallback
        for d in [SPOOLMAN_DATA, FILAMAN_DATA]:
            if d.exists():
                d.rename(str(d) + "_pre_restore")

        # Copy new data
        for src in (tmp_dir / "spoolman-data", tmp_dir / "filaman-data"):
            if src.exists():
                shutil.copytree(src, BASE_DIR / src.name)

        # Restart backend
        if active in ("spoolman", "filaman"):
            ok, out = run(f"docker start {active}", timeout=30)
            if not ok:
                # Rollback
                for d in [SPOOLMAN_DATA, FILAMAN_DATA]:
                    pre = Path(str(d) + "_pre_restore")
                    if pre.exists():
                        if d.exists():
                            shutil.rmtree(d)
                        pre.rename(d)
                run(f"docker start {active}", timeout=30)
                return jsonify({"ok": False, "msg": f"Container failed to start after restore. Rolled back.\n{out}"})

        # Cleanup pre-restore fallback
        for d in [SPOOLMAN_DATA, FILAMAN_DATA]:
            pre = Path(str(d) + "_pre_restore")
            if pre.exists():
                shutil.rmtree(pre)

        return jsonify({"ok": True, "msg": "Restore successful."})

    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})
    finally:
        tmp_zip.unlink(missing_ok=True)
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
