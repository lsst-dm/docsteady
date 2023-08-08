import json
from unittest import TestCase

from marshmallow import EXCLUDE, INCLUDE

from docsteady.config import Config
from docsteady.cycle import TestCycle
from docsteady.spec import TestStep


def write(data: dict, name: str) -> None:
    fn = f"data/{name}.json"
    with open(fn, "w") as f:
        json.dump(data, f)


def read(name: str) -> None:
    fn = f"data/{name}.json"
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
