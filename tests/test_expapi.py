import unittest
import subprocess
from unittest.mock import patch, ANY
from fastapi.testclient import TestClient
from volexport.api import api


class TestExportAPI(unittest.TestCase):
    maxDiff = None

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
            ["sudo", "tgtadm", "--lld", "iscsi", "--mode", "target", "--op", "show"],
            capture_output=True,
            encoding="utf-8",
        )

    @patch("subprocess.run")
    def test_exportlist(self, run):
        target_show = """
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
        run.return_value.exit_code = 0
        run.return_value.stdout = target_show
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
                    volumes=["/dev/vg0/vol01", "/dev/vg0/vol02"],
                )
            ],
            res.json(),
        )
