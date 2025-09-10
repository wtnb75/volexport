import grpc
import requests
from volexport.version import VERSION
from volexport.client import VERequest
from google.protobuf import wrappers_pb2
from logging import getLogger
from . import api
from .accesslog import servicer_accesslog

_log = getLogger(__name__)


@servicer_accesslog
class VolExpIdentity(api.IdentityServicer):
    def __init__(self, config: dict):
        self.config = config
        self.req = VERequest(config["endpoint"])

    def GetPluginInfo(self, request: api.GetPluginInfoRequest, context: grpc.ServicerContext):
        return api.GetPluginInfoResponse(name="volexport", vendor_version=VERSION)

    def GetPluginCapabilities(self, request: api.GetPluginCapabilitiesRequest, context: grpc.ServicerContext):
        return api.GetPluginCapabilitiesResponse(
            capabilities=[
                api.PluginCapability(
                    service=api.PluginCapability.Service(
                        type=api.PluginCapability.Service.Type.CONTROLLER_SERVICE,
                    )
                ),
                api.PluginCapability(
                    volume_expansion=api.PluginCapability.VolumeExpansion(
                        type=api.PluginCapability.VolumeExpansion.Type.ONLINE,
                    )
                ),
            ]
        )

    def Probe(self, request: api.ProbeRequest, context: grpc.ServicerContext):
        try:
            res = self.req.get("/health")
            if res.status_code == requests.codes.ok:
                return api.ProbeResponse(ready=wrappers_pb2.BoolValue(value=True))
        except Exception as e:
            _log.warning("health check error", exc_info=e)
        return api.ProbeResponse(ready=wrappers_pb2.BoolValue(value=False))
