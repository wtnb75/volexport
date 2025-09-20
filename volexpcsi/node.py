import grpc
import subprocess
import shlex
from pathlib import Path
from logging import getLogger
from google.protobuf.message import Message
from google.protobuf.json_format import MessageToDict
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
        notempty = {"volume_id", "target_path"}
        for i in notempty:
            if hasattr(request, i):
                if not getattr(request, i):
                    raise ValueError(f"empty {i}")

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
        if not request.staging_target_path:
            raise ValueError("no staging target path")
        if not MessageToDict(request.volume_capability):
            raise ValueError("no capability")
        # attach iscsi
        targetname = request.publish_context.get("targetname")
        username = request.publish_context.get("user")
        password = request.publish_context.get("passwd")
        addrs = self.req.get("/address").json()
        self.iscsiadm(m="discovery", t="st", p=addrs[0])
        self.iscsiadm(m="node", T=targetname, o="update", n="node.session.auth.authmethod", v="CHAP")
        self.iscsiadm(m="node", T=targetname, o="update", n="node.session.auth.username", v=username)
        self.iscsiadm(m="node", T=targetname, o="update", n="node.session.auth.password", v=password)
        try:
            self.iscsiadm(m="node", T=targetname, l=None)
        except subprocess.CalledProcessError as e:
            if e.returncode == 15 and "already present" in e.stderr:
                _log.info("alread logged in: %s", targetname)
            else:
                raise
        return api.NodeStageVolumeResponse()

    def NodeUnstageVolume(self, request: api.NodeUnstageVolumeRequest, context: grpc.ServicerContext):
        self._validate(request)
        if not request.staging_target_path:
            raise ValueError("no staging target path")
        # detach iscsi
        res = self.req.get("/export", params=dict(volume=request.volume_id))
        res.raise_for_status()
        for tgt in res.json():
            if request.volume_id not in tgt["volumes"]:
                _log.warning("export response: volume_id=%s, tgt=%s", request.volume_id, tgt)
                continue
            targetname = tgt.get("targetname")
            portal = None
            try:
                cmdres = self.iscsiadm(m="node", T=targetname, u=None)
                for line in cmdres.stdout.splitlines():
                    if line.endswith("successful."):
                        portal = line.split("[", 1)[-1].split("]", 1)[0].rsplit(maxsplit=1)[-1]
                        break
            except subprocess.CalledProcessError as e:
                if e.returncode == 21 and "No matching sessions found" in e.stderr:
                    _log.info("already logout? %s", targetname)
                    pass
                else:
                    raise
            if portal:
                self.iscsiadm(m="discoverydb", t="st", p=portal, o="delete")
        return api.NodeUnstageVolumeResponse()

    def NodePublishVolume(self, request: api.NodePublishVolumeRequest, context: grpc.ServicerContext):
        self._validate(request)
        if not MessageToDict(request.volume_capability):
            raise ValueError("no capability")
        # mount device
        p = Path(request.target_path)
        if not p.exists():
            p.mkdir()
        try:
            self.runcmd(["mount", "-L", request.volume_id[:16], request.target_path], root=True)
        except subprocess.CalledProcessError as e:
            if e.returncode == 32 and "already mounted" in e.stderr:
                _log.info("alread mounted: %s", request.volume_id)
            else:
                raise
        return api.NodePublishVolumeResponse()

    def NodeUnpublishVolume(self, request: api.NodeUnpublishVolumeRequest, context: grpc.ServicerContext):
        self._validate(request)
        p = Path(request.target_path)
        if p.is_mount():
            # umount device
            self.runcmd(["umount", request.target_path], root=True)
            p.rmdir()
        else:
            raise FileNotFoundError(f"target path is not mounted: {request.target_path}")
        return api.NodeUnpublishVolumeResponse()

    def NodeExpandVolume(self, request: api.NodeExpandVolumeRequest, context: grpc.ServicerContext):
        self._validate(request)
        if not request.volume_path:
            raise ValueError("no volume path")
        try:
            res = self.runcmd(["blkid", "-L", request.volume_id[:16]])
        except subprocess.CalledProcessError:
            raise FileNotFoundError(f"volume not found: {request.volume_id}")
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
