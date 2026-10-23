"""The address setup against a fake scale that behaves like the firmware:
a new mode takes effect one status poll later, and /api/host sets the
address of the backend the scale uses right now."""

import pytest

from spoolmanscale_pro import scale_setup
from spoolmanscale_pro.backends import backend_by_key
from spoolmanscale_pro.scale_api import ScaleError

NAMES = {0: "Spoolman", 1: "FilaMan", 2: "BamBuddy"}


class FakeScale:
    def __init__(self, mode=0, stuck=False):
        self.mode, self.pending, self.stuck = mode, None, stuck
        self.hosts = {}

    def status(self):
        if self.pending is not None and not self.stuck:
            self.mode, self.pending = self.pending, None
        return {"backend": NAMES[self.mode]}

    def set_mode(self, mode):
        self.pending = mode

    def set_host(self, host):
        self.hosts[self.mode] = host
        return {"queued": True}

    def host_test(self):
        return {"state": "done", "ok": self.mode == 1, "msg": "test"}


class Progress:
    def step(self, code):
        pass

    def set_result(self, **values):
        pass


def test_every_backend_gets_its_address_and_the_scale_ends_on_the_active_one():
    scale = FakeScale(mode=0)
    instant = scale_setup.Timing(sleep=lambda s: None, now=lambda: 0)
    results = scale_setup.configure(scale, "demo.local", backend_by_key("filaman"), Progress(), instant)
    assert scale.hosts == {0: "demo.local:7912", 1: "demo.local:8002", 2: "demo.local:8000"}
    assert scale.mode == 1
    assert results["filaman"]["ok"] and not results["spoolman"]["ok"]


def test_a_scale_that_never_switches_stops_the_setup():
    ticks = iter(range(0, 10000, 5))
    scale = FakeScale(mode=0, stuck=True)
    with pytest.raises(ScaleError) as e:
        scale_setup.configure(scale, "demo.local", backend_by_key("spoolman"), Progress(),
                              scale_setup.Timing(sleep=lambda s: None, now=lambda: next(ticks)))
    assert e.value.code == "scale_mode_timeout"
    # Spoolman was set before the scale got stuck switching to FilaMan.
    assert scale.hosts == {0: "demo.local:7912"}
