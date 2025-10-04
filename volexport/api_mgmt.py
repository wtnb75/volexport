from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pathlib import Path
from typing import Iterator
import io
import datetime
import zipfile
import tempfile
from .config import config
from .config2 import config2
from .tgtd import Tgtd
from .lvm2 import VG
from .exceptions import InvalidArgument
from logging import getLogger

_log = getLogger(__name__)
router = APIRouter()


def _backup_file(name) -> Path:
    assert "/" not in name
    assert not name.startswith(".")
    dir = Path(config.BACKUP_DIR)
    return (dir / name).with_suffix(".backup")


def _list_backup() -> Iterator[Path]:
    dir = Path(config.BACKUP_DIR)
    return dir.glob("*.backup")


@router.post("/mgmt/backup", description="create backup")
def create_backup() -> dict[str, str]:
    basename = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    outfile = _backup_file(basename)
    with zipfile.ZipFile(outfile, "w", compression=zipfile.ZIP_DEFLATED) as zf, tempfile.NamedTemporaryFile("r+") as tf:
        zf.writestr("export", Tgtd().dump())
        VG(config2.VG).backup(Path(tf.name))
        zf.writestr("volume", Path(tf.name).read_bytes())
    _log.info("backup created: %s", outfile)
    return {"name": basename}


@router.get("/mgmt/backup", description="list backup files")
def list_backup() -> list[dict]:
    return [dict(name=path.with_suffix("").name) for path in sorted(_list_backup())]


@router.delete("/mgmt/backup", description="delete old backup file")
def forget_backup(keep: int = 2) -> dict[str, str]:
    files = sorted(_list_backup(), reverse=True)
    for f in files[keep:]:
        _log.info("delete old backup(export): %s", f)
        f.unlink()
    return {"status": "OK"}


@router.get("/mgmt/backup/{name}", description="download backup file")
def get_backup(name: str) -> FileResponse:
    path = _backup_file(name)
    if path.exists():
        return FileResponse(path, filename=path.name)
    raise FileNotFoundError("backup file not found")


@router.put("/mgmt/backup/{name}", description="upload backup file")
async def put_backup(name: str, req: Request) -> dict[str, str]:
    path = _backup_file(name)
    if path.exists():
        raise FileExistsError("backup already exists")
    # validate
    try:
        buf = io.BytesIO(await req.body())
        zf = zipfile.ZipFile(buf, "r")
    except zipfile.BadZipFile as e:
        raise InvalidArgument(f"invalid backup file: {e}")
    chk = zf.testzip()
    if chk is not None:
        raise InvalidArgument(f"invalid backup file: {chk}")
    if set(zf.namelist()) != {"volume", "export"}:
        raise InvalidArgument("invalid backup file")

    path.write_bytes(buf.getbuffer())
    return {"status": "OK"}


@router.post("/mgmt/backup/{name}", description="restore backup")
def restore_backup(name: str) -> dict[str, str]:
    path = _backup_file(name)
    if path.exists():
        with zipfile.ZipFile(path, "r") as zf, tempfile.NamedTemporaryFile("r+") as tf:
            Tgtd().restore(zf.read("export").decode("utf-8"))
            Path(tf.name).write_bytes(zf.read("volume"))
            VG(config2.VG).restore(Path(tf.name))
        return {"status": "OK"}
    raise FileNotFoundError("backup file not found")


@router.delete("/mgmt/backup/{name}", description="delete specified backup file")
def delete_backup(name: str) -> dict[str, str]:
    path = _backup_file(name)
    if path.exists():
        _log.info("delete backup: %s", path)
        path.unlink()
        return {"status": "OK"}
    raise FileNotFoundError("backup file not found")
