import stat

from spoolmanscale_pro import backend_secrets
from spoolmanscale_pro.paths import SECRETS_FILE


def test_filaman_admin_is_made_once_and_then_kept():
    first = backend_secrets.filaman_admin()
    assert first["email"] == backend_secrets.FILAMAN_ADMIN_EMAIL
    assert len(first["password"]) >= 16
    assert backend_secrets.filaman_admin() == first
    assert stat.S_IMODE(SECRETS_FILE.stat().st_mode) == 0o600


def test_compose_gets_both_values():
    env = backend_secrets.compose_environment()
    assert env["FILAMAN_ADMIN_EMAIL"] and env["FILAMAN_ADMIN_PASSWORD"]
