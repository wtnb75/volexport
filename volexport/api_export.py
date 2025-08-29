from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from .config2 import config2
from .tgtd import Tgtd
from .lvm2 import LV

router = APIRouter()


class ExportRequest(BaseModel):
    volname: str = Field(description="Volume name to export", examples=["volume1"])
    acl: list[str] | None = Field(description="Source IP Addresses to allow access")
    readonly: bool = Field(default=False, description="read-only if true", examples=[True, False])


class ExportResponse(BaseModel):
    protocol: str = Field(description="access protocol", examples=["iscsi"])
    addresses: list[str] = Field(description="IP addresses of the target")
    targetname: str = Field(description="target name", examples=["iqn.2025-08.volexport:abcde"])
    tid: int = Field(description="target ID")
    user: str = Field(description="user name for access", examples=["admin"])
    passwd: str = Field(description="password for access", examples=["password123"])
    lun: int = Field(description="LUN number", examples=[1, 2, 3])
    acl: list[str] = Field(description="Access Control List (ACL) for the export")


class ClientInfo(BaseModel):
    address: list[str] = Field(description="IP addresses of the client")
    initiator: str = Field(description="Initiator name", examples=["iqn.2025-08.volimport:client1"])


class ExportReadResponse(BaseModel):
    protocol: str = Field(description="access protocol", examples=["iscsi"])
    connected: list[ClientInfo] = Field(description="List of connected clients")
    targetname: str = Field(description="target name", examples=["iqn.2025-08.volexport:abcde"])
    tid: int = Field(description="target ID")
    volumes: list[str] = Field(description="List of volumes exported", examples=["volume1"])
    users: list[str] = Field(description="List of users with access", examples=["admin", "user1"])
    acl: list[str] = Field(description="Access Control List (ACL) for the export")


class ExportStats(BaseModel):
    targets: int = Field(description="Number of export targets", examples=[5])
    clients: int = Field(description="Number of connected clients", examples=[10])
    volumes: int = Field(description="Number of volumes exported", examples=[15])


def _fixpath(data: dict) -> dict:
    if "volumes" in data:
        data["volumes"] = [LV(config2.VG).volume_path2vol(x) for x in data["volumes"]]
    return data


@router.get("/export", description="List all exports")
def list_export() -> list[ExportReadResponse]:
    return [ExportReadResponse.model_validate(_fixpath(x)) for x in Tgtd().export_list()]


@router.post("/export", description="Create a new export")
def create_export(req: Request, arg: ExportRequest) -> ExportResponse:
    filename = LV(config2.VG, arg.volname).volume_vol2path()
    if not arg.acl:
        assert req.client is not None
        arg.acl = [req.client.host]
    return ExportResponse.model_validate(Tgtd().export_volume(filename=filename, acl=arg.acl, readonly=arg.readonly))


@router.get("/export/{name}", description="Read export details by name or TID")
def read_export(name) -> ExportReadResponse:
    res = [_fixpath(x) for x in Tgtd().export_list() if x["targetname"] == name or x["tid"] == name]
    if len(res) == 0:
        raise HTTPException(status_code=404, detail="export not found")
    return ExportReadResponse.model_validate(res[0])


@router.delete("/export/{name}", description="Delete an export by name or TID")
def delete_export(name, force: bool = False):
    return Tgtd().unexport_volume(targetname=name, force=force)


@router.get("/address", description="Get addresses of the target")
def get_address() -> list[str]:
    return Tgtd().myaddress()


@router.get("/stats/export", description="Get statistics of exports")
def stats_export() -> ExportStats:
    info = Tgtd().export_list()
    return ExportStats(
        targets=len(info),
        clients=sum([len(x["connected"]) for x in info]),
        volumes=sum([len(x["volumes"]) for x in info]),
    )
