import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .config import config
from .lvm2 import LV, VG

router = APIRouter()


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


class VolumeUpdateRequest(BaseModel):
    size: int | None = None
    readonly: bool | None = None


class PoolStats(BaseModel):
    total: int
    used: int
    free: int
    volumes: int


@router.get("/volume")
def list_volume():
    return [VolumeReadResponse.model_validate(x) for x in LV(config.VG).volume_list()]


@router.post("/volume")
def create_volume(arg: VolumeCreateRequest):
    return VolumeCreateResponse.model_validate(LV(config.VG, arg.name).create(size=arg.size))


@router.get("/volume/{name}")
def read_volume(name):
    res = LV(config.VG, name).volume_read()
    if res is None:
        raise HTTPException(status_code=404, detail="volume not found")
    return VolumeReadResponse.model_validate(res)


@router.delete("/volume/{name}")
def delete_volume(name) -> dict:
    LV(config.VG, name).delete()
    return {}


@router.post("/volume/{name}")
def update_volume(name, arg: VolumeUpdateRequest) -> VolumeReadResponse:
    if arg.readonly is not None:
        LV(config.VG, name).read_only(arg.readonly)
    if arg.size is not None:
        LV(config.VG, name).resize(arg.size)
    return VolumeReadResponse.model_validate(LV(config.VG, name).volume_read())


@router.get("/stats/volume")
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
