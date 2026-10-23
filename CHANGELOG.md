# Changelog

One section per version, newest first. VERSION names the current one;
scripts/check.sh fails when it has no section here.

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
