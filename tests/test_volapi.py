import unittest
import json
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
        run.assert_called_once_with(
            ["sudo", "lvs", "-o", "lv_all", "--reportformat", "json", "--unit", "b", "--nosuffix"], **self.run_basearg
        )

    lv1 = dict(
        lv_name="lv1",
        lv_full_name="vg0/lv1",
        lv_path="/dev/vg0/lv1",
        lv_tags="volname.lv1",
        lv_time="2025-08-10 16:48:15 +0900",
        lv_active="active",
        lv_size="68719476736",
        lv_permissions="writeable",
        origin="",
        pool_lv="",
        lv_device_open="",
        lv_uuid="xyz",
    )
    lv1_ro = dict(
        lv_name="lv1",
        lv_full_name="vg0/lv1",
        lv_path="/dev/vg0/lv1",
        lv_tags="volname.lv1",
        lv_time="2025-08-10 16:48:15 +0900",
        lv_active="active",
        lv_size="68719476736",
        lv_permissions="read-only",
        origin="",
        pool_lv="",
        lv_device_open="",
        lv_uuid="xyz",
    )
    lv2 = dict(
        lv_name="lv2",
        lv_full_name="vg0/lv2",
        lv_path="/dev/vg0/lv2",
        lv_tags="volname.lv2",
        lv_time="2025-08-12 16:48:15 +0900",
        lv_active="active",
        lv_size="20000000000",
        lv_permissions="writeable",
        origin="",
        pool_lv="",
        lv_device_open="",
        lv_uuid="xyz",
    )
    lvsnap_thin = dict(
        lv_name="lvsnap",
        lv_full_name="vg0/lvsnap",
        lv_path="/dev/vg0/lvsnap",
        lv_tags="volname.lvsnap",
        lv_time="2025-08-12 16:48:15 +0900",
        lv_active="active",
        lv_size="20000000000",
        lv_permissions="writeable",
        origin="thin1",
        pool_lv="pool1",
        lv_device_open="",
        lv_uuid="xyz",
    )
    lvs = json.dumps({"report": [{"lv": [lv1, lv2]}]})
    lvs1 = json.dumps({"report": [{"lv": [lv1]}]})
    lvs1_ro = json.dumps({"report": [{"lv": [lv1_ro]}]})
    lvs2 = json.dumps({"report": [{"lv": [lv2]}]})
    lvsempty = json.dumps({"report": [{"lv": []}]})
    lvsnap = json.dumps({"report": [{"lv": [lvsnap_thin]}]})
    volume_info = [
        dict(
            name="lv1",
            created="2025-08-10T16:48:15+09:00",
            size=68719476736,
            used=False,
            readonly=False,
            thin=False,
            parent="",
        ),
        dict(
            name="lv2",
            created="2025-08-12T16:48:15+09:00",
            size=20000000000,
            used=False,
            readonly=False,
            thin=False,
            parent="",
        ),
    ]

    @patch("subprocess.run")
    def test_listvol(self, run):
        run.return_value.exit_code = 0
        run.return_value.stdout = self.lvs
        res = TestClient(api).get("/volume")
        self.assertEqual(200, res.status_code)
        self.assertEqual(self.volume_info, res.json())
        run.assert_called_once_with(
            ["sudo", "lvs", "-o", "lv_all", "--reportformat", "json", "--unit", "b", "--nosuffix"], **self.run_basearg
        )

    @patch("subprocess.run")
    def test_readvol(self, run):
        run.return_value.exit_code = 0
        run.return_value.stdout = self.lvs2
        res = TestClient(api).get("/volume/lv2")
        self.assertEqual(200, res.status_code)
        self.assertEqual(self.volume_info[1], res.json())
        run.assert_called_once_with(
            [
                "sudo",
                "lvs",
                "-o",
                "lv_all",
                "--reportformat",
                "json",
                "--unit",
                "b",
                "--nosuffix",
                "-S",
                "tags=volname.lv2",
            ],
            **self.run_basearg,
        )

    @patch("subprocess.run")
    def test_readvol_notfound(self, run):
        run.return_value.exit_code = 0
        run.return_value.stdout = self.lvsempty
        res = TestClient(api).get("/volume/not-found")
        self.assertEqual(404, res.status_code)
        self.assertEqual({"detail": "volume not found"}, res.json())
        run.assert_called_once_with(
            [
                "sudo",
                "lvs",
                "-o",
                "lv_all",
                "--reportformat",
                "json",
                "--unit",
                "b",
                "--nosuffix",
                "-S",
                "tags=volname.not-found",
            ],
            **self.run_basearg,
        )

    def test_createvol_sector(self):
        res = TestClient(api).post("/volume", json={"name": "volname1", "size": 12345})
        self.assertEqual(422, res.status_code)

    @patch("subprocess.run")
    def test_createvol(self, run):
        create = MagicMock(exit_code=0)
        read = MagicMock(exit_code=0, stdout=self.lvs1)
        run.side_effect = [create, read]
        res = TestClient(api).post("/volume", json={"name": "lv1", "size": 512})
        self.assertEqual(200, res.status_code)
        self.assertEqual({"name": "lv1", "size": 68719476736}, res.json())
        run.assert_any_call(
            ["sudo", "lvcreate", "--size", "512b", "vg0", "--name", ANY, "--addtag", "volname.lv1"], **self.run_basearg
        )

    @patch("subprocess.run")
    def test_deletevol(self, run):
        run.side_effect = [MagicMock(exit_code=0, stdout=self.lvs1), MagicMock(returncode=0)]
        res = TestClient(api).delete("/volume/volname1")
        self.assertEqual(200, res.status_code)
        self.assertEqual({}, res.json())
        run.assert_any_call(["sudo", "lvremove", "vg0/lv1", "--yes"], **self.run_basearg)

    @patch("subprocess.run")
    def test_statsvol(self, run):
        run.return_value.exit_code = 0
        run.return_value.stdout = json.dumps(
            {
                "report": [
                    {
                        "vg": [
                            dict(
                                vg_name="vg0",
                                vg_size="68178411520",
                                vg_free="4194304",
                                lv_count="1",
                                snap_count="1",
                            )
                        ]
                    }
                ]
            }
        )
        res = TestClient(api).get("/stats/volume")
        self.assertEqual(200, res.status_code)
        self.assertEqual(
            {"free": 4194304, "total": 68178411520, "used": 68174217216, "volumes": 1, "snapshots": 1}, res.json()
        )
        run.assert_called_once_with(
            [
                "sudo",
                "vgs",
                "-o",
                "vg_all",
                "--reportformat",
                "json",
                "--unit",
                "b",
                "--nosuffix",
                "-S",
                'vg_name="vg0"',
            ],
            **self.run_basearg,
        )

    @patch("subprocess.run")
    def test_statsvol_notfound(self, run):
        run.return_value.exit_code = 0
        run.return_value.stdout = json.dumps({"report": [{"vg": []}]})
        res = TestClient(api).get("/stats/volume")
        self.assertEqual(404, res.status_code)
        self.assertEqual({"detail": "pool not found"}, res.json())
        run.assert_called_once_with(
            [
                "sudo",
                "vgs",
                "-o",
                "vg_all",
                "--reportformat",
                "json",
                "--unit",
                "b",
                "--nosuffix",
                "-S",
                'vg_name="vg0"',
            ],
            **self.run_basearg,
        )

    @patch("subprocess.run")
    def test_snapshot_create(self, run):
        run.return_value.exit_code = 0
        run.return_value.stdout = self.lvsnap
        res = TestClient(api).post("/volume/vol123/snapshot", json=dict(name="snap123", size=1024 * 1024 * 1024))
        self.assertEqual(200, res.status_code)
        run.assert_any_call(
            [
                "sudo",
                "lvcreate",
                "--snapshot",
                "--size",
                "1073741824b",
                "--name",
                ANY,
                "--addtag",
                "volname.snap123",
                "/dev/vg0/vol123",
            ],
            **self.run_basearg,
        )

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
        lvs1 = MagicMock(returncode=0, stdout=self.lvs1)
        run.side_effect = [
            lvs1,
            noout,  # lvresize
            lvs1,
            tgtadm_show,  # tgtadm show target
            noout,  # tgtadm remove lun
            noout,  # tgtadm add lun
            lvs1,
        ]
        expected = {
            "created": ANY,
            "name": "lv1",
            "readonly": False,
            "size": 68719476736,
            "used": False,
            "thin": False,
            "parent": "",
        }
        res = TestClient(api).post("/volume/lv1", json={"size": 1024})
        self.assertEqual(200, res.status_code)
        self.assertEqual(expected, res.json())
        run.assert_any_call(["sudo", "lvresize", "--size", "1024b", "vg0/lv1", "--yes"], **self.run_basearg)
        run.assert_any_call(
            ["sudo", "tgtadm", "--lld", "iscsi", "--mode", "target", "--op", "show"], **self.run_basearg
        )
        run.assert_any_call(
            [
                "sudo",
                "lvs",
                "-o",
                "lv_all",
                "--reportformat",
                "json",
                "--unit",
                "b",
                "--nosuffix",
                "-S",
                "tags=volname.lv1",
            ],
            **self.run_basearg,
        )

    @patch("subprocess.run")
    def test_ro(self, run):
        noout = MagicMock()
        lvs1 = MagicMock(returncode=0, stdout=self.lvs1)
        lvs1_ro = MagicMock(returncode=0, stdout=self.lvs1_ro)
        run.side_effect = [
            lvs1,  # lvs
            noout,  # lvchange
            lvs1_ro,  # lvs
        ]
        expected = {
            "created": ANY,
            "name": "lv1",
            "readonly": True,
            "size": 68719476736,
            "used": False,
            "thin": False,
            "parent": "",
        }
        res = TestClient(api).post("/volume/lv1", json={"readonly": True})
        self.assertEqual(200, res.status_code)
        self.assertEqual(expected, res.json())
        run.assert_any_call(["sudo", "lvchange", "--permission", "r", "vg0/lv1"], **self.run_basearg)
        run.assert_any_call(
            [
                "sudo",
                "lvs",
                "-o",
                "lv_all",
                "--reportformat",
                "json",
                "--unit",
                "b",
                "--nosuffix",
                "-S",
                "tags=volname.lv1",
            ],
            **self.run_basearg,
        )

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_mkfs(self, which, run):
        run.side_effect = [
            MagicMock(stdout=self.lvs1),
            MagicMock(exit_code=0),
            MagicMock(stdout=self.lvs1),
        ]
        which.return_value = "/bin/mkfs.ext4"
        res = TestClient(api).post("/volume/lv1/mkfs", json={"filesystem": "ext4"})
        self.assertEqual(200, res.status_code)
        run.assert_any_call(["sudo", "mkfs.ext4", "-L", "lv1", "/dev/vg0/lv1"], **self.run_basearg)
        run.assert_any_call(
            [
                "sudo",
                "lvs",
                "-o",
                "lv_all",
                "--reportformat",
                "json",
                "--unit",
                "b",
                "--nosuffix",
                "-S",
                "tags=volname.lv1",
            ],
            **self.run_basearg,
        )

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_mkfs_vfat(self, which, run):
        run.side_effect = [
            MagicMock(stdout=self.lvs1),
            MagicMock(exit_code=0),
            MagicMock(stdout=self.lvs1),
        ]
        which.return_value = "/bin/mkfs.ext4"
        res = TestClient(api).post("/volume/lv1/mkfs", json={"filesystem": "vfat"})
        self.assertEqual(200, res.status_code)
        run.assert_any_call(["sudo", "mkfs.vfat", "-n", "lv1", "/dev/vg0/lv1"], **self.run_basearg)
        run.assert_any_call(
            [
                "sudo",
                "lvs",
                "-o",
                "lv_all",
                "--reportformat",
                "json",
                "--unit",
                "b",
                "--nosuffix",
                "-S",
                "tags=volname.lv1",
            ],
            **self.run_basearg,
        )

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
