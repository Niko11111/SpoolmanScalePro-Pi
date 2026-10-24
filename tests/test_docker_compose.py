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


def test_states_asks_again_when_a_container_vanished_mid_listing(monkeypatch):
    import subprocess

    from spoolmanscale_pro import docker_compose
    answers = [subprocess.CompletedProcess([], 1, "", "Error response from daemon: No such container: 5d3a"),
               subprocess.CompletedProcess([], 0, '{"Service":"spoolman","State":"running"}\n', "")]
    monkeypatch.setattr(docker_compose.subprocess, "run", lambda *a, **k: answers.pop(0))
    assert docker_compose.states() == {"spoolman": "running"}


def test_states_gives_up_when_docker_does_not_answer(monkeypatch):
    import subprocess

    from spoolmanscale_pro import docker_compose
    calls = []

    def fail(*a, **k):
        calls.append(1)
        return subprocess.CompletedProcess([], 1, "", "Cannot connect to the Docker daemon")
    monkeypatch.setattr(docker_compose.subprocess, "run", fail)
    assert docker_compose.states() is None and len(calls) == 1
