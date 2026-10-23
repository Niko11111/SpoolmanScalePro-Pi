from spoolmanscale_pro.backends import backend_by_key
from spoolmanscale_pro.scale_api import summarize, switch_and_confirm

FILAMAN = backend_by_key("filaman")


def test_summarize_on_the_active_backend_and_pointing_here():
    status = {"backend": "FilaMan", "backendUrl": "http://pi.local:8002/api/v1",
              "backendOk": True, "version": "v0.8.3", "weight": "812"}
    s = summarize(status, FILAMAN, {"pi", "pi.local", "192.168.4.1"})
    assert s["on_active"] and s["points_here"] and s["backend_ok"]


def test_summarize_points_elsewhere():
    status = {"backend": "FilaMan", "backendUrl": "http://192.168.4.100:8002", "backendOk": True}
    assert not summarize(status, FILAMAN, {"pi.local", "192.168.4.1"})["points_here"]


def test_summarize_without_scheme_in_the_url():
    status = {"backend": "FilaMan", "backendUrl": "192.168.4.1:8002", "backendOk": False}
    assert summarize(status, FILAMAN, {"192.168.4.1"})["points_here"]


class FakeScale:
    def __init__(self, answers):
        self.answers = list(answers)
        self.modes = []

    def status(self):
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]

    def set_mode(self, mode):
        self.modes.append(mode)


def test_switch_sets_the_mode_and_waits_for_the_backend():
    scale = FakeScale([
        {"backend": "Spoolman", "backendOk": True},
        {"backend": "Spoolman", "backendOk": True},
        {"backend": "FilaMan", "backendOk": False},
        {"backend": "FilaMan", "backendOk": True},
    ])
    status = switch_and_confirm(scale, FILAMAN, sleep=lambda s: None)
    assert scale.modes == [1]
    assert status == {"backend": "FilaMan", "backendOk": True}


def test_switch_leaves_a_scale_alone_that_is_already_there():
    scale = FakeScale([{"backend": "FilaMan", "backendOk": True}])
    switch_and_confirm(scale, FILAMAN, sleep=lambda s: None)
    assert scale.modes == []


def test_switch_gives_up_after_the_timeout():
    ticks = iter(range(0, 1000, 10))
    scale = FakeScale([{"backend": "Spoolman", "backendOk": True}])
    status = switch_and_confirm(scale, FILAMAN, timeout_s=30, sleep=lambda s: None,
                                clock=lambda: next(ticks))
    assert status["backend"] == "Spoolman"
