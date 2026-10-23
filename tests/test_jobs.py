import threading

from spoolmanscale_pro.jobs import JobFailed, JobRunner


def _wait(runner):
    for _ in range(200):
        job = runner.current()
        if job and not job["running"]:
            return job
        threading.Event().wait(0.01)
    raise AssertionError("job did not finish")


def test_second_job_is_refused_while_one_runs():
    runner, release = JobRunner(), threading.Event()
    assert runner.start("switch", "spoolman", lambda p: release.wait(2)) is not None
    assert runner.start("switch", "filaman", lambda p: None) is None
    release.set()
    _wait(runner)
    assert runner.start("switch", "filaman", lambda p: None) is not None


def test_failure_code_and_warnings_are_kept():
    runner = JobRunner()

    def fn(progress):
        progress.step("starting")
        progress.warn("scale_unreachable")
        raise JobFailed("not_ready", "filaman")

    runner.start("switch", "filaman", fn)
    job = _wait(runner)
    assert job["ok"] is False and job["error"] == "not_ready"
    assert job["warnings"] == ["scale_unreachable"] and job["step"] == "failed"


def test_a_crash_becomes_internal_error():
    runner = JobRunner()
    runner.start("switch", "x", lambda p: 1 / 0)
    assert _wait(runner)["error"] == "internal_error"
