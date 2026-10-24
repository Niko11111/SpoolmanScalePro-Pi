from spoolmanscale_pro import backend_counts as bc


def test_spoolman_total_header():
    assert bc.parse_total_header("24") == 24
    assert bc.parse_total_header(" 0 ") == 0
    for bad in (None, "", "-1", "many"):
        assert bc.parse_total_header(bad) is None, bad


def test_bambuddy_list_length():
    assert bc.parse_list_length([{"id": 1}, {"id": 2}]) == 2
    assert bc.parse_list_length([]) == 0
    assert bc.parse_list_length({"detail": "Not authenticated"}) is None


def test_a_count_is_asked_again_after_its_time():
    assert bc.stale(None, 100.0)
    assert not bc.stale(100.0, 100.0 + bc.COUNT_TTL_S - 1)
    assert bc.stale(100.0, 100.0 + bc.COUNT_TTL_S)
