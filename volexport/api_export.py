from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .config import config
from .tgtd import Tgtd
from .lvm2 import LV

router = APIRouter()


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


def _fixpath(data: dict) -> dict:
    if "volumes" in data:
        data["volumes"] = [LV(config.VG).volume_path2vol(x) for x in data["volumes"]]
    return data


@router.get("/export")
def list_export() -> list[ExportReadResponse]:
    return [ExportReadResponse.model_validate(_fixpath(x)) for x in Tgtd().export_list()]


@router.post("/export")
def create_export(arg: ExportRequest) -> ExportResponse:
    filename = LV(config.VG, arg.volname).volume_vol2path()
    if arg.readonly:
        params = dict(params=dict(readonly="1"))
    else:
        params = {}
    return ExportResponse.model_validate(Tgtd().export_volume(filename=filename, acl=arg.acl, **params))


@router.get("/export/{name}")
def read_export(name) -> ExportReadResponse:
    res = [_fixpath(x) for x in Tgtd().export_list() if x["targetname"] == name or x["tid"] == name]
    if len(res) == 0:
        raise HTTPException(status_code=404, detail="export not found")
    return ExportReadResponse.model_validate(res[0])


@router.delete("/export/{name}")
def delete_export(name, force: bool = False):
    return Tgtd().unexport_volume(targetname=name, force=force)


@router.get("/address")
def get_address() -> list[str]:
    return Tgtd().myaddress()


@router.get("/stats/export")
def stats_export() -> ExportStats:
    info = Tgtd().export_list()
    return ExportStats(
        targets=len(info),
        clients=sum([len(x["connected"]) for x in info]),
        volumes=sum([len(x["volumes"]) for x in info]),
    )
