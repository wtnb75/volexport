import datetime
from typing import Annotated
from enum import Enum
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, AfterValidator
from .config2 import config2
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
    """Request type for POST /volume"""

    name: str = Field(description="Name of the volume to create", examples=["volume1"])
    size: VolumeSize = Field(description="Size of the volume in bytes", examples=[1073741824], gt=0)


class VolumeCreateResponse(BaseModel):
    """Response type for POST /volume"""

    name: str = Field(description="Name of the created volume", examples=["volume1"])
    size: VolumeSize = Field(description="Size of the created volume in bytes", examples=[1073741824], gt=0)


class VolumeReadResponse(BaseModel):
    """Response type for GET /volume/{name}, GET /volume, POST /volume/{name}"""

    name: str = Field(description="Name of the volume", examples=["volume1"])
    created: datetime.datetime = Field(description="Creation timestamp of the volume", examples=["2023-10-01T12:00:00"])
    size: VolumeSize = Field(description="Size of the volume in bytes", examples=[1073741824], gt=0)
    used: int = Field(description="in-use count", examples=[0, 1])
    readonly: bool = Field(description="true if read-only", examples=[True, False])
    thin: bool = Field(description="true if thin volume", examples=[True, False])
    parent: str | None = Field(description="parent volname if snapshot")


class VolumeUpdateRequest(BaseModel):
    """Request type for POST /volume/{name}"""

    size: VolumeSize | None = Field(
        default=None, description="New size of the volume in bytes", examples=[2147483648], gt=0
    )
    readonly: bool | None = Field(default=None, description="Set volume to read-only if true", examples=[True, False])


class Filesystem(str, Enum):
    """supported filesystems"""

    ext4 = "ext4"
    xfs = "xfs"
    btrfs = "btrfs"
    vfat = "vfat"
    ntfs = "ntfs"
    exfat = "exfat"
    nilfs2 = "nilfs2"


class VolumeFormatRequest(BaseModel):
    """Request type for POST /volume/{name}/mkfs"""

    filesystem: Filesystem = Field(default=Filesystem.ext4, description="Make filesystem in the volume")
    label: str | None = Field(default=None, description="Label of filesystem")


class SnapshotCreateRequest(BaseModel):
    """Request type for POST /volume/{name}/snapshot"""

    name: str = Field(description="Name of snapshot volume", examples=["snap001", "snap002"])
    size: int | None = Field(default=None, description="Size of snapshot CoW (ignore if using thinpool)")


class PoolStats(BaseModel):
    """Response type for GET /stats/volume"""

    total: int = Field(description="Total size of the pool in bytes", examples=[10737418240])
    used: int = Field(description="Used size of the pool in bytes", examples=[5368709120])
    free: int = Field(description="Free size of the pool in bytes", examples=[5368709120])
    volumes: int = Field(description="Number of volumes in the pool", examples=[10])


@router.get("/volume", description="List all volumes")
def list_volume() -> list[VolumeReadResponse]:
    return [VolumeReadResponse.model_validate(x) for x in LV(config2.VG).volume_list()]


@router.post("/volume", description="Create a new volume")
def create_volume(arg: VolumeCreateRequest) -> VolumeCreateResponse:
    if config.LVM_THINPOOL:
        return VolumeCreateResponse.model_validate(
            LV(config2.VG, arg.name).create_thin(size=arg.size, thinpool=config.LVM_THINPOOL)
        )
    return VolumeCreateResponse.model_validate(LV(config2.VG, arg.name).create(size=arg.size))


@router.get("/volume/{name}", description="Read volume details by name")
def read_volume(name) -> VolumeReadResponse:
    res = LV(config2.VG, name).volume_read()
    if res is None:
        raise HTTPException(status_code=404, detail="volume not found")
    return VolumeReadResponse.model_validate(res)


@router.delete("/volume/{name}", description="Delete a volume by name")
def delete_volume(name) -> dict:
    LV(config2.VG, name).delete()
    return {}


@router.post("/volume/{name}/snapshot", description="Create snapshot")
def create_snapshot(name, arg: SnapshotCreateRequest) -> VolumeReadResponse:
    if config.LVM_THINPOOL:
        res = LV(config2.VG, arg.name).create_thinsnap(parent=name)
        return VolumeReadResponse.model_validate(res)
    assert arg.size
    res = LV(config2.VG, arg.name).create_snapshot(size=arg.size, parent=name)
    return VolumeReadResponse.model_validate(res)


@router.get("/volume/{name}/snapshot", description="List snapshot")
def list_snapshot(name) -> list[VolumeReadResponse]:
    return [VolumeReadResponse.model_validate(x) for x in LV(config2.VG).volume_list() if x.get("parent") == name]


@router.get("/volume/{name}/snapshot/{snapname}", description="Read snapshot")
def read_snapshot(name, snapname) -> VolumeReadResponse:
    # check if name is parent
    lv = LV(config2.VG, snapname)
    if lv.get_parent() != name:
        raise HTTPException(status_code=404, detail="volume not found")
    res = LV(config2.VG, snapname).volume_read()
    if res is None:
        raise HTTPException(status_code=404, detail="volume not found")
    return VolumeReadResponse.model_validate(res)


@router.delete("/volume/{name}/snapshot/{snapname}", description="Delete snapshot")
def delete_snapshot(name, snapname) -> dict:
    # check if name is parent
    LV(config2.VG, snapname).delete()
    return {}


@router.post("/volume/{name}", description="Update a volume by name")
def update_volume(name, arg: VolumeUpdateRequest) -> VolumeReadResponse:
    lv = LV(config2.VG, name)
    if arg.readonly is not None:
        lv.read_only(arg.readonly)
    if arg.size is not None:
        lv.resize(arg.size)
        try:
            Tgtd().refresh_volume_bypath(lv.volume_vol2path())
        except FileNotFoundError:
            # not exported
            pass
    return VolumeReadResponse.model_validate(lv.volume_read())


@router.post("/volume/{name}/mkfs", description="Format a volume, make filesystem")
def format_volume(name, arg: VolumeFormatRequest) -> VolumeReadResponse:
    lv = LV(config2.VG, name)
    lv.format_volume(arg.filesystem.value, arg.label)
    return VolumeReadResponse.model_validate(lv.volume_read())


@router.get("/stats/volume", description="Get statistics of the volume pool")
def stats_volume() -> PoolStats:
    info = VG(config2.VG).get()
    if info is None:
        raise HTTPException(status_code=404, detail="pool not found")
    vols = info.get("Cur LV", 0)
    pesize = int(info["PE Size"].removesuffix(" B"))
    total_pe = int(info["Total PE"])
    alloc_pe = int(info["Alloc PE / Size"].split()[0])
    free_pe = int(info["Free  PE / Size"].split()[0])
    return PoolStats(total=pesize * total_pe, used=pesize * alloc_pe, free=pesize * free_pe, volumes=vols)
