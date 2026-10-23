from spoolmanscale_pro import hardware as hw
from spoolmanscale_pro.backend_plan import start_refusal

SMALL, MEDIUM, LARGE = hw.rules(427), hw.rules(906), hw.rules(4096)


def test_the_first_backend_always_starts():
    for rules in (SMALL, MEDIUM, LARGE):
        assert start_refusal(rules, False, [], False) is None


def test_a_second_one():
    assert start_refusal(SMALL, False, ["spoolman"], True) == "parallel_off"
    assert start_refusal(MEDIUM, True, ["spoolman"], False) == "confirm_needed"
    assert start_refusal(MEDIUM, True, ["spoolman"], True) is None
    assert start_refusal(MEDIUM, False, ["spoolman"], True) == "parallel_off"
    assert start_refusal(LARGE, True, ["spoolman", "filaman"], False) is None
