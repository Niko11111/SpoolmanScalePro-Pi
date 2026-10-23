"""SpoolmanScale Pro: runs one filament inventory backend on a Raspberry Pi
(Spoolman, FilaMan or BamBuddy) and keeps a SpoolmanScale pointed at it.

The package is a small Flask service. It never runs as root and never runs a
shell: Docker is driven through `docker compose` with argument lists
(docker_compose.py), and the few things that need root go through a helper
with a fixed list of verbs (host_actions.py).
"""
