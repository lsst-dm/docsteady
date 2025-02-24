import unittest
from typing import List

from DocsteadyTestUtils import read_test_data

# , getTestCaseData, , getTestStepData, getTestCycleData
from marshmallow import EXCLUDE

from docsteady.config import Config
from docsteady.cycle import TestCycle
from docsteady.spec import Issue, TestCase
from docsteady.utils import fix_json


class TestTcycle(unittest.TestCase):
    def test_tcycle(self) -> None:
        # getTestCycleData("LVV-R181")
        # just call once to get a file for testing
        data = read_test_data("TestCycle-LVV-R181")
        Config.CACHED_USERS["557058:20ad3b56-9b88-4b76-bb4e-576e831f79ae"] = {
            "displayName": "wil"
        }
        Config.CACHED_POINTERS[
            "https://api.zephyrscale.smartbear.com/v2/statuses/7920152"
        ] = "Done"

        testcycle: dict = TestCycle(unknown=EXCLUDE).load(data)
        self.assertEqual(testcycle["key"], "LVV-R181")

    def test_TestCycleLVVR181(self) -> None:
        Config.CACHED_POINTERS = read_test_data("POINTERS")
        data = read_test_data("TestCycle-LVV-R181")
        Config.CACHED_USERS["557058:20ad3b56-9b88-4b76-bb4e-576e831f79ae"] = {
            "displayName": "wil"
        }
        Config.CACHED_USERS["gpdf"] = {
            "displayName": "Gregory Dubois-Felsmann"
        }
        Config.CACHED_USERS["mareuter"] = {"displayName": "Michael Reuter"}

        testcycle: dict = TestCycle(unknown=EXCLUDE).load(data, partial=True)
        self.assertEqual(testcycle["key"], "LVV-R181")

    def test_TestCase(self) -> None:
        Config.CACHED_POINTERS = read_test_data("POINTERS")
        # getTestCaseData("LVV-T2338")
        data = read_test_data("TestCase-LVV-T2338")
        Config.CACHED_USERS["557058:20ad3b56-9b88-4b76-bb4e-576e831f79ae"] = {
            "displayName": "wil"
        }
        issue_key = "LVV-71"
        issue: Issue = Issue()
        issue.key = issue_key  # type: ignore
        issue.summary = "Test Case for LVV-71"  # type: ignore
        Config.CACHED_VELEMENTS[issue_key] = issue
        Config.REQUIREMENTS_TO_TESTCASES.setdefault(issue_key, []).append(
            data["key"]
        )
        testcase: dict = TestCase(unknown=EXCLUDE).load(data, partial=True)
        self.assertEqual(testcase["key"], "LVV-T2338")

        issues: List[Issue] = testcase["requirements"]
        self.assertEqual(1, len(issues))
        self.assertEqual("LVV-71", issues[0].key)

    def test_TestCase2339(self) -> None:
        # getTestCaseData("LVV-T2339")
        Config.CACHED_USERS["557058:20ad3b56-9b88-4b76-bb4e-576e831f79ae"] = {
            "displayName": "wil"
        }
        Config.CACHED_POINTERS = read_test_data("POINTERS")
        issue = Issue()
        Config.CACHED_VELEMENTS["LVV-9979"] = issue
        data = read_test_data("TestCase-LVV-T2339")
        testcase: dict = TestCase(unknown=EXCLUDE).load(
            fix_json(data), partial=True
        )
        self.assertEqual(testcase["key"], "LVV-T2339")
        self.assertTrue(testcase["test_personnel"].startswith("William"))


python_classes = "TestCase"
