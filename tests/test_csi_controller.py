import unittest
from unittest.mock import patch, MagicMock
from volexpcsi.controller import VolExpControl
from volexpcsi import api
from requests.exceptions import HTTPError
import grpc


class dummyctxt:
    def peer(self):
        return "client"

    def abort(self, code, details):
        self.code = code
        self.details = details


class TestCsiControl(unittest.TestCase):
    def setUp(self):
        self.srv = VolExpControl(dict(endpoint="http://dummy"))

    def tearDown(self):
        del self.srv

    @patch("volexport.client.VERequest.get")
    def test_GetCapacity(self, get):
        get.return_value.status_code = 200
        get.return_value.json.return_value = dict(free=12345)
        arg = api.GetCapacityRequest(
            volume_capabilities=[
                api.VolumeCapability(access_mode=api.VolumeCapability.AccessMode(mode="SINGLE_NODE_WRITER"))
            ]
        )
        ctxt = dummyctxt()
        res = self.srv.GetCapacity(arg, ctxt)
        self.assertEqual(12345, res.available_capacity)
        get.assert_called_once_with("/stats/volume")

    @patch("volexport.client.VERequest.get")
    def test_GetCapacity_error(self, get):
        get.return_value.status_code = 500
        get.return_value.raise_for_status.side_effect = HTTPError("error", response=MagicMock(status_code=500))
        arg = api.GetCapacityRequest(
            volume_capabilities=[
                api.VolumeCapability(access_mode=api.VolumeCapability.AccessMode(mode="SINGLE_NODE_WRITER"))
            ]
        )
        ctxt = dummyctxt()
        res = self.srv.GetCapacity(arg, ctxt)
        self.assertIsNone(res)
        self.assertEqual(grpc.StatusCode.INTERNAL, ctxt.code)
        get.assert_called_once_with("/stats/volume")

    @patch("volexport.client.VERequest.get")
    def test_GetCapacity_timeout(self, get):
        get.return_value.raise_for_status.side_effect = TimeoutError("timed out")
        arg = api.GetCapacityRequest(
            volume_capabilities=[
                api.VolumeCapability(access_mode=api.VolumeCapability.AccessMode(mode="SINGLE_NODE_WRITER"))
            ]
        )
        ctxt = dummyctxt()
        res = self.srv.GetCapacity(arg, ctxt)
        self.assertIsNone(res)
        self.assertEqual(grpc.StatusCode.DEADLINE_EXCEEDED, ctxt.code)
        get.assert_called_once_with("/stats/volume")

    def test_ControllerGetCapbilities(self):
        arg = api.ControllerGetCapabilitiesRequest()
        ctxt = dummyctxt()
        res = self.srv.ControllerGetCapabilities(arg, ctxt)
        self.assertIsNotNone(res)

    @patch("volexport.client.VERequest.get")
    def test_ListVolumes(self, get):
        get.return_value.status_code = 200
        get.return_value.json.return_value = [
            dict(name="vol123", size=12345),
            dict(name="vol234", size=23456),
            dict(name="volnext", size=999),
        ]
        arg = api.ListVolumesRequest(max_entries=2)
        ctxt = dummyctxt()
        res = self.srv.ListVolumes(arg, ctxt)
        self.assertEqual(2, len(res.entries))
        self.assertEqual("vol-volnext", res.next_token)
        self.assertEqual("vol123", res.entries[0].volume.volume_id)
        self.assertEqual(12345, res.entries[0].volume.capacity_bytes)
        self.assertEqual("vol234", res.entries[1].volume.volume_id)
        self.assertEqual(23456, res.entries[1].volume.capacity_bytes)
        get.assert_called_once_with("/volume")
        get.reset_mock()
        # next token
        arg = api.ListVolumesRequest(max_entries=2, starting_token=res.next_token)
        res = self.srv.ListVolumes(arg, ctxt)
        self.assertEqual(1, len(res.entries))
        self.assertEqual("", res.next_token)
        self.assertEqual("volnext", res.entries[0].volume.volume_id)
        self.assertEqual(999, res.entries[0].volume.capacity_bytes)
        get.assert_called_once_with("/volume")

    @patch("volexport.client.VERequest.get")
    def test_ListVolumes_invalid(self, get):
        get.return_value.status_code = 200
        get.return_value.json.return_value = [
            dict(name="vol123", size=12345),
            dict(name="vol234", size=23456),
            dict(name="volnext", size=999),
        ]
        arg = api.ListVolumesRequest(max_entries=2, starting_token="dummy")
        ctxt = dummyctxt()
        res = self.srv.ListVolumes(arg, ctxt)
        self.assertIsNone(res)
        self.assertEqual(grpc.StatusCode.ABORTED, ctxt.code)
        self.assertIn("invalid starting token", ctxt.details)
        get.assert_called_once_with("/volume")

    @patch("volexport.client.VERequest.get")
    @patch("volexport.client.VERequest.post")
    def test_CreateVolume(self, post, get):
        get.return_value.status_code = 404
        post.return_value.status_code = 200
        post.return_value.json.return_value = dict(name="vol123", size=1024)
        arg = api.CreateVolumeRequest(name="vol123", capacity_range=api.CapacityRange(required_bytes=123))
        ctxt = dummyctxt()
        res = self.srv.CreateVolume(arg, ctxt)
        self.assertIsNotNone(res)
        self.assertEqual("vol123", res.volume.volume_id)
        self.assertEqual(1024, res.volume.capacity_bytes)
        get.assert_called_once_with("/volume/vol123")
        post.assert_any_call("/volume", json=dict(name="vol123", size=123))
        post.assert_any_call("/volume/vol123/mkfs", json={})

    @patch("volexport.client.VERequest.get")
    @patch("volexport.client.VERequest.post")
    def test_CreateVolume_exists_ok(self, post, get):
        get.return_value.status_code = 200
        get.return_value.json.return_value = dict(name="vol123", size=1024)
        arg = api.CreateVolumeRequest(name="vol123", capacity_range=api.CapacityRange(required_bytes=123))
        ctxt = dummyctxt()
        res = self.srv.CreateVolume(arg, ctxt)
        self.assertIsNotNone(res)
        self.assertEqual("vol123", res.volume.volume_id)
        self.assertEqual(1024, res.volume.capacity_bytes)
        get.assert_called_once_with("/volume/vol123")
        post.assert_not_called()

    @patch("volexport.client.VERequest.get")
    def test_CreateVolume_exists_undersize(self, get):
        get.return_value.status_code = 200
        get.return_value.json.return_value = dict(name="vol123", size=1024)
        arg = api.CreateVolumeRequest(name="vol123", capacity_range=api.CapacityRange(required_bytes=2048))
        ctxt = dummyctxt()
        res = self.srv.CreateVolume(arg, ctxt)
        self.assertIsNone(res)
        self.assertEqual(grpc.StatusCode.ALREADY_EXISTS, ctxt.code)

    @patch("volexport.client.VERequest.get")
    def test_CreateVolume_exists_oversize(self, get):
        get.return_value.status_code = 200
        get.return_value.json.return_value = dict(name="vol123", size=10240)
        arg = api.CreateVolumeRequest(
            name="vol123", capacity_range=api.CapacityRange(required_bytes=2048, limit_bytes=4096)
        )
        ctxt = dummyctxt()
        res = self.srv.CreateVolume(arg, ctxt)
        self.assertIsNone(res)
        self.assertEqual(grpc.StatusCode.ALREADY_EXISTS, ctxt.code)

    def test_CreateVolume_noname(self):
        arg = api.CreateVolumeRequest(capacity_range=api.CapacityRange(required_bytes=2048))
        ctxt = dummyctxt()
        res = self.srv.CreateVolume(arg, ctxt)
        self.assertIsNone(res)
        self.assertEqual(grpc.StatusCode.INVALID_ARGUMENT, ctxt.code)

    def test_CreateVolume_nocapacity(self):
        arg = api.CreateVolumeRequest(name="vol123")
        ctxt = dummyctxt()
        res = self.srv.CreateVolume(arg, ctxt)
        self.assertIsNone(res)
        self.assertEqual(grpc.StatusCode.INVALID_ARGUMENT, ctxt.code)

    @patch("volexport.client.VERequest.delete")
    def test_DeleteVolume(self, delete):
        delete.return_value.status_code = 200
        arg = api.DeleteVolumeRequest(volume_id="vol123")
        ctxt = dummyctxt()
        res = self.srv.DeleteVolume(arg, ctxt)
        self.assertIsNotNone(res)
        delete.assert_called_once_with("/volume/vol123")

    @patch("volexport.client.VERequest.delete")
    def test_DeleteVolume_notfound_ok(self, delete):
        delete.return_value.status_code = 404
        arg = api.DeleteVolumeRequest(volume_id="vol123")
        ctxt = dummyctxt()
        res = self.srv.DeleteVolume(arg, ctxt)
        self.assertIsNotNone(res)
        delete.assert_called_once_with("/volume/vol123")

    @patch("volexport.client.VERequest.post")
    def test_ControllerPublishVolume(self, post):
        post.return_value.status_code = 200
        postres = dict(
            protocol="iscsi",
            addresses=["1.1.1.1", "2.2.2.2"],
            targetname="iqn.abc:def",
            tid=1,
            user="user123",
            passwd="passwd123",
            lun=1,
            acl=["3.3.3.3"],
        )
        post.return_value.json.return_value = postres
        arg = api.ControllerPublishVolumeRequest(
            volume_id="vol123",
            node_id="node123",
            volume_capability=api.VolumeCapability(
                access_mode=api.VolumeCapability.AccessMode(mode="SINGLE_NODE_WRITER"),
                mount=api.VolumeCapability.MountVolume(fs_type="ext4"),
            ),
        )
        ctxt = dummyctxt()
        res = self.srv.ControllerPublishVolume(arg, ctxt)
        self.assertIsNotNone(res)
        self.assertEqual({k: str(v) for k, v in postres.items()}, res.publish_context)
        post.assert_called_once_with("/export", json=dict(name="vol123", readonly=False, acl=None))

    def test_ControllerPublishVolume_nodeid_empty(self):
        arg = api.ControllerPublishVolumeRequest(
            volume_id="vol123",
            volume_capability=api.VolumeCapability(
                access_mode=api.VolumeCapability.AccessMode(mode="SINGLE_NODE_WRITER"),
                mount=api.VolumeCapability.MountVolume(fs_type="ext4"),
            ),
        )
        ctxt = dummyctxt()
        res = self.srv.ControllerPublishVolume(arg, ctxt)
        self.assertIsNone(res)
        self.assertEqual(grpc.StatusCode.INVALID_ARGUMENT, ctxt.code)

    def test_ControllerPublishVolume_volumeid_empty(self):
        arg = api.ControllerPublishVolumeRequest(
            node_id="node123",
            volume_capability=api.VolumeCapability(
                access_mode=api.VolumeCapability.AccessMode(mode="SINGLE_NODE_WRITER"),
                mount=api.VolumeCapability.MountVolume(fs_type="ext4"),
            ),
        )
        ctxt = dummyctxt()
        res = self.srv.ControllerPublishVolume(arg, ctxt)
        self.assertIsNone(res)
        self.assertEqual(grpc.StatusCode.INVALID_ARGUMENT, ctxt.code)

    def test_ControllerPublishVolume_capability_empty(self):
        arg = api.ControllerPublishVolumeRequest(
            volume_id="vol123",
            node_id="node123",
        )
        ctxt = dummyctxt()
        res = self.srv.ControllerPublishVolume(arg, ctxt)
        self.assertIsNone(res)
        self.assertEqual(grpc.StatusCode.INVALID_ARGUMENT, ctxt.code)

    def test_ControllerPublishVolume_invalid_fs(self):
        arg = api.ControllerPublishVolumeRequest(
            volume_id="vol123",
            node_id="node123",
            volume_capability=api.VolumeCapability(
                access_mode=api.VolumeCapability.AccessMode(mode="SINGLE_NODE_WRITER"),
            ),
        )
        ctxt = dummyctxt()
        res = self.srv.ControllerPublishVolume(arg, ctxt)
        self.assertIsNone(res)
        self.assertEqual(grpc.StatusCode.INVALID_ARGUMENT, ctxt.code)

    @patch("volexport.client.VERequest.delete")
    @patch("volexport.client.VERequest.get")
    def test_ControllerUnpublishVolume(self, get, delete):
        get.return_value.status_code = 200
        get.return_value.json.return_value = [
            dict(targetname="iqn.abc:invalid", volumes=["vol999"]),
            dict(targetname="iqn.abc:def", volumes=["vol123"]),
        ]
        delete.return_value.status_code = 200
        arg = api.ControllerUnpublishVolumeRequest(volume_id="vol123", node_id="node123")
        ctxt = dummyctxt()
        res = self.srv.ControllerUnpublishVolume(arg, ctxt)
        self.assertIsNotNone(res)
        get.assert_called_once_with("/export", params=dict(volume="vol123"))
        delete.assert_called_once_with("/export/iqn.abc:def")

    @patch("volexport.client.VERequest.delete")
    @patch("volexport.client.VERequest.get")
    def test_ControllerUnpublishVolume_notfound(self, get, delete):
        get.return_value.status_code = 200
        get.return_value.json.return_value = []
        delete.return_value.status_code = 200
        arg = api.ControllerUnpublishVolumeRequest(volume_id="vol123", node_id="node123")
        ctxt = dummyctxt()
        res = self.srv.ControllerUnpublishVolume(arg, ctxt)
        self.assertIsNotNone(res)
        get.assert_called_once_with("/export", params=dict(volume="vol123"))
        delete.assert_not_called()

    @patch("volexport.client.VERequest.post")
    def test_ControllerExpandVolume(self, post):
        post.return_value.status_code = 200
        post.return_value.json.return_value = dict(size=15000)
        arg = api.ControllerExpandVolumeRequest(
            volume_id="vol123", capacity_range=api.CapacityRange(required_bytes=12345, limit_bytes=23456)
        )
        ctxt = dummyctxt()
        res = self.srv.ControllerExpandVolume(arg, ctxt)
        self.assertIsNotNone(res)
        self.assertEqual(15000, res.capacity_bytes)
        self.assertTrue(res.node_expansion_required)
        post.assert_called_once_with("/volume/vol123", json=dict(size=12345))

    @patch("volexport.client.VERequest.get")
    def test_ControllerGetVolume(self, get):
        volget = MagicMock(status_code=200)
        volget.json.return_value = dict(name="vol123", size=15000)
        expget = MagicMock(status_code=200)
        expget.json.return_value = [dict(connected=dict(address="1.1.1.1"))]
        get.side_effect = [volget, expget]
        arg = api.ControllerGetVolumeRequest(volume_id="vol123")
        ctxt = dummyctxt()
        res = self.srv.ControllerGetVolume(arg, ctxt)
        self.assertIsNotNone(res)
        self.assertEqual(15000, res.volume.capacity_bytes)
        self.assertEqual("vol123", res.volume.volume_id)
        get.assert_any_call("/volume/vol123")
        get.assert_any_call("/export", params=dict(volume="vol123"))
