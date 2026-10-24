# SpoolmanScale Pro

A Raspberry Pi as the filament server for your
[SpoolmanScale](https://github.com/Niko11111/SpoolmanScale). It runs one
inventory backend, [Spoolman](https://github.com/Donkie/Spoolman),
[FilaMan](https://filaman.app) or [BamBuddy](https://github.com/maziggy/bambuddy),
and switches between them from a web page. The scale is switched along with
it.

> **Status: 0.2 beta.** A complete rewrite of version 0.1, which stays on
> the `main` branch until 0.2.0 is released.

## What it does

- **One backend or several**, as far as the Pi allows: a Pi Zero 2 W one at a
  time, a Pi 3 two after a warning, a Pi 4 or 5 all three. Switching shows
  each step: stop the running backend, start the chosen one, wait until it
  answers, switch the scale. The data of each backend stays where it is.
- **Takes the scale along.** Pair the scale once by its name or address; every
  switch then sets the scale to the same backend through the scale's own web
  interface. The page shows whether the scale reached it and whether it
  points at this Pi.
- **One address for everything:** the scale's own web interface shows on
  the Pi's page too, passed through by the Pi on port 8081.
- **The Pi at a glance:** RAM, compressed swap, SD card, CPU temperature,
  uptime and clock. A Pi has no battery-backed clock; when it is off, the
  page sets it from the browser's time.
- **Protected** by a user name and password from the first visit on, which
  password managers can store. Running without a password is possible
  after a clear warning, for networks you trust.
- **Backups** per backend, by hand and once a day by themselves, to
  download, restore or bring back from a file.
- **Backend updates** with the release notes of every version in between,
  a backup before each one, and the old version back by itself when the
  new one does not start.
- **Raspberry Pi OS updates** from the page: see what would change first,
  then install with the log live.
- **Remote access** through Tailscale, installed and connected from the
  page.
- **Works without internet** once the backends are downloaded, for example as
  a hotspot of its own (see below).
- English and German.

## Requirements

- Raspberry Pi Zero 2 W, 3, 4 or 5 with 64-bit **Raspberry Pi OS Lite**
  (Bookworm or Trixie); a Pi 4 or 5 with 2 GB for several backends at once
- A SpoolmanScale with firmware 0.7.0 or newer for the switching
- About 3.5 GB free on the SD card for all three backends (16 GB card or larger)

RAM in use, measured: Spoolman about 100 MB, BamBuddy 240 to 420 MB, FilaMan
about 480 MB (it starts four worker processes). A Pi Zero 2 W (512 MB) runs Spoolman well;
FilaMan and BamBuddy are slow there.

## Install

On the Pi, with internet:

```bash
git clone https://github.com/Niko11111/SpoolmanScalePro-Pi.git
cd SpoolmanScalePro-Pi
sudo scripts/install.sh --pull-all
```

`--pull-all` downloads all three backends right away, so each one can later
start without internet. The installer checks the Pi first, numbers its
steps and logs to `/var/log/spoolmanscale-pro/install.log`. It also turns
on the hardware watchdog, Debian's daily security updates and SSH without
root login (and without passwords once an SSH key is on the Pi). Then open `http://<hostname>.local` and create the
login.

Later versions install from the **Updates** page (or by `git pull` and
`sudo scripts/install.sh` again). Your data is not touched, and the version
before stays on the Pi to go back to.

## Pair the scale

1. On the scale, turn on *Settings > System > Web interface > Settings*.
   This is the one step on the device: it lets the Pi configure the scale.
2. On the **Scale** tab, search the network and pick the scale (or type its
   address), then press *Enter this Pi on the scale*: the Pi sets itself as
   the server of all three backends.
3. With FilaMan active, *Register the scale in FilaMan*. A BamBuddy API key,
   only needed when BamBuddy's login is on, is pasted there as well.

FilaMan's admin login, which the Pi creates when it first starts FilaMan,
is under *Login* on FilaMan's tile.

## Network

The **Network** page sets the Pi's name (it answers as `<name>.local`,
`spoolmanscale-pro.local` after the install), joins a WLAN, or opens the
Pi's own WLAN for places without one: a WPA2 network on 2.4 GHz (the scale
has no 5 GHz), with the Pi at `192.168.50.1`.

**No network at all?** When neither a WLAN nor a cable connects within 90
seconds of booting, the Pi opens the WLAN `SpoolmanScale-Pro-Setup`
(password `spoolmanscale`). Join it with a phone, open `http://192.168.50.1`
and choose a WLAN on the Network page.

The same from a terminal: `sudo scripts/setup-hotspot.sh --ssid NAME --channel 6`
(and `--remove`).

## How it is built

| Part | Where |
|---|---|
| Web service (Flask, served by waitress) | `spoolmanscale_pro/` |
| The backends, one compose profile each | `compose/docker-compose.yml` |
| Page (plain JavaScript, no build step) | `templates/`, `static/` |
| systemd unit, sudoers rule, root helper | `system/` |
| Install and hotspot | `scripts/` |

The service runs as its own user `spoolmanscale`, not as root and not in a
container. It drives Docker through `docker compose` with argument lists,
never through a shell. Restart, shutdown and setting the clock go through
`system/host-helper.sh`, which knows exactly those verbs; sudo allows the
service user that one file. The service user is in the `docker` group,
which amounts to root, so the page's password is what guards the Pi: choose
a real one.

Forgot the password? On the Pi: `sudo rm /var/lib/spoolmanscale-pro/auth.json`,
then reload the page and create the login again.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
SSPRO_DATA_DIR=$PWD/.devdata .venv/bin/python -m spoolmanscale_pro --port 8090
scripts/check.sh
```

Docker Desktop on a Mac with Apple silicon runs the same arm64 images as the
Pi. `scripts/check.sh` runs the house rules and the tests, and CI runs it on
every push.

## License

GPL-3.0, see [LICENSE](LICENSE). Part of the
[SpoolmanScale](https://github.com/Niko11111/SpoolmanScale) project.
