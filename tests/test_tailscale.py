import json

from spoolmanscale_pro.tailscale import parse_status


def test_needs_login_carries_the_link():
    text = json.dumps({"BackendState": "NeedsLogin", "AuthURL": "https://login.tailscale.com/a/abc",
                       "Self": {"TailscaleIPs": []}})
    assert parse_status(text) == {"state": "NeedsLogin", "auth_url": "https://login.tailscale.com/a/abc",
                                  "addresses": [], "name": "", "tailnet": ""}


def test_running():
    text = json.dumps({"BackendState": "Running", "AuthURL": "",
                       "Self": {"TailscaleIPs": ["100.101.102.103", "fd7a::1"],
                                "DNSName": "spoolmanscale-pro.tail1234.ts.net."},
                       "CurrentTailnet": {"Name": "nikolai@example.com"}})
    s = parse_status(text)
    assert s["state"] == "Running" and s["addresses"][0] == "100.101.102.103"
    assert s["name"] == "spoolmanscale-pro.tail1234.ts.net"


def test_garbage():
    assert parse_status("not json") == {"state": "unknown"}
