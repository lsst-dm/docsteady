import unittest

from DocsteadyTestUtils import read
from marshmallow import EXCLUDE

from docsteady.config import Config
from docsteady.cycle import ScriptResult


class TestiResults(unittest.TestCase):
    def test_TestScriptRestult(self) -> None:
        data = read("TestResult")
        Config.CACHED_USERS["womullan"] = {"displayName": "wil"}
        scripts = data[0]["scriptResults"]
        result = ScriptResult(unknown=EXCLUDE).load(scripts[0], partial=True)
        self.assertEqual(3, result["index"])
