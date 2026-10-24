# Changelog

One section per version, newest first. VERSION names the current one;
scripts/check.sh fails when it has no section here.

## 2.0.0-beta.22

- The browser tab shows the same icon as SpoolmanScale's own web
  interface, a transparent PNG: the JPEG logo it used before drew a black
  box around the spool on a dark tab strip. Saved to the home screen, the
  page gets the matching 180x180 icon.
- Each backend tile has an Info button: what the backend is, a link to its
  project page, and what this Pi means for it. On a Pi smaller than a Pi 4
  BamBuddy's says which of its features need a Pi 4 (the live camera view
  of X1, H2 and P2, timelapses) and which need a service of their own
  (slicing on the server, Obico failure detection).
- A backend installed since the last search for updates is looked at
  within ten minutes rather than with the next round up to six hours
  later, so BamBuddy's switch to daily builds shows soon after BamBuddy is
  first started.
- The Demo page writes the test inventory into any running backend: 21
  spools from 7 manufacturers, the same in Spoolman, FilaMan and BamBuddy,
  with each backend's own fields (vendor, filament and spool in Spoolman;
  manufacturer, colour, filament and spool in FilaMan; the spool alone in
  BamBuddy). Only what a backend lacks is created, so writing twice adds
  nothing.

## 2.0.0-beta.21

- The service looks for updates on its own, every 6 hours, for itself and
  every installed backend (a Pi without internet tries again after an
  hour). It only looks, nothing is installed by itself. What it finds shows
  as a number on the Updates tab and as a link on the backend's tile; the
  Updates page opens with the last result and when it was found. A switch
  on that page turns the search off.
- BamBuddy can run its daily builds: "Switch to daily builds" on its
  Updates card backs it up and installs the build the daily tag points to,
  pinned by its digest, so the Pi stays on exactly that build. A newer
  daily build is found by the search and installed like an update. Back to
  the releases: a release newer than the daily build is offered as a normal
  update, or at once with the backup from before the switch, which is kept
  apart from the update backups so it is never pruned away.

## 2.0.0-beta.20

- The page header shows the Pi's IP address next to the version, the
  cable's before the WLAN's (in its own WLAN 192.168.50.1), unless the page
  was opened by that address anyway.
- Each backend tile shows the version it runs and how many spools it holds
  (archived ones left out). The count is asked for in the background and
  kept for a minute, so a slow backend never holds up the overview; FilaMan
  is asked as the admin this Pi made, BamBuddy only while its login is off.

## 2.0.0-beta.19

- The overview no longer reports Docker as not answering while a backup or
  a restore runs: the throwaway container that packs the data could vanish
  while Docker listed the containers, and the list is now asked for again.

## 2.0.0-beta.18

From the first install on a Pi 3 B (Raspberry Pi OS Trixie):

- The installer creates the releases folder on a first install (beta.17
  stopped there), shows one line per backend download instead of Docker's
  progress bars, and reads whether the WLAN is blocked from the system: the
  rfkill tool is not part of Raspberry Pi OS Lite.
- The logs of OS updates, self-updates and Tailscale no longer show the
  internal end marker.
- More room between text, notices, buttons and log boxes on the System
  page.
- The scale's weight on the overview shows its unit once ("0 g", not
  "0 g g").
- The warning about a power supply that was too low since the restart
  can be marked as seen: it stays quiet until the next restart. A voltage
  that is too low right now is always shown.

## 2.0.0-beta.17

- The installer accepts every Pi this runs on: it asked for about 1 GB of
  RAM, which refused a Pi Zero 2 W and could refuse a Pi 3 whose GPU takes
  more; it now needs 380 MB, one backend at a time.
- Installing the same version again builds it next to the running one and
  swaps it in, instead of deleting the files the service runs from.
- The installer warns when the WLAN is blocked (no WLAN country set), adds
  libnss-mdns so the scale's .local name resolves, and never stops at a
  package question hidden behind its log.
- The Network page takes a WLAN by hand (a hidden network, or any network
  while the Pi runs its own WLAN and cannot search). A search that the Pi
  refuses shows the networks it saw last.
- Checking an address says "checking failed" when arping cannot run,
  instead of "taken".
- When the active backend has stopped (a switch away from it that failed,
  or a crash), its tile offers Activate again.
- Without a login on the Pi, the scale page through the Pi asks for the
  scale's PIN in the browser instead of adding the stored one.
- The setup WLAN's wait at boot no longer holds up the start of the Pi.

## 2.0.0-beta.16

- The Network page shows the Pi's IP address, whether it comes from the
  router or is fixed, the router and the MAC address (to copy, for a
  reservation in the router, which is the recommended way).
- One button keeps the current address; another address can be checked
  first (same network, not the router's, and no device answering for it)
  and then used. If the Pi cannot reach the router with the new address
  within 30 seconds, it goes back to an address from the router by itself.
  And back to automatic with one button.
- The installer adds iputils-arping for the check.

## 2.0.0-beta.15

- Several backends at once, as far as the Pi allows. It is recognised by its
  model and RAM: a Pi Zero 2 W runs one backend at a time (switching only,
  Spoolman recommended, FilaMan and BamBuddy with a warning that they are
  slow there); a Pi 3 runs two at once after a warning with the numbers; a
  Pi 4 or 5 with 2 GB and more runs all three. "Several at once" follows the
  Pi by default and can be switched on or off on the System page.
- With several running, each tile starts and stops its backend and one of
  them is "for the scale". Each running tile shows the RAM it uses. A card
  shows the addresses the backends use to reach each other (BamBuddy with
  Spoolman as inventory, FilaMan's BamBuddy plugin).
- On a Pi Zero and a Pi 3 each backend gets a RAM limit of twice its typical
  use, at most what the Pi can spare; swapping stays allowed, so one that
  grows gets slow instead of freezing the Pi.
- The daily backup covers every running backend.

## 2.0.0-beta.14

- Remote access with Tailscale from the System page: install it (from
  Tailscale's signed Debian repository, not its install script), connect
  with the login link Tailscale gives, disconnect. Installing and
  connecting show their log live. The Pi keeps its own name resolution, and
  the page still asks for its login over Tailscale.

## 2.0.0-beta.13

- A setup assistant opens after the first login: pick a backend (with the
  switch's progress), find and pair the scale and enter the Pi on it, done.
  It can be skipped and opened again from the System page; it uses the same
  tiles and cards as the other pages.

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
