"""The test inventory (demo_inventory.json) and what writing it into a
backend means, as pure functions: no network. inventory_writers.py does the
requests.

Writing only adds and can be repeated: what a backend already has is left
alone. A vendor counts as there by its name, a filament by vendor, name and
material, and a kind of spool (the same three) by how many spools of it
exist, archived ones included. So a second run creates nothing, and a
backend that already holds some of the list only gets the rest.

Each backend gets the fields it has a place for; the body builders below say
which. Tested in tests/test_inventory_import.py.
"""

import json
from collections import Counter
from pathlib import Path

INVENTORY_FILE = Path(__file__).with_name("demo_inventory.json")

VENDOR_FIELDS = ("name", "empty_spool_weight_g")
SPOOL_FIELDS = ("key", "vendor", "name", "material", "color_hex", "weight_g",
                "spool_weight_g", "remaining_g", "density", "diameter_mm")
OPAQUE_ALPHA = "FF"


class InventoryError(Exception):
    pass


def load(path: Path = INVENTORY_FILE) -> dict:
    """The list, checked: every spool has the fields the writers use and a
    vendor that is in the list."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise InventoryError(f"{path.name} unreadable: {e}") from e
    vendors = data.get("vendors") if isinstance(data, dict) else None
    spools = data.get("spools") if isinstance(data, dict) else None
    if not isinstance(vendors, list) or not isinstance(spools, list):
        raise InventoryError(f"{path.name} needs a vendors and a spools list")
    names = set()
    for v in vendors:
        if not isinstance(v, dict) or any(f not in v for f in VENDOR_FIELDS):
            raise InventoryError(f"vendor without {', '.join(VENDOR_FIELDS)}: {v}")
        names.add(v["name"].lower())
    for s in spools:
        if not isinstance(s, dict) or any(f not in s for f in SPOOL_FIELDS):
            raise InventoryError(f"spool without {', '.join(SPOOL_FIELDS)}: {s.get('key') if isinstance(s, dict) else s}")
        if s["vendor"].lower() not in names:
            raise InventoryError(f"spool {s['key']}: vendor {s['vendor']} is not in the list")
    return data


def kind(vendor: str, name: str, material: str) -> tuple[str, str, str]:
    return ((vendor or "").strip().lower(), (name or "").strip().lower(), (material or "").strip().lower())


def kind_of(spool: dict) -> tuple[str, str, str]:
    return kind(spool["vendor"], spool["name"], spool["material"])


def kinds(spools: list[dict]) -> list[dict]:
    """The first spool of each kind, in list order: one filament each."""
    seen, out = set(), []
    for s in spools:
        if kind_of(s) not in seen:
            seen.add(kind_of(s))
            out.append(s)
    return out


def missing_spools(spools: list[dict], have: Counter) -> list[dict]:
    """The spools still to create when the backend has have[kind] of each."""
    left = Counter(have)
    out = []
    for s in spools:
        if left[kind_of(s)] > 0:
            left[kind_of(s)] -= 1
        else:
            out.append(s)
    return out


def rgba(color_hex: str) -> str:
    """RRGGBB or RRGGBBAA -> RRGGBBAA, upper case."""
    value = color_hex.strip().lstrip("#").upper()
    return value + OPAQUE_ALPHA if len(value) == 6 else value


def used_g(spool: dict) -> float:
    return max(spool["weight_g"] - spool["remaining_g"], 0)


def _optional(**fields) -> dict:
    return {k: v for k, v in fields.items() if v is not None}


# Spoolman (API v1): vendor, filament, spool.

def spoolman_vendor(vendor: dict) -> dict:
    return {"name": vendor["name"], "empty_spool_weight": vendor["empty_spool_weight_g"]}


def spoolman_filament(spool: dict, vendor_id: int) -> dict:
    return {"name": spool["name"], "vendor_id": vendor_id, "material": spool["material"],
            "color_hex": spool["color_hex"], "density": spool["density"],
            "diameter": spool["diameter_mm"], "weight": spool["weight_g"],
            "spool_weight": spool["spool_weight_g"],
            **_optional(settings_extruder_temp=spool.get("extruder_temp"),
                        settings_bed_temp=spool.get("bed_temp"),
                        article_number=spool.get("article_number"))}


def spoolman_spool(spool: dict, filament_id: int) -> dict:
    return {"filament_id": filament_id, "remaining_weight": spool["remaining_g"],
            "spool_weight": spool["spool_weight_g"], "archived": bool(spool.get("archived")),
            **_optional(comment=spool.get("comment"))}


# FilaMan (API v1.4.3): manufacturer, colour, filament, spool. A spool is
# archived afterwards through its status; FilaMan has no temperatures and
# no spool comment.

def filaman_manufacturer(vendor: dict) -> dict:
    return {"name": vendor["name"], "empty_spool_weight_g": vendor["empty_spool_weight_g"]}


def filaman_color(spool: dict) -> dict:
    return {"name": spool["name"], "hex_code": "#" + spool["color_hex"].upper()}


def filaman_filament(spool: dict, manufacturer_id: int, color_id: int) -> dict:
    return {"manufacturer_id": manufacturer_id, "designation": spool["name"],
            "material_type": spool["material"], "diameter_mm": spool["diameter_mm"],
            "manufacturer_color_name": spool["name"], "raw_material_weight_g": spool["weight_g"],
            "default_spool_weight_g": spool["spool_weight_g"], "density_g_cm3": spool["density"],
            "color_mode": "single", "colors": [{"color_id": color_id, "position": 1}]}


def filaman_spool(spool: dict, filament_id: int) -> dict:
    # initial_total_weight_g is the full spool on the scale: filament and
    # the empty spool.
    return {"filament_id": filament_id,
            "initial_total_weight_g": spool["weight_g"] + spool["spool_weight_g"],
            "empty_spool_weight_g": spool["spool_weight_g"], "remaining_weight_g": spool["remaining_g"]}


# BamBuddy (API of 1.2.5.7): a spool carries vendor, material and colour
# itself; there is no filament. Archived afterwards.

def bambuddy_spool(spool: dict) -> dict:
    temp = spool.get("extruder_temp")
    return {"material": spool["material"], "brand": spool["vendor"], "color_name": spool["name"],
            "rgba": rgba(spool["color_hex"]), "label_weight": spool["weight_g"],
            "core_weight": spool["spool_weight_g"], "weight_used": used_g(spool),
            **_optional(nozzle_temp_min=temp, nozzle_temp_max=temp, note=spool.get("comment"),
                        material_number=spool.get("article_number"))}
