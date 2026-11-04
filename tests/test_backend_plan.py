from spoolmanscale_pro import hardware as hw
from spoolmanscale_pro.backend_plan import filaman_reads_workers, start_refusal

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


def test_filaman_reads_its_worker_count_from_1_6_1():
    assert not filaman_reads_workers("v1.4.3")
    assert not filaman_reads_workers("v1.6.0")
    assert filaman_reads_workers("v1.6.1")
    assert filaman_reads_workers("v2.0.0")
    assert not filaman_reads_workers("not-a-version")
