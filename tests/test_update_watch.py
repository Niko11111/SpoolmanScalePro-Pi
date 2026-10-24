"""When the search on its own runs, which kept results still count, and what
they offer."""

import pytest

from spoolmanscale_pro import update_watch as uw
from spoolmanscale_pro.paths import UPDATE_CHECK_FILE
from spoolmanscale_pro.release_sources import SourceError


def test_due():
    assert uw.due(1000.0, None, True)
    assert uw.due(1000.0, 1000.0, True)
    assert not uw.due(999.0, 1000.0, True)
    assert not uw.due(1000.0, None, False)


def test_a_result_counts_only_for_the_version_it_was_found_for():
    item = {"current": "0.27.0", "result": {"newer": ["0.28.0"]}}
    assert uw.fresh(item, "0.27.0")
    assert not uw.fresh(item, "0.28.0")
    assert not uw.fresh({"current": "0.27.0", "error": "no_internet"}, "0.27.0")
    assert not uw.fresh(None, "0.27.0")


def test_offer():
    assert uw.offer({"newer": ["0.28.0", "0.27.1"]}) == {"version": "0.28.0"}
    assert uw.offer({"newer": [], "daily": {"update": True}}) == {"daily": True}
    assert uw.offer({"newer": [], "daily": {"update": False}}) is None


@pytest.fixture
def clean_file():
    UPDATE_CHECK_FILE.unlink(missing_ok=True)
    yield
    UPDATE_CHECK_FILE.unlink(missing_ok=True)


def test_a_failure_keeps_the_result_found_before(clean_file, monkeypatch):
    answers = [{"newer": ["2.0.0-beta.99"], "notes": []}]

    def check():
        if not answers:
            raise SourceError("no_internet")
        return answers.pop()

    monkeypatch.setattr(uw.app_update, "check", check)
    uw.check_app()
    with pytest.raises(SourceError):
        uw.check_app()
    item = uw.known()["app"]
    assert item["result"]["newer"] == ["2.0.0-beta.99"] and item["error"] == "no_internet"
    assert uw.summary()["available"] == {"app": {"version": "2.0.0-beta.99"}}


def test_a_round_without_internet_tries_again_sooner(clean_file, monkeypatch):
    def offline():
        raise SourceError("no_internet")

    monkeypatch.setattr(uw.app_update, "check", offline)
    monkeypatch.setattr(uw.docker_compose, "states", lambda: {})
    monkeypatch.setattr(uw.time, "time", lambda: 1000.0)
    uw.run_round()
    assert uw._load()["next_at"] == 1000.0 + uw.RETRY_S
    monkeypatch.setattr(uw.app_update, "check", lambda: {"newer": [], "notes": []})
    uw.run_round()
    assert uw._load()["next_at"] == 1000.0 + uw.CHECK_EVERY_S
