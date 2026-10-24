import re

from spoolmanscale_pro.backends import BACKEND_KEYS, BACKENDS, backend_by_key
from spoolmanscale_pro.paths import COMPOSE_FILE


def _compose_services() -> dict[str, list[str]]:
    """Service name -> profiles, read from the compose file's text. Enough
    for a file this repository writes itself; no YAML library needed."""
    services, current, inside = {}, None, False
    for line in COMPOSE_FILE.read_text().splitlines():
        if line.startswith("services:"):
            inside = True
            continue
        if inside and re.match(r"^\S", line):
            inside = False
        if not inside:
            continue
        name = re.match(r"^  ([a-z0-9-]+):\s*$", line)
        if name:
            current = name.group(1)
            services[current] = []
        profiles = re.match(r'^    profiles: \[(.*)\]', line)
        if profiles and current:
            services[current] = [p.strip().strip('"') for p in profiles.group(1).split(",")]
    return services


def test_every_backend_is_a_compose_service_with_its_own_profile():
    services = _compose_services()
    assert set(services) == set(BACKEND_KEYS)
    for key in BACKEND_KEYS:
        assert services[key] == [key]


def test_scale_modes_match_the_firmware_enum():
    # BackendMode in the firmware's services/backend.h
    assert {b.key: b.scale_mode for b in BACKENDS} == {"spoolman": 0, "filaman": 1, "bambuddy": 2}


def test_ports_are_unique_and_published_in_compose():
    text = COMPOSE_FILE.read_text()
    ports = [b.port for b in BACKENDS]
    assert len(set(ports)) == len(ports)
    for port in ports:
        assert f'"{port}:' in text


def test_backend_by_key():
    assert backend_by_key("filaman").label == "FilaMan"
    assert backend_by_key("../etc") is None


def test_compose_pulls_from_the_registry_image_with_its_version_variable():
    from spoolmanscale_pro.backend_updates import compose_default_version
    text = COMPOSE_FILE.read_text()
    for b in BACKENDS:
        assert f"image: ghcr.io/{b.image}:${{{b.version_env}:-" in text, b.key
        assert compose_default_version(text, b) is not None, b.key
