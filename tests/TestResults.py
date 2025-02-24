import unittest

from DocsteadyTestUtils import read_test_data  # getScriptStepsData,
from marshmallow import EXCLUDE

from docsteady.config import Config
from docsteady.cycle import ScriptResult


class TestiResults(unittest.TestCase):
    def test_TestScriptRestult(self) -> None:
        # getScriptStepsData("LVV-E1552")
        script = read_test_data("ScriptSteps-LVV-E1552")
        Config.CACHED_USERS["womullan"] = {"displayName": "wil"}
        Config.CACHED_POINTERS[
            "https://api.zephyrscale.smartbear.com/v2/statuses/7920141"
        ] = "Pass"
        result = ScriptResult(unknown=EXCLUDE).load(script[0], partial=True)
        self.assertEqual(1, result["index"])
