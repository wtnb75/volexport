import grpc
from concurrent import futures
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from grpc_reflection.v1alpha import reflection
from logging import getLogger
from . import api
from .identity import VolExpIdentity
from .controller import VolExpControl
from .node import VolExpNode

_log = getLogger(__name__)


def boot_server(hostport: str, config: dict, cred: grpc.ServerCredentials | None = None):
    _log.info("booting server at %s", hostport)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=config.get("max_workers")))
    health_pb2_grpc.add_HealthServicer_to_server(health.HealthServicer(), server)
    api.add_IdentityServicer_to_server(VolExpIdentity(config), server)
    api.add_ControllerServicer_to_server(VolExpControl(config), server)
    api.add_NodeServicer_to_server(VolExpNode(config), server)
    SERVICE_NAMES = (
        health_pb2.DESCRIPTOR.services_by_name["Health"].full_name,
        reflection.SERVICE_NAME,
        api.DESCRIPTOR.services_by_name["Identity"].full_name,
        api.DESCRIPTOR.services_by_name["Controller"].full_name,
        # api.DESCRIPTOR.services_by_name["GroupController"].full_name,
        # api.DESCRIPTOR.services_by_name["SnapshotMetadata"].full_name,
        api.DESCRIPTOR.services_by_name["Node"].full_name,
    )
    reflection.enable_server_reflection(SERVICE_NAMES, server)
    if cred:
        port = server.add_secure_port(hostport, cred)
    else:
        port = server.add_insecure_port(hostport)
    server.start()
    return port, server
