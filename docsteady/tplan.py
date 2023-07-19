# LSST Data Management System
# Copyright 2018 AURA/LSST.
#
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the LSST License Statement and
# the GNU General Public License along with this program.  If not,
# see <http://www.lsstcorp.org/LegalNotices/>.

"""
Code for Test Report (Run) Model Generation
"""
import datetime
from base64 import b64encode

import requests
from marshmallow import Schema, fields, pre_load

from .config import Config
from .cycle import TestCycle, TestResult
from .spec import TestCase
from .utils import (
    HtmlPandocField,
    SubsectionableHtmlPandocField,
    as_arrow,
    create_folders_and_files,
    download_attachments,
    owner_for_id,
)


class TestPlan(Schema):
    key = fields.String(required=True)
    # the name (TPR title) can contain extra characters that requires pandoc.
    # this may break the bib reference generation
    name = HtmlPandocField(required=True)
    objective = SubsectionableHtmlPandocField(extractable=["scope"])
    status = fields.String(required=True)
    folder = fields.String(required=True)
    created_on = fields.Function(
        deserialize=lambda o: as_arrow(o["createdOn"])
    )
    updated_on = fields.Function(
        deserialize=lambda o: as_arrow(o["updatedOn"])
    )
    owner_id = fields.String(load_from="owner", required=True)
    owner = fields.Function(deserialize=lambda obj: owner_for_id(obj))
    created_by = fields.Function(
        deserialize=lambda obj: owner_for_id(obj), load_from="createdBy"
    )
    custom_fields = fields.Dict(load_from="customFields")

    # See preprocess_plan function for this. It's really nested, but we
    # pull out the keys and ignore ``testRuns``
    cycles = fields.List(fields.String())

    # Derived fields
    milestone_id = fields.String()
    milestone_name = HtmlPandocField()
    product = fields.String()
    doc_name = HtmlPandocField()

    # custom fields
    system_overview = SubsectionableHtmlPandocField(
        extractable=["applicable_documents"]
    )
    verification_environment = HtmlPandocField()
    entry_criteria = HtmlPandocField()
    exit_criteria = HtmlPandocField()
    pmcs_activity = HtmlPandocField()
    verification_artifacts = HtmlPandocField()
    observing_required = fields.Boolean()
    overall_assessment = HtmlPandocField()
    recommended_improvements = HtmlPandocField()
    document_id = fields.String()
    extract_date = fields.String()

    # Note: Add More custom fields above here
    # (and don't forget preprocess_plan)

    @pre_load(pass_many=False)
    def preprocess_plan(self, data):
        """
        During pre_load, we modify the input dictionary to make it look like
        extra data was in the request information. This means that we "pull up"
        custom fields in from the ``customFields`` dict, and we also, for the
        test plan, extract milestone information from the folder information.

        Marshmallow will see the modified input dictionary and use the
        schema definition appropriately.
        """

        def _set_if(target_field, custom_field):
            if custom_field in custom_fields:
                data[target_field] = custom_fields[custom_field]

        # Handle custom fields first
        if "customFields" in data.keys():
            custom_fields = data["customFields"]

            _set_if("system_overview", "System Overview")
            _set_if("verification_environment", "Verification Environment")
            _set_if("exit_criteria", "Exit Criteria")
            _set_if("entry_criteria", "Entry Criteria")
            _set_if("pmcs_activity", "PMCS Activity")
            _set_if("observing_required", "Observing Required")
            _set_if("verification_artifacts", "Verification Artifacts")
            _set_if("overall_assessment", "Overall Assessment")
            _set_if("recommended_improvements", "Recommended Improvements")
            _set_if("document_id", "Document ID")
            data["extract_date"] = datetime.date.today().isoformat()
            # Note: Add More custom fields above here

        # Derived fields
        # Extract milestone information
        sname = data["name"].split(":")
        if len(sname) != 1:
            data["milestone_id"] = sname[0]
            data["milestone_name"] = (
                data["name"].replace(sname[0], "").replace(":", "").strip()
            )
            data["doc_name"] = (
                data["milestone_id"] + ": " + data["milestone_name"]
            )
        else:
            data["milestone_id"] = ""
            data["milestone_name"] = data["name"].strip()
            data["doc_name"] = data["key"] + ": " + data["name"].strip()

        # Product
        data["product"] = data["folder"].split("/")[-1]

        # Flatten out testRuns
        data["cycles"] = [cycle["key"] for cycle in data["testRuns"]]
        return data


