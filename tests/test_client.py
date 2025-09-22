import unittest
import json
import tempfile
import requests
from unittest.mock import patch, ANY
from click.testing import CliRunner
from volexport.client import cli


class TestClientCLI(unittest.TestCase):
    envs = {"VOLEXP_ENDPOINT": "http://dummy.local"}

    def test_help(self):
        res = CliRunner().invoke(cli, ["--help"])
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertIn("volume-create", res.stdout)

    @patch.object(requests.Session, "request")
    def test_volume_list(self, req):
        output = [{"name": "volume1"}]
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["volume-list"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with("GET", "http://dummy.local/volume", allow_redirects=True)

    @patch.object(requests.Session, "request")
    def test_volume_list_yaml(self, req):
        output = [{"name": "volume1"}]
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["volume-list", "--format", "yaml"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual("- name: volume1", res.stdout.strip())
        req.assert_called_once_with("GET", "http://dummy.local/volume", allow_redirects=True)

    @patch.object(requests.Session, "request")
    def test_volume_list_pprint(self, req):
        output = [{"name": "volume1"}]
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["volume-list", "--format", "pprint"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual("[{'name': 'volume1'}]", res.stdout.strip())
        req.assert_called_once_with("GET", "http://dummy.local/volume", allow_redirects=True)

    @patch.object(requests.Session, "request")
    def test_volume_list_ijson(self, req):
        output = [{"name": "volume1"}]
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["volume-list", "--format", "pjson"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with("GET", "http://dummy.local/volume", allow_redirects=True)

    @patch.object(requests.Session, "request")
    def test_volume_list_notjson(self, req):
        req.return_value.status_code = 200
        req.return_value.text = "plain text"
        req.return_value.json.side_effect = ValueError("not json")
        res = CliRunner().invoke(cli, ["volume-list"], env=self.envs)
        self.assertEqual(1, res.exit_code)
        req.assert_called_once_with("GET", "http://dummy.local/volume", allow_redirects=True)

    @patch.object(requests.Session, "request")
    def test_volume_list_error(self, req):
        req.return_value.status_code = 500
        req.return_value.json.return_value = {"detail": "something went wrong"}
        exc = Exception("error")
        req.return_value.raise_for_status.side_effect = exc
        res = CliRunner().invoke(cli, ["volume-list"], env=self.envs)
        self.assertEqual(exc, res.exception)
        self.assertEqual(1, res.exit_code)
        req.assert_called_once_with("GET", "http://dummy.local/volume", allow_redirects=True)

    @patch.object(requests.Session, "request")
    def test_volume_read(self, req):
        output = {"name": "volume1"}
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["volume-read", "--name", "name"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with("GET", "http://dummy.local/volume/name", allow_redirects=True)

    @patch.object(requests.Session, "request")
    def test_volume_read_validation(self, req):
        output = {"detail": [{"loc": [], "msg": "invalid input"}]}
        req.return_value.status_code = 422
        req.return_value.json.return_value = output
        with self.assertLogs(level="WARNING") as alog:
            res = CliRunner().invoke(cli, ["volume-read", "--name", "name"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertIn("invalid input", "\n".join(alog.output))
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with("GET", "http://dummy.local/volume/name", allow_redirects=True)

    @patch.object(requests.Session, "request")
    def test_volume_read_connection(self, req):
        exc = TimeoutError("timeout")
        req.side_effect = exc
        res = CliRunner().invoke(cli, ["volume-read", "--name", "name"], env=self.envs)
        self.assertEqual(exc, res.exception)
        self.assertEqual(1, res.exit_code)
        req.assert_called_once_with("GET", "http://dummy.local/volume/name", allow_redirects=True)

    @patch.object(requests.Session, "request")
    def test_volume_create(self, req):
        output = {"name": "volume1"}
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["volume-create", "--name", "vol123", "--size", "1G"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with(
            "POST", "http://dummy.local/volume", data=None, json={"name": "vol123", "size": 1024 * 1024 * 1024}
        )

    @patch.object(requests.Session, "request")
    def test_volume_delete(self, req):
        output = {"status": "OK"}
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["volume-delete", "--name", "vol123"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with("DELETE", "http://dummy.local/volume/vol123")

    @patch.object(requests.Session, "request")
    def test_volume_stats(self, req):
        output = {"abc": 123}
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["volume-stats"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with("GET", "http://dummy.local/stats/volume", allow_redirects=True)

    @patch.object(requests.Session, "request")
    def test_volume_readonly(self, req):
        output = {"abc": 123}
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["volume-readonly", "--name", "vol123"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with("POST", "http://dummy.local/volume/vol123", json={"readonly": True}, data=None)

    @patch.object(requests.Session, "request")
    def test_volume_resize(self, req):
        output = {"abc": 123}
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["volume-resize", "--name", "vol123", "--size", "1T"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with("POST", "http://dummy.local/volume/vol123", json={"size": 1024**4}, data=None)

    @patch.object(requests.Session, "request")
    def test_volume_mkfs(self, req):
        output = {"abc": 123}
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["volume-mkfs", "--name", "vol123", "--filesystem", "xfs"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with(
            "POST", "http://dummy.local/volume/vol123/mkfs", json={"filesystem": "xfs", "label": None}, data=None
        )

    @patch.object(requests.Session, "request")
    def test_export_list(self, req):
        output = [{"abc": 123}]
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["export-list"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with("GET", "http://dummy.local/export", allow_redirects=True)

    @patch.object(requests.Session, "request")
    def test_export_stats(self, req):
        output = {"abc": 123}
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["export-stats"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with("GET", "http://dummy.local/stats/export", allow_redirects=True)

    @patch.object(requests.Session, "request")
    def test_export_create(self, req):
        output = {"addresses": ["1.2.3.4"], "targetname": "iqn.abc:def", "user": "user123", "passwd": "passwd123"}
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["export-create", "--name", "vol123"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        req.assert_called_once_with("POST", "http://dummy.local/export", json={"name": "vol123", "acl": []}, data=None)
        self.assertIn("iscsiadm", res.stdout)
        self.assertIn("iqn.abc:def", res.stdout)
        self.assertIn("user123", res.stdout)
        self.assertIn("passwd123", res.stdout)
        self.assertIn("1.2.3.4", res.stdout)

    @patch.object(requests.Session, "request")
    def test_export_read(self, req):
        output = {"abc": 123}
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["export-read", "--targetname", "iqn.abc:def"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with("GET", "http://dummy.local/export/iqn.abc:def", allow_redirects=True)

    @patch.object(requests.Session, "request")
    def test_export_delete(self, req):
        output = {"abc": 123}
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["export-delete", "--targetname", "iqn.abc:def"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with("DELETE", "http://dummy.local/export/iqn.abc:def", params={})

    @patch.object(requests.Session, "request")
    def test_export_delete_force(self, req):
        output = {"abc": 123}
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["export-delete", "--targetname", "iqn.abc:def", "--force"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with("DELETE", "http://dummy.local/export/iqn.abc:def", params={"force": "1"})

    @patch.object(requests.Session, "request")
    def test_address(self, req):
        output = ["1.2.3.4"]
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["address"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with("GET", "http://dummy.local/address", allow_redirects=True)

    @patch.object(requests.Session, "request")
    def test_snapshot_create(self, req):
        output = {"abc": 123}
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(
            cli, ["snapshot-create", "--name", "vol123", "--parent", "parent123", "--size", "10M"], env=self.envs
        )
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with(
            "POST",
            "http://dummy.local/volume/parent123/snapshot",
            data=None,
            json=dict(name="vol123", size=10 * 1024 * 1024),
        )

    @patch.object(requests.Session, "request")
    def test_snapshot_list(self, req):
        output = {"abc": 123}
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["snapshot-list", "--parent", "parent123"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with(
            "GET",
            "http://dummy.local/volume/parent123/snapshot",
            allow_redirects=True,
        )

    @patch.object(requests.Session, "request")
    def test_snapshot_get(self, req):
        output = {"abc": 123}
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["snapshot-get", "--parent", "parent123", "--name", "vol123"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with(
            "GET",
            "http://dummy.local/volume/parent123/snapshot/vol123",
            allow_redirects=True,
        )

    @patch.object(requests.Session, "request")
    def test_snapshot_delete(self, req):
        output = {"abc": 123}
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["snapshot-delete", "--parent", "parent123", "--name", "vol123"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with("DELETE", "http://dummy.local/volume/parent123/snapshot/vol123")

    @patch.object(requests.Session, "request")
    def test_backup_list(self, req):
        output = {"abc": 123}
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["backup-list"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with("GET", "http://dummy.local/mgmt/backup", allow_redirects=True)

    @patch.object(requests.Session, "request")
    def test_backup_create(self, req):
        output = {"abc": 123}
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["backup-create"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with("POST", "http://dummy.local/mgmt/backup", data=None, json=None)

    @patch.object(requests.Session, "request")
    def test_backup_read(self, req):
        req.return_value.status_code = 200
        req.return_value.text = "hello\n"
        res = CliRunner().invoke(cli, ["backup-read", "--name", "backup123"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual("hello\n", res.stdout)
        req.assert_called_once_with("GET", "http://dummy.local/mgmt/backup/backup123", allow_redirects=True)

    @patch.object(requests.Session, "request")
    def test_backup_restore(self, req):
        output = {"abc": 123}
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["backup-restore", "--name", "backup123"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with("POST", "http://dummy.local/mgmt/backup/backup123", data=None, json=None)

    @patch.object(requests.Session, "request")
    def test_backup_put(self, req):
        output = {"abc": 123}
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        with tempfile.NamedTemporaryFile("r+") as tf:
            tf.write("hello\n")
            tf.flush()
            res = CliRunner().invoke(cli, ["backup-put", "--name", "backup123", "--input", tf.name], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with("PUT", "http://dummy.local/mgmt/backup/backup123", data="hello\n")

    @patch.object(requests.Session, "request")
    def test_backup_forget(self, req):
        output = {"abc": 123}
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["backup-forget", "--keep", "10"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with("DELETE", "http://dummy.local/mgmt/backup", params=dict(keep=10))

    @patch.object(requests.Session, "request")
    def test_backup_delete(self, req):
        output = {"abc": 123}
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["backup-delete", "--name", "backup123"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        self.assertEqual(output, json.loads(res.stdout))
        req.assert_called_once_with("DELETE", "http://dummy.local/mgmt/backup/backup123")

    @patch.object(requests.Session, "request")
    @patch("subprocess.run")
    def test_attach_volume(self, run, req):
        output = dict(targetname="iqn.abc:def", user="user123", passwd="pass123", addresses=["1.1.1.1"])
        req.return_value.status_code = 200
        req.return_value.json.return_value = output
        res = CliRunner().invoke(cli, ["attach-volume", "--name", "volume123"], env=self.envs)
        if res.exception:
            raise res.exception
        self.assertEqual(0, res.exit_code)
        req.assert_called_once_with(
            "POST", "http://dummy.local/export", data=None, json=dict(name="volume123", acl=ANY)
        )
        basearg = dict(
            capture_output=True,
            encoding="utf-8",
            timeout=10.0,
            stdin=-3,
            start_new_session=True,
        )
        run.assert_any_call(["sudo", "iscsiadm", "-m", "discovery", "-t", "st", "-p", "1.1.1.1"], **basearg)
        run.assert_any_call(
            [
                "sudo",
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
            **basearg,
        )
        run.assert_any_call(
            [
                "sudo",
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
            **basearg,
        )
        run.assert_any_call(
            [
                "sudo",
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
            **basearg,
        )
        run.assert_any_call(
            ["sudo", "iscsiadm", "-m", "node", "-T", "iqn.abc:def", "-l"],
            **basearg,
        )
