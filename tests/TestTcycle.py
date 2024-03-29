import unittest
from typing import List

from DocsteadyTestUtils import read_test_data
from marshmallow import EXCLUDE, INCLUDE

from docsteady.config import Config
from docsteady.cycle import TestCycle
from docsteady.spec import Issue, TestCase, TestStep


class TestTcycle(unittest.TestCase):
    def test_tcycle(self) -> None:
        data = read_test_data("cycledata")

        Config.CACHED_USERS["womullan"] = {"displayName": "wil"}
        testcycle: dict = TestCycle(unknown=EXCLUDE).load(data)
        self.assertEqual(testcycle["key"], "LVV-C181")

    def test_TestStep(self) -> None:
        data = read_test_data("TestStep")

        Config.CACHED_USERS["womullan"] = {"displayName": "wil"}
        teststeps = TestStep(unknown=INCLUDE).load(
            data, many=True, unknown=INCLUDE
        )
        teststep = teststeps[0]
        self.assertEqual(7, len(teststeps))
        self.assertEqual(20455, teststep["id"])

    def test_TestCycle(self) -> None:
        data = read_test_data("TestCycle")
        Config.CACHED_USERS["womullan"] = {"displayName": "wil"}
        testcycle: dict = TestCycle(unknown=EXCLUDE).load(data, partial=True)
        self.assertEqual(testcycle["key"], "LVV-T2338")

    def test_TestCycleLVVC181(self) -> None:
        data = read_test_data("TestCycle-LVV-C181")
        Config.CACHED_USERS["womullan"] = {"displayName": "wil"}
        Config.CACHED_USERS["gpdf"] = {
            "displayName": "Gregory Dubois-Felsmann"
        }
        Config.CACHED_USERS["mareuter"] = {"displayName": "Michael Reuter"}

        testcycle: dict = TestCycle(unknown=EXCLUDE).load(data, partial=True)
        self.assertEqual(testcycle["key"], "LVV-C181")

    def test_TestCase(self) -> None:
        data = read_test_data("TestCase")
        Config.CACHED_USERS["womullan"] = {"displayName": "wil"}

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


python_classes = "TestCase"
