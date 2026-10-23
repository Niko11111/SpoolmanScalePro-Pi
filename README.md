# SpoolmanScale Pro

A Raspberry Pi as the filament server for your
[SpoolmanScale](https://github.com/Niko11111/SpoolmanScale). It runs one
inventory backend, [Spoolman](https://github.com/Donkie/Spoolman),
[FilaMan](https://filaman.app) or [BamBuddy](https://github.com/maziggy/bambuddy),
and switches between them from a web page. The scale is switched along with
it.

> **Status: 2.0 beta.** A rebuild of version 0.1, which stays on the `main`
> branch until 2.0 is released.

## What it does

- **One backend at a time**, started and stopped with Docker. Switching shows
  each step: stop the running backend, start the chosen one, wait until it
  answers, switch the scale. The data of each backend stays where it is.
- **Takes the scale along.** Pair the scale once by its name or address; every
  switch then sets the scale to the same backend through the scale's own web
  interface. The page shows whether the scale reached it and whether it
  points at this Pi.
- **The Pi at a glance:** RAM, compressed swap, SD card, CPU temperature,
  uptime and clock. A Pi has no battery-backed clock; when it is off, the
  page sets it from the browser's time.
- **Protected** by a user name and password from the first visit on, which
  password managers can store. Running without a password is possible
  after a clear warning, for networks you trust.
- **Works without internet** once the backends are downloaded, for example as
  a hotspot of its own (see below).
- English and German.

## Requirements

- Raspberry Pi 3B or newer, 64-bit **Raspberry Pi OS Lite** (Bookworm or Trixie)
- A SpoolmanScale with firmware 0.7.0 or newer for the switching
- About 3.5 GB free on the SD card for all three backends (16 GB card or larger)

One backend at a time fits in 1 GB of RAM. Measured right after the first
start on 64-bit ARM: Spoolman about 100 MB, BamBuddy about 190 MB, FilaMan
about 370 MB.

## Install

On the Pi, with internet:

```bash
git clone https://github.com/Niko11111/SpoolmanScalePro-Pi.git
cd SpoolmanScalePro-Pi
sudo scripts/install.sh --pull-all
```

`--pull-all` downloads all three backends right away, so each one can later
start without internet. Then open `http://<hostname>.local` and create the
login.

To update, `git pull` and run `sudo scripts/install.sh` again. Your data is
not touched.

## Pair the scale

On the **Scale** tab, enter the scale's name or address. On the scale itself,
once:

1. Turn on *Settings > System > Web interface > Settings*. This lets the Pi
   switch the scale's backend.
2. Choose each backend once and enter the Pi as its server, with the port
   from the Scale tab (Spoolman 7912, FilaMan 8002, BamBuddy 8000).
3. Register the scale in FilaMan, and enter a BamBuddy API key on the scale,
   while that backend is active.

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
