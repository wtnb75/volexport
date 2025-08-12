from logging import getLogger
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from .config import config
from .tgtd import Tgtd
from .lvm2 import LV, VG

_log = getLogger(__name__)
api = FastAPI()


class Volume(BaseModel):
    name: str
    size: int


class Export(BaseModel):
    volname: str
    acl: list[str]


class PoolInfo(BaseModel):
    total: int
    used: int
    free: int
    volumes: int


@api.exception_handler(FileNotFoundError)
def notfound(request: Request, exc: FileNotFoundError):
    return JSONResponse(status_code=404, content=dict(detail="\n".join(exc.args)))


@api.exception_handler(NotImplementedError)
def notimplemented(request: Request, exc: NotImplementedError):
    return JSONResponse(status_code=501, content=dict(detail="\n".join(exc.args)))


@api.get("/health")
def health():
    return "OK"


@api.get("/volume")
def list_volume():
    return LV(config.VG).volume_list()


@api.post("/volume")
def create_volume(arg: Volume):
    return LV(config.VG, arg.name).create(size=arg.size)


@api.get("/volume/{name}")
def read_volume(name):
    res = LV(config.VG, name).volume_read()
    if res is None:
        raise HTTPException(status_code=404, detail="volume not found")
    return res


@api.delete("/volume/{name}")
def delete_volume(name):
    res = LV(config.VG, name).delete()
    if res is None:
        raise HTTPException(status_code=404, detail="volume not found")
    return res


@api.get("/export")
def list_export():
    return Tgtd().export_list()


@api.post("/export")
def create_export(arg: Export):
    return Tgtd().export_volume(filename=arg.volname, acl=arg.acl)


@api.get("/export/{name}")
def read_export(name):
    res = [x for x in Tgtd().export_list() if x["name"] == name or x["tid"] == name]
    if len(res) == 0:
        raise HTTPException(status_code=404, detail="export not found")
    return res[0]


@api.delete("/export/{name}")
def delete_export(name, force: bool = False):
    return Tgtd().unexport_volume(targetname=name, force=force)


@api.get("/address")
def get_address():
    return Tgtd().myaddress()


@api.get("/stats/volume")
def stats_volume() -> PoolInfo:
    info = VG(config.VG).get()
    if info is None:
        raise HTTPException(status_code=404, detail="pool not found")
    vols = info.get("Cur LV", 0)
    pesize = int(info["PE Size"].removesuffix(" B"))
    total_pe = int(info["Total PE"])
    alloc_pe = int(info["Alloc PE / Size"].split()[0])
    free_pe = int(info["Free  PE / Size"].split()[0])
    return PoolInfo(total=pesize * total_pe, used=pesize * alloc_pe, free=pesize * free_pe, volumes=vols)


@api.get("/stats/export")
def stats_export() -> dict:
    info = Tgtd().export_list()
    return dict(
        targets=len(info),
        clients=sum([len(x["connected"]) for x in info]),
        volumes=sum([len(x["volumes"]) for x in info]),
    )
