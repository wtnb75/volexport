import unittest
from unittest.mock import patch
from volexpcsi.identity import VolExpIdentity
from volexpcsi import api


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
        hdl = VolExpIdentity(dict(endpoint="hello"))
        req = api.GetPluginInfoRequest()
        ctxt = dummyctxt()
        res = hdl.GetPluginInfo(req, ctxt)
        self.assertEqual("volexport", res.name)
        self.assertNotEqual("", res.vendor_version)

    def test_GetPluginCapabilities(self):
        hdl = VolExpIdentity(dict(endpoint="hello"))
        req = api.GetPluginCapabilitiesRequest()
        ctxt = dummyctxt()
        res = hdl.GetPluginCapabilities(req, ctxt)
        self.assertEqual(2, len(res.capabilities))

    @patch("volexport.client.VERequest.get")
    def test_Probe(self, vreq):
        vreq.return_value.status_code = 200
        hdl = VolExpIdentity(dict(endpoint="hello"))
        req = api.ProbeRequest()
        ctxt = dummyctxt()
        res = hdl.Probe(req, ctxt)
        self.assertTrue(res.ready.value)
        vreq.assert_called_once_with("/health")

    @patch("volexport.client.VERequest.get")
    def test_Probe_fail(self, vreq):
        vreq.side_effect = TimeoutError("timed out")
        hdl = VolExpIdentity(dict(endpoint="hello"))
        req = api.ProbeRequest()
        ctxt = dummyctxt()
        res = hdl.Probe(req, ctxt)
        self.assertFalse(res.ready.value)
        vreq.assert_called_once_with("/health")

    @patch("volexport.client.VERequest.get")
    def test_Probe_notfound(self, vreq):
        vreq.return_value.status_code = 404
        hdl = VolExpIdentity(dict(endpoint="hello"))
        req = api.ProbeRequest()
        ctxt = dummyctxt()
        res = hdl.Probe(req, ctxt)
        self.assertFalse(res.ready.value)
        vreq.assert_called_once_with("/health")
