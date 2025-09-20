import grpc
from logging import getLogger
from volexport.client import VERequest
from google.protobuf.message import Message
from google.protobuf.json_format import MessageToDict
from . import api
from .accesslog import servicer_accesslog

_log = getLogger(__name__)


@servicer_accesslog
class VolExpControl(api.ControllerServicer):
    def __init__(self, config: dict):
        self.config = config
        self.req = VERequest(config["endpoint"])

    def _validate(self, request: Message):
        if hasattr(request, "volume_id"):
            if not getattr(request, "volume_id"):
                raise ValueError("volume id is empty")

    def GetCapacity(self, request: api.GetCapacityRequest, context: grpc.ServicerContext):
        res = self.req.get("/stats/volume")
        res.raise_for_status()
        resj = res.json()
        return api.GetCapacityResponse(available_capacity=resj["free"])

    def ControllerGetCapabilities(self, request: api.ControllerGetCapabilitiesRequest, context: grpc.ServicerContext):
        caps: list[api.ControllerServiceCapability.RPC.Type] = [
            api.ControllerServiceCapability.RPC.CREATE_DELETE_VOLUME,
            api.ControllerServiceCapability.RPC.PUBLISH_UNPUBLISH_VOLUME,
            api.ControllerServiceCapability.RPC.LIST_VOLUMES,
            api.ControllerServiceCapability.RPC.EXPAND_VOLUME,
            api.ControllerServiceCapability.RPC.GET_CAPACITY,
            api.ControllerServiceCapability.RPC.GET_VOLUME,
            api.ControllerServiceCapability.RPC.PUBLISH_READONLY,
            # api.ControllerServiceCapability.RPC.MODIFY_VOLUME,
            # api.ControllerServiceCapability.RPC.GET_SNAPSHOT,
        ]
        res: list[api.ControllerServiceCapability] = [
            api.ControllerServiceCapability(rpc=api.ControllerServiceCapability.RPC(type=typ)) for typ in caps
        ]
        return api.ControllerGetCapabilitiesResponse(capabilities=res)

    def ListVolumes(self, request: api.ListVolumesRequest, context: grpc.ServicerContext):
        vols = self.req.get("/volume")
        vols.raise_for_status()
        res: list[api.ListVolumesResponse.Entry] = []
        flag = True
        if request.starting_token:
            if not request.starting_token.startswith("vol-"):
                raise AssertionError(f"invalid starting token: {request.starting_token}")
            flag = False
        next_entry: str | None = None
        for vol in vols.json():
            if request.max_entries and request.max_entries < len(res):
                next_entry = vol["name"]
                break
            if not flag and vol["name"] == request.starting_token.removeprefix("vol-"):
                flag = True
            if not flag:
                continue
            vent = api.Volume(
                volume_id=vol.get("name"),
                capacity_bytes=vol.get("size"),
            )
            stat = api.ListVolumesResponse.VolumeStatus(
                volume_condition=api.VolumeCondition(abnormal=False),
                published_node_ids=vol.get("addresses", []),
            )
            ent = api.ListVolumesResponse.Entry(volume=vent, status=stat)
            res.append(ent)
        if next_entry:
            return api.ListVolumesResponse(entries=res, next_token="vol-" + next_entry)
        return api.ListVolumesResponse(entries=res)

    def CreateVolume(self, request: api.CreateVolumeRequest, context: grpc.ServicerContext):
        self._validate(request)
        if not request.name:
            raise ValueError("no volume name")
        if not request.capacity_range.required_bytes:
            raise ValueError("no capacity specified")
        chk = self.req.get(f"/volume/{request.name}")
        if chk.status_code == 200:
            volsize = chk.json()["size"]
            if request.capacity_range.required_bytes and volsize < request.capacity_range.required_bytes:
                raise FileExistsError("volume already exists(short)")
            if request.capacity_range.limit_bytes and request.capacity_range.limit_bytes < volsize:
                raise FileExistsError("volume already exists(too large)")
            return api.CreateVolumeResponse(volume=api.Volume(capacity_bytes=volsize, volume_id=request.name))
        res = self.req.post(
            "/volume",
            json=dict(
                name=request.name,
                size=request.capacity_range.required_bytes,
            ),
        )
        res.raise_for_status()
        resj = res.json()
        volname = resj["name"]
        mkfsres = self.req.post(f"/volume/{volname}/mkfs", json=dict())
        mkfsres.raise_for_status()
        return api.CreateVolumeResponse(
            volume=api.Volume(
                capacity_bytes=resj["size"],
                volume_id=resj["name"],
            )
        )

    def DeleteVolume(self, request: api.DeleteVolumeRequest, context: grpc.ServicerContext):
        self._validate(request)
        res = self.req.delete(f"/volume/{request.volume_id}")
        if res.status_code == 404:
            _log.info("delete not found: %s", request.volume_id)
            return api.DeleteSnapshotRequest()
        res.raise_for_status()
        return api.DeleteVolumeResponse()

    def ControllerPublishVolume(self, request: api.ControllerPublishVolumeRequest, context: grpc.ServicerContext):
        self._validate(request)
        if not request.node_id:
            raise ValueError("no node_id")
        if not MessageToDict(request.volume_capability):
            raise ValueError("no capability")
        # if request.volume_capability.access_mode not in (api.VolumeCapability.AccessMode.SINGLE_NODE_WRITER,):
        #     raise ValueError("invalid mode")
        if not request.volume_capability.mount:
            raise ValueError("invalid type")
        res = self.req.post("/export", json=dict(name=request.volume_id, readonly=request.readonly, acl=None))
        res.raise_for_status()
        resj = res.json()
        ctxt = {k: str(v) for k, v in resj.items()}
        return api.ControllerPublishVolumeResponse(publish_context=ctxt)

    def ControllerUnpublishVolume(self, request: api.ControllerUnpublishVolumeRequest, context: grpc.ServicerContext):
        self._validate(request)
        qres = self.req.get("/export", params=dict(volume=request.volume_id))
        qres.raise_for_status()
        for tgt in qres.json():
            if request.volume_id not in tgt["volumes"]:
                _log.warning("export response: volume_id=%s, tgt=%s", request.volume_id, tgt)
                continue
            tgtname = tgt["targetname"]
            res = self.req.delete(f"/export/{tgtname}")
            res.raise_for_status()
        return api.ControllerUnpublishVolumeResponse()

    def ControllerExpandVolume(self, request: api.ControllerExpandVolumeRequest, context: grpc.ServicerContext):
        self._validate(request)
        res = self.req.post(f"/volume/{request.volume_id}", json=dict(size=request.capacity_range.required_bytes))
        res.raise_for_status()
        return api.ControllerExpandVolumeResponse(capacity_bytes=res.json()["size"], node_expansion_required=True)

    def ControllerGetVolume(self, request: api.ControllerGetVolumeRequest, context: grpc.ServicerContext):
        self._validate(request)
        res = self.req.get(f"/volume/{request.volume_id}")
        res.raise_for_status()
        resj = res.json()
        qres = self.req.get("/export", params=dict(volume=request.volume_id))
        qres.raise_for_status()
        qresj = res.json()
        nodes = []
        for i in qresj:
            nodes.extend(i["connected"]["address"])
        return api.ControllerGetVolumeResponse(
            volume=api.Volume(
                capacity_bytes=resj["size"],
                volume_id=resj["name"],
            ),
            status=api.ControllerGetVolumeResponse.VolumeStatus(
                published_node_ids=nodes, volume_condition=api.VolumeCondition(abnormal=False)
            ),
        )

    def ControllerModifyVolume(self, request: api.ControllerModifyVolumeRequest, context: grpc.ServicerContext):
        self._validate(request)
        return super().ControllerModifyVolume(request, context)

    def ValidateVolumeCapabilities(self, request: api.ValidateVolumeCapabilitiesRequest, context: grpc.ServicerContext):
        self._validate(request)
        if not request.volume_capabilities:
            raise ValueError("no capabilities")
        res = self.req.get(f"/volume/{request.volume_id}")
        if res.status_code != 200:
            raise FileNotFoundError(f"volume not found: {request.volume_id}")
        supported_mode = [
            api.VolumeCapability.AccessMode.Mode.SINGLE_NODE_WRITER,
        ]
        caps: list[api.VolumeCapability] = []
        for cap in request.volume_capabilities:
            if cap.access_mode.mode in supported_mode:
                caps.append(cap)
        return api.ValidateVolumeCapabilitiesResponse(
            confirmed=api.ValidateVolumeCapabilitiesResponse.Confirmed(
                volume_capabilities=caps,
                parameters=request.parameters,
                mutable_parameters=request.mutable_parameters,
            ),
        )

    def ListSnapshots(self, request: api.ListSnapshotsRequest, context: grpc.ServicerContext):
        return super().ListSnapshots(request, context)

    def CreateSnapshot(self, request: api.CreateSnapshotRequest, context: grpc.ServicerContext):
        return super().CreateSnapshot(request, context)

    def DeleteSnapshot(self, request: api.DeleteSnapshotRequest, context: grpc.ServicerContext):
        return super().DeleteSnapshot(request, context)

    def GetSnapshot(self, request: api.GetSnapshotRequest, context: grpc.ServicerContext):
        return super().GetSnapshot(request, context)
