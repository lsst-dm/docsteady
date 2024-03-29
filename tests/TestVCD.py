import unittest

from DocsteadyTestUtils import read_test_data
from marshmallow import EXCLUDE
from requests.sessions import Session

from docsteady.config import Config
from docsteady.vcd import VerificationE
from docsteady.ve_baseline import process_raw_test_cases


class TestVCD(unittest.TestCase):
    def test_ve(self) -> None:
        data = read_test_data("VEdata")
        ve_details = VerificationE(unknown=EXCLUDE).load(data)
        self.assertEqual(ve_details["key"], "LVV-3")
        tc_LVVT101 = read_test_data("TCdata-LVV-T101")
        Config.CACHED_TESTCASES[tc_LVVT101["key"]] = tc_LVVT101
        tc_LVVT217 = read_test_data("TCdata-LVV-T217")
        Config.CACHED_TESTCASES[tc_LVVT217["key"]] = tc_LVVT217
        session: Session = Session()  # Not valid, but good enough for testing
        process_raw_test_cases(session, ve_details)
        test_cases = ve_details["test_cases"]
        self.assertEqual(len(test_cases), 2)

    def test_ve_LVV_27(self) -> None:
        data = read_test_data("LVV-27-data")
        ve_details = VerificationE(unknown=EXCLUDE).load(data, partial=True)
        self.assertEqual(ve_details["key"], "LVV-27")
        self.assertIsNotNone(ve_details["verified_by"])
        self.assertEqual(4, len(ve_details["verified_by"]))
