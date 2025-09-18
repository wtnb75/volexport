import shlex
import datetime
import shutil
import string
from subprocess import CalledProcessError
from abc import abstractmethod
from .util import runcmd
from .config import config
from .exceptions import InvalidArgument
from logging import getLogger
from typing import Sequence, override

_log = getLogger(__name__)


def parse(input: Sequence[str], indent: int, width: int) -> list[dict]:
    """Parse LVM command output"""
    res = []
    ent = {}
    prevname: str | None = None
    for i in input:
        if len(i) < indent:
            _log.debug("short line: %s", i)
            continue
        if not i.startswith(" " * indent):
            _log.debug("no indent: %s", i)
            continue
        if i[indent : indent + 3] == "---":
            _log.debug("separator: %s", i)
            if ent:
                _log.debug("append: %s", i)
                res.append(ent)
                ent = {}
            continue
        if len(i) <= indent + width:
            _log.debug("short width: %s", i)
            continue
        if i[indent + width] != " ":
            _log.debug("not split: %s / %s", repr(i[indent + width]), i)
            continue
        name = i[indent : indent + width].strip()
        val = i[indent + width + 1 :].strip()
        if not name:
            ent[prevname] += " " + val
        else:
            ent[name] = val
            prevname = name
    if ent:
        res.append(ent)
    return res


def runparse(cmd: list[str], indent: int, width: int) -> list[dict]:
    """Run LVM command and parse the output"""
    if config.LVM_BIN:
        cmd[0:0] = shlex.split(config.LVM_BIN)
    res = runcmd(cmd, root=True)
    return parse(res.stdout.splitlines(keepends=False), indent, width)


class Base:
    ACCEPT_CHARS = string.ascii_letters + string.digits + "-_"

    def __init__(self, name: str | None = None):
        if name is not None and any(x not in self.ACCEPT_CHARS for x in name):
            raise ValueError(f"invalid name: {name}")
        self.name = name

    def find_by(self, data: list[dict], keyname: str, value: str):
        """Find an entry in a list of dictionaries by key and value"""
        for i in data:
            if i.get(keyname) == value:
                return i
        return None

    @abstractmethod
    def get(self) -> dict | None:
        """Get a single entry by name"""
        raise NotImplementedError("get")

    @abstractmethod
    def getlist(self) -> list[dict]:
        """Get a list of entries"""
        raise NotImplementedError("list")

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

    @override
    def get(self) -> dict | None:
        if self.name is None:
            return None
        return self.find_by(self.getlist(), "PV Name", self.name)

    @override
    def getlist(self) -> list[dict]:
        return runparse(["pvdisplay", "--unit", "b"], 2, 21)

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

    @override
    def get(self) -> dict | None:
        if self.name is None:
            return None
        res = runparse(["vgdisplay", "--unit", "b", self.name], indent=2, width=21)
        if len(res) == 0:
            return None
        return res[0]

    @override
    def getlist(self) -> list[dict]:
        return runparse(["vgdisplay", "--unit", "b"], 2, 21)

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


class LV(Base):
    """Class to manage logical volumes in LVM"""

    def __init__(self, vgname: str, name: str | None = None):
        super().__init__(name)
        self.vgname = vgname

    @property
    def volname(self):
        assert self.name is not None
        return self.vgname + "/" + self.name

    @override
    def get(self) -> dict | None:
        if self.name is None:
            return None
        return self.find_by(self.getlist(self.name), "LV Name", self.name)

    @override
    def getlist(self, volname: str | None = None) -> list[dict]:
        if volname:
            try:
                return runparse(["lvdisplay", "--unit", "b", f"{self.vgname}/{volname}"], 2, 22)
            except CalledProcessError as e:
                if "Failed to find logical volume" in e.stderr:
                    raise FileNotFoundError(f"volume does not exists: {volname}")
        return runparse(["lvdisplay", "--unit", "b", self.vgname], 2, 22)

    @override
    def create(self, size: int) -> dict:
        assert self.name is not None
        try:
            runcmd(["lvcreate", "--size", f"{size}b", self.vgname, "--name", self.name])
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
        runcmd(["lvcreate", "--snapshot", "--size", f"{size}b", "--name", self.name, f"/dev/{self.vgname}/{parent}"])
        return self.volume_read()

    def create_thinpool(self, size: int) -> dict:
        """Create a thin pool logical volume"""
        assert self.name is not None
        runcmd(["lvcreate", "--thinpool", self.name, "--size", f"{size}b", self.vgname])
        return dict(name=self.name, size=size, device=self.volume_vol2path())

    def create_thin(self, size: int, thinpool: str) -> dict | None:
        """Create a thin logical volume in a thin pool"""
        assert self.name is not None
        runcmd(["lvcreate", "--thin", "--virtualsize", f"{size}b", "--name", self.name, f"{self.vgname}/{thinpool}"])
        return self.volume_read()

    def create_thinsnap(self, parent: str) -> dict | None:
        """Create a snapshot volume in a thin pool"""
        assert self.name is not None
        runcmd(["lvcreate", "--snapshot", "--name", self.name, f"{self.vgname}/{parent}"])
        runcmd(["lvchange", "--activate", "y", f"/dev/{self.vgname}/{self.name}", "--ignoreactivationskip"])
        return self.volume_read()

    def rollback_snapshot(self) -> dict | None:
        assert self.name is not None
        parent = self.get_parent()
        runcmd(["lvconvert", "--merge", f"{self.vgname}/{self.name}"])
        return LV(self.vgname, parent).volume_read()

    def get_parent(self):
        vol = self.get()
        if vol is None:
            return None
        res = self.vol2dict(vol)
        if res is None:
            return None
        return res.get("parent")

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
        created = datetime.datetime.strptime(
            vol["LV Creation host, time"].split(",", 1)[-1].strip(), "%Y-%m-%d %H:%M:%S %z"
        )
        if "LV Pool metadata" in vol:
            # thin pool
            return None
        if vol.get("LV Status") not in ("available",):
            # not available
            return None
        size = int(vol["LV Size"].removesuffix(" B"))
        readonly = vol["LV Write Access"] == "read only"
        thin = "LV Pool name" in vol
        parent = vol.get("LV Thin origin name")
        if not parent:
            snapstate = vol.get("LV snapshot status")
            if snapstate:
                if snapstate.startswith("active destination for"):
                    parent = snapstate.removeprefix("active destination for ")
        return dict(
            name=vol["LV Name"],
            created=created.isoformat(),
            size=size,
            used=int(vol["# open"]),
            readonly=readonly,
            thin=thin,
            parent=parent,
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
        return f"/dev/{self.vgname}/{self.name}"

    def volume_path2vol(self, name: str):
        """Convert device path to volume name"""
        if not name.startswith(f"/dev/{self.vgname}/"):
            raise Exception(f"invalid format: {name}, vg={self.vgname}")
        return name.removeprefix(f"/dev/{self.vgname}/")

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
