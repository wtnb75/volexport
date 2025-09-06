import unittest
import subprocess
from unittest.mock import patch, ANY, MagicMock
from fastapi.testclient import TestClient
from volexport.api import api


class TestVolumeAPI(unittest.TestCase):
    run_basearg = dict(capture_output=True, encoding="utf-8", timeout=10.0, stdin=-3, start_new_session=True)

    def test_healthcheck(self):
        res = TestClient(api).get("/health")
        self.assertEqual(200, res.status_code)
        self.assertEqual({"status": "OK"}, res.json())

    def test_notfound(self):
        res = TestClient(api).get("/not-found")
        self.assertEqual(404, res.status_code)
        self.assertEqual({"detail": "Not Found"}, res.json())

    @patch("subprocess.run")
    def test_internal(self, run):
        run.side_effect = subprocess.CalledProcessError(returncode=1, cmd="command")
        res = TestClient(api).get("/volume")
        self.assertEqual(500, res.status_code)
        self.assertEqual({"detail": ANY}, res.json())
        run.assert_called_once_with(["sudo", "lvdisplay", "--unit", "b", "vg0"], **self.run_basearg)

    lvdisplay = """
  --- Logical volume ---
  LV Path                /dev/vg0/lv1
  LV Name                lv1
  VG Name                vg0
  LV UUID                a3OsbU-WC1S-CfDC-MImV-qnqK-oXi0-mmXdqZ
  LV Write Access        read/write
  LV Creation host, time base, 2025-08-10 16:48:15 +0900
  LV Status              available
  # open                 1
  LV Size                68719476736 B
  Current LE             16255
  Segments               1
  Allocation             inherit
  Read ahead sectors     auto
  - currently set to     256
  Block device           252:0

  --- Logical volume ---
  LV Path                /dev/vg0/lv2
  LV Name                lv2
  VG Name                vg0
  LV UUID                a3OsbU-WC1S-CfDC-MImV-qnqK-oXi0-mmXdqZ
  LV Write Access        read/write
  LV Creation host, time base, 2025-08-12 16:48:15 +0900
  LV Status              available
  # open                 0
  LV Size                20000000000 B
  Current LE             16255
  Segments               1
  Allocation             inherit
  Read ahead sectors     auto
  - currently set to     256
  Block device           252:1
    """
    volume_info = [
        dict(
            name="lv1",
            created="2025-08-10T16:48:15+09:00",
            size=68719476736,
            used=1,
            readonly=False,
            thin=False,
            parent=None,
        ),
        dict(
            name="lv2",
            created="2025-08-12T16:48:15+09:00",
            size=20000000000,
            used=0,
            readonly=False,
            thin=False,
            parent=None,
        ),
    ]

    @patch("subprocess.run")
    def test_listvol(self, run):
        run.return_value.exit_code = 0
        run.return_value.stdout = self.lvdisplay
        res = TestClient(api).get("/volume")
        self.assertEqual(200, res.status_code)
        self.assertEqual(self.volume_info, res.json())
        run.assert_called_once_with(["sudo", "lvdisplay", "--unit", "b", "vg0"], **self.run_basearg)

    @patch("subprocess.run")
    def test_readvol(self, run):
        run.return_value.exit_code = 0
        run.return_value.stdout = self.lvdisplay
        res = TestClient(api).get("/volume/lv2")
        self.assertEqual(200, res.status_code)
        self.assertEqual(self.volume_info[1], res.json())
        run.assert_called_once_with(["sudo", "lvdisplay", "--unit", "b", "vg0/lv2"], **self.run_basearg)

    @patch("subprocess.run")
    def test_readvol_notfound(self, run):
        run.return_value.exit_code = 0
        run.return_value.stdout = self.lvdisplay
        res = TestClient(api).get("/volume/not-found")
        self.assertEqual(404, res.status_code)
        self.assertEqual({"detail": "volume not found"}, res.json())
        run.assert_called_once_with(["sudo", "lvdisplay", "--unit", "b", "vg0/not-found"], **self.run_basearg)

    def test_createvol_sector(self):
        res = TestClient(api).post("/volume", json={"name": "volname1", "size": 12345})
        self.assertEqual(422, res.status_code)

    @patch("subprocess.run")
    def test_createvol(self, run):
        create = MagicMock(exit_code=0)
        read = MagicMock(exit_code=0, stdout=self.lvdisplay)
        run.side_effect = [create, read]
        res = TestClient(api).post("/volume", json={"name": "lv1", "size": 512})
        self.assertEqual(200, res.status_code)
        self.assertEqual({"name": "lv1", "size": 68719476736}, res.json())
        run.assert_any_call(["sudo", "lvcreate", "--size", "512b", "vg0", "--name", "lv1"], **self.run_basearg)

    @patch("subprocess.run")
    def test_deletevol(self, run):
        run.return_value.exit_code = 0
        res = TestClient(api).delete("/volume/volname1")
        self.assertEqual(200, res.status_code)
        self.assertEqual({}, res.json())
        run.assert_called_once_with(["sudo", "lvremove", "vg0/volname1", "--yes"], **self.run_basearg)

    @patch("subprocess.run")
    def test_statsvol(self, run):
        run.return_value.exit_code = 0
        run.return_value.stdout = """
  --- Volume group ---
  VG Name               vg0
  System ID
  Format                lvm2
  Metadata Areas        1
  Metadata Sequence No  2
  VG Access             read/write
  VG Status             resizable
  MAX LV                0
  Cur LV                1
  Open LV               1
  Max PV                0
  Cur PV                1
  Act PV                1
  VG Size               68178411520 B
  PE Size               4194304 B
  Total PE              16255
  Alloc PE / Size       16254 / 68174217216 B
  Free  PE / Size       1 / 4194304 B
  VG UUID               hPuYd4-QEoi-RcvL-Jdr5-XLrf-urQm-hgybLl
"""
        res = TestClient(api).get("/stats/volume")
        self.assertEqual(200, res.status_code)
        self.assertEqual({"free": 4194304, "total": 68178411520, "used": 68174217216, "volumes": 1}, res.json())
        run.assert_called_once_with(["sudo", "vgdisplay", "--unit", "b", "vg0"], **self.run_basearg)

    @patch("subprocess.run")
    def test_statsvol_notfound(self, run):
        run.return_value.exit_code = 0
        run.return_value.stdout = ""
        res = TestClient(api).get("/stats/volume")
        self.assertEqual(404, res.status_code)
        self.assertEqual({"detail": "pool not found"}, res.json())
        run.assert_called_once_with(["sudo", "vgdisplay", "--unit", "b", "vg0"], **self.run_basearg)

    @patch("subprocess.run")
    def test_resize(self, run):
        noout = MagicMock()
        tgtadm_show = MagicMock(
            stdout="""
Target 1: iqn.def
    System information:
        Driver: iscsi
        State: ready
    I_T nexus information:
        I_T nexus: 3
            Initiator: iqn.1996-04.org.alpinelinux:01:c1f2520715f alias: test1
            Connection: 0
                IP Address: 192.168.64.41
            Connection: 1
                IP Address: 192.168.64.42
    LUN information:
        LUN: 0
            Type: controller
            SCSI ID: IET     00010000
            SCSI SN: beaf10
            Size: 0 MB, Block size: 1
            Online: Yes
            Removable media: No
            Prevent removal: No
            Readonly: No
            SWP: No
            Thin-provisioning: No
            Backing store type: null
            Backing store path: None
            Backing store flags:
        LUN: 1
            Type: disk
            SCSI ID: IET     00010001
            SCSI SN: beaf11
            Size: 10737 MB, Block size: 512
            Online: Yes
            Removable media: No
            Prevent removal: No
            Readonly: No
            SWP: No
            Thin-provisioning: No
            Backing store type: rdwr
            Backing store path: /dev/vg0/lv1
            Backing store flags:
    Account information:
        user123
    ACL information:
        0.0.0.0/0
        192.168.64.0/24
"""
        )
        lvdisplay = MagicMock(stdout=self.lvdisplay)
        run.side_effect = [
            noout,  # lvresize
            tgtadm_show,  # tgtadm show target
            noout,  # tgtadm remove lun
            noout,  # tgtadm add lun
            lvdisplay,  # lvdisplay
        ]
        expected = {
            "created": ANY,
            "name": "lv1",
            "readonly": False,
            "size": 68719476736,
            "used": 1,
            "thin": False,
            "parent": None,
        }
        res = TestClient(api).post("/volume/lv1", json={"size": 1024})
        self.assertEqual(200, res.status_code)
        self.assertEqual(expected, res.json())
        run.assert_any_call(["sudo", "lvresize", "--size", "1024b", "vg0/lv1", "--yes"], **self.run_basearg)
        run.assert_any_call(
            ["sudo", "tgtadm", "--lld", "iscsi", "--mode", "target", "--op", "show"], **self.run_basearg
        )
        run.assert_any_call(["sudo", "lvdisplay", "--unit", "b", "vg0/lv1"], **self.run_basearg)

    @patch("subprocess.run")
    def test_ro(self, run):
        noout = MagicMock()
        lvdisplay = MagicMock(
            stdout="""
  --- Logical volume ---
  LV Path                /dev/vg0/lv1
  LV Name                lv1
  VG Name                vg0
  LV UUID                a3OsbU-WC1S-CfDC-MImV-qnqK-oXi0-mmXdqZ
  LV Write Access        read only
  LV Creation host, time base, 2025-08-10 16:48:15 +0900
  LV Status              available
  # open                 1
  LV Size                68719476736 B
  Current LE             16255
  Segments               1
  Allocation             inherit
  Read ahead sectors     auto
  - currently set to     256
  Block device           252:0
"""
        )
        run.side_effect = [
            noout,  # lvchange
            lvdisplay,  # lvdisplay
        ]
        expected = {
            "created": ANY,
            "name": "lv1",
            "readonly": True,
            "size": 68719476736,
            "used": 1,
            "thin": False,
            "parent": None,
        }
        res = TestClient(api).post("/volume/lv1", json={"readonly": True})
        self.assertEqual(200, res.status_code)
        self.assertEqual(expected, res.json())
        run.assert_any_call(["sudo", "lvchange", "--permission", "r", "vg0/lv1"], **self.run_basearg)
        run.assert_any_call(["sudo", "lvdisplay", "--unit", "b", "vg0/lv1"], **self.run_basearg)

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_mkfs(self, which, run):
        run.side_effect = [
            MagicMock(exit_code=0),
            MagicMock(stdout=self.lvdisplay),
        ]
        which.return_value = "/bin/mkfs.ext4"
        res = TestClient(api).post("/volume/lv1/mkfs", json={"filesystem": "ext4"})
        self.assertEqual(200, res.status_code)
        run.assert_any_call(["sudo", "mkfs.ext4", "-L", "lv1", "/dev/vg0/lv1"], **self.run_basearg)
        run.assert_any_call(["sudo", "lvdisplay", "--unit", "b", "vg0/lv1"], **self.run_basearg)

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_mkfs_vfat(self, which, run):
        run.side_effect = [
            MagicMock(exit_code=0),
            MagicMock(stdout=self.lvdisplay),
        ]
        which.return_value = "/bin/mkfs.ext4"
        res = TestClient(api).post("/volume/lv1/mkfs", json={"filesystem": "vfat"})
        self.assertEqual(200, res.status_code)
        run.assert_any_call(["sudo", "mkfs.vfat", "-n", "lv1", "/dev/vg0/lv1"], **self.run_basearg)
        run.assert_any_call(["sudo", "lvdisplay", "--unit", "b", "vg0/lv1"], **self.run_basearg)

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_mkfs_invalid_mkfscmd(self, which, run):
        which.return_value = None
        res = TestClient(api).post("/volume/lv1/mkfs", json={"filesystem": "vfat"})
        self.assertEqual(501, res.status_code)
        run.assert_not_called()

    def test_mkfs_invalid_name(self):
        res = TestClient(api).post("/volume/lv1!2/mkfs", json={"filesystem": "vfat"})
        self.assertEqual(400, res.status_code)
