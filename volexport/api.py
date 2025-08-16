from logging import getLogger
from subprocess import SubprocessError
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from .config import config
from .tgtd import Tgtd
from .lvm2 import LV, VG
import datetime

_log = getLogger(__name__)
api = FastAPI()


class VolumeCreateRequest(BaseModel):
    name: str
    size: int


class VolumeCreateResponse(BaseModel):
    name: str
    size: int
    device: str


class VolumeReadResponse(BaseModel):
    name: str
    created: datetime.datetime
    size: int
    used: int


class ExportRequest(BaseModel):
    volname: str
    acl: list[str]
    readonly: bool = False


class ExportResponse(BaseModel):
    protocol: str
    addresses: list[str]
    targetname: str
    tid: int
    user: str
    passwd: str
    lun: int
    acl: list[str]


class ClientInfo(BaseModel):
    address: list[str]
    initiator: str


class ExportReadResponse(BaseModel):
    protocol: str
    connected: list[ClientInfo]
    targetname: str
    tid: int
    volumes: list[str]
    users: list[str]
    acl: list[str]


class ExportStats(BaseModel):
    targets: int
    clients: int
    volumes: int


class PoolStats(BaseModel):
    total: int
    used: int
    free: int
    volumes: int


@api.exception_handler(FileNotFoundError)
def notfound(request: Request, exc: FileNotFoundError):
    return JSONResponse(status_code=404, content=dict(detail="\n".join(exc.args)))


@api.exception_handler(FileExistsError)
def inuse(request: Request, exc: FileExistsError):
    return JSONResponse(status_code=400, content=dict(detail="\n".join(exc.args)))


@api.exception_handler(NotImplementedError)
def notimplemented(request: Request, exc: NotImplementedError):
    return JSONResponse(status_code=501, content=dict(detail=str(exc)))


@api.exception_handler(SubprocessError)
def commanderror(request: Request, exc: SubprocessError):
    return JSONResponse(status_code=500, content=dict(detail=str(exc)))


@api.get("/health")
def health():
    return {"status": "OK"}


@api.get("/volume")
def list_volume():
    return [VolumeReadResponse.model_validate(x) for x in LV(config.VG).volume_list()]


@api.post("/volume")
def create_volume(arg: VolumeCreateRequest):
    return VolumeCreateResponse.model_validate(LV(config.VG, arg.name).create(size=arg.size))


@api.get("/volume/{name}")
def read_volume(name):
    res = LV(config.VG, name).volume_read()
    if res is None:
        raise HTTPException(status_code=404, detail="volume not found")
    return VolumeReadResponse.model_validate(res)


@api.delete("/volume/{name}")
def delete_volume(name) -> dict:
    LV(config.VG, name).delete()
    return {}


def _fixpath(data: dict) -> dict:
    if "volumes" in data:
        data["volumes"] = [LV(config.VG).volume_path2vol(x) for x in data["volumes"]]
    return data


@api.get("/export")
def list_export():
    return [ExportReadResponse.model_validate(_fixpath(x)) for x in Tgtd().export_list()]


@api.post("/export")
def create_export(arg: ExportRequest):
    filename = LV(config.VG, arg.volname).volume_vol2path()
    if arg.readonly:
        params = dict(params=dict(readonly="1"))
    else:
        params = {}
    return ExportResponse.model_validate(Tgtd().export_volume(filename=filename, acl=arg.acl, **params))


@api.get("/export/{name}")
def read_export(name):
    res = [_fixpath(x) for x in Tgtd().export_list() if x["targetname"] == name or x["tid"] == name]
    if len(res) == 0:
        raise HTTPException(status_code=404, detail="export not found")
    return ExportReadResponse.model_validate(res[0])


@api.delete("/export/{name}")
def delete_export(name, force: bool = False):
    return Tgtd().unexport_volume(targetname=name, force=force)


@api.get("/address")
def get_address() -> list[str]:
    return Tgtd().myaddress()


@api.get("/stats/volume")
def stats_volume() -> PoolStats:
    info = VG(config.VG).get()
    if info is None:
        raise HTTPException(status_code=404, detail="pool not found")
    vols = info.get("Cur LV", 0)
    pesize = int(info["PE Size"].removesuffix(" B"))
    total_pe = int(info["Total PE"])
    alloc_pe = int(info["Alloc PE / Size"].split()[0])
    free_pe = int(info["Free  PE / Size"].split()[0])
    return PoolStats(total=pesize * total_pe, used=pesize * alloc_pe, free=pesize * free_pe, volumes=vols)


@api.get("/stats/export")
def stats_export() -> ExportStats:
    info = Tgtd().export_list()
    return ExportStats(
        targets=len(info),
        clients=sum([len(x["connected"]) for x in info]),
        volumes=sum([len(x["volumes"]) for x in info]),
    )
