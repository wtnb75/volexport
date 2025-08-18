import shlex
import datetime
from abc import abstractmethod
from .util import runcmd
from .config import config
from logging import getLogger
from typing import Sequence, override

_log = getLogger(__name__)


def parse(input: Sequence[str], indent: int, width: int) -> list[dict]:
    res = []
    ent = {}
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
        ent[name] = val
    if ent:
        res.append(ent)
    return res


def runparse(cmd: list[str], indent: int, width: int) -> list[dict]:
    if config.LVM_BIN:
        cmd[0:0] = shlex.split(config.LVM_BIN)
    res = runcmd(cmd, root=True)
    return parse(res.stdout.splitlines(keepends=False), indent, width)


class Base:
    def __init__(self, name: str | None = None):
        self.name = name

    def find_by(self, data: list[dict], keyname: str, value: str):
        for i in data:
            if i.get(keyname) == value:
                return i
        return None

    @abstractmethod
    def get(self) -> dict | None:
        raise NotImplementedError("get")

    @abstractmethod
    def getlist(self) -> list[dict]:
        raise NotImplementedError("list")

    @abstractmethod
    def create(self) -> dict:
        raise NotImplementedError("create")

    @abstractmethod
    def delete(self) -> None:
        raise NotImplementedError("delete")

    @abstractmethod
    def scan(self) -> list[dict]:
        raise NotImplementedError("scan")


class PV(Base):
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
        runcmd(["pvremove", self.name, "-y"], True)

    @override
    def scan(self) -> list[dict]:
        runcmd(["pvscan"], True)
        return self.getlist()


class VG(Base):
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
        runcmd(["vgremove", self.name, "-y"], True)

    @override
    def scan(self) -> list[dict]:
        runcmd(["vgscan"], True)
        return self.getlist()

    def addpv(self, pv: PV):
        assert self.name is not None
        assert pv.name is not None
        runcmd(["vgextend", self.name, pv.name], True)

    def delpv(self, pv: PV):
        assert self.name is not None
        assert pv.name is not None
        runcmd(["vgreduce", self.name, pv.name], True)


class LV(Base):
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
        return self.find_by(self.getlist(), "LV Name", self.name)

    @override
    def getlist(self) -> list[dict]:
        return runparse(["lvdisplay", "--unit", "b", self.vgname], 2, 22)

    @override
    def create(self, size: int) -> dict:
        assert self.name is not None
        runcmd(["lvcreate", "--size", f"{size}b", self.vgname, "--name", self.name])
        return dict(name=self.name, size=size, device=f"/dev/{self.vgname}/{self.name}")

    def create_snapshot(self, size: int, parent: str) -> dict:
        assert self.name is not None
        runcmd(["lvcreate", "--snapshot", "--size", f"{size}b", "--name", self.name, f"/dev/{self.vgname}/{parent}"])
        return dict(name=self.name, size=size, device=f"/dev/{self.vgname}/{self.name}")

    def create_thinpool(self, size: int) -> dict:
        assert self.name is not None
        runcmd(["lvcreate", "--thinpool", self.name, "-L", f"{size}b", self.vgname])
        return dict(name=self.name, size=size, device=f"/dev/{self.vgname}/{self.name}")

    def create_thin(self, size: int, thinpool: str) -> dict:
        assert self.name is not None
        runcmd(["lvcreate", "--thin", "-V", f"{size}b", "-n", self.name, f"{self.vgname}/{thinpool}"])
        return dict(name=self.name, size=size, device=f"/dev/{self.vgname}/{self.name}")

    @override
    def delete(self) -> None:
        runcmd(["lvremove", self.volname])

    @override
    def scan(self) -> list[dict]:
        runcmd(["lvscan"], True)
        return self.getlist()

    def volume_list(self):
        vols = self.getlist()
        res = []
        for vol in vols:
            created = datetime.datetime.strptime(
                vol["LV Creation host, time"].split(",", 1)[-1].strip(), "%Y-%m-%d %H:%M:%S %z"
            )
            size = int(vol["LV Size"].removesuffix(" B"))
            res.append(dict(name=vol["LV Name"], created=created.isoformat(), size=size, used=int(vol["# open"])))
        return res

    def volume_read(self):
        vols = self.getlist()
        for vol in vols:
            if vol["LV Name"] != self.name:
                continue
            created = datetime.datetime.strptime(
                vol["LV Creation host, time"].split(",", 1)[-1].strip(), "%Y-%m-%d %H:%M:%S %z"
            )
            size = int(vol["LV Size"].removesuffix(" B"))
            return dict(name=vol["LV Name"], created=created.isoformat(), size=size, used=int(vol["# open"]))
        return None

    def volume_vol2path(self):
        return f"/dev/{self.vgname}/{self.name}"

    def volume_path2vol(self, name: str):
        if not name.startswith(f"/dev/{self.vgname}/"):
            raise Exception(f"invalid format: {name}, vg={self.vgname}")
        return name.removeprefix(f"/dev/{self.vgname}/")

    def read_only(self, readonly: bool):
        if readonly:
            runcmd(["lvchange", "--permission", "r", self.volname])
        else:
            runcmd(["lvchange", "--permission", "rw", self.volname])

    def resize(self, newsize: int):
        assert self.name is not None
        runcmd(["lvresize", "--size", str(newsize), self.volname])
