import unittest
import tempfile
import zipfile
import io
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
        run.assert_any_call(["sudo", "tgt-admin", "--dump"], **self.run_basearg)
        run.assert_any_call(["sudo", "vgcfgbackup", "--file", ANY, "vg0"], **self.run_basearg)

        reslist = client.get("/mgmt/backup")
        self.assertEqual(200, reslist.status_code)
        self.assertEqual([{"name": name}], reslist.json())

        resget = client.get(f"/mgmt/backup/{name}")
        self.assertEqual(200, resget.status_code)
        zf = zipfile.ZipFile(io.BytesIO(resget.content))
        exp = zf.read("export").decode("utf-8")
        self.assertEqual(run.return_value.stdout, exp)

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

    def _example_backup(self, export: bytes, volume: bytes):
        buf = io.BytesIO()
        zf = zipfile.ZipFile(buf, "w")
        zf.writestr("export", export)
        zf.writestr("volume", volume)
        zf.close()
        return buf.getvalue()

    def test_put_delete(self):
        bkdir = Path(self.td.name)
        content = self._example_backup(b"hello export\n", b"hello volume\n")
        res = TestClient(api).put("/mgmt/backup/2025-08-31", content=content)
        self.assertEqual(200, res.status_code)
        self.assertEqual({"status": "OK"}, res.json())
        self.assertTrue((bkdir / "2025-08-31.backup").exists())
        self.assertEqual(content, (bkdir / "2025-08-31.backup").read_bytes())

        resexists = TestClient(api).put("/mgmt/backup/2025-08-31", content=content)
        self.assertEqual(400, resexists.status_code)
        self.assertEqual({"detail": "backup already exists"}, resexists.json())

        resdel = TestClient(api).delete("/mgmt/backup/2025-08-31")
        self.assertEqual(200, resdel.status_code)
        self.assertEqual({"status": "OK"}, resdel.json())
        self.assertFalse((bkdir / "2025-08-31.backup").exists())

    def test_put_invalid1(self):
        content = self._example_backup(b"hello export\n", b"hello volume\n")
        content = b"invalid" + content[7:]
        res = TestClient(api).put("/mgmt/backup/2025-08-31", content=content)
        self.assertEqual(400, res.status_code)
        self.assertIn("detail", res.json())

    def test_put_invalid2(self):
        content = b"hello world\n"
        res = TestClient(api).put("/mgmt/backup/2025-08-31", content=content)
        self.assertEqual(400, res.status_code)
        self.assertIn("detail", res.json())

    def test_put_invalid3(self):
        buf = io.BytesIO()
        zf = zipfile.ZipFile(buf, "w")
        zf.writestr("export", b"hello export\n")
        zf.writestr("volume", b"hello volume\n")
        zf.writestr("blabla", b"hello blabla\n")
        zf.close()
        content = buf.getvalue()
        res = TestClient(api).put("/mgmt/backup/2025-08-31", content=content)
        self.assertEqual(400, res.status_code)
        self.assertIn("detail", res.json())

    def test_delete_notfound(self):
        res = TestClient(api).delete("/mgmt/backup/notfound")
        self.assertEqual(404, res.status_code)
        self.assertEqual({"detail": "backup file not found"}, res.json())

    @patch("subprocess.run")
    def test_restore(self, run):
        bkdir = Path(self.td.name)
        (bkdir / "2025-08-31.backup").write_bytes(self._example_backup(b"exp123", b"vol123"))
        res = TestClient(api).post("/mgmt/backup/2025-08-31")
        self.assertEqual(200, res.status_code)
        self.assertEqual({"status": "OK", "export": "restored", "volume": "restored"}, res.json())
        run.assert_any_call(["sudo", "tgt-admin", "-c", ANY, "-e"], **self.run_basearg)
        run.assert_any_call(["sudo", "vgcfgrestore", "--file", ANY, "vg0"], **self.run_basearg)

    @patch("subprocess.run")
    def test_restore_volume(self, run):
        bkdir = Path(self.td.name)
        (bkdir / "2025-08-31.backup").write_bytes(self._example_backup(b"exp123", b"vol123"))
        res = TestClient(api).post("/mgmt/backup/2025-08-31", params=dict(export=False))
        self.assertEqual(200, res.status_code)
        self.assertEqual({"status": "OK", "export": "skipped", "volume": "restored"}, res.json())
        run.assert_called_once_with(["sudo", "vgcfgrestore", "--file", ANY, "vg0"], **self.run_basearg)

    @patch("subprocess.run")
    def test_restore_export(self, run):
        bkdir = Path(self.td.name)
        (bkdir / "2025-08-31.backup").write_bytes(self._example_backup(b"exp123", b"vol123"))
        res = TestClient(api).post("/mgmt/backup/2025-08-31", params=dict(volume=False))
        self.assertEqual(200, res.status_code)
        self.assertEqual({"status": "OK", "export": "restored", "volume": "skipped"}, res.json())
        run.assert_called_once_with(["sudo", "tgt-admin", "-c", ANY, "-e"], **self.run_basearg)

    @patch("subprocess.run")
    def test_restore_invalid(self, run):
        bkdir = Path(self.td.name)
        (bkdir / "2025-08-31.backup").write_bytes(self._example_backup(b"exp123", b"vol123"))
        res = TestClient(api).post("/mgmt/backup/2025-08-31", params=dict(volume=False, export=False))
        self.assertEqual(400, res.status_code)
        run.assert_not_called()

    def test_restore_notfound(self):
        res = TestClient(api).post("/mgmt/backup/notfound")
        self.assertEqual(404, res.status_code)
        self.assertEqual({"detail": "backup file not found"}, res.json())

    export_content = """
default-driver iscsi

<target iqn.2025-08.com.github.wtnb75:2142ad0609d8e2b59f5e>
        backing-store /dev/vg0/b49090c0-f254-4c5d-a5ca-96d59dfbfb0f
        incominguser aab3c716718ddd3f9efb PLEASE_CORRECT_THE_PASSWORD
        initiator-address 192.168.104.3
</target>

<target iqn.2025-08.com.github.wtnb75:38bc4b71cd59d2184c86>
        backing-store /dev/vg0/608dec48-a7f6-43ea-8319-87f99979a0db
        incominguser 1331744c5ae3d1f1c797 PLEASE_CORRECT_THE_PASSWORD
        initiator-address 192.168.104.3
</target>
"""

    volume_content = """
# Generated by LVM2 version 2.03.16(2) (2022-05-18): Sun Oct 12 08:40:11 2025

contents = "Text Format Volume Group"
version = 1

description = "vgcfgbackup --file /tmp/tmphpuxcu9w vg0"

creation_host = "lima-server"	# Linux lima-server 6.8.0-63-generic #66-Ubuntu SMP PREEMPT_DYNAMIC Fri Jun 13 20:09:49 UTC 2025 aarch64
creation_time = 1760226011	# Sun Oct 12 08:40:11 2025

vg0 {
	id = "VuhVBu-g8uH-mYag-L7Ma-lHst-N60P-p31JU1"
	seqno = 3
	format = "lvm2"			# informational
	status = ["RESIZEABLE", "READ", "WRITE"]
	flags = []
	extent_size = 8192		# 4 Megabytes
	max_lv = 0
	max_pv = 0
	metadata_copies = 0

	physical_volumes {

		pv0 {
			id = "38PCVU-G7iU-n5P0-GBvH-fSoL-HQWc-Khv8b0"
			device = "/dev/vdb"	# Hint only

			status = ["ALLOCATABLE"]
			flags = []
			dev_size = 524288000	# 250 Gigabytes
			pe_start = 2048
			pe_count = 63999	# 249.996 Gigabytes
		}
	}

	logical_volumes {

		608dec48-a7f6-43ea-8319-87f99979a0db {
			id = "p29l7T-Kn30-VbRn-C7HV-fltO-ieD9-Ra9RuL"
			status = ["READ", "WRITE", "VISIBLE"]
			flags = []
			tags = ["volname.vol001"]
			creation_time = 1760225467	# 2025-10-12 08:31:07 +0900
			creation_host = "lima-server"
			segment_count = 1

			segment1 {
				start_extent = 0
				extent_count = 2560	# 10 Gigabytes

				type = "striped"
				stripe_count = 1	# linear

				stripes = [
					"pv0", 0
				]
			}
		}

		b49090c0-f254-4c5d-a5ca-96d59dfbfb0f {
			id = "Q7v35H-nYKU-DXPi-0jou-uXcR-zEhb-oudEql"
			status = ["READ", "WRITE", "VISIBLE"]
			flags = []
			tags = ["volname.vol002"]
			creation_time = 1760225506	# 2025-10-12 08:31:46 +0900
			creation_host = "lima-server"
			segment_count = 1

			segment1 {
				start_extent = 0
				extent_count = 256	# 1024 Megabytes

				type = "striped"
				stripe_count = 1	# linear

				stripes = [
					"pv0", 2560
				]
			}
		}
	}

}
"""

    def test_read_export(self):
        bkdir = Path(self.td.name)
        (bkdir / "2025-08-31.backup").write_bytes(
            self._example_backup(self.export_content.encode(), self.volume_content.encode())
        )
        res = TestClient(api).get("/mgmt/backup/2025-08-31/export")
        self.assertEqual(200, res.status_code)
        self.assertEqual(
            [
                dict(
                    protocol="iscsi",
                    connected=[],
                    targetname="iqn.2025-08.com.github.wtnb75:2142ad0609d8e2b59f5e",
                    tid=0,
                    volumes=["vol002"],
                    users=["aab3c716718ddd3f9efb"],
                    acl=["192.168.104.3"],
                ),
                dict(
                    protocol="iscsi",
                    connected=[],
                    targetname="iqn.2025-08.com.github.wtnb75:38bc4b71cd59d2184c86",
                    tid=0,
                    volumes=["vol001"],
                    users=["1331744c5ae3d1f1c797"],
                    acl=["192.168.104.3"],
                ),
            ],
            res.json(),
        )

    def test_read_volume(self):
        bkdir = Path(self.td.name)
        (bkdir / "2025-08-31.backup").write_bytes(
            self._example_backup(self.export_content.encode(), self.volume_content.encode())
        )
        res = TestClient(api).get("/mgmt/backup/2025-08-31/volume")
        self.assertEqual(200, res.status_code)
        self.assertEqual(
            [
                dict(
                    name="vol001",
                    created="2025-10-11T23:31:07Z",
                    size=10 * 1024 * 1024 * 1024,
                    used=False,
                    readonly=False,
                    thin=False,
                    parent=None,
                ),
                dict(
                    name="vol002",
                    created="2025-10-11T23:31:46Z",
                    size=1 * 1024 * 1024 * 1024,
                    used=False,
                    readonly=False,
                    thin=False,
                    parent=None,
                ),
            ],
            res.json(),
        )
