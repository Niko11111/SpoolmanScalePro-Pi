from spoolmanscale_pro.docker_compose import parse_ps_output


def test_one_object_per_line():
    text = ('{"Service":"spoolman","State":"exited"}\n'
            '{"Service":"filaman","State":"running"}\n')
    assert parse_ps_output(text) == {"spoolman": "exited", "filaman": "running"}


def test_array_form_of_older_compose():
    text = '[{"Service":"bambuddy","State":"running"}]'
    assert parse_ps_output(text) == {"bambuddy": "running"}


def test_nothing_running():
    assert parse_ps_output("") == {}
    assert parse_ps_output("\n") == {}
