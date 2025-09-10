import unittest


class dummyctxt:
    def peer(self):
        return "client"

    def abort(self, code, details):
        self.code = code
        self.details = details


class TestCsiControl(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass
