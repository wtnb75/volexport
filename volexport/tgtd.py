from urllib.parse import urlsplit
from socket import AF_INET6, AF_INET
import shlex
import secrets
import ifaddr
import tempfile
from pathlib import Path
from logging import getLogger
from typing import Sequence
from .config import config
from .util import runcmd

_log = getLogger(__name__)


class Tgtd:
    """Class to manage tgtadm operations for stgt"""

    def __init__(self):
        self.lld = "iscsi"

    def parse(self, lines: Sequence[str]):
        """Parse the output of tgtadm"""

        def linegen(lines: Sequence[str]):
            for line in lines:
                indent = len(line) - len(line.lstrip())
                if " (" in line:
                    kv = line[indent:].split("(", 1)
                    if len(kv) == 2:
                        v = kv[1].strip(" )")
                        if v == "":
                            v = None
                        yield {"indent": indent, "key": kv[0].strip(), "value": v}
                    elif len(kv) == 1:
                        yield {"indent": indent, "key": kv[0].strip()}
                elif ":" in line or "=" in line:
                    kv = line[indent:].split(":", 1)
                    if len(kv) == 1:
                        kv = line[indent:].split("=", 1)
                    if len(kv) == 2:
                        k = kv[0].strip()
                        v = kv[1].strip()
                        if v == "":
                            v = None
                        if k in ("LUN", "I_T nexus", "Connection", "Session"):  # special case
                            k = f"{k} {v}"
                        yield {"indent": indent, "key": k, "value": v}
                elif len(line[indent:]) != 0:
                    yield {"indent": indent, "key": line[indent:].strip()}

        res = {}
        levels: list[str] = []
        for node in linegen(lines):
            assert node["indent"] % 4 == 0
            level = int(node["indent"] / 4)
            _log.debug("node %s, level=%s", node, level)
            # select target
            target = res
            for k in levels[:level]:
                if target.get(k) is None:
                    target[k] = {}
                if isinstance(target[k], dict):
                    target = target[k]
                else:
                    target[k] = {"name": target[k]}
                    target = target[k]
            levels = levels[:level]
            levels.append(node["key"])
            target[node["key"]] = node.get("value")
            _log.debug("levels: %s, res=%s", levels, res)
        return res

    def tgtadm(self, **kwargs):
        """Run tgtadm command with given parameters"""
        cmd = shlex.split(config.TGTADM_BIN)
        for k, v in kwargs.items():
            if len(k) == 1:
                cmd.append(f"-{k}")
            else:
                cmd.append(f"--{k.replace('_', '-')}")
            if v is not None:
                if isinstance(v, dict):
                    cmd.append(",".join([f"{kk}={vv}" for kk, vv in v.items()]))
                else:
                    cmd.append(str(v))
        return runcmd(cmd, True)

    def target_create(self, tid: int, name: str):
        """Create a new target with the given TID and name"""
        return self.tgtadm(lld=self.lld, mode="target", op="new", tid=tid, targetname=name)

    def target_delete(self, tid: int, force: bool = False):
        """Delete a target by TID"""
        if force:
            return self.tgtadm(lld=self.lld, mode="target", op="delete", force=None, tid=tid)
        return self.tgtadm(lld=self.lld, mode="target", op="delete", tid=tid)

    def target_list(self):
        """List all targets"""
        return self.parse(self.tgtadm(lld=self.lld, mode="target", op="show").stdout.splitlines())

    def target_show(self, tid: int):
        """Show details of a target by TID"""
        return self.parse(self.tgtadm(lld=self.lld, mode="target", op="show", tid=tid).stdout.splitlines())

    def target_update(self, tid: int, param, value):
        """Update a target parameter by TID"""
        return self.tgtadm(lld=self.lld, mode="target", op="update", tid=tid, name=param, value=value)

    def target_bind_address(self, tid: int, addr):
        """Bind a target to an initiator address"""
        return self.tgtadm(lld=self.lld, mode="target", op="bind", tid=tid, initiator_address=addr)

    def target_bind_name(self, tid: int, name):
        """Bind a target to an initiator name"""
        return self.tgtadm(lld=self.lld, mode="target", op="bind", tid=tid, initiator_name=name)

    def target_unbind_address(self, tid: int, addr):
        """Unbind a target from an initiator address"""
        return self.tgtadm(lld=self.lld, mode="target", op="unbind", tid=tid, initiator_address=addr)

    def target_unbind_name(self, tid: int, name):
        """Unbind a target from an initiator name"""
        return self.tgtadm(lld=self.lld, mode="target", op="unbind", tid=tid, initiator_name=name)

    def lun_create(self, tid: int, lun: int, path: str, **kwargs):
        """Create a new logical unit (LUN) for a target"""
        return self.tgtadm(lld=self.lld, mode="logicalunit", op="new", tid=tid, lun=lun, backing_store=path, **kwargs)

    def lun_update(self, tid: int, lun: int, **kwargs):
        """Update an existing logical unit (LUN) for a target"""
        return self.tgtadm(lld=self.lld, mode="logicalunit", op="update", tid=tid, lun=lun, params=kwargs)

    def lun_delete(self, tid: int, lun: int):
        """Delete a logical unit (LUN) from a target"""
        return self.tgtadm(lld=self.lld, mode="logicalunit", op="delete", tid=tid, lun=lun)

    def account_create(self, user: str, password: str, outgoing: bool = False):
        """Create a new account for a target"""
        if outgoing:
            return self.tgtadm(lld=self.lld, mode="account", op="new", user=user, password=password, outgoing=None)
        return self.tgtadm(lld=self.lld, mode="account", op="new", user=user, password=password)

    def account_list(self):
        """List all accounts for the target"""
        return self.parse(self.tgtadm(lld=self.lld, mode="account", op="show").stdout.splitlines())

    def account_delete(self, user: str, outgoing: bool = False):
        """Delete an account from the target"""
        if outgoing:
            return self.tgtadm(lld=self.lld, mode="account", op="delete", user=user, outgoing=None)
        return self.tgtadm(lld=self.lld, mode="account", op="delete", user=user)

    def account_bind(self, tid: int, user: str):
        """Bind an account to a target"""
        return self.tgtadm(lld=self.lld, mode="account", op="bind", tid=tid, user=user)

    def account_unbind(self, tid: int, user: str):
        """Unbind an account from a target"""
        return self.tgtadm(lld=self.lld, mode="account", op="unbind", tid=tid, user=user)

    def lld_start(self):
        """Start the LLD"""
        return self.tgtadm(lld=self.lld, mode="lld", op="start")

    def lld_stop(self):
        """Stop the LLD"""
        return self.tgtadm(lld=self.lld, mode="lld", op="stop")

    def sys_show(self):
        """Get system information"""
        return self.parse(self.tgtadm(mode="sys", op="show").stdout.splitlines())

    def sys_set(self, name, value):
        """Set a system parameter"""
        return self.tgtadm(mode="sys", op="update", name=name, value=value)

    def sys_ready(self):
        """Set the system state to ready"""
        return self.tgtadm(mode="sys", op="update", name="State", value="ready")

    def sys_offline(self):
        """Set the system state to offline"""
        return self.tgtadm(mode="sys", op="update", name="State", value="offline")

    def portal_list(self):
        """List all portals"""
        return [
            x.split(":", 1)[-1].strip()
            for x in self.tgtadm(lld=self.lld, mode="portal", op="show").stdout.splitlines()
            if x.startswith("Portal:")
        ]

    def portal_add(self, hostport):
        """Add a new portal"""
        return self.tgtadm(lld=self.lld, mode="portal", op="new", param=dict(portal=hostport))

    def portal_delete(self, hostport):
        """Delete a portal"""
        return self.tgtadm(lld=self.lld, mode="portal", op="delete", param=dict(portal=hostport))

    def list_session(self, tid: int):
        """List all sessions for a target"""
        return self.parse(self.tgtadm(lld=self.lld, mode="conn", op="show", tid=tid).stdout.splitlines())

    def disconnect_session(self, tid: int, sid: int, cid: int):
        """Disconnect a session by TID, SID, and CID"""
        return self.tgtadm(lld=self.lld, mode="conn", op="delete", tid=tid, sid=sid, cid=cid)

    def myaddress(self):
        """Get the addresses of the target"""
        portal_addrs = [x.removesuffix(",1") for x in self.portal_list()]
        res = []
        ifaddrs = {AF_INET: [], AF_INET6: []}
        for adapter in ifaddr.get_adapters():
            _log.debug("check %s / %s", adapter, config.NICS)
            if adapter.name in config.NICS:
                _log.debug("adapter %s", adapter.name)
                for ip in adapter.ips:
                    if isinstance(ip.ip, tuple):
                        if ip.ip[2] != 0:
                            # scope id (is link local address)
                            continue
                        addr = ip.ip[0]
                    else:
                        addr = ip.ip
                    if ip.is_IPv4:
                        ifaddrs[AF_INET].append(addr)
                    elif ip.is_IPv6:
                        ifaddrs[AF_INET6].append(addr)
        _log.debug("ifaddrs: %s", ifaddrs)
        for a in portal_addrs:
            u = urlsplit("//" + a)
            port = u.port or 3260
            _log.warning("url: %s (hostname=%s)", u, u.hostname)
            if u.hostname == "0.0.0.0":
                _log.warning("v4 address: %s", ifaddrs[AF_INET])
                # all v4 addr
                res.extend([f"{x}:{port}" for x in ifaddrs[AF_INET]])
            elif u.hostname == "::":
                _log.warning("v6 address: %s", ifaddrs[AF_INET6])
                # all v6 addr
                res.extend([f"[{x}]:{port}" for x in ifaddrs[AF_INET6] if "%" not in x])
        return res

    # tgt-admin operations
    def dump(self):
        """Dump the current configuration"""
        res = runcmd(["tgt-admin", "--dump"], root=True)
        return res.stdout

    def restore(self, data: str):
        """Restore configuration from the given data"""
        with tempfile.NamedTemporaryFile("r+") as tf:
            tf.write(data)
            tf.flush()
            res = runcmd(["tgt-admin", "-c", tf.name, "-e"], root=True)
            return res.stdout

    # compound operation
    def export_list(self):
        """List all exports"""
        res = []
        for tgtid, tgtinfo in self.target_list().items():
            if tgtinfo is None:
                continue
            tgtid = tgtid.removeprefix("Target ")
            name = tgtinfo["name"]
            itn = tgtinfo.get("I_T nexus information", {})
            connected_from = []
            if itn is not None:
                addrs = []
                for itnv in itn.values():
                    addrs.extend([v.get("IP Address") for k, v in itnv.items() if k.startswith("Connection")])
                connected_from = [
                    {
                        "address": addrs,
                        "initiator": x.get("Initiator").split(" ")[0],
                    }
                    for x in itn.values()
                ]
            luns = tgtinfo.get("LUN information", {})
            volumes = []
            for lun in luns.values():
                if lun["Type"] == "controller":
                    continue
                volumes.append(lun["Backing store path"])
            accounts = list(tgtinfo.get("Account information", {}).keys())
            acls = list(tgtinfo.get("ACL information", {}).keys())
            res.append(
                dict(
                    protocol=self.lld,
                    tid=tgtid,
                    targetname=name,
                    connected=connected_from,
                    volumes=volumes,
                    users=accounts,
                    acl=acls,
                )
            )
        return res

    def export_volume(self, filename: str, acl: list[str], readonly: bool = False):
        """Export a volume by its filename with specified ACL and read-only option"""
        assert Path(filename).exists()
        iqname = secrets.token_hex(10)
        tgts = [x.removeprefix("Target ") for x in self.target_list().keys() if x.startswith("Target ")]
        _log.debug("existing target: %s", tgts)
        tgts.append("0")
        max_tgt = max([int(x) for x in tgts])
        tid = max_tgt + 1
        lun = 1
        name = f"{config.IQN_BASE}:{iqname}"
        user = secrets.token_hex(10)
        passwd = secrets.token_hex(20)
        self.target_create(tid=tid, name=name)
        opts = {}
        if config.TGT_BSOPTS:
            opts["bsopts"] = config.TGT_BSOPTS
        if config.TGT_BSOFLAGS:
            opts["bsoflags"] = config.TGT_BSOFLAGS
        if readonly:
            opts["params"] = dict(readonly=1)
        self.lun_create(tid=tid, lun=lun, path=filename, bstype=config.TGT_BSTYPE, **opts)
        self.account_create(user=user, password=passwd)
        self.account_bind(tid=tid, user=user)
        for addr in acl:
            self.target_bind_address(tid=tid, addr=addr)
        addrs = self.myaddress()
        return dict(
            protocol=self.lld,
            addresses=addrs,  # list of host:port
            targetname=name,
            tid=tid,
            user=user,
            passwd=passwd,
            lun=lun,
            acl=acl,
        )

    def refresh_volume(self, tid: int, lun: int):
        for tgtid, tgtinfo in self.target_list().items():
            if tgtinfo is None:
                continue
            tgtid = tgtid.removeprefix("Target ")
            if int(tgtid) != tid:
                continue
            luns = tgtinfo.get("LUN information", {})
            for lunid, luninfo in luns.items():
                lunid = lunid.removeprefix("LUN ")
                if int(lunid) != lun:
                    continue
                _log.info("found lun: tid=%s, lun=%s, info=%s", tgtid, lunid, luninfo)
                pathname = luninfo["Backing store path"]
                readonly = luninfo["Readonly"] in ("Yes",)
                opts = {}
                if config.TGT_BSOPTS:
                    opts["bsopts"] = config.TGT_BSOPTS
                if config.TGT_BSOFLAGS:
                    opts["bsoflags"] = config.TGT_BSOFLAGS
                if readonly:
                    opts["params"] = dict(readonly=1)
                self.lun_delete(tid=tid, lun=lun)
                self.lun_create(tid=tid, lun=lun, path=pathname, bstype=config.TGT_BSTYPE, **opts)
                return

    def refresh_volume_bypath(self, pathname: str):
        for tgtid, tgtinfo in self.target_list().items():
            if tgtinfo is None:
                continue
            tgtid = tgtid.removeprefix("Target ")
            luns = tgtinfo.get("LUN information", {})
            for lunid, luninfo in luns.items():
                lunid = lunid.removeprefix("LUN ")
                bs_pathname = luninfo["Backing store path"]
                if bs_pathname != pathname:
                    continue
                _log.info("found lun: tid=%s, lun=%s, info=%s", tgtid, lunid, luninfo)
                readonly = luninfo["Readonly"] in ("Yes",)
                opts = {}
                if config.TGT_BSOPTS:
                    opts["bsopts"] = config.TGT_BSOPTS
                if config.TGT_BSOFLAGS:
                    opts["bsoflags"] = config.TGT_BSOFLAGS
                if readonly:
                    opts["params"] = dict(readonly=1)
                self.lun_delete(tid=int(tgtid), lun=int(lunid))
                self.lun_create(tid=int(tgtid), lun=int(lunid), path=pathname, bstype=config.TGT_BSTYPE, **opts)

    def get_export_bypath(self, filename: str):
        """Get export details by volume path"""
        res = self.export_list()
        for tgt in res:
            if filename in tgt.get("volumes"):
                return tgt

    def get_export_byname(self, targetname: str):
        """Get export details by target name"""
        res = self.export_list()
        for tgt in res:
            if targetname == tgt.get("targetname"):
                return tgt

    def unexport_volume(self, targetname: str, force: bool = False):
        """Unexport a volume by target name"""
        info = self.target_list()
        for tgtidstr, data in info.items():
            if data.get("name") != targetname:
                continue
            tgtid = int(tgtidstr.split()[-1])
            itn = data.get("I_T nexus information")
            if itn is not None:
                _log.warning("client connected: %s", itn)
                if not force:
                    addrs = [x.get("Connection", {}).get("IP Address") for x in itn.values()]
                    raise FileExistsError(f"client connected: {addrs}")
            try:
                accounts = data.get("Account information", {})
                if accounts is not None:
                    for acct in accounts.keys():
                        self.account_unbind(tid=tgtid, user=acct)
                        self.account_delete(user=acct)
                acls = data.get("ACL information", {})
                if acls is not None:
                    for acl in acls.keys():
                        self.target_unbind_address(tid=tgtid, addr=acl)
                luns = data.get("LUN information", {})
                if luns is not None:
                    for lun in sorted(
                        data.get("LUN information", {}).values(), key=lambda f: int(f["name"]), reverse=True
                    ):
                        if lun.get("Type") != "controller":
                            lunid = int(lun["name"])
                            self.lun_delete(tid=tgtid, lun=lunid)
            except Exception:
                if not force:
                    raise
            self.target_delete(tid=tgtid, force=force)
            break
        else:
            raise FileNotFoundError(f"target not found: {targetname}")
