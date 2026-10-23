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


def test_stats_of_this_projects_backends_only():
    from spoolmanscale_pro.docker_compose import parse_stats
    text = ('{"Name":"spoolmanscale-pro-filaman-1","MemUsage":"365.9MiB / 7.748GiB"}\n'
            '{"Name":"spoolmanscale-pro-spoolman-1","MemUsage":"95.78MiB / 906MiB"}\n'
            '{"Name":"spoolmanscale-pro-bambuddy-1","MemUsage":"1.1GiB / 7.7GiB"}\n'
            '{"Name":"homeassistant","MemUsage":"500MiB / 7.7GiB"}\n'
            'not json\n')
    assert parse_stats(text) == {"filaman": 366, "spoolman": 96, "bambuddy": 1126}
