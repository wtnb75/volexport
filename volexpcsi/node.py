import grpc
import json
import subprocess
import shlex
from logging import getLogger
from google.protobuf.message import Message
from volexport.client import VERequest
from . import api
from .accesslog import servicer_accesslog

_log = getLogger(__name__)


@servicer_accesslog
class VolExpNode(api.NodeServicer):
    def __init__(self, config: dict):
        self.config = config
        self.req = VERequest(config["endpoint"])
        self.become_method: str | None = config.get("become_method")

    def _validate(self, request: Message):
        if hasattr(request, "volume_id"):
            if not getattr(request, "volume_id"):
                raise ValueError("empty volume id")

    def runcmd(self, cmd: list[str], root: bool = True):
        """Run a command"""
        _log.info("run %s, root=%s", cmd, root)
        if root and self.become_method:
            if self.become_method in ("su",):
                cmd = ["su", "-c", shlex.join(cmd)]
            elif self.become_method.lower() not in ("false", "none"):
                cmd[0:0] = shlex.split(self.become_method)
        res = subprocess.run(
            cmd,
            capture_output=True,
            encoding="utf-8",
            timeout=10.0,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        _log.info("returncode=%s, stdout=%s, stderr=%s", res.returncode, repr(res.stdout), repr(res.stderr))
        res.check_returncode()
        return res

    def iscsiadm(self, **kwargs):
        arg = ["iscsiadm"]
        for k, v in kwargs.items():
            if len(k) == 1:
                arg.append(f"-{k}")
            else:
                arg.append(f"--{k}")
            if v is not None:
                arg.append(v)
        return self.runcmd(arg, root=True)

    def NodeGetInfo(self, request: api.NodeGetInfoRequest, context: grpc.ServicerContext):
        return api.NodeGetInfoResponse(node_id=self.config["nodeid"])

    def NodeStageVolume(self, request: api.NodeStageVolumeRequest, context: grpc.ServicerContext):
        self._validate(request)
        # attach iscsi
        targetname = request.publish_context.get("targetname")
        username = request.publish_context.get("user")
        password = request.publish_context.get("passwd")
        addrs: list[str] = json.loads(request.publish_context.get("addresses", "[]"))
        self.iscsiadm(m="discovery", t="st", p=addrs[0])
        self.iscsiadm(m="node", T=targetname, o="update", n="node.session.auth.authmethod", v="CHAP")
        self.iscsiadm(m="node", T=targetname, o="update", n="node.session.auth.username", v=username)
        self.iscsiadm(m="node", T=targetname, o="update", n="node.session.auth.password", v=password)
        self.iscsiadm(m="node", T=targetname, l=None)
        return api.NodeStageVolumeResponse()

    def NodeUnstageVolume(self, request: api.NodeUnstageVolumeRequest, context: grpc.ServicerContext):
        self._validate(request)
        # detach iscsi
        res = self.req.get("/export", params=dict(volname=request.volume_id))
        res.raise_for_status()
        assert len(res.json()) == 1
        targetname = res.json()[0].get("targetname")
        res = self.iscsiadm(m="node", T=targetname, u=None)
        portal = None
        for line in res.stdout.splitlines():
            if line.endswith("successful."):
                portal = line.split("[", 1)[-1].split("]", 1)[0].rsplit(maxsplit=1)[-1]
                break
        if portal:
            self.iscsiadm(m="discoverydb", t="st", p=portal, o="delete")
        return api.NodeUnstageVolumeResponse()

    def NodePublishVolume(self, request: api.NodePublishVolumeRequest, context: grpc.ServicerContext):
        self._validate(request)
        # mount device
        res = self.runcmd(["mount", "-L", request.volume_id, request.target_path], root=True)
        res.check_returncode()
        return api.NodePublishVolumeResponse()

    def NodeUnpublishVolume(self, request: api.NodeUnpublishVolumeRequest, context: grpc.ServicerContext):
        self._validate(request)
        # umount device
        res = self.runcmd(["umount", request.target_path], root=True)
        res.check_returncode()
        return api.NodeUnpublishVolumeResponse()

    def NodeExpandVolume(self, request: api.NodeExpandVolumeRequest, context: grpc.ServicerContext):
        self._validate(request)
        res = self.runcmd(["blkid", "-L", request.volume_id])
        res.check_returncode()
        devname = res.stdout.strip()
        targetname = ""
        # rescan iscsi
        self.iscsiadm(m="node", T=targetname, R=None)
        # online resize
        self.runcmd(["resize2fs", devname], root=True)
        return api.NodeExpandVolumeResponse()

    def NodeGetCapabilities(self, request: api.NodeGetCapabilitiesRequest, context: grpc.ServicerContext):
        caps: list[api.NodeServiceCapability.RPC.Type] = [
            api.NodeServiceCapability.RPC.Type.STAGE_UNSTAGE_VOLUME,
            api.NodeServiceCapability.RPC.Type.EXPAND_VOLUME,
        ]
        return api.NodeGetCapabilitiesResponse(
            capabilities=[api.NodeServiceCapability(rpc=api.NodeServiceCapability.RPC(type=x)) for x in caps]
        )

    def NodeGetVolumeStats(self, request: api.NodeGetVolumeStatsRequest, context: grpc.ServicerContext):
        self._validate(request)
        # df
        return api.NodeGetVolumeStatsResponse()
