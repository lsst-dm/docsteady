import unittest

from DocsteadyTestUtils import read_test_data

# from DocsteadyTestUtils import  getTestStepData
from marshmallow import INCLUDE

from docsteady.config import Config
from docsteady.spec import TestStep


class TestTsteps(unittest.TestCase):
    def test_TestStep(self) -> None:
        # to remake the json test file uncomment the next line
        # getTestStepData("LVV-T2338")
        #  this has test steps not a script.
        #  so can not call  getTestScript("LVV-T2338")
        data = read_test_data("TestSteps-LVV-T2338")

        Config.CACHED_USERS["womullan"] = {"displayName": "wil"}
        teststeps = TestStep(unknown=INCLUDE).load(
            data, many=True, unknown=INCLUDE
        )
        self.assertEqual(7, len(teststeps))
        # steps no longer have an ID
        # self.assertEqual(20455, teststep["id"])


python_classes = "TestCase"
