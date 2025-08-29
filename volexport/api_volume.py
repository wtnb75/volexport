import datetime
from typing import Annotated
from enum import Enum
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, AfterValidator
from .config import config
from .lvm2 import LV, VG
from .tgtd import Tgtd

router = APIRouter()


def _is_volsize(value: int):
    if value % 512 != 0:
        raise ValueError(f"invalid volume size: {value} is not multiple of 512")
    return value


VolumeSize = Annotated[int, AfterValidator(_is_volsize)]


class VolumeCreateRequest(BaseModel):
    name: str = Field(description="Name of the volume to create", examples=["volume1"])
    size: VolumeSize = Field(description="Size of the volume in bytes", examples=[1073741824], gt=0)


class VolumeCreateResponse(BaseModel):
    name: str = Field(description="Name of the created volume", examples=["volume1"])
    size: VolumeSize = Field(description="Size of the created volume in bytes", examples=[1073741824], gt=0)


class VolumeReadResponse(BaseModel):
    name: str = Field(description="Name of the volume", examples=["volume1"])
    created: datetime.datetime = Field(description="Creation timestamp of the volume", examples=["2023-10-01T12:00:00"])
    size: VolumeSize = Field(description="Size of the volume in bytes", examples=[1073741824], gt=0)
    used: int = Field(description="in-use count", examples=[0, 1])
    readonly: bool = Field(description="true if read-only", examples=[True, False])


class VolumeUpdateRequest(BaseModel):
    size: VolumeSize | None = Field(
        default=None, description="New size of the volume in bytes", examples=[2147483648], gt=0
    )
    readonly: bool | None = Field(default=None, description="Set volume to read-only if true", examples=[True, False])


class Filesystem(str, Enum):
    ext4 = "ext4"
    xfs = "xfs"
    btrfs = "btrfs"
    vfat = "vfat"
    ntfs = "ntfs"
    exfat = "exfat"
    nilfs2 = "nilfs2"


class VolumeFormatRequest(BaseModel):
    filesystem: Filesystem = Field(default=Filesystem.ext4, description="Make filesystem in the volume")
    label: str | None = Field(default=None, description="Label of filesystem")


class PoolStats(BaseModel):
    total: int = Field(description="Total size of the pool in bytes", examples=[10737418240])
    used: int = Field(description="Used size of the pool in bytes", examples=[5368709120])
    free: int = Field(description="Free size of the pool in bytes", examples=[5368709120])
    volumes: int = Field(description="Number of volumes in the pool", examples=[10])


@router.get("/volume", description="List all volumes")
def list_volume():
    return [VolumeReadResponse.model_validate(x) for x in LV(config.VG).volume_list()]


@router.post("/volume", description="Create a new volume")
def create_volume(arg: VolumeCreateRequest):
    return VolumeCreateResponse.model_validate(LV(config.VG, arg.name).create(size=arg.size))


@router.get("/volume/{name}", description="Read volume details by name")
def read_volume(name):
    res = LV(config.VG, name).volume_read()
    if res is None:
        raise HTTPException(status_code=404, detail="volume not found")
    return VolumeReadResponse.model_validate(res)


@router.delete("/volume/{name}", description="Delete a volume by name")
def delete_volume(name) -> dict:
    LV(config.VG, name).delete()
    return {}


@router.post("/volume/{name}", description="Update a volume by name")
def update_volume(name, arg: VolumeUpdateRequest) -> VolumeReadResponse:
    lv = LV(config.VG, name)
    if arg.readonly is not None:
        lv.read_only(arg.readonly)
    if arg.size is not None:
        lv.resize(arg.size)
        Tgtd().refresh_volume_bypath(lv.volume_vol2path())
    return VolumeReadResponse.model_validate(lv.volume_read())


@router.post("/volume/{name}/mkfs", description="Format a volume, make filesystem")
def format_volume(name, arg: VolumeFormatRequest) -> VolumeReadResponse:
    lv = LV(config.VG, name)
    lv.format_volume(arg.filesystem.value, arg.label)
    return VolumeReadResponse.model_validate(lv.volume_read())


@router.get("/stats/volume", description="Get statistics of the volume pool")
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
