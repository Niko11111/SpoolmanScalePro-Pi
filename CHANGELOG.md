# Changelog

One section per version, newest first. VERSION names the current one;
scripts/check.sh fails when it has no section here.

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
