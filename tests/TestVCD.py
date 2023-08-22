import unittest

from DocsteadyTestUtils import read
from marshmallow import EXCLUDE

from docsteady.config import Config
from docsteady.vcd import VerificationE
from docsteady.ve_baseline import process_raw_test_cases


class TestVCD(unittest.TestCase):
    def test_ve(self) -> None:
        data = read("VEdata")
        ve_details = VerificationE(unknown=EXCLUDE).load(data)
        self.assertEqual(ve_details["key"], "LVV-3")
        tc_LVVT101 = read("TCdata-LVV-T101")
        Config.CACHED_TESTCASES[tc_LVVT101["key"]] = tc_LVVT101
        tc_LVVT217 = read("TCdata-LVV-T217")
        Config.CACHED_TESTCASES[tc_LVVT217["key"]] = tc_LVVT217

        process_raw_test_cases(None, ve_details)
        test_cases = ve_details["test_cases"]
        self.assertEqual(len(test_cases), 2)
