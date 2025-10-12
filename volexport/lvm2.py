import os
import shlex
import datetime
import shutil
import string
import uuid
import json
from pathlib import Path
from subprocess import CalledProcessError
from abc import abstractmethod
from .util import runcmd
from .config import config
from .exceptions import InvalidArgument
from logging import getLogger
from typing import override

_log = getLogger(__name__)


def runparse_report(mode: str, filter: str | None = None) -> list[dict]:
    """Run LVM command and parse the output"""
    cmd = [
        mode + "s",
        "-o",
        f"{mode}_all",
        "--reportformat",
        "json",
        "--unit",
        "b",
        "--nosuffix",
    ]
    if filter:
        cmd.extend(["-S", filter])
    if config.LVM_BIN:
        cmd[0:0] = shlex.split(config.LVM_BIN)
    res0 = runcmd(cmd, root=True)
    res = []
    for i in json.loads(res0.stdout).get("report", []):
        res.extend(i.get(mode, []))
    return res


class Base:
    ACCEPT_CHARS = string.ascii_letters + string.digits + "-_"
    mode: str = "DUMMY"

    def __init__(self, name: str | None = None):
        if name is not None and any(x not in self.ACCEPT_CHARS for x in name):
            raise ValueError(f"invalid name: {name}")
        self.name = name

    def get(self) -> dict | None:
        """Get a single entry by name"""
        if self.name is None:
            return None
        res = runparse_report(mode=self.mode, filter=f'{self.mode}_name="{self.name}"')
        if len(res) == 0:
            return None
        return res[0]

    def getlist(self) -> list[dict]:
        """Get a list of entries"""
        return runparse_report(mode=self.mode)

    def find_by(self, data: list[dict], keyname: str, value: str):
        """Find an entry in a list of dictionaries by key and value"""
        for i in data:
            if i.get(keyname) == value:
                return i
        return None

    @abstractmethod
    def create(self) -> dict:
        """Create a new entry"""
        raise NotImplementedError("create")

    @abstractmethod
    def delete(self) -> None:
        """Delete an entry"""
        raise NotImplementedError("delete")

    @abstractmethod
    def scan(self) -> list[dict]:
        """Scan for entries"""
        raise NotImplementedError("scan")


class PV(Base):
    """Class to manage physical volumes in LVM"""

    mode = "pv"

    @override
    def create(self) -> dict:
        assert self.name is not None
        runcmd(["pvcreate", self.name], True)
        res = self.get()
        assert res is not None
        return res

    @override
    def delete(self) -> None:
        assert self.name is not None
        runcmd(["pvremove", self.name, "--yes"], True)

    @override
    def scan(self) -> list[dict]:
        runcmd(["pvscan"], True)
        return self.getlist()


class VG(Base):
    """Class to manage volume groups in LVM"""

    mode = "vg"

    @override
    def create(self, pvs: list[PV]) -> dict:
        assert self.name is not None
        runcmd(["vgcreate", self.name, *[x.name for x in pvs if x.name is not None]], True)
        res = self.get()
        assert res is not None
        return res

    @override
    def delete(self) -> None:
        assert self.name is not None
        runcmd(["vgremove", self.name, "--yes"], True)

    @override
    def scan(self) -> list[dict]:
        runcmd(["vgscan"], True)
        return self.getlist()

    def addpv(self, pv: PV):
        """Add a physical volume to the volume group"""
        assert self.name is not None
        assert pv.name is not None
        runcmd(["vgextend", self.name, pv.name], True)

    def delpv(self, pv: PV):
        """Remove a physical volume from the volume group"""
        assert self.name is not None
        assert pv.name is not None
        runcmd(["vgreduce", self.name, pv.name], True)

    def backup(self, outname: Path):
        assert self.name is not None
        runcmd(["vgcfgbackup", "--file", str(outname), self.name])
        if os.getuid() != 0:
            runcmd(["chown", str(os.getuid()), str(outname)])

    def restore(self, inname: Path):
        assert self.name is not None
        runcmd(["vgcfgrestore", "--file", str(inname), self.name])


