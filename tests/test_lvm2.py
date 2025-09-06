import unittest

from volexport import lvm2


class TestLVM2(unittest.TestCase):
    maxDiff = None

    def test_parse_pvdisplay(self):
        input_str = """
  --- Physical volume ---
  PV Name               /dev/vda2
  VG Name               vg0
  PV Size               <63.50 GiB / not usable 2.00 MiB
  Allocatable           yes (but full)
  PE Size               4.00 MiB
  Total PE              16255
  Free PE               0
  Allocated PE          16255
  PV UUID               t3Aaxo-KWAp-AFP6-nEIN-xJn6-oUkv-ZGBM99
"""
        expected = {
            "PV Name": "/dev/vda2",
            "VG Name": "vg0",
            "PV Size": "<63.50 GiB / not usable 2.00 MiB",
            "Allocatable": "yes (but full)",
            "PE Size": "4.00 MiB",
            "Total PE": "16255",
            "Free PE": "0",
            "Allocated PE": "16255",
            "PV UUID": "t3Aaxo-KWAp-AFP6-nEIN-xJn6-oUkv-ZGBM99",
        }
        res = lvm2.parse(input_str.splitlines(), indent=2, width=21)
        self.assertEqual([expected], res)

    def test_parse_vgdisplay(self):
        input_str = """
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
  VG Size               <63.50 GiB
  PE Size               4.00 MiB
  Total PE              16255
  Alloc PE / Size       16255 / <63.50 GiB
  Free  PE / Size       0 / 0
  VG UUID               hPuYd4-QEoi-RcvL-Jdr5-XLrf-urQm-hgybLl
"""
        expected = {
            "VG Name": "vg0",
            "Format": "lvm2",
            "Metadata Areas": "1",
            "Metadata Sequence No": "2",
            "VG Access": "read/write",
            "VG Status": "resizable",
            "MAX LV": "0",
            "Cur LV": "1",
            "Open LV": "1",
            "Max PV": "0",
            "Cur PV": "1",
            "Act PV": "1",
            "VG Size": "<63.50 GiB",
            "PE Size": "4.00 MiB",
            "Total PE": "16255",
            "Alloc PE / Size": "16255 / <63.50 GiB",
            "Free  PE / Size": "0 / 0",
            "VG UUID": "hPuYd4-QEoi-RcvL-Jdr5-XLrf-urQm-hgybLl",
        }
        res = lvm2.parse(input_str.splitlines(), indent=2, width=21)
        self.assertEqual([expected], res)

    def test_parse_lvdisplay(self):
        input_str = """
  --- Logical volume ---
  LV Path                /dev/vg0/lv_root
  LV Name                lv_root
  VG Name                vg0
  LV UUID                a3OsbU-WC1S-CfDC-MImV-qnqK-oXi0-mmXdqZ
  LV Write Access        read/write
  LV Creation host, time base, 2025-08-10 16:48:15 +0900
  LV Status              available
  # open                 1
  LV Size                <63.50 GiB
  Current LE             16255
  Segments               1
  Allocation             inherit
  Read ahead sectors     auto
  - currently set to     256
  Block device           252:0
"""
        expected = {
            "LV Path": "/dev/vg0/lv_root",
            "LV Name": "lv_root",
            "VG Name": "vg0",
            "LV UUID": "a3OsbU-WC1S-CfDC-MImV-qnqK-oXi0-mmXdqZ",
            "LV Write Access": "read/write",
            "LV Creation host, time": "base, 2025-08-10 16:48:15 +0900",
            "LV Status": "available",
            "# open": "1",
            "LV Size": "<63.50 GiB",
            "Current LE": "16255",
            "Segments": "1",
            "Allocation": "inherit",
            "Read ahead sectors": "auto",
            "- currently set to": "256",
            "Block device": "252:0",
        }
        res = lvm2.parse(input_str.splitlines(), indent=2, width=22)
        self.assertEqual([expected], res)

    def test_parse_lvdisplay_snapshot(self):
        input_str = """
  --- Logical volume ---
  LV Path                /dev/vg0/vol001
  LV Name                vol001
  VG Name                vg0
  LV UUID                U1GR1C-37A5-qoyq-vjQw-EsAq-7CXS-PhsHfr
  LV Write Access        read/write
  LV Creation host, time lima-server, 2025-09-06 16:53:53 +0900
  LV snapshot status     source of
                         snap001 [active]
  LV Status              available
  # open                 0
  LV Size                10.00 GiB
  Current LE             2560
  Segments               1
  Allocation             inherit
  Read ahead sectors     auto
  - currently set to     256
  Block device           252:0

  --- Logical volume ---
  LV Path                /dev/vg0/snap001
  LV Name                snap001
  VG Name                vg0
  LV UUID                3ofMuS-gP7w-ifv7-bN0G-ftX5-pGVE-yIfcR3
  LV Write Access        read/write
  LV Creation host, time lima-server, 2025-09-06 16:54:25 +0900
  LV snapshot status     active destination for vol001
  LV Status              available
  # open                 0
  LV Size                10.00 GiB
  Current LE             2560
  COW-table size         1.00 GiB
  COW-table LE           256
  Allocated to snapshot  0.00%
  Snapshot chunk size    4.00 KiB
  Segments               1
  Allocation             inherit
  Read ahead sectors     auto
  - currently set to     256
  Block device           252:3
"""
        expected1 = {
            "LV Path": "/dev/vg0/vol001",
            "LV Name": "vol001",
            "VG Name": "vg0",
            "LV UUID": "U1GR1C-37A5-qoyq-vjQw-EsAq-7CXS-PhsHfr",
            "LV Write Access": "read/write",
            "LV Creation host, time": "lima-server, 2025-09-06 16:53:53 +0900",
            "LV snapshot status": "source of snap001 [active]",
            "LV Status": "available",
            "# open": "0",
            "LV Size": "10.00 GiB",
            "Current LE": "2560",
            "Segments": "1",
            "Allocation": "inherit",
            "Read ahead sectors": "auto",
            "- currently set to": "256",
            "Block device": "252:0",
        }
        expected2 = {
            "LV Path": "/dev/vg0/snap001",
            "LV Name": "snap001",
            "VG Name": "vg0",
            "LV UUID": "3ofMuS-gP7w-ifv7-bN0G-ftX5-pGVE-yIfcR3",
            "LV Write Access": "read/write",
            "LV Creation host, time": "lima-server, 2025-09-06 16:54:25 +0900",
            "LV snapshot status": "active destination for vol001",
            "LV Status": "available",
            "# open": "0",
            "LV Size": "10.00 GiB",
            "Current LE": "2560",
            "COW-table size": "1.00 GiB",
            "COW-table LE": "256",
            "Allocated to snapshot": "0.00%",
            "Snapshot chunk size": "4.00 KiB",
            "Segments": "1",
            "Allocation": "inherit",
            "Read ahead sectors": "auto",
            "- currently set to": "256",
            "Block device": "252:3",
        }
        res = lvm2.parse(input_str.splitlines(), indent=2, width=22)
        self.assertEqual([expected1, expected2], res)

    def test_parse_lvdisplay_thinsnap(self):
        input_str = """
  --- Logical volume ---
  LV Name                thp
  VG Name                vg0
  LV UUID                C5CFTY-cjJx-eY1q-FcJ9-FT7I-YYMh-24Vzv1
  LV Write Access        read/write (activated read only)
  LV Creation host, time lima-server, 2025-09-06 16:45:09 +0900
  LV Pool metadata       thp_tmeta
  LV Pool data           thp_tdata
  LV Status              available
  # open                 0
  LV Size                200.00 GiB
  Allocated pool data    0.00%
  Allocated metadata     10.43%
  Current LE             51200
  Segments               1
  Allocation             inherit
  Read ahead sectors     auto
  - currently set to     512
  Block device           252:3

  --- Logical volume ---
  LV Path                /dev/vg0/vol001
  LV Name                vol001
  VG Name                vg0
  LV UUID                p2b0xP-7Aqk-rX22-XYoY-9u5v-8lE2-Bfd7mR
  LV Write Access        read/write
  LV Creation host, time lima-server, 2025-09-06 16:46:21 +0900
  LV Pool name           thp
  LV Status              available
  # open                 0
  LV Size                10.00 GiB
  Mapped size            0.00%
  Current LE             2560
  Segments               1
  Allocation             inherit
  Read ahead sectors     auto
  - currently set to     512
  Block device           252:4

  --- Logical volume ---
  LV Path                /dev/vg0/snap001
  LV Name                snap001
  VG Name                vg0
  LV UUID                AIXu0m-6MkP-n6kt-OYlw-cJb2-ahBn-WMhkbe
  LV Write Access        read/write
  LV Creation host, time lima-server, 2025-09-06 16:50:32 +0900
  LV Pool name           thp
  LV Thin origin name    vol001
  LV Status              available
  # open                 0
  LV Size                10.00 GiB
  Mapped size            0.00%
  Current LE             2560
  Segments               1
  Allocation             inherit
  Read ahead sectors     auto
  - currently set to     512
  Block device           252:5
"""
        expected1 = {
            "LV Name": "thp",
            "VG Name": "vg0",
            "LV UUID": "C5CFTY-cjJx-eY1q-FcJ9-FT7I-YYMh-24Vzv1",
            "LV Write Access": "read/write (activated read only)",
            "LV Creation host, time": "lima-server, 2025-09-06 16:45:09 +0900",
            "LV Pool metadata": "thp_tmeta",
            "LV Pool data": "thp_tdata",
            "LV Status": "available",
            "# open": "0",
            "LV Size": "200.00 GiB",
            "Allocated pool data": "0.00%",
            "Allocated metadata": "10.43%",
            "Current LE": "51200",
            "Segments": "1",
            "Allocation": "inherit",
            "Read ahead sectors": "auto",
            "- currently set to": "512",
            "Block device": "252:3",
        }
        expected2 = {
            "LV Path": "/dev/vg0/vol001",
            "LV Name": "vol001",
            "VG Name": "vg0",
            "LV UUID": "p2b0xP-7Aqk-rX22-XYoY-9u5v-8lE2-Bfd7mR",
            "LV Write Access": "read/write",
            "LV Creation host, time": "lima-server, 2025-09-06 16:46:21 +0900",
            "LV Pool name": "thp",
            "LV Status": "available",
            "# open": "0",
            "LV Size": "10.00 GiB",
            "Mapped size": "0.00%",
            "Current LE": "2560",
            "Segments": "1",
            "Allocation": "inherit",
            "Read ahead sectors": "auto",
            "- currently set to": "512",
            "Block device": "252:4",
        }
        expected3 = {
            "LV Path": "/dev/vg0/snap001",
            "LV Name": "snap001",
            "VG Name": "vg0",
            "LV UUID": "AIXu0m-6MkP-n6kt-OYlw-cJb2-ahBn-WMhkbe",
            "LV Write Access": "read/write",
            "LV Creation host, time": "lima-server, 2025-09-06 16:50:32 +0900",
            "LV Pool name": "thp",
            "LV Thin origin name": "vol001",
            "LV Status": "available",
            "# open": "0",
            "LV Size": "10.00 GiB",
            "Mapped size": "0.00%",
            "Current LE": "2560",
            "Segments": "1",
            "Allocation": "inherit",
            "Read ahead sectors": "auto",
            "- currently set to": "512",
            "Block device": "252:5",
        }
        res = lvm2.parse(input_str.splitlines(), indent=2, width=22)
        self.assertEqual([expected1, expected2, expected3], res)
