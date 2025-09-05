import unittest
import subprocess
from collections import namedtuple
from unittest.mock import patch, ANY, MagicMock
from fastapi.testclient import TestClient
from volexport.api import api


class TestExportAPI(unittest.TestCase):
    maxDiff = None
    run_basearg = dict(capture_output=True, encoding="utf-8", timeout=10.0, stdin=-3, start_new_session=True)

    def test_healthcheck(self):
        res = TestClient(api).get("/health")
        self.assertEqual(200, res.status_code)
        self.assertEqual({"status": "OK"}, res.json())

    @patch("subprocess.run")
    def test_commanderror(self, run):
        run.side_effect = subprocess.CalledProcessError(returncode=1, cmd="command")
        res = TestClient(api).get("/export")
        self.assertEqual(500, res.status_code)
        self.assertEqual({"detail": ANY}, res.json())
        run.assert_called_once_with(
            ["sudo", "tgtadm", "--lld", "iscsi", "--mode", "target", "--op", "show"], **self.run_basearg
        )

    target_show_str = """
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
            Backing store path: /dev/vg0/vol01
            Backing store flags:
        LUN: 2
            Type: disk
            SCSI ID: IET     00010002
            SCSI SN: beaf12
            Size: 107374 MB, Block size: 512
            Online: Yes
            Removable media: No
            Prevent removal: No
            Readonly: No
            SWP: No
            Thin-provisioning: No
            Backing store type: rdwr
            Backing store path: /dev/vg0/vol02
            Backing store flags:
    Account information:
        user123
    ACL information:
        0.0.0.0/0
        192.168.64.0/24
"""

    @patch("subprocess.run")
    def test_exportlist(self, run):
        run.return_value.exit_code = 0
        run.return_value.stdout = self.target_show_str
        res = TestClient(api).get("/export")
        self.assertEqual(200, res.status_code)
        self.assertEqual(
            [
                dict(
                    protocol="iscsi",
                    tid=1,
                    targetname="iqn.def",
                    connected=[
                        dict(
                            initiator="iqn.1996-04.org.alpinelinux:01:c1f2520715f",
                            address=["192.168.64.41", "192.168.64.42"],
                        )
                    ],
                    acl=["0.0.0.0/0", "192.168.64.0/24"],
                    users=["user123"],
                    volumes=["vol01", "vol02"],
                )
            ],
            res.json(),
        )

    @patch("subprocess.run")
    def test_exportread(self, run):
        run.return_value.exit_code = 0
        run.return_value.stdout = self.target_show_str
        res = TestClient(api).get("/export/iqn.def")
        self.assertEqual(200, res.status_code)
        self.assertEqual(
            dict(
                protocol="iscsi",
                tid=1,
                targetname="iqn.def",
                connected=[
                    dict(
                        initiator="iqn.1996-04.org.alpinelinux:01:c1f2520715f",
                        address=["192.168.64.41", "192.168.64.42"],
                    )
                ],
                acl=["0.0.0.0/0", "192.168.64.0/24"],
                users=["user123"],
                volumes=["vol01", "vol02"],
            ),
            res.json(),
        )

    @patch("subprocess.run")
    @patch("volexport.tgtd.Path")
    def test_exportcreate(self, path, run):
        path.return_value.exists.return_value = True
        listvol_str = """
Target 1: iqn.def
    System information:
        Driver: iscsi
        State: ready
"""
        listvol = MagicMock(exit_code=0, stdout=listvol_str)
        simple_ok = MagicMock(exit_code=0, stdout="")
        portal_list = MagicMock(exit_code=0, stdout="Portal 0.0.0.0:3260,1")
        run.side_effect = [
            listvol,
            simple_ok,  # create target
            simple_ok,  # create lun
            simple_ok,  # update lun
            simple_ok,  # create account
            simple_ok,  # bind account
            simple_ok,  # setup ACL
            portal_list,
        ]
        expected = {
            "protocol": "iscsi",
            "addresses": [],
            "targetname": ANY,
            "tid": 2,
            "user": ANY,
            "passwd": ANY,
            "lun": 1,
            "acl": ["1.1.1.1/32"],
        }
        res = TestClient(api).post("/export", json={"volname": "vol00", "acl": ["1.1.1.1/32"]})
        self.assertEqual(200, res.status_code)
        self.assertEqual(expected, res.json())
        self.assertEqual(8, run.call_count)
        run.assert_any_call(
            ["sudo", "tgtadm", "--lld", "iscsi", "--mode", "target", "--op", "show"], **self.run_basearg
        )
        run.assert_any_call(
            ["sudo", "tgtadm", "--lld", "iscsi", "--mode", "target", "--op", "new", "--tid", "2", "--targetname", ANY],
            **self.run_basearg,
        )
        run.assert_any_call(
            [
                "sudo",
                "tgtadm",
                "--lld",
                "iscsi",
                "--mode",
                "logicalunit",
                "--op",
                "new",
                "--tid",
                "2",
                "--lun",
                "1",
                "--backing-store",
                "/dev/vg0/vol00",
                "--bstype",
                "rdwr",
            ],
            **self.run_basearg,
        )
        run.assert_any_call(
            [
                "sudo",
                "tgtadm",
                "--lld",
                "iscsi",
                "--mode",
                "account",
                "--op",
                "new",
                "--user",
                ANY,
                "--password",
                ANY,
            ],
            **self.run_basearg,
        )
        run.assert_any_call(
            ["sudo", "tgtadm", "--lld", "iscsi", "--mode", "account", "--op", "bind", "--tid", "2", "--user", ANY],
            **self.run_basearg,
        )
        run.assert_any_call(
            [
                "sudo",
                "tgtadm",
                "--lld",
                "iscsi",
                "--mode",
                "target",
                "--op",
                "bind",
                "--tid",
                "2",
                "--initiator-address",
                "1.1.1.1/32",
            ],
            **self.run_basearg,
        )
        run.assert_any_call(
            ["sudo", "tgtadm", "--lld", "iscsi", "--mode", "portal", "--op", "show"], **self.run_basearg
        )

    @patch("subprocess.run")
    @patch("volexport.tgtd.Path")
    def test_exportcreate_auth(self, path, run):
        path.return_value.exists.return_value = True
        listvol_str = """
Target 1: iqn.def
    System information:
        Driver: iscsi
        State: ready
"""
        listvol = MagicMock(exit_code=0, stdout=listvol_str)
        simple_ok = MagicMock(exit_code=0, stdout="")
        portal_list = MagicMock(exit_code=0, stdout="Portal 0.0.0.0:3260,1")
        run.side_effect = [
            listvol,
            simple_ok,  # create target
            simple_ok,  # create lun
            simple_ok,  # update lun
            simple_ok,  # create account
            simple_ok,  # bind account
            simple_ok,  # setup ACL
            portal_list,
        ]
        expected = {
            "protocol": "iscsi",
            "addresses": [],
            "targetname": ANY,
            "tid": 2,
            "user": ANY,
            "passwd": ANY,
            "lun": 1,
            "acl": ["1.1.1.1/32"],
        }
        res = TestClient(api).post(
            "/export", json={"volname": "vol00", "acl": ["1.1.1.1/32"], "user": "user123", "passwd": "pass123"}
        )
        self.assertEqual(200, res.status_code)
        self.assertEqual(expected, res.json())
        self.assertEqual(8, run.call_count)
        run.assert_any_call(
            ["sudo", "tgtadm", "--lld", "iscsi", "--mode", "target", "--op", "show"], **self.run_basearg
        )
        run.assert_any_call(
            ["sudo", "tgtadm", "--lld", "iscsi", "--mode", "target", "--op", "new", "--tid", "2", "--targetname", ANY],
            **self.run_basearg,
        )
        run.assert_any_call(
            [
                "sudo",
                "tgtadm",
                "--lld",
                "iscsi",
                "--mode",
                "logicalunit",
                "--op",
                "new",
                "--tid",
                "2",
                "--lun",
                "1",
                "--backing-store",
                "/dev/vg0/vol00",
                "--bstype",
                "rdwr",
            ],
            **self.run_basearg,
        )
        run.assert_any_call(
            [
                "sudo",
                "tgtadm",
                "--lld",
                "iscsi",
                "--mode",
                "account",
                "--op",
                "new",
                "--user",
                "user123",
                "--password",
                "pass123",
            ],
            **self.run_basearg,
        )
        run.assert_any_call(
            ["sudo", "tgtadm", "--lld", "iscsi", "--mode", "account", "--op", "bind", "--tid", "2", "--user", ANY],
            **self.run_basearg,
        )
        run.assert_any_call(
            [
                "sudo",
                "tgtadm",
                "--lld",
                "iscsi",
                "--mode",
                "target",
                "--op",
                "bind",
                "--tid",
                "2",
                "--initiator-address",
                "1.1.1.1/32",
            ],
            **self.run_basearg,
        )
        run.assert_any_call(
            ["sudo", "tgtadm", "--lld", "iscsi", "--mode", "portal", "--op", "show"], **self.run_basearg
        )

    @patch("subprocess.run")
    @patch("volexport.tgtd.Path")
    def test_exportcreate_noacl(self, path, run):
        path.return_value.exists.return_value = True
        listvol_str = """
Target 1: iqn.def
    System information:
        Driver: iscsi
        State: ready
"""
        listvol = MagicMock(exit_code=0, stdout=listvol_str)
        simple_ok = MagicMock(exit_code=0, stdout="")
        portal_list = MagicMock(exit_code=0, stdout="Portal 0.0.0.0:3260,1")
        run.side_effect = [
            listvol,
            simple_ok,  # create target
            simple_ok,  # create lun
            simple_ok,  # update lun
            simple_ok,  # create account
            simple_ok,  # bind account
            simple_ok,  # setup ACL
            portal_list,
        ]
        expected = {
            "protocol": "iscsi",
            "addresses": [],
            "targetname": ANY,
            "tid": 2,
            "user": ANY,
            "passwd": ANY,
            "lun": 1,
            "acl": [ANY],
        }
        res = TestClient(api).post("/export", json={"volname": "vol00", "acl": []})
        self.assertEqual(200, res.status_code)
        self.assertEqual(expected, res.json())
        self.assertEqual(8, run.call_count)
        run.assert_any_call(
            ["sudo", "tgtadm", "--lld", "iscsi", "--mode", "target", "--op", "show"], **self.run_basearg
        )
        run.assert_any_call(
            ["sudo", "tgtadm", "--lld", "iscsi", "--mode", "target", "--op", "new", "--tid", "2", "--targetname", ANY],
            **self.run_basearg,
        )
        run.assert_any_call(
            [
                "sudo",
                "tgtadm",
                "--lld",
                "iscsi",
                "--mode",
                "logicalunit",
                "--op",
                "new",
                "--tid",
                "2",
                "--lun",
                "1",
                "--backing-store",
                "/dev/vg0/vol00",
                "--bstype",
                "rdwr",
            ],
            **self.run_basearg,
        )
        run.assert_any_call(
            [
                "sudo",
                "tgtadm",
                "--lld",
                "iscsi",
                "--mode",
                "account",
                "--op",
                "new",
                "--user",
                ANY,
                "--password",
                ANY,
            ],
            **self.run_basearg,
        )
        run.assert_any_call(
            ["sudo", "tgtadm", "--lld", "iscsi", "--mode", "account", "--op", "bind", "--tid", "2", "--user", ANY],
            **self.run_basearg,
        )
        run.assert_any_call(
            [
                "sudo",
                "tgtadm",
                "--lld",
                "iscsi",
                "--mode",
                "target",
                "--op",
                "bind",
                "--tid",
                "2",
                "--initiator-address",
                ANY,
            ],
            **self.run_basearg,
        )
        run.assert_any_call(
            ["sudo", "tgtadm", "--lld", "iscsi", "--mode", "portal", "--op", "show"], **self.run_basearg
        )

    @patch("subprocess.run")
    @patch("volexport.tgtd.Path")
    def test_exportcreate_ro(self, path, run):
        path.return_value.exists.return_value = True
        listvol_str = """
Target 1: iqn.def
    System information:
        Driver: iscsi
        State: ready
"""
        listvol = MagicMock(exit_code=0, stdout=listvol_str)
        simple_ok = MagicMock(exit_code=0, stdout="")
        portal_list = MagicMock(exit_code=0, stdout="Portal 0.0.0.0:3260,1")
        run.side_effect = [
            listvol,
            simple_ok,  # create target
            simple_ok,  # create lun
            simple_ok,  # update lun
            simple_ok,  # create account
            simple_ok,  # bind account
            simple_ok,  # setup ACL
            portal_list,
        ]
        expected = {
            "protocol": "iscsi",
            "addresses": [],
            "targetname": ANY,
            "tid": 2,
            "user": ANY,
            "passwd": ANY,
            "lun": 1,
            "acl": ["1.1.1.1/32"],
        }
        res = TestClient(api).post("/export", json={"volname": "vol00", "acl": ["1.1.1.1/32"], "readonly": True})
        self.assertEqual(200, res.status_code)
        self.assertEqual(expected, res.json())
        self.assertEqual(8, run.call_count)
        run.assert_any_call(
            ["sudo", "tgtadm", "--lld", "iscsi", "--mode", "target", "--op", "show"], **self.run_basearg
        )
        run.assert_any_call(
            ["sudo", "tgtadm", "--lld", "iscsi", "--mode", "target", "--op", "new", "--tid", "2", "--targetname", ANY],
            **self.run_basearg,
        )
        run.assert_any_call(
            [
                "sudo",
                "tgtadm",
                "--lld",
                "iscsi",
                "--mode",
                "logicalunit",
                "--op",
                "new",
                "--tid",
                "2",
                "--lun",
                "1",
                "--backing-store",
                "/dev/vg0/vol00",
                "--bstype",
                "rdwr",
                "--params",
                "readonly=1",
            ],
            **self.run_basearg,
        )
        run.assert_any_call(
            [
                "sudo",
                "tgtadm",
                "--lld",
                "iscsi",
                "--mode",
                "account",
                "--op",
                "new",
                "--user",
                ANY,
                "--password",
                ANY,
            ],
            **self.run_basearg,
        )
        run.assert_any_call(
            ["sudo", "tgtadm", "--lld", "iscsi", "--mode", "account", "--op", "bind", "--tid", "2", "--user", ANY],
            **self.run_basearg,
        )
        run.assert_any_call(
            [
                "sudo",
                "tgtadm",
                "--lld",
                "iscsi",
                "--mode",
                "target",
                "--op",
                "bind",
                "--tid",
                "2",
                "--initiator-address",
                "1.1.1.1/32",
            ],
            **self.run_basearg,
        )
        run.assert_any_call(
            ["sudo", "tgtadm", "--lld", "iscsi", "--mode", "portal", "--op", "show"], **self.run_basearg
        )

    @patch("subprocess.run")
    def test_exportdelete_inuse(self, run):
        run.return_value.exit_code = 0
        run.return_value.stdout = self.target_show_str
        res = TestClient(api).delete("/export/iqn.def")
        self.assertEqual(400, res.status_code)

    @patch("subprocess.run")
    def test_exportdelete_notfound(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = self.target_show_str
        res = TestClient(api).delete("/export/iqn.notfound")
        self.assertEqual(404, res.status_code)

    @patch("subprocess.run")
    def test_exportdelete(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = """
Target 1: iqn.def
    System information:
        Driver: iscsi
        State: ready
    I_T nexus information:
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
            Backing store path: /dev/vg0/vol01
            Backing store flags:
        LUN: 2
            Type: disk
            SCSI ID: IET     00010002
            SCSI SN: beaf12
            Size: 107374 MB, Block size: 512
            Online: Yes
            Removable media: No
            Prevent removal: No
            Readonly: No
            SWP: No
            Thin-provisioning: No
            Backing store type: rdwr
            Backing store path: /dev/vg0/vol02
            Backing store flags:
    Account information:
        user123
    ACL information:
        0.0.0.0/0
        192.168.64.0/24
"""
        res = TestClient(api).delete("/export/iqn.def")
        self.assertEqual(200, res.status_code)
        self.assertEqual(8, run.call_count)
        run.assert_any_call(
            ["sudo", "tgtadm", "--lld", "iscsi", "--mode", "target", "--op", "show"], **self.run_basearg
        )
        run.assert_any_call(
            [
                "sudo",
                "tgtadm",
                "--lld",
                "iscsi",
                "--mode",
                "account",
                "--op",
                "unbind",
                "--tid",
                "1",
                "--user",
                "user123",
            ],
            **self.run_basearg,
        )
        run.assert_any_call(
            ["sudo", "tgtadm", "--lld", "iscsi", "--mode", "account", "--op", "delete", "--user", "user123"],
            **self.run_basearg,
        )
        run.assert_any_call(
            [
                "sudo",
                "tgtadm",
                "--lld",
                "iscsi",
                "--mode",
                "target",
                "--op",
                "unbind",
                "--tid",
                "1",
                "--initiator-address",
                "0.0.0.0/0",
            ],
            **self.run_basearg,
        )
        run.assert_any_call(
            [
                "sudo",
                "tgtadm",
                "--lld",
                "iscsi",
                "--mode",
                "target",
                "--op",
                "unbind",
                "--tid",
                "1",
                "--initiator-address",
                "192.168.64.0/24",
            ],
            **self.run_basearg,
        )
        run.assert_any_call(
            [
                "sudo",
                "tgtadm",
                "--lld",
                "iscsi",
                "--mode",
                "logicalunit",
                "--op",
                "delete",
                "--tid",
                "1",
                "--lun",
                "2",
            ],
            **self.run_basearg,
        )
        run.assert_any_call(
            [
                "sudo",
                "tgtadm",
                "--lld",
                "iscsi",
                "--mode",
                "logicalunit",
                "--op",
                "delete",
                "--tid",
                "1",
                "--lun",
                "1",
            ],
            **self.run_basearg,
        )
        run.assert_any_call(
            ["sudo", "tgtadm", "--lld", "iscsi", "--mode", "target", "--op", "delete", "--tid", "1"], **self.run_basearg
        )

    @patch("subprocess.run")
    def test_exportstat(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = self.target_show_str
        res = TestClient(api).get("/stats/export")
        self.assertEqual(200, res.status_code)
        self.assertEqual(
            dict(targets=1, clients=1, volumes=2),
            res.json(),
        )

    @patch("subprocess.run")
    @patch("ifaddr.get_adapters")
    def test_address(self, geta, run):
        run.return_value.returncode = 0
        run.return_value.stdout = "Portal: 0.0.0.0:3260,1\nPortal: [::]:3260,1\n"
        ifaddr_cls = namedtuple("ifaddrcls", ["name", "ips"])
        ip_cls = namedtuple("ipcls", ["ip", "is_IPv4", "is_IPv6"])
        eth0 = ifaddr_cls("eth0", [ip_cls("1.1.1.1", True, False), ip_cls("1111::1", False, True)])
        eth1 = ifaddr_cls("eth1", [ip_cls("9.9.9.9", True, False)])
        geta.return_value = [eth0, eth1]
        res = TestClient(api).get("/address")
        self.assertEqual(200, res.status_code)
        self.assertEqual(
            ["1.1.1.1:3260", "[1111::1]:3260"],
            res.json(),
        )
