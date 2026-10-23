import io
import tarfile
from datetime import datetime

import pytest

from spoolmanscale_pro import archive_format as af


def _data_archive(path, members):
    """members: (name, kind) with kind "file", "dir", "symlink"."""
    with tarfile.open(path, "w:gz") as tar:
        for name, kind in members:
            info = tarfile.TarInfo(name)
            if kind == "dir":
                info.type = tarfile.DIRTYPE
                tar.addfile(info)
            elif kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = "/etc/passwd"
                tar.addfile(info)
            else:
                info.size = 3
                tar.addfile(info, io.BytesIO(b"abc"))
    return path


def test_name_round_trip():
    when = datetime(2026, 11, 17, 9, 30, 5)
    name = af.backup_name("filaman", when)
    assert name == "filaman_2026-11-17_093005.tar"
    assert af.parse_backup_name(name) == {"backend": "filaman", "created": "2026-11-17T09:30:05",
                                          "before_restore": False}
    assert af.parse_backup_name(af.backup_name("spoolman", when, True))["before_restore"]


def test_names_from_outside_are_refused():
    for bad in ("../etc/passwd", "filaman_2026-11-17_093005.tar/..", "x.tar",
                "filaman_2026-13-45_999999.tar", "upload-ab12.upload"):
        assert af.parse_backup_name(bad) is None, bad


def test_bundle_round_trip(tmp_path):
    data = _data_archive(tmp_path / "d.tar.gz", [("./", "dir"), ("./spoolman.db", "file")])
    meta = af.make_meta("spoolman", "ghcr.io/donkie/spoolman:0.27.0", "2.0.0-beta.2", datetime(2026, 1, 1))
    bundle = tmp_path / "b.tar"
    af.write_bundle(bundle, meta, data)
    assert af.read_meta(bundle) == meta
    out = tmp_path / "out.tar.gz"
    af.extract_data(bundle, out)
    assert out.read_bytes() == data.read_bytes()
    af.check_data_archive(out)


def test_not_a_bundle(tmp_path):
    junk = tmp_path / "junk.tar"
    junk.write_bytes(b"this is not a tar file at all" * 100)
    with pytest.raises(af.ArchiveError) as e:
        af.read_meta(junk)
    assert e.value.code == "archive_unreadable"


def test_tar_without_meta(tmp_path):
    plain = tmp_path / "plain.tar"
    with tarfile.open(plain, "w") as tar:
        info = tarfile.TarInfo("something.txt")
        info.size = 1
        tar.addfile(info, io.BytesIO(b"x"))
    with pytest.raises(af.ArchiveError) as e:
        af.read_meta(plain)
    assert e.value.code == "archive_wrong_format"


@pytest.mark.parametrize("members", [
    [("../../etc/cron.d/x", "file")],
    [("/etc/passwd", "file")],
    [("./link", "symlink")],
])
def test_unsafe_data_archives(tmp_path, members):
    data = _data_archive(tmp_path / "d.tar.gz", members)
    with pytest.raises(af.ArchiveError) as e:
        af.check_data_archive(data)
    assert e.value.code == "archive_unsafe"


def test_empty_data_archive(tmp_path):
    data = _data_archive(tmp_path / "d.tar.gz", [])
    with pytest.raises(af.ArchiveError) as e:
        af.check_data_archive(data)
    assert e.value.code == "archive_wrong_format"


def test_too_many_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(af, "DATA_MAX_MEMBERS", 2)
    data = _data_archive(tmp_path / "d.tar.gz", [(f"./f{i}", "file") for i in range(3)])
    with pytest.raises(af.ArchiveError) as e:
        af.check_data_archive(data)
    assert e.value.code == "archive_too_big"
