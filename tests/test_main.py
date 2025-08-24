import unittest
from unittest.mock import patch, ANY, MagicMock
from volexport.main import cli
from click.testing import CliRunner


class TestCLI(unittest.TestCase):
    def test_help(self):
        res = CliRunner().invoke(cli, ["--help"])
        self.assertEqual(0, res.exit_code)
        if res.exception:
            raise res.exception
        self.assertIn("server", res.output)
        self.assertIn("apispec", res.output)

    @patch("sys.exit")
    def test_unknown(self, exit):
        res = CliRunner().invoke(cli, ["notfound"])
        if res.exception:
            raise res.exception
        self.assertIn("No such command", res.output)
        exit.assert_called_once_with(2)

    def test_apispec_yaml(self):
        import yaml

        res = CliRunner().invoke(cli, ["apispec"])
        self.assertEqual(0, res.exit_code)
        if res.exception:
            raise res.exception
        resdict = yaml.safe_load(res.output)
        self.assertIn("paths", resdict)

    def test_apispec_json(self):
        import json

        res = CliRunner().invoke(cli, ["apispec", "--format", "json"])
        self.assertEqual(0, res.exit_code)
        if res.exception:
            raise res.exception
        resdict = json.loads(res.output)
        self.assertIn("paths", resdict)

    vgdisplay = MagicMock(
        stdout="""
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
    )
    tgtd = MagicMock(stdout="")

    @patch("uvicorn.run")
    @patch("subprocess.run")
    def test_server_verbose(self, prun, urun):
        prun.side_effect = [self.vgdisplay, self.tgtd]
        res = CliRunner().invoke(cli, ["server", "--verbose"])
        self.assertEqual(0, res.exit_code)
        if res.exception:
            raise res.exception
        urun.assert_called_once_with(ANY, host="127.0.0.1", port=8080, log_config=None)

    @patch("uvicorn.run")
    @patch("subprocess.run")
    def test_server_opts(self, prun, urun):
        prun.side_effect = [self.vgdisplay, self.tgtd]
        res = CliRunner().invoke(
            cli, ["server", "--quiet", "--vg", "vg123", "--nics", "eth0", "--nics", "eth1", "--port", "9999"]
        )
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        urun.assert_called_once_with(ANY, host="127.0.0.1", port=9999, log_config=None)