class LV(Base):
    """Class to manage logical volumes in LVM"""

    mode = "lv"
    nametag_prefix = "volname."

    def __init__(self, vgname: str, name: str | None = None):
        super().__init__(name)
        self.vgname = vgname

    @property
    def tagname(self):
        assert self.name is not None
        return self.nametag_prefix + self.name

    @property
    def volname(self):
        assert self.name is not None
        info = self.get()
        if info is None:
            raise FileNotFoundError(f"volume does not exists: {self.name}")
        return info["lv_full_name"]

    @override
    def get(self) -> dict | None:
        if self.name is None:
            return None
        res = runparse_report(mode=self.mode, filter=f"tags={self.tagname}")
        if len(res) == 1:
            return res[0]
        return None

    def getbydev(self, devname) -> dict | None:
        res = runparse_report(mode=self.mode, filter=f"lv_path={devname}")
        if len(res) == 1:
            return res[0]
        return None

    @override
    def getlist(self, volname: str | None = None) -> list[dict]:
        if volname:
            try:
                return runparse_report(mode=self.mode, filter=f"tags={self.tagname}")
            except CalledProcessError as e:
                if "Failed to find logical volume" in e.stderr:
                    raise FileNotFoundError(f"volume does not exists: {volname}")
        return runparse_report(mode=self.mode)

    @override
    def create(self, size: int) -> dict:
        assert self.name is not None
        name = str(uuid.uuid4())
        try:
            runcmd(
                [
                    "lvcreate",
                    "--size",
                    f"{size}b",
                    self.vgname,
                    "--name",
                    name,
                    "--addtag",
                    self.tagname,
                ]
            )
            res = self.volume_read()
            assert res is not None
            return res
        except CalledProcessError as e:
            if e.returncode == 3 and "Size is not a multiple" in e.stderr:
                raise InvalidArgument(f"invalid size: {size}")
            raise

    def create_snapshot(self, size: int, parent: str) -> dict | None:
        """Create a snapshot of a logical volume"""
        assert self.name is not None
        name = str(uuid.uuid4())
        runcmd(
            [
                "lvcreate",
                "--snapshot",
                "--size",
                f"{size}b",
                "--name",
                name,
                "--addtag",
                self.tagname,
                f"/dev/{self.vgname}/{parent}",
            ]
        )
        return self.volume_read()

    def create_thinpool(self, size: int) -> dict:
        """Create a thin pool logical volume"""
        assert self.name is not None
        runcmd(["lvcreate", "--thinpool", self.name, "--size", f"{size}b", self.vgname])
        return dict(name=self.name, size=size, device=self.volume_vol2path())

    def create_thin(self, size: int, thinpool: str) -> dict | None:
        """Create a thin logical volume in a thin pool"""
        assert self.name is not None
        name = str(uuid.uuid4())
        runcmd(
            [
                "lvcreate",
                "--thin",
                "--virtualsize",
                f"{size}b",
                "--name",
                name,
                "--addtag",
                self.tagname,
                f"{self.vgname}/{thinpool}",
            ]
        )
        return self.volume_read()

    def create_thinsnap(self, parent: str) -> dict | None:
        """Create a snapshot volume in a thin pool"""
        assert self.name is not None
        name = str(uuid.uuid4())
        runcmd(
            [
                "lvcreate",
                "--snapshot",
                "--name",
                name,
                "--addtag",
                self.tagname,
                f"{self.vgname}/{parent}",
            ]
        )
        runcmd(["lvchange", "--activate", "y", f"/dev/{self.vgname}/{self.name}", "--ignoreactivationskip"])
        return self.volume_read()

    def rollback_snapshot(self) -> dict | None:
        assert self.name is not None
        parent = self.get_parent()
        runcmd(["lvconvert", "--merge", self.volname])
        return LV(self.vgname, parent).volume_read()

    def get_parent(self):
        vol = self.get()
        if vol is None:
            return None
        res = vol["lv_parent"]
        if not res:
            return None
        return res

    @override
    def delete(self) -> None:
        try:
            runcmd(["lvremove", self.volname, "--yes"])
        except CalledProcessError as e:
            if e.returncode == 5 and "Failed to find" in e.stderr:
                pass
            else:
                raise

    @override
    def scan(self) -> list[dict]:
        runcmd(["lvscan"], True)
        return self.getlist()

    def vol2dict(self, vol: dict):
        created = datetime.datetime.strptime(vol["lv_time"], "%Y-%m-%d %H:%M:%S %z")
        if not vol["lv_path"]:
            # thin pool? no device
            _log.debug("no device: %s", vol["lv_name"])
            return None
        if vol.get("lv_active") not in ("active",):
            # not available
            _log.debug("not active: %s", vol["lv_name"])
            return None
        size = int(vol["lv_size"])
        readonly = vol["lv_permissions"] != "writeable"
        parent = vol["origin"]
        thin = bool(vol["pool_lv"])
        used = bool(vol["lv_device_open"])
        tags = vol["lv_tags"]
        for tag in tags.split(","):
            if tag.startswith(self.nametag_prefix):
                name = tag.removeprefix(self.nametag_prefix)
                break
        else:
            name = vol["lv_name"]
        return dict(
            name=name,
            created=created.isoformat(),
            size=size,
            used=used,
            readonly=readonly,
            thin=thin,
            parent=parent,
            lvm_name=vol["lv_name"],
            lvm_id=vol["lv_uuid"],
        )

    def volume_list(self):
        """List all logical volumes in the volume group"""
        vols = self.getlist()
        res = []
        for vol in vols:
            ent = self.vol2dict(vol)
            if ent:
                res.append(ent)
        return res

    def volume_read(self):
        """Read details of a specific logical volume"""
        vol = self.get()
        if vol is None:
            return None
        return self.vol2dict(vol)

    def volume_vol2path(self):
        """Convert volume name to device path"""
        return f"/dev/{self.volname}"

    def volume_path2vol(self, name: str):
        """Convert device path to volume name"""
        if not name.startswith(f"/dev/{self.vgname}/"):
            raise Exception(f"invalid format: {name}, vg={self.vgname}")
        vol = self.getbydev(name)
        if vol is None:
            raise FileNotFoundError(f"volume does not exists: {name}")
        tags = vol["lv_tags"]
        for tag in tags.split(","):
            if tag.startswith(self.nametag_prefix):
                return tag.removeprefix(self.nametag_prefix)
        return None

    def read_only(self, readonly: bool):
        """Set the logical volume to read-only or read-write"""
        if readonly:
            runcmd(["lvchange", "--permission", "r", self.volname])
        else:
            runcmd(["lvchange", "--permission", "rw", self.volname])

    def resize(self, newsize: int):
        """Resize the logical volume to a new size in bytes"""
        assert self.name is not None
        runcmd(["lvresize", "--size", f"{newsize}b", self.volname, "--yes"])

    def format_volume(self, filesystem: str, label: str | None):
        """Format the logical volume to make filesystem"""
        if shutil.which(f"mkfs.{filesystem}") is None:
            _log.error("command does not found: mkfs.%s", filesystem)
            raise NotImplementedError("not supported")

        volpath = self.volume_vol2path()
        if filesystem in ("ext4", "xfs", "exfat", "btrfs", "ntfs", "nilfs2"):
            lbl = ["-L", label or self.name]
            runcmd([f"mkfs.{filesystem}", *lbl, volpath])
        elif filesystem in ("vfat",):
            lbl = ["-n", label or self.name]
            runcmd([f"mkfs.{filesystem}", *lbl, volpath])
        else:
            _log.error("no such filesystem: %s", filesystem)
            raise NotImplementedError("not supported")
