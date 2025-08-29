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
        dict(name="lv1", created="2025-08-10T16:48:15+09:00", size=68719476736, used=1, readonly=False),
        dict(name="lv2", created="2025-08-12T16:48:15+09:00", size=20000000000, used=0, readonly=False),
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
        run.assert_called_once_with(["sudo", "lvdisplay", "--unit", "b", "vg0"], **self.run_basearg)

    @patch("subprocess.run")
    def test_readvol_notfound(self, run):
        run.return_value.exit_code = 0
        run.return_value.stdout = self.lvdisplay
        res = TestClient(api).get("/volume/not-found")
        self.assertEqual(404, res.status_code)
        self.assertEqual({"detail": "volume not found"}, res.json())
        run.assert_called_once_with(["sudo", "lvdisplay", "--unit", "b", "vg0"], **self.run_basearg)

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
        run.assert_called_once_with(["sudo", "lvremove", "vg0/volname1", "-y"], **self.run_basearg)

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
