"""Writes the test inventory into a running backend, as a job from the Demo
page. What to create and how each body looks is decided in
inventory_import.py; here are the requests, one writer per backend.

  Spoolman  GET/POST /api/v1/vendor, /filament, /spool (open, no login)
  FilaMan   /api/v1/manufacturers, /colors, /filaments, /spools as its admin
            (filaman_admin.py); archived through POST /spools/{id}/status
  BamBuddy  GET/POST /api/v1/inventory/spools, then /spools/{id}/archive
            (open while BamBuddy's login is off, its default)

Every spool created is one line in the job's output.
"""

import json
import logging
import urllib.error
import urllib.request
from collections import Counter

from . import backend_secrets, health
from . import inventory_import as ii
from .backends import Backend
from .filaman_admin import FilamanAdmin, FilamanError
from .jobs import JobFailed, Progress

log = logging.getLogger(__name__)

REQUEST_TIMEOUT_S = 20
FILAMAN_PAGE_SIZE = 200


class _Json:
    """JSON over HTTP to a backend without a login."""

    def __init__(self, base_url: str):
        self.base_url = base_url

    def call(self, method: str, path: str, body: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            detail = e.read()[:300].decode("utf-8", "replace")
            raise JobFailed("import_refused", f"{method} {path}: HTTP {e.code} {detail}") from e
        except (urllib.error.URLError, OSError) as e:
            raise JobFailed("import_unreachable", f"{method} {path}: {e}") from e
        try:
            return json.loads(raw) if raw else {}
        except json.JSONDecodeError as e:
            raise JobFailed("import_refused", f"{path} gave no JSON") from e


def _spool_line(spool: dict) -> str:
    archived = " (archived)" if spool.get("archived") else ""
    return f"+ {spool['vendor']} {spool['material']} {spool['name']}, {spool['remaining_g']} g{archived}"


def _spoolman(base_url: str, inventory: dict, report) -> int:
    api = _Json(base_url + "/api/v1")
    vendors = {v["name"].lower(): v["id"] for v in api.call("GET", "/vendor")}
    for v in inventory["vendors"]:
        if v["name"].lower() not in vendors:
            vendors[v["name"].lower()] = api.call("POST", "/vendor", ii.spoolman_vendor(v))["id"]
    filaments = {ii.kind((f.get("vendor") or {}).get("name", ""), f["name"], f.get("material")): f["id"]
                 for f in api.call("GET", "/filament")}
    for s in ii.kinds(inventory["spools"]):
        if ii.kind_of(s) not in filaments:
            body = ii.spoolman_filament(s, vendors[s["vendor"].lower()])
            filaments[ii.kind_of(s)] = api.call("POST", "/filament", body)["id"]
    kind_by_id = {fid: k for k, fid in filaments.items()}
    have = Counter(kind_by_id.get(sp["filament"]["id"]) for sp in api.call("GET", "/spool?allow_archived=true"))
    missing = ii.missing_spools(inventory["spools"], have)
    for s in missing:
        api.call("POST", "/spool", ii.spoolman_spool(s, filaments[ii.kind_of(s)]))
        report(_spool_line(s))
    return len(missing)


def _filaman_all(admin: FilamanAdmin, path: str) -> list[dict]:
    """Every item of a paged FilaMan list."""
    items, page = [], 1
    sep = "&" if "?" in path else "?"
    while True:
        data = admin.request("GET", f"{path}{sep}page={page}&page_size={FILAMAN_PAGE_SIZE}")
        batch = data.get("items") or []
        items += batch
        if not batch or len(items) >= data.get("total", 0):
            return items
        page += 1


def _filaman_filaments(admin: FilamanAdmin, inventory: dict) -> dict:
    """Kind -> filament id, with the manufacturers, colours and filaments
    that were missing created."""
    makers = {m["name"].lower(): m["id"] for m in _filaman_all(admin, "/api/v1/manufacturers")}
    for v in inventory["vendors"]:
        if v["name"].lower() not in makers:
            makers[v["name"].lower()] = admin.request("POST", "/api/v1/manufacturers", ii.filaman_manufacturer(v))["id"]
    colors = {c["hex_code"].upper(): c["id"] for c in _filaman_all(admin, "/api/v1/colors")}
    filaments = {ii.kind((f.get("manufacturer") or {}).get("name", ""), f["designation"], f["material_type"]): f["id"]
                 for f in _filaman_all(admin, "/api/v1/filaments")}
    for s in ii.kinds(inventory["spools"]):
        if ii.kind_of(s) in filaments:
            continue
        color = ii.filaman_color(s)
        if color["hex_code"] not in colors:
            colors[color["hex_code"]] = admin.request("POST", "/api/v1/colors", color)["id"]
        body = ii.filaman_filament(s, makers[s["vendor"].lower()], colors[color["hex_code"]])
        filaments[ii.kind_of(s)] = admin.request("POST", "/api/v1/filaments", body)["id"]
    return filaments


def _filaman_write(admin: FilamanAdmin, inventory: dict, report) -> int:
    filaments = _filaman_filaments(admin, inventory)
    kind_by_id = {fid: k for k, fid in filaments.items()}
    spools = _filaman_all(admin, "/api/v1/spools?include_archived=true")
    have = Counter(kind_by_id.get(sp["filament_id"]) for sp in spools)
    missing = ii.missing_spools(inventory["spools"], have)
    for s in missing:
        made = admin.request("POST", "/api/v1/spools", ii.filaman_spool(s, filaments[ii.kind_of(s)]))
        if s.get("archived"):
            admin.request("POST", f"/api/v1/spools/{made['id']}/status", {"status": "archived"})
        report(_spool_line(s))
    return len(missing)


def _filaman(base_url: str, inventory: dict, report) -> int:
    login = backend_secrets.filaman_admin()
    admin = FilamanAdmin(base_url, timeout_s=REQUEST_TIMEOUT_S)
    try:
        admin.login(login["email"], login["password"])
        try:
            return _filaman_write(admin, inventory, report)
        finally:
            admin.logout()
    except FilamanError as e:
        raise JobFailed(e.code, str(e)) from e


def _bambuddy(base_url: str, inventory: dict, report) -> int:
    api = _Json(base_url + "/api/v1/inventory")
    have = Counter(ii.kind(sp.get("brand"), sp.get("color_name"), sp.get("material"))
                   for sp in api.call("GET", "/spools?include_archived=true"))
    missing = ii.missing_spools(inventory["spools"], have)
    for s in missing:
        made = api.call("POST", "/spools", ii.bambuddy_spool(s))
        if s.get("archived"):
            api.call("POST", f"/spools/{made['id']}/archive")
        report(_spool_line(s))
    return len(missing)


_WRITERS = {"spoolman": _spoolman, "filaman": _filaman, "bambuddy": _bambuddy}


def write(backend: Backend, progress: Progress) -> None:
    """The job: adds what the backend lacks of the test inventory."""
    if not health.is_ready(backend):
        raise JobFailed("import_not_ready", backend.key)
    try:
        inventory = ii.load()
    except ii.InventoryError as e:
        raise JobFailed("import_list_invalid", str(e)) from e
    progress.step("importing")
    created = _WRITERS[backend.key](health.backend_url(backend), inventory,
                                    lambda line: progress.output([line]))
    progress.set_result(created=created, listed=len(inventory["spools"]))
    if not created:
        progress.warn("import_all_there")
    log.info("Test inventory into %s: %d spools created", backend.key, created)
