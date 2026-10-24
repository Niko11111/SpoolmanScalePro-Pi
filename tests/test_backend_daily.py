"""The daily build with Docker, ghcr.io, GitHub and the backups replaced by
fakes: switching to it, a newer one, and the two ways back."""

from pathlib import Path

import pytest

from spoolmanscale_pro import backend_daily as bd
from spoolmanscale_pro import backend_updates as bu
from spoolmanscale_pro import settings
from spoolmanscale_pro.backends import backend_by_key
from spoolmanscale_pro.docker_compose import CommandResult
from spoolmanscale_pro.jobs import JobFailed

BAMBUDDY = backend_by_key("bambuddy")
OLD = "sha256:" + "a" * 64
NEW = "sha256:" + "b" * 64
BACKUP = "bambuddy_2026-10-24_120000_before-daily.tar"


class Progress:
    def __init__(self):
        self.steps, self.result = [], {}

    def step(self, code):
        self.steps.append(code)

    def warn(self, code):
        pass

    def set_result(self, **values):
        self.result.update(values)


@pytest.fixture
def fake(monkeypatch):
    calls = {"digest": OLD, "backups": [], "restored": [], "restore_ok": True, "before_daily": None}
    settings.update({"backend_versions": {}, "daily_releases": {}, "include_prereleases": False})
    monkeypatch.setattr(bd.release_sources, "tag_digest", lambda image, tag: calls["digest"])
    monkeypatch.setattr(bd.release_sources, "image_tags", lambda image: ["1.2.5.7", "daily"])
    monkeypatch.setattr(bd.release_sources, "releases", lambda repo: [
        {"tag": "v1.3.0b1-daily.20261024", "published": "2026-10-24"}, {"tag": "v1.2.5.7", "published": "2026-10-02"}])
    for module in (bd.docker_compose, bu.docker_compose):
        monkeypatch.setattr(module, "states", lambda: {"bambuddy": "running"})
        monkeypatch.setattr(module, "pull", lambda key: CommandResult(True, ""))
        monkeypatch.setattr(module, "up", lambda key: CommandResult(True, ""))
        monkeypatch.setattr(module, "image_of", lambda key: "ghcr.io/maziggy/bambuddy:" + bu.current_version(BAMBUDDY))
        monkeypatch.setattr(module, "remove_image", lambda ref: True)
    monkeypatch.setattr(bu.health, "wait_until_ready", lambda backend: True)

    def create(backend, progress, reason):
        calls["backups"].append(reason)
        return f"bambuddy_x_{reason}.tar"

    def restore(backend, path, progress, keep_safety=True):
        if not calls["restore_ok"]:
            raise JobFailed("restore_failed", backend.key)
        calls["restored"].append(path.name)

    monkeypatch.setattr(bu.backups, "create", create)
    monkeypatch.setattr(bd.backups, "restore", restore)
    monkeypatch.setattr(bd.backups, "newest", lambda key, reason: calls["before_daily"])
    monkeypatch.setattr(bd.archive_format, "read_meta", lambda path: {"image": "ghcr.io/maziggy/bambuddy:1.2.5.7"})
    return calls


def test_switching_pins_the_build_backs_up_first_and_names_it(fake):
    bd.install(BAMBUDDY, Progress())
    assert bu.current_version(BAMBUDDY) == "daily@" + OLD
    assert fake["backups"] == ["before-daily"]
    assert settings.load()["daily_releases"]["bambuddy"] == {"tag": "v1.3.0b1-daily.20261024", "published": "2026-10-24"}


def test_a_newer_daily_build_is_seen_and_installed_like_an_update(fake):
    bd.install(BAMBUDDY, Progress())
    assert bd.check(BAMBUDDY)["daily"]["update"] is False
    fake["digest"] = NEW
    found = bd.check(BAMBUDDY)
    assert found["daily"]["on"] and found["daily"]["update"]
    bd.install(BAMBUDDY, Progress())
    assert bu.current_version(BAMBUDDY) == "daily@" + NEW
    assert fake["backups"] == ["before-daily", "before-update"]


def test_the_same_build_twice_is_refused(fake):
    bd.install(BAMBUDDY, Progress())
    with pytest.raises(JobFailed) as e:
        bd.install(BAMBUDDY, Progress())
    assert e.value.code == "already_installed"


def test_only_a_release_newer_than_the_daily_build_is_offered(fake, monkeypatch):
    bd.install(BAMBUDDY, Progress())
    assert bd.check(BAMBUDDY)["newer"] == []  # 1.2.5.7 would be a downgrade
    monkeypatch.setattr(bd.release_sources, "image_tags", lambda image: ["1.2.5.7", "1.3.0", "daily"])
    assert bd.check(BAMBUDDY)["newer"] == ["1.3.0"]


def test_leaving_puts_the_release_and_the_backup_back(fake):
    bd.install(BAMBUDDY, Progress())
    fake["before_daily"] = Path(BACKUP)
    assert bd.check(BAMBUDDY)["daily"]["back"] == {"backup": BACKUP, "version": "1.2.5.7"}
    bd.leave(BAMBUDDY, Progress())
    assert bu.current_version(BAMBUDDY) == "1.2.5.7"
    assert fake["restored"] == [BACKUP]


def test_leaving_without_the_backup_is_refused(fake):
    bd.install(BAMBUDDY, Progress())
    with pytest.raises(JobFailed) as e:
        bd.leave(BAMBUDDY, Progress())
    assert e.value.code == "no_backup_before_daily"
    assert bu.current_version(BAMBUDDY) == "daily@" + OLD


def test_a_failed_restore_keeps_the_daily_build(fake):
    bd.install(BAMBUDDY, Progress())
    fake["before_daily"] = Path(BACKUP)
    fake["restore_ok"] = False
    with pytest.raises(JobFailed):
        bd.leave(BAMBUDDY, Progress())
    assert bu.current_version(BAMBUDDY) == "daily@" + OLD


def test_leaving_needs_a_daily_build(fake):
    with pytest.raises(JobFailed) as e:
        bd.leave(BAMBUDDY, Progress())
    assert e.value.code == "not_on_daily_build"