def labelResults(result):
    # The results index is not unqique - if there are multiple parameters the
    # script repeats each step  for each set of parameters
    # (think multiple pointings)
    # Previously this was sorted on index which works for one run
    # but not for multiples.
    # Jira does not number them 1.1 1.2 etc .
    # but based on the order we label them like that
    do_level = False
    step0 = 0
    # first see if we have multiple step 0s
    for r in result["script_results"]:
        if r["index"] == 0:
            step0 = step0 + 1
        if step0 > 1:
            do_level = True
            break

    level = 0
    for i, r in enumerate(result["script_results"]):
        if r["index"] == 0:
            level = level + 1
        if do_level:
            r["label"] = level + (r["index"] + 1) / 10.0
        else:
            r["label"] = r["index"] + 1

    pass


def build_tpr_model(tplan_key):
    # create folders for images and attachments if not already there
    create_folders_and_files()

    # get a list of extra fields
    # not possible now.

    # initialize connection to Jira REST API
    usr_pwd = Config.AUTH[0] + ":" + Config.AUTH[1]
    connection_str = b64encode(usr_pwd.encode("ascii")).decode("ascii")
    headers = {
        "accept": "application/json",
        "authorization": "Basic %s" % connection_str,
        "Connection": "close",
    }
    rs = requests.Session()
    rs.headers = headers

    test_cycles_map = {}
    test_results_map = {}
    test_cases_map = {}
    attachments = {}

    # get test plan information
    tplan_url = Config.TESTPLAN_URL.format(testplan=tplan_key)
    # print("test Plan:", tplan_url)
    resp = rs.get(tplan_url)
    resp.raise_for_status()
    testplan, errors = TestPlan().load(resp.json())
    if "document_id" not in testplan or testplan["document_id"] == "":
        print(
            f"ERROR: Document ID missing in {tplan_key}. "
            f"Please complete the metadata before proceeding with the extraction."
        )
        exit()
    attachments[tplan_key] = download_attachments(
        rs, Config.TESTPLAN_ATTACHMENTS.format(tplan_KEY=tplan_key)
    )
    n_attachments = len(attachments[tplan_key])

    # get test cycles and results information
    attachments["cycles"] = dict()
    attachments["results"] = dict()
    for cycle_key in testplan["cycles"]:
        # print("Test Cycle:", Config.TESTCYCLE_URL.format(testrun=cycle_key))
        resp = rs.get(Config.TESTCYCLE_URL.format(testrun=cycle_key))
        test_cycle, error = TestCycle().load(resp.json())
        test_cycles_map[cycle_key] = test_cycle
        attachments["cycles"][cycle_key] = download_attachments(
            rs, Config.TESTCYCLE_ATTACHMENTS.format(tcycle_KEY=cycle_key)
        )
        n_attachments = n_attachments + len(attachments["cycles"][cycle_key])

        resp = rs.get(Config.TESTRESULTS_URL.format(testrun=cycle_key))
        resp.raise_for_status()
        testresults, errors = TestResult().load(resp.json(), many=True)
        test_results_map[cycle_key] = {}
        for result in testresults:
            # Jira does not number them 1.1 1.2 etc
            if (
                result["status"] == "Not Executed"
                and result["test_case_key"] in test_results_map[cycle_key]
            ):
                continue
            # print(result['key'], result['id'])
            labelResults(result)
            result["sorted"] = sorted(
                result["script_results"], key=lambda step: step["label"]
            )
            test_results_map[cycle_key][result["test_case_key"]] = result
            attachments["results"][result["id"]] = download_attachments(
                rs,
                Config.TESTRESULT_ATTACHMENTS.format(result_ID=result["id"]),
            )
            n_attachments = n_attachments + len(
                attachments["results"][result["id"]]
            )

        # Get all the test cases from the test items
        for test_item in test_cycle["test_items"]:
            if test_item["test_case_key"] not in test_cases_map.keys():
                resp = rs.get(
                    Config.TESTCASE_URL.format(
                        testcase=test_item["test_case_key"]
                    )
                )
                if resp.status_code == 200:
                    testcase, errors = TestCase().load(resp.json())
                else:
                    testcase = {
                        "objective": "This Test Case has been archived. "
                        "Information here may not completed.",
                        "key": test_item["test_case_key"],
                        "status": "ARCHIVED",
                    }
                test_cases_map[test_item["test_case_key"]] = testcase
    attachments["n_attachments"] = n_attachments

    # print(attachments)
    tpr = {
        "tplan": testplan,
        "test_cycles_map": test_cycles_map,
        "test_results_map": test_results_map,
        "test_cases_map": test_cases_map,
        "attachments": attachments,
    }

    return tpr
