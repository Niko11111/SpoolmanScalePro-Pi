from datetime import datetime, timedelta

from spoolmanscale_pro import archive_format, backups
from spoolmanscale_pro.paths import BACKUP_DIR


def test_automatic_and_other_backups_are_kept_separately():
    start = datetime(2026, 1, 1)
    made = []
    for i in range(12):
        made.append(archive_format.backup_name("bambuddy", start + timedelta(days=i), "auto"))
        made.append(archive_format.backup_name("bambuddy", start + timedelta(days=i, hours=1)))
    for name in made:
        (BACKUP_DIR / name).write_bytes(b"x")
    backups._prune("bambuddy")
    left = sorted(p.name for p in BACKUP_DIR.glob("bambuddy_*.tar"))
    auto = [n for n in left if n.endswith("_auto.tar")]
    assert len(auto) == backups.AUTO_BACKUPS_KEPT
    assert len(left) - len(auto) == backups.BACKUPS_KEPT
    # The newest of each kind survive.
    assert archive_format.backup_name("bambuddy", start + timedelta(days=11), "auto") in auto
    for name in left:
        (BACKUP_DIR / name).unlink()
