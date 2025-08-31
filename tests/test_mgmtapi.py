import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, ANY
from fastapi.testclient import TestClient
from volexport.api import api
from volexport.config import config


class TestMgmtAPI(unittest.TestCase):
    run_basearg = dict(capture_output=True, encoding="utf-8", timeout=10.0, stdin=-3, start_new_session=True)

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.orig_bak = config.BACKUP_DIR
        config.BACKUP_DIR = self.td.name

    def tearDown(self):
        self.td.cleanup()
        config.BACKUP_DIR = self.orig_bak

    @patch("subprocess.run")
    def test_create_list_get_backup(self, run):
        run.return_value.stdout = """
hello world
"""
        client = TestClient(api)
        res = client.post("/mgmt/backup")
        self.assertEqual(200, res.status_code)
        self.assertIn("name", res.json())
        name: str = res.json()["name"]
        self.assertTrue((Path(self.td.name) / name).with_suffix(".backup").exists())
        run.assert_called_once_with(["sudo", "tgt-admin", "--dump"], **self.run_basearg)

        reslist = client.get("/mgmt/backup")
        self.assertEqual(200, reslist.status_code)
        self.assertEqual([{"name": name}], reslist.json())

        resget = client.get(f"/mgmt/backup/{name}")
        self.assertEqual(200, resget.status_code)
        self.assertEqual(run.return_value.stdout, resget.text)

        resnotfound = client.get("/mgmt/backup/notfound")
        self.assertEqual(404, resnotfound.status_code)

    def test_forget(self):
        bkdir = Path(self.td.name)
        (bkdir / "2025-08-29.backup").write_text("123")
        (bkdir / "2025-08-30.backup").write_text("234")
        (bkdir / "2025-08-31.backup").write_text("345")
        (bkdir / "2025-09-01.backup").write_text("456")
        (bkdir / "2025-09-02.backup").write_text("567")
        res = TestClient(api).delete("/mgmt/backup", params={"keep": 3})
        self.assertEqual(200, res.status_code)
        self.assertEqual({"status": "OK"}, res.json())
        self.assertFalse((bkdir / "2025-08-29.backup").exists())
        self.assertFalse((bkdir / "2025-08-30.backup").exists())
        self.assertTrue((bkdir / "2025-08-31.backup").exists())
        self.assertTrue((bkdir / "2025-09-01.backup").exists())
        self.assertTrue((bkdir / "2025-09-02.backup").exists())

    def test_put_delete(self):
        bkdir = Path(self.td.name)
        res = TestClient(api).put("/mgmt/backup/2025-08-31", content=b"hello\n")
        self.assertEqual(200, res.status_code)
        self.assertEqual({"status": "OK"}, res.json())
        self.assertTrue((bkdir / "2025-08-31.backup").exists())
        self.assertEqual("hello\n", (bkdir / "2025-08-31.backup").read_text())

        resexists = TestClient(api).put("/mgmt/backup/2025-08-31", content=b"hello\n")
        self.assertEqual(400, resexists.status_code)
        self.assertEqual({"detail": "backup already exists"}, resexists.json())

        resdel = TestClient(api).delete("/mgmt/backup/2025-08-31")
        self.assertEqual(200, resdel.status_code)
        self.assertEqual({"status": "OK"}, resdel.json())
        self.assertFalse((bkdir / "2025-08-31.backup").exists())

    def test_delete_notfound(self):
        res = TestClient(api).delete("/mgmt/backup/notfound")
        self.assertEqual(404, res.status_code)
        self.assertEqual({"detail": "backup file not found"}, res.json())

    @patch("subprocess.run")
    def test_restore(self, run):
        bkdir = Path(self.td.name)
        (bkdir / "2025-08-31.backup").write_text("123")
        res = TestClient(api).post("/mgmt/backup/2025-08-31")
        self.assertEqual(200, res.status_code)
        self.assertEqual({"status": "OK"}, res.json())
        run.assert_called_once_with(["sudo", "tgt-admin", "-c", ANY, "-e"], **self.run_basearg)

    def test_restore_notfound(self):
        res = TestClient(api).post("/mgmt/backup/notfound")
        self.assertEqual(404, res.status_code)
        self.assertEqual({"detail": "backup file not found"}, res.json())
