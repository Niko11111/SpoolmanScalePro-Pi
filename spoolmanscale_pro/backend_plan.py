"""Whether several backends may run here, and whether one more may start.

situation() joins what the Pi is (hardware.py) with the owner's choice
(settings "parallel_mode"). start_refusal() is the one decision a start
passes through; it is pure and tested in tests/test_backend_plan.py.
"""

from . import hardware, settings


def situation() -> dict:
    found = hardware.detect()
    ram_mb = hardware.effective_ram_mb(found)
    rules = hardware.rules(ram_mb, found["model"])
    choice = settings.load()["parallel_mode"]
    enabled = rules["parallel"] != "blocked" and (rules["parallel_default"] if choice is None else choice)
    return {"model": found["model"], "ram_mb": found["ram_mb"], "budget_ram_mb": ram_mb,
            "rules": rules, "parallel": enabled, "parallel_choice": choice}


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
