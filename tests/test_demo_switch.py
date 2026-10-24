"""Demo mode is the flag file; the hidden switch writes and removes it."""

from spoolmanscale_pro import demo


def test_switching_demo_mode_on_and_off():
    demo.set_enabled(True)
    assert demo.enabled()
    demo.set_enabled(True)
    assert demo.enabled()
    demo.set_enabled(False)
    assert not demo.enabled()
    demo.set_enabled(False)
    assert not demo.enabled()
