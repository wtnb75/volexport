import unittest
import grpc
import tempfile
from pathlib import Path
from unittest.mock import patch
from volexpcsi.node import VolExpNode
from volexpcsi import api


class dummyctxt:
    def peer(self):
        return "client"

    def abort(self, code, details):
        self.code = code
        self.details = details


class TestCsiNode(unittest.TestCase):
    basearg = dict(
        capture_output=True,
        encoding="utf-8",
        timeout=10.0,
        stdin=-3,
        start_new_session=True,
    )

    def setUp(self):
        self.srv = VolExpNode(dict(endpoint="http://dummy", nodeid="node123"))

    def tearDown(self):
        del self.srv

    def test_NodeGetInfo(self):
        ctxt = dummyctxt()
        arg = api.NodeGetInfoRequest()
        res = self.srv.NodeGetInfo(arg, ctxt)
        self.assertIsNotNone(res)
        self.assertEqual("node123", res.node_id)

    @patch("volexport.client.VERequest.get")
    @patch("subprocess.run")
    def test_NodeStageVolume(self, run, get):
        get.return_value.status_code = 200
        get.return_value.json.return_value = ["1.1.1.1"]
        ctxt = dummyctxt()
        arg = api.NodeStageVolumeRequest(
            volume_id="volume123",
            staging_target_path="/mnt/tmp",
            volume_capability=api.VolumeCapability(
                access_mode=api.VolumeCapability.AccessMode(mode="SINGLE_NODE_WRITER")
            ),
            publish_context=dict(targetname="iqn.abc:def", user="user123", passwd="pass123"),
        )
        res = self.srv.NodeStageVolume(arg, ctxt)
        self.assertIsNotNone(res)
        get.assert_called_once_with("/address")
        run.assert_any_call(["iscsiadm", "-m", "discovery", "-t", "st", "-p", "1.1.1.1"], **self.basearg)
        run.assert_any_call(
            [
                "iscsiadm",
                "-m",
                "node",
                "-T",
                "iqn.abc:def",
                "-o",
                "update",
                "-n",
                "node.session.auth.authmethod",
                "-v",
                "CHAP",
            ],
            **self.basearg,
        )
        run.assert_any_call(
            [
                "iscsiadm",
                "-m",
                "node",
                "-T",
                "iqn.abc:def",
                "-o",
                "update",
                "-n",
                "node.session.auth.username",
                "-v",
                "user123",
            ],
            **self.basearg,
        )
        run.assert_any_call(
            [
                "iscsiadm",
                "-m",
                "node",
                "-T",
                "iqn.abc:def",
                "-o",
                "update",
                "-n",
                "node.session.auth.password",
                "-v",
                "pass123",
            ],
            **self.basearg,
        )
        run.assert_any_call(["iscsiadm", "-m", "node", "-T", "iqn.abc:def", "-l"], **self.basearg)

    def test_NodeStageVolume_nopath(self):
        ctxt = dummyctxt()
        arg = api.NodeStageVolumeRequest(
            volume_id="volume123",
            volume_capability=api.VolumeCapability(
                access_mode=api.VolumeCapability.AccessMode(mode="SINGLE_NODE_WRITER")
            ),
            publish_context=dict(targetname="iqn.abc:def", user="user123", passwd="pass123"),
        )
        res = self.srv.NodeStageVolume(arg, ctxt)
        self.assertIsNone(res)
        self.assertEqual(grpc.StatusCode.INVALID_ARGUMENT, ctxt.code)

    def test_NodeStageVolume_novol(self):
        ctxt = dummyctxt()
        arg = api.NodeStageVolumeRequest(
            staging_target_path="/mnt/tmp",
            volume_capability=api.VolumeCapability(
                access_mode=api.VolumeCapability.AccessMode(mode="SINGLE_NODE_WRITER")
            ),
            publish_context=dict(targetname="iqn.abc:def", user="user123", passwd="pass123"),
        )
        res = self.srv.NodeStageVolume(arg, ctxt)
        self.assertIsNone(res)
        self.assertEqual(grpc.StatusCode.INVALID_ARGUMENT, ctxt.code)

    @patch("volexport.client.VERequest.get")
    @patch("subprocess.run")
    def test_NodeUnstageVolume(self, run, get):
        get.return_value.status_code = 200
        get.return_value.json.return_value = [dict(targetname="iqn.abc:def", volumes=["volume123"])]
        run.return_value.stdout = "Logout from [1.1.1.1:3260] successful."
        ctxt = dummyctxt()
        arg = api.NodeUnstageVolumeRequest(
            volume_id="volume123",
            staging_target_path="/mnt/tmp",
        )
        res = self.srv.NodeUnstageVolume(arg, ctxt)
        self.assertIsNotNone(res)
        get.assert_called_once_with("/export", params=dict(volume="volume123"))
        run.assert_any_call(["iscsiadm", "-m", "node", "-T", "iqn.abc:def", "-u"], **self.basearg)
        run.assert_any_call(
            ["iscsiadm", "-m", "discoverydb", "-t", "st", "-p", "1.1.1.1:3260", "-o", "delete"], **self.basearg
        )

    def test_NodeUnstageVolume_nopath(self):
        ctxt = dummyctxt()
        arg = api.NodeUnstageVolumeRequest(
            volume_id="volume123",
        )
        res = self.srv.NodeUnstageVolume(arg, ctxt)
        self.assertIsNone(res)
        self.assertEqual(grpc.StatusCode.INVALID_ARGUMENT, ctxt.code)

    def test_NodeUnstageVolume_novolume(self):
        ctxt = dummyctxt()
        arg = api.NodeUnstageVolumeRequest(
            staging_target_path="/mnt/tmp",
        )
        res = self.srv.NodeUnstageVolume(arg, ctxt)
        self.assertIsNone(res)
        self.assertEqual(grpc.StatusCode.INVALID_ARGUMENT, ctxt.code)

    @patch("subprocess.run")
    def test_NodePublishVolume(self, run):
        ctxt = dummyctxt()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "target"
            arg = api.NodePublishVolumeRequest(
                volume_id="volume123",
                target_path=str(path),
                volume_capability=api.VolumeCapability(mount=api.VolumeCapability.MountVolume(fs_type="ext4")),
            )
            self.assertFalse(path.exists())
            res = self.srv.NodePublishVolume(arg, ctxt)
            self.assertIsNotNone(res)
            self.assertTrue(path.exists())
            run.assert_any_call(["mount", "-L", "volume123", str(path)], **self.basearg)

    @unittest.skip("pathlib.Path.is_mount?")
    @patch("subprocess.run")
    def test_NodeUnpublishVolume(self, run):
        ctxt = dummyctxt()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "target"
            path.mkdir()
            with patch("pathlib.Path") as p:
                p.return_value.is_mount.return_value = True
                arg = api.NodeUnpublishVolumeRequest(
                    volume_id="volume123",
                    target_path=str(path),
                )
            self.assertTrue(path.exists())
            res = self.srv.NodeUnpublishVolume(arg, ctxt)
            self.assertIsNotNone(res)
            self.assertFalse(path.exists())
            run.assert_any_call(["umount", str(path)], **self.basearg)

    @patch("volexport.client.VERequest.get")
    @patch("subprocess.run")
    def test_NodeExpandVolume(self, run, get):
        run.return_value.stdout = "/dev/sda\n"
        get.return_value.status_code = 200
        get.return_value.json.return_value = [dict(targetname="iqn.abc:def", volumes=["volume123"])]
        ctxt = dummyctxt()
        arg = api.NodeExpandVolumeRequest(
            volume_id="volume123", volume_path="/mnt/tmp", capacity_range=api.CapacityRange(required_bytes=10240)
        )
        res = self.srv.NodeExpandVolume(arg, ctxt)
        self.assertIsNotNone(res)
        run.assert_any_call(["blkid", "-L", "volume123"], **self.basearg)
        run.assert_any_call(["iscsiadm", "-m", "node", "-T", "iqn.abc:def", "-R"], **self.basearg)
        run.assert_any_call(["resize2fs", "/dev/sda"], **self.basearg)

    def test_NodeGetCapabilities(self):
        ctxt = dummyctxt()
        arg = api.NodeGetCapabilitiesRequest()
        res = self.srv.NodeGetCapabilities(arg, ctxt)
        self.assertIsNotNone(res)
