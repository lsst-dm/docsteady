import json
from unittest import TestCase

from marshmallow import EXCLUDE, INCLUDE

from docsteady import spec
from docsteady.config import Config
from docsteady.cycle import TestCycle
from docsteady.spec import Issue, TestStep

ROOT = "tests/data"


def write(data: dict, name: str) -> None:
    fn = f"{ROOT}/{name}.json"
    with open(fn, "w") as f:
        json.dump(data, f)


def read(name: str) -> None:
    fn = f"{ROOT}/{name}.json"
    with open(fn) as f:
        return json.load(f)


class TestTcycle(TestCase):
    def test_tcycle(self) -> None:
        data = read("cycledata")

        Config.CACHED_USERS["womullan"] = {"displayName": "wil"}
        testcycle: dict = TestCycle(unknown=EXCLUDE).load(data)
        self.assertEqual(testcycle["key"], "LVV-C181")

    def test_TestStep(self) -> None:
        data = read("TestStep")

        Config.CACHED_USERS["womullan"] = {"displayName": "wil"}
        teststeps = TestStep(unknown=INCLUDE).load(
            data, many=True, unknown=INCLUDE
        )
        teststep = teststeps[0]
        self.assertEqual(7, len(teststeps))
        self.assertEqual(20455, teststep["id"])

    def test_TestCycle(self) -> None:
        data = read("TestCycle")
        Config.CACHED_USERS["womullan"] = {"displayName": "wil"}
        testcycle: dict = TestCycle(unknown=EXCLUDE).load(data, partial=True)
        self.assertEqual(testcycle["key"], "LVV-T2338")

    def test_TestCycleLVVC181(self) -> None:
        data = read("TestCycle-LVV-C181")
        Config.CACHED_USERS["womullan"] = {"displayName": "wil"}
        Config.CACHED_USERS["gpdf"] = {
            "displayName": "Gregory Dubois-Felsmann"
        }
        Config.CACHED_USERS["mareuter"] = {"displayName": "Michael Reuter"}

        testcycle: dict = TestCycle(unknown=EXCLUDE).load(data, partial=True)
        self.assertEqual(testcycle["key"], "LVV-C181")

    def test_TestCase(self) -> None:
        data = read("TestCase")
        Config.CACHED_USERS["womullan"] = {"displayName": "wil"}
        issue_key = "LVV-71"
        issue: Issue = Issue()
        issue.key = issue_key
        Config.CACHED_VELEMENTS[issue_key] = issue
        testcase: dict = spec.TestCase(unknown=EXCLUDE).load(
            data, partial=True
        )
        self.assertEqual(testcase["key"], "LVV-T2338")