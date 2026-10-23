# Changelog

One section per version, newest first. VERSION names the current one;
scripts/check.sh fails when it has no section here.

## 2.0.0-beta.12

- The installer checks the Pi first (64-bit, RAM, free space, internet),
  numbers its steps, writes everything to
  /var/log/spoolmanscale-pro/install.log, says which step failed if one
  does, and ends with the address and what to do next.
- It also sets up what a Pi running unattended needs: the hardware watchdog
  (a hung Pi restarts by itself), a capped system log, Debian's security
  updates every day without automatic restarts, and SSH without root login;
  passwords for SSH are switched off once a key is on the Pi.
- The overview shows the power supply: too low now, too low since the last
  restart, or fine, with what to do about it.
- A backend update removes the image it replaced (up to 1.8 GB), and a
  failed one the image it brought.
- The OS update waits for the daily security updates instead of failing on
  apt's lock.

## 2.0.0-beta.11

- SpoolmanScale Pro updates itself from its GitHub releases, on the
  Updates page: newer releases with their notes, install, and back to the
  version installed before. The download is checked against the release's
  checksum and installed by the release's own install.sh, as a systemd unit
  of its own, since it restarts the service; the page reloads once the new
  version answers. A Pi running a beta is offered betas.
- A tag v<VERSION> builds the release archive (everything Git tracks
  except tests, CI and the house-rule checks) and publishes the GitHub
  release with this file's section as its notes; betas become
  pre-releases. scripts/build_release.sh builds the same archive locally.

## 2.0.0-beta.10

- A daily backup of the active backend, on by default, from a chosen hour
  (03:00 unless set otherwise on the Backup page). A Pi that is off at that
  hour catches up later the same day; a restart of the service does not
  make a second one.
- Automatic backups are marked as such and kept apart: the newest 7 of
  them, and as before the newest 10 of all others, so a week of automatic
  ones never pushes out a backup made by hand or before an update.

## 2.0.0-beta.9

- The paired scale's own web interface shows on the new Scale tab, served
  by this Pi on port 8081, so one address is enough for everything. The
  former Scale tab is now called Pairing.
- The proxy lets only visitors logged in to this Pi through, refuses
  changing requests from other pages, sends the scale its own address as
  Host and its web password if one is stored. The scale's protection
  against foreign frames stays, with this Pi's page as the one allowed.

## 2.0.0-beta.8

- FilaMan gets an admin login when this Pi starts it. FilaMan creates its
  first admin only from ADMIN_EMAIL and ADMIN_PASSWORD and has no page to
  register one, so until now a FilaMan started here had no user at all.
  The login is made once with a random password, kept in the data
  directory (0600) and shown under "Login" on FilaMan's tile.
- The Scale page registers the scale in FilaMan from here: the Pi logs in
  to FilaMan, makes an API key and a device, and the scale registers with
  the device code and gets the key. With a FilaMan password changed by
  hand, the page asks for it once and does not keep it.
- A BamBuddy API key (only needed when BamBuddy's login is on) is pasted
  on the Scale page and sent to the scale, instead of typed on its screen.

## 2.0.0-beta.7

- The Scale page finds SpoolmanScales on the network by mDNS (the scale
  announces model, firmware, id and backend) and pairs one with a tap,
  instead of typing its address.
- One button enters this Pi on the scale as the server of all three
  backends: backend by backend the scale is switched, the address set
  (<name>.local:<port>, or the IP if chosen) and the scale's own test
  awaited, and it ends on the backend that runs here. The manual step of
  typing three addresses on the device is gone.
- The installer adds avahi-utils for the search.

## 2.0.0-beta.6

- Raspberry Pi OS updates on the System page, as in TheRentalScale: a
  search that installs nothing and lists every package with its old and new
  version (and any that would be removed), then the install with apt's log
  live on the page, and a restart button when a new kernel needs one.
- The upgrade runs as a systemd unit of its own, so a restart of the
  service cannot cut dpkg off halfway; the page picks a running upgrade up
  again after a reload. Each upgrade first finishes one a power cut left
  open (dpkg --configure -a).
- Jobs can show their output live under their progress.

## 2.0.0-beta.5

- Updates page: for each backend, the version it runs and the one this
  release was tested with, a search for newer versions on ghcr.io, the
  release notes from GitHub for everything in between, and installing one.
- Installing makes a "before update" backup first, downloads the image while
  the backend keeps running, then restarts it with the new version. When it
  does not come up, the old version and the backup go back by themselves:
  a database a newer FilaMan migrated cannot be read by the older one.
- Only newer versions are offered, never older ones. Pre-releases can be
  offered with a switch, where a backend publishes them with a version
  number.
- The chosen versions live in the data directory and survive updates of
  SpoolmanScale Pro; compose/docker-compose.yml keeps the tested default.
- FilaMan's own backup folder is left out of our archives, like
  Spoolman's and BamBuddy's.

## 2.0.0-beta.4

- Network page: the Pi's name on the network (<name>.local), the WLAN it is
  in, a search for networks and joining one, and the Pi's own WLAN
  (hotspot) with name, password and channel 1, 6 or 11.
- Joining a WLAN that does not work within 45 seconds puts the Pi back in
  the network it was in. The hotspot can only be switched off while another
  network is there to go back to.
- When neither a WLAN nor a cable connects within 90 seconds of booting, the
  Pi opens the setup WLAN "SpoolmanScale-Pro-Setup" (password
  "spoolmanscale") and is reachable at 192.168.50.1. Only at boot, never
  while running.
- The installer renames a Pi still called "raspberrypi" to
  "spoolmanscale-pro", so it answers as spoolmanscale-pro.local; the scale
  keeps spoolmanscale.local.
- WLAN passwords reach the root helper on stdin, never as arguments or in a
  log. scripts/setup-hotspot.sh now uses the same helper.

## 2.0.0-beta.3

- The login has a user name next to the password, chosen on the first
  visit (suggested: admin), so password managers store and fill it. Name
  and password can be changed under System.
- The password can be switched off, on the first visit or later under
  System, after a warning that anyone on the network can then control the
  Pi. Requests from foreign pages stay blocked either way.
- The project links of the scale's web interface (GitHub, Ko-fi, Discord,
  MakerWorld) close every page.

## 2.0.0-beta.2

- Backups per backend: the backend is stopped for the few seconds its data
  are packed, then started again. Download, delete, restore from the list or
  from a file. A file is checked before anything is replaced (its backend,
  only plain files and folders, size limits). Before each restore the data
  it replaces are saved as a backup of their own, and put back if the
  restore fails. The newest 10 per backend are kept; Spoolman's and
  BamBuddy's own backup folders are left out of the archive.
- Demo mode for trade fairs, off unless enabled on the Pi itself: a demo
  state per backend and one button that resets every saved backend to it,
  the active one first, then waits until the scale has reached it again. It
  restores files, so FilaMan's device token and BamBuddy's API key survive a
  reset.
- The progress of a job is shown on every page that starts one.

## 2.0.0-beta.1

A rebuild from scratch. Version 0.1 was a Flask app in a privileged Docker
container; it stays available on the `main` branch until 2.0 is released.

- Runs Spoolman 0.27.0, FilaMan 1.4.3 or BamBuddy 1.2.5.7, one at a time,
  from one compose file with a profile per backend. Images are pinned.
- Switching a backend is a background job with visible steps: stop the
  running one, start the chosen one, wait until its health route answers,
  then switch the paired SpoolmanScale over through its web interface.
- The scale is paired once by name or address (and its web password, if it
  has one). The overview shows which backend the scale uses, whether it
  reached it, and whether it points at this Pi.
- A password protects the page from the first visit on; changing requests
  need a header a foreign page cannot send.
- The service runs as its own user under systemd, not in a container. The
  few root actions (restart, shut down, set the clock) go through a helper
  with a fixed list of verbs.
- RAM, swap, SD card, CPU temperature, uptime and clock on the overview;
  a clock that is more than two minutes off can be set from the browser.
- English and German.
