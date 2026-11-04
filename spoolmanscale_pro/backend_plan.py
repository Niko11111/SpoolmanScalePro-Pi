"""Whether several backends may run here, and whether one more may start.

situation() joins what the Pi is (hardware.py) with the owner's choice
(settings "parallel_mode"). start_refusal() is the one decision a start
passes through; it is pure and tested in tests/test_backend_plan.py.
"""

from . import backend_updates, hardware, settings
from . import version_rules as vr
from .backends import backend_by_key

# The first FilaMan whose image reads WEB_CONCURRENCY instead of fixing 4.
FILAMAN_WORKERS_SINCE = "v1.6.1"


def filaman_reads_workers(version: str) -> bool:
    return vr.parse(version) is not None and vr.sort_key(version) >= vr.sort_key(FILAMAN_WORKERS_SINCE)


def _filaman_workers(ram_mb: int, model: str, choice: int | None) -> dict:
    version = backend_updates.current_version(backend_by_key("filaman"))
    return {"choice": choice, "in_use": hardware.filaman_workers(ram_mb, model, choice),
            "automatic": hardware.filaman_workers(ram_mb, model),
            "choices": list(hardware.FILAMAN_WORKER_CHOICES),
            "supported": filaman_reads_workers(version), "version": vr.display(version)}


def situation() -> dict:
    found = hardware.detect()
    ram_mb = hardware.effective_ram_mb(found)
    rules = hardware.rules(ram_mb, found["model"])
    current = settings.load()
    choice = current["parallel_mode"]
    enabled = rules["parallel"] != "blocked" and (rules["parallel_default"] if choice is None else choice)
    return {"model": found["model"], "ram_mb": found["ram_mb"], "budget_ram_mb": ram_mb,
            "rules": rules, "parallel": enabled, "parallel_choice": choice,
            "filaman_workers": _filaman_workers(ram_mb, found["model"], current["filaman_workers"])}


def start_refusal(rules: dict, parallel: bool, others: list[str], confirmed: bool) -> str | None:
    """Why `start` (next to the running `others`) is refused, or None.
    parallel_off: several at once is not on here; switch instead.
    confirm_needed: a Pi 3 starts a second backend only after the owner saw
    the numbers (hardware.budget)."""
    if not others:
        return None
    if not parallel:
        return "parallel_off"
    if rules["parallel"] == "warn" and not confirmed:
        return "confirm_needed"
    return None
