import unittest
import os
import shutil
import subprocess
from volexpcsi.server import boot_server

have_sanity = shutil.which(os.getenv("TEST_CSI_SANITY_BIN", "csi-sanity"))
have_volexport = os.getenv("TEST_VOLEXPORT")


@unittest.skipUnless(have_sanity and have_volexport, "do not have csi-sanity")
class TestCsiSanity(unittest.TestCase):
    def setUp(self):
        self.port, self.srv = boot_server("localhost:0", {"endpoint": have_volexport, "nodeid": "node123"})

    def tearDown(self):
        if hasattr(self, "srv"):
            self.srv.stop(grace=1.0)
        del self.srv
        del self.port

    def test_sanity(self):
        assert have_sanity is not None
        res = subprocess.run([have_sanity, f"--csi.endpoint=localhost:{self.port}"])
        res.check_returncode()
