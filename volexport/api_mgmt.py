from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from pathlib import Path
import datetime
from .config import config
from .tgtd import Tgtd
from logging import getLogger

_log = getLogger(__name__)
router = APIRouter()


def _backup_file(name) -> Path:
    assert "/" not in name
    assert not name.startswith(".")
    dir = Path(config.BACKUP_DIR)
    return (dir / name).with_suffix(".backup")


@router.post("/mgmt/backup")
def create_backup():
    basename = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    outpath = _backup_file(basename)
    outpath.write_text(Tgtd().dump())
    _log.info("backup created: %s", outpath)
    return {"name": basename}


@router.get("/mgmt/backup")
def list_backup():
    dir = Path(config.BACKUP_DIR)
    return [{"name": x.with_suffix("").name} for x in sorted(dir.glob("*.backup"))]


@router.delete("/mgmt/backup")
def forget_backup(keep: int = 2):
    dir = Path(config.BACKUP_DIR)
    files = sorted(dir.glob("*.backup"), reverse=True)
    for f in files[keep:]:
        _log.info("delete old backup: %s", f)
        f.unlink()
    return {"status": "OK"}


@router.get("/mgmt/backup/{name}")
def get_backup(name: str):
    path = _backup_file(name)
    if path.exists():
        return PlainTextResponse(path.read_text())
    raise FileNotFoundError("backup file not found")


@router.put("/mgmt/backup/{name}")
async def put_backup(name: str, req: Request):
    path = _backup_file(name)
    if path.exists():
        raise FileExistsError("backup already exists")
    path.write_bytes(await req.body())
    return {"status": "OK"}


@router.post("/mgmt/backup/{name}")
def restore_backup(name: str):
    path = _backup_file(name)
    if path.exists():
        Tgtd().restore(path.read_text())
        return {"status": "OK"}
    raise FileNotFoundError("backup file not found")


@router.delete("/mgmt/backup/{name}")
def delete_backup(name: str):
    path = _backup_file(name)
    if path.exists():
        _log.info("delete backup: %s", path)
        path.unlink()
        return {"status": "OK"}
    raise FileNotFoundError("backup file not found")
