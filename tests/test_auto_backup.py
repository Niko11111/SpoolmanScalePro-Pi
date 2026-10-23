from datetime import datetime

from spoolmanscale_pro.auto_backup import due

THREE_AM = 3


def test_due_once_a_day_from_the_hour_on():
    assert not due(datetime(2026, 11, 17, 2, 59), True, THREE_AM, "")
    assert due(datetime(2026, 11, 17, 3, 0), True, THREE_AM, "")
    assert due(datetime(2026, 11, 17, 3, 0), True, THREE_AM, "2026-11-16")
    assert not due(datetime(2026, 11, 17, 9, 0), True, THREE_AM, "2026-11-17")


def test_a_pi_off_at_the_hour_catches_up_later_that_day():
    assert due(datetime(2026, 11, 17, 15, 30), True, THREE_AM, "2026-11-16")


def test_off_means_never():
    assert not due(datetime(2026, 11, 17, 3, 0), False, THREE_AM, "")
