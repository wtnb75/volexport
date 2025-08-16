import unittest
from unittest.mock import patch, ANY
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

    @patch("uvicorn.run")
    def test_server_verbose(self, run):
        res = CliRunner().invoke(cli, ["server", "--verbose"])
        self.assertEqual(0, res.exit_code)
        if res.exception:
            raise res.exception
        run.assert_called_once_with(ANY, host="127.0.0.1", port=8080, log_config=None)

    @patch("uvicorn.run")
    def test_server_opts(self, run):
        res = CliRunner().invoke(
            cli, ["server", "--quiet", "--vg", "vg123", "--nics", "eth0", "--nics", "eth1", "--port", "9999"]
        )
        self.assertEqual(0, res.exit_code)
        if res.exception:
            raise res.exception
        run.assert_called_once_with(ANY, host="127.0.0.1", port=9999, log_config=None)
