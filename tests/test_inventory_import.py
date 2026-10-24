"""The test inventory: the list itself, what counts as already there, the
bodies per backend, and a second run against a fake Spoolman creating
nothing."""

import json
from collections import Counter

import pytest

from spoolmanscale_pro import inventory_import as ii
from spoolmanscale_pro import inventory_writers as iw

YELLOW = {"key": "y", "vendor": "Bambu Lab", "name": "Yellow", "material": "PLA", "color_hex": "F4EE2A",
          "weight_g": 1000, "spool_weight_g": 250, "remaining_g": 919, "density": 1.24, "diameter_mm": 1.75,
          "extruder_temp": 220, "bed_temp": 60, "article_number": "10400"}


def test_the_shipped_list_is_valid():
    data = ii.load()
    assert len(data["spools"]) == 21 and len(data["vendors"]) == 7
    assert len({s["key"] for s in data["spools"]}) == len(data["spools"])


def test_a_spool_with_an_unknown_vendor_is_refused(tmp_path):
    path = tmp_path / "inv.json"
    path.write_text(json.dumps({"vendors": [], "spools": [YELLOW]}), encoding="utf-8")
    with pytest.raises(ii.InventoryError):
        ii.load(path)


def test_only_what_is_missing_is_created():
    second = dict(YELLOW, key="y2")
    other = dict(YELLOW, key="b", name="Black")
    spools = [YELLOW, second, other]
    assert ii.missing_spools(spools, Counter()) == spools
    assert ii.missing_spools(spools, Counter({ii.kind_of(YELLOW): 1})) == [second, other]
    assert ii.missing_spools(spools, Counter({ii.kind_of(YELLOW): 5, ii.kind_of(other): 1})) == []
    assert ii.kinds(spools) == [YELLOW, other]


def test_kinds_ignore_case_and_spaces():
    assert ii.kind("Bambu Lab ", "yellow", "pla") == ii.kind_of(YELLOW)


def test_colours():
    assert ii.rgba("f4ee2a") == "F4EE2AFF"
    assert ii.rgba("00000000") == "00000000"
    assert ii.filaman_color(YELLOW) == {"name": "Yellow", "hex_code": "#F4EE2A"}


def test_bodies():
    assert ii.filaman_spool(YELLOW, 3) == {"filament_id": 3, "initial_total_weight_g": 1250,
                                           "empty_spool_weight_g": 250, "remaining_weight_g": 919}
    bb = ii.bambuddy_spool(YELLOW)
    assert bb["weight_used"] == 81 and bb["rgba"] == "F4EE2AFF" and bb["brand"] == "Bambu Lab"
    assert "note" not in bb
    assert ii.spoolman_spool(dict(YELLOW, archived=True), 7)["archived"] is True
    assert ii.used_g(dict(YELLOW, remaining_g=1200)) == 0


class FakeSpoolman:
    """Just enough of Spoolman's API for the writer."""

    def __init__(self):
        self.rows = {"/vendor": [], "/filament": [], "/spool": []}

    def call(self, method, path, body=None):
        table = path.split("?")[0]
        if method == "GET":
            return self.rows[table]
        row = dict(body, id=len(self.rows[table]) + 1)
        if table == "/filament":
            row["vendor"] = next(v for v in self.rows["/vendor"] if v["id"] == body["vendor_id"])
        if table == "/spool":
            row["filament"] = next(f for f in self.rows["/filament"] if f["id"] == body["filament_id"])
        self.rows[table].append(row)
        return row


def test_a_second_run_creates_nothing(monkeypatch):
    fake = FakeSpoolman()
    monkeypatch.setattr(iw._Json, "call", lambda self, *a, **k: fake.call(*a, **k))
    inventory = ii.load()
    lines = []
    assert iw._spoolman("http://x", inventory, lines.append) == 21
    assert len(fake.rows["/vendor"]) == 7 and len(fake.rows["/filament"]) == 20
    assert iw._spoolman("http://x", inventory, lines.append) == 0
    assert len(fake.rows["/spool"]) == 21 and len(lines) == 21
