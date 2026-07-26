import unittest
from unittest.mock import ANY, patch

from volexpcsi import api
from volexpcsi.identity import VolExpIdentity
from volexpcsi.server import boot_server


class dummyctxt:
    def peer(self):
        return "client"

    def abort(self, code, details):
        self.code = code
        self.details = details


class TestCsiIdentity(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_GetPluginInfo(self):
        hdl = VolExpIdentity({"endpoint": "hello"})
        req = api.GetPluginInfoRequest()
        ctxt = dummyctxt()
        res = hdl.GetPluginInfo(req, ctxt)
        self.assertEqual("volexport", res.name)
        self.assertNotEqual("", res.vendor_version)

    def test_GetPluginCapabilities(self):
        hdl = VolExpIdentity({"endpoint": "hello"})
        req = api.GetPluginCapabilitiesRequest()
        ctxt = dummyctxt()
        res = hdl.GetPluginCapabilities(req, ctxt)
        self.assertEqual(2, len(res.capabilities))

    @patch("volexport.client.VERequest.get")
    def test_Probe(self, vreq):
        vreq.return_value.status_code = 200
        hdl = VolExpIdentity({"endpoint": "hello"})
        req = api.ProbeRequest()
        ctxt = dummyctxt()
        res = hdl.Probe(req, ctxt)
        self.assertTrue(res.ready.value)
        vreq.assert_called_once_with("/health")

    @patch("volexport.client.VERequest.get")
    def test_Probe_fail(self, vreq):
        vreq.side_effect = TimeoutError("timed out")
        hdl = VolExpIdentity({"endpoint": "hello"})
        req = api.ProbeRequest()
        ctxt = dummyctxt()
        res = hdl.Probe(req, ctxt)
        self.assertFalse(res.ready.value)
        vreq.assert_called_once_with("/health")

    @patch("volexport.client.VERequest.get")
    def test_Probe_notfound(self, vreq):
        vreq.return_value.status_code = 404
        hdl = VolExpIdentity({"endpoint": "hello"})
        req = api.ProbeRequest()
        ctxt = dummyctxt()
        res = hdl.Probe(req, ctxt)
        self.assertFalse(res.ready.value)
        vreq.assert_called_once_with("/health")


class TestCsiBoot(unittest.TestCase):
    @patch("grpc.server")
    def test_boot(self, server):
        server.return_value.add_insecure_port.return_value = 9999
        res = boot_server("localhost:9999", {"endpoint": "http://localhost:9998"})
        self.assertEqual((9999, ANY), res)
