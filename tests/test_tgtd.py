import unittest
import subprocess
from unittest.mock import patch, ANY
from volexport import tgtd


class TestTgtd(unittest.TestCase):
    maxDiff = None
    default_exec = dict(
        capture_output=True,
        encoding="utf-8",
        timeout=10.0,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )

    def test_parse_sys(self):
        testdata_sys = """
System:
    State: ready
    debug: off
LLDs:
    iscsi: ready
Backing stores:
    sheepdog
    bsg
    sg
    null
    ssc
    smc (bsoflags sync:direct)
    mmc (bsoflags sync:direct)
    rdwr (bsoflags sync:direct)
Device types:
    disk
    cd/dvd
    osd
    controller
    changer
    tape
    passthrough
iSNS:
    iSNS=Off
    iSNSServerIP=
    iSNSServerPort=3205
    iSNSAccessControl=Off
"""
        expected = {
            "System": {
                "State": "ready",
                "debug": "off",
            },
            "LLDs": {
                "iscsi": "ready",
            },
            "Backing stores": {
                "sheepdog": None,
                "bsg": None,
                "sg": None,
                "null": None,
                "ssc": None,
                "smc": "bsoflags sync:direct",
                "mmc": "bsoflags sync:direct",
                "rdwr": "bsoflags sync:direct",
            },
            "Device types": {
                "disk": None,
                "cd/dvd": None,
                "osd": None,
                "controller": None,
                "changer": None,
                "tape": None,
                "passthrough": None,
            },
            "iSNS": {
                "iSNS": "Off",
                "iSNSServerIP": None,
                "iSNSServerPort": "3205",
                "iSNSAccessControl": "Off",
            },
        }
        t = tgtd.Tgtd()
        res = t.parse(testdata_sys.splitlines())
        self.assertEqual(expected, res)

    def test_parse_target(self):
        testdata_target = """
Target 1: iqn.abc
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
    Account information:
    ACL information:
"""
        expected = {
            "Target 1": {
                "name": "iqn.abc",
                "System information": {
                    "Driver": "iscsi",
                    "State": "ready",
                },
                "I_T nexus information": None,
                "LUN information": {
                    "LUN 0": {
                        "name": "0",
                        "Type": "controller",
                        "SCSI ID": "IET     00010000",
                        "SCSI SN": "beaf10",
                        "Size": "0 MB, Block size: 1",
                        "Online": "Yes",
                        "Removable media": "No",
                        "Prevent removal": "No",
                        "Readonly": "No",
                        "SWP": "No",
                        "Thin-provisioning": "No",
                        "Backing store type": "null",
                        "Backing store path": "None",
                        "Backing store flags": None,
                    }
                },
                "Account information": None,
                "ACL information": None,
            },
        }
        t = tgtd.Tgtd()
        res = t.parse(testdata_target.splitlines())
        self.assertEqual(expected, res)

    def test_parse_target2(self):
        testdata_target = """
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
        expected = {
            "Target 1": {
                "name": "iqn.def",
                "System information": {
                    "Driver": "iscsi",
                    "State": "ready",
                },
                "I_T nexus information": {
                    "I_T nexus 3": {
                        "name": "3",
                        "Initiator": "iqn.1996-04.org.alpinelinux:01:c1f2520715f alias: test1",
                        "Connection 0": {"name": "0", "IP Address": "192.168.64.41"},
                        "Connection 1": {"name": "1", "IP Address": "192.168.64.42"},
                    }
                },
                "LUN information": {
                    "LUN 0": {
                        "name": "0",
                        "Type": "controller",
                        "SCSI ID": "IET     00010000",
                        "SCSI SN": "beaf10",
                        "Size": "0 MB, Block size: 1",
                        "Online": "Yes",
                        "Removable media": "No",
                        "Prevent removal": "No",
                        "Readonly": "No",
                        "SWP": "No",
                        "Thin-provisioning": "No",
                        "Backing store type": "null",
                        "Backing store path": "None",
                        "Backing store flags": None,
                    },
                    "LUN 1": {
                        "name": "1",
                        "Type": "disk",
                        "SCSI ID": "IET     00010001",
                        "SCSI SN": "beaf11",
                        "Size": "10737 MB, Block size: 512",
                        "Online": "Yes",
                        "Removable media": "No",
                        "Prevent removal": "No",
                        "Readonly": "No",
                        "SWP": "No",
                        "Thin-provisioning": "No",
                        "Backing store type": "rdwr",
                        "Backing store path": "/dev/vg0/vol01",
                        "Backing store flags": None,
                    },
                    "LUN 2": {
                        "name": "2",
                        "Type": "disk",
                        "SCSI ID": "IET     00010002",
                        "SCSI SN": "beaf12",
                        "Size": "107374 MB, Block size: 512",
                        "Online": "Yes",
                        "Removable media": "No",
                        "Prevent removal": "No",
                        "Readonly": "No",
                        "SWP": "No",
                        "Thin-provisioning": "No",
                        "Backing store type": "rdwr",
                        "Backing store path": "/dev/vg0/vol02",
                        "Backing store flags": None,
                    },
                },
                "Account information": {"user123": None},
                "ACL information": {
                    "0.0.0.0/0": None,
                    "192.168.64.0/24": None,
                },
            },
        }
        t = tgtd.Tgtd()
        res = t.parse(testdata_target.splitlines())
        self.assertEqual(expected, res)

    @patch("subprocess.run")
    def test_dump(self, run):
        run.return_value.stdout = "dummy text"
        t = tgtd.Tgtd()
        data = t.dump()
        self.assertEqual("dummy text", data)
        run.assert_called_once_with(["sudo", "tgt-admin", "--dump"], **self.default_exec)

    @patch("subprocess.run")
    def test_restore(self, run):
        run.return_value.stdout = ""
        t = tgtd.Tgtd()
        data = t.restore("dummy text")
        self.assertEqual("", data)
        run.assert_called_once_with(["sudo", "tgt-admin", "-c", ANY, "-e"], **self.default_exec)
