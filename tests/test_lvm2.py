import unittest
import os

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
