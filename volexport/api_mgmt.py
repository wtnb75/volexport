from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pathlib import Path
from typing import Iterator
import io
import yaml
import datetime
import zipfile
import tempfile
from .config import config
from .config2 import config2
from .tgtd import Tgtd
from .lvm2 import VG
from .api_export import ExportReadResponse
from .api_volume import VolumeReadResponse
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


def parse_volbackup(s: str) -> dict:
    s = s.replace(" =", ":")
    s = s.replace(" {", ":")
    s = s.replace("\t", " ")
    s = s.replace("}", "")
    return yaml.safe_load("\n".join([x.rstrip() for x in s.splitlines()]))


def parse_export(s: str) -> list[dict]:
    res = []
    ent = {}
    for line in s.splitlines():
        if line.startswith("<target "):
            ent["name"] = line.split()[-1].rstrip(">")
        elif line.lstrip().startswith("backing-store"):
            ent["volume"] = line.split()[-1].split("/")[-1]
        elif line.lstrip().startswith("incominguser"):
            ent["user"] = line.strip().split()[1]
            ent["password"] = "******"
        elif line.lstrip().startswith("initiator-address"):
            if "acl" not in ent:
                ent["acl"] = []
            ent["acl"].extend(line.strip().split()[1:])
        elif line.startswith("</target>"):
            res.append(ent)
            ent = {}
    return res


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


@router.get("/mgmt/backup/{name}/export", description="get export list of backup")
def get_backup_export(name: str) -> list[ExportReadResponse]:
    path = _backup_file(name)
    if not path.exists():
        raise FileNotFoundError("backup file not found")
    res = []
    with zipfile.ZipFile(path, "r") as zf:
        voldata = zf.read("volume").decode("utf-8")
        volparsed = parse_volbackup(voldata)
        data = zf.read("export").decode("utf-8")
        parsed = parse_export(data)
        for exp in parsed:
            vol = volparsed.get(config2.VG, {}).get("logical_volumes", {}).get(exp["volume"])
            if not vol:
                raise Exception(f"invalid backup format: vol {exp['volume']}")
            volname = [x.removeprefix("volname.") for x in vol.get("tags", []) if x.startswith("volname.")][0]
            res.append(
                ExportReadResponse(
                    protocol="iscsi",
                    connected=[],
                    targetname=exp["name"],
                    tid=0,
                    volumes=[volname],
                    users=[exp["user"]],
                    acl=exp["acl"],
                )
            )
    return res


@router.get("/mgmt/backup/{name}/volume", description="get volume list of backup")
def get_backup_volume(name: str) -> list[VolumeReadResponse]:
    path = _backup_file(name)
    if not path.exists():
        raise FileNotFoundError("backup file not found")
    res = []
    with zipfile.ZipFile(path, "r") as zf:
        data = zf.read("volume").decode("utf-8")
        parsed = parse_volbackup(data)
        if parsed.get("version") != 1:
            raise Exception(f"invalid backup format: version={parsed.get('version')}")
        vginfo = parsed.get(config2.VG)
        if not vginfo:
            raise Exception("invalid backup format: no vg")
        extent_size = vginfo.get("extent_size")
        if not extent_size:
            raise Exception(f"invalid backup format: extent size={extent_size}")
        for lvinfo in vginfo.get("logical_volumes", {}).values():
            tags = lvinfo.get("tags", [])
            volname = [x.removeprefix("volname.") for x in tags if x.startswith("volname.")][0]
            if "VISIBLE" not in lvinfo.get("status", []):
                continue
            extents = 0
            for i in range(lvinfo.get("segment_count")):
                extents += lvinfo.get(f"segment{i + 1}", {}).get("extent_count")
            res.append(
                VolumeReadResponse(
                    name=volname,
                    created=datetime.datetime.fromtimestamp(lvinfo.get("creation_time")),
                    size=extents * extent_size * 512,
                    used=False,
                    readonly="WRITE" not in lvinfo.get("status", []),
                    thin=False,
                    parent=None,
                )
            )
    return res


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
def restore_backup(name: str, export: bool = True, volume: bool = True) -> dict[str, str]:
    path = _backup_file(name)
    if not (export or volume):
        raise InvalidArgument("nothing to restore")
    if path.exists():
        result = dict(status="OK")
        with zipfile.ZipFile(path, "r") as zf, tempfile.NamedTemporaryFile("r+") as tf:
            if export:
                Tgtd().restore(zf.read("export").decode("utf-8"))
                result["export"] = "restored"
            else:
                result["export"] = "skipped"
            if volume:
                Path(tf.name).write_bytes(zf.read("volume"))
                VG(config2.VG).restore(Path(tf.name))
                result["volume"] = "restored"
            else:
                result["volume"] = "skipped"
        return result
    raise FileNotFoundError("backup file not found")


@router.delete("/mgmt/backup/{name}", description="delete specified backup file")
def delete_backup(name: str) -> dict[str, str]:
    path = _backup_file(name)
    if path.exists():
        _log.info("delete backup: %s", path)
        path.unlink()
        return {"status": "OK"}
    raise FileNotFoundError("backup file not found")
