import unittest

from DocsteadyTestUtils import (  # noqa: F401
    dumpTestcases,
    getTestCaseData,
    getTestCases,
    getVEdata,
    getVEdetail,
    getVEmodel,
    read_test_data,
)
from jinja2 import (
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    PackageLoader,
    Template,
)
from marshmallow import EXCLUDE

from docsteady.config import Config
from docsteady.vcd import VerificationE, build_vcd_dict, summary
from docsteady.ve_baseline import do_ve_model, process_test_cases

# set this to True to create new test files - need all the credentials.
GET_DATA = False


class TestVCD(unittest.TestCase):
    def test_ve(self) -> None:
        # un comments to replace the VE-DM- json file
        key = "LVV-3"
        if GET_DATA:
            getVEdetail(key)
        data = read_test_data(f"VE-{key}")
        ve_details = VerificationE(unknown=EXCLUDE).load(data)
        self.assertEqual(ve_details["key"], "LVV-3")

        tc = "LVV-T101"
        if GET_DATA:
            getTestCaseData(tc)
        tc_LVVT101 = read_test_data(f"TestCase-{tc}")
        Config.CACHED_TESTCASES[tc_LVVT101["key"]] = tc_LVVT101
        tc = "LVV-T217"
        if GET_DATA:
            getTestCaseData(tc)
        tc_LVVT217 = read_test_data(f"TestCase-{tc}")
        Config.CACHED_TESTCASES[tc_LVVT217["key"]] = tc_LVVT217

        tcs = ["LVV-T217", "LVV-T101"]
        process_test_cases(tcs, ve_details)
        test_cases = ve_details["test_cases"]

        self.assertEqual(len(test_cases), 2)

    def test_ve_LVV_27(self) -> None:
        key = "LVV-27"
        if GET_DATA:
            getVEdetail(key)
        data = read_test_data(f"VE-{key}")
        ve_details = VerificationE(unknown=EXCLUDE).load(data, partial=True)
        self.assertEqual(ve_details["key"], "LVV-27")
        self.assertIsNotNone(ve_details["verified_by"])
        self.assertEqual(4, len(ve_details["verified_by"]))

    def test_baseline(self) -> None:
        if GET_DATA:
            getVEmodel()
        ve_model = read_test_data("VEmodel")

        env = Environment(
            loader=ChoiceLoader(
                [
                    FileSystemLoader(Config.TEMPLATE_DIRECTORY),
                    PackageLoader("docsteady", "templates"),
                ]
            ),
            lstrip_blocks=True,
            trim_blocks=True,
            autoescape=False,
        )
        Config.TEMPLATE_DIRECTORY = "src/docsteady/templates::"
        template_path = f"ve.{Config.TEMPLATE_LANGUAGE}.jinja2"
        template: Template = env.get_template(template_path)

        metadata = {}
        metadata["component"] = "DM"
        metadata["subcomponent"] = ""
        metadata["template"] = str(template.filename)
        text = template.render(
            metadata=metadata,
            velements=ve_model,
            reqs={"DMS-REQ-0002": ["LVV-3"], "DMS-REQ-0008": ["LVV-5"]},
            test_cases=Config.CACHED_TESTCASES,
        )

        self.assertTrue(len(text) > 1000)

    def test_vcd(self) -> None:
        # can only get data running locally with all creds
        if GET_DATA:
            ve_model = do_ve_model("DM", "Infrastructure", DOFEW=True)
        else:
            ve_model = read_test_data("VEmodel")
        vcd_dict = build_vcd_dict(
            ve_model, usedump=not GET_DATA, path="tests/data"
        )
        sum_dict = summary(vcd_dict)
        self.assertTrue(sum_dict[0]["Deprecated"] == 3)

        coverage = Config.coverage
        req_coverage = Config.req_coverage
        for cov in coverage:
            print(f" {cov['name']}({cov['label']})", end="")
        print("Total")
        print("--------------------------------------------------")
        print(" Requirements     (All)")

        for cov in req_coverage:
            if cov["key"] in sum_dict[2]:
                print(f"{sum_dict[2][cov['key']]}")
            else:
                print(f"No {cov['key']}")

        print(f"               {sum_dict[6][0]}")
        print("--------------------------------------------------")
        for doc, dcounts in sum_dict[3].items():
            loop = 1
            for priority, pcounts in dcounts.items():
                if priority != "count" and priority != "zAll":
                    if loop == 1:
                        print(f"{doc}", end="")
                    print(f"        {priority}", end="")
                    print(f"    {pcounts}")

        print("--------------------------------------------------")
        for cov in coverage:
            if cov["key"] in dcounts["zAll"]:
                print(f"{dcounts['zAll'][cov['key']]}    {dcounts['count']}")

        print("--------------------------------------------------")
        print("Verification E.      (All)", end="")
        for state in Config.tcresults:
            if state["key"] in sum_dict[1]:
                print(f" {sum_dict[1][state['key']]}", end="")
        print(f"{sum_dict[6][1]}")
