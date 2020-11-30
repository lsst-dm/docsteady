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
Code for Test Specification Model Generation
"""
import re
import requests
import sys

from marshmallow import Schema, fields, post_load, pre_load

from .config import Config
from .formatters import as_anchor, alphanum_key
from .utils import owner_for_id, as_arrow, HtmlPandocField, \
    MarkdownableHtmlPandocField, test_case_for_key, get_folders, create_folders_and_files


class Issue(Schema):
    key = fields.String(required=True)
    summary = MarkdownableHtmlPandocField()
    jira_url = fields.String()

    @pre_load(pass_many=False)
    def extract_fields(self, data):
        data_fields = data["fields"]
        data["summary"] = data_fields["summary"]
        data["jira_url"] = Config.ISSUE_UI_URL.format(issue=data["key"])
        return data


class TestStep(Schema):
    index = fields.Integer()
    test_case_key = fields.String(load_from="testCaseKey")
    description = MarkdownableHtmlPandocField()
    expected_result = MarkdownableHtmlPandocField(load_from="expectedResult")
    test_data = MarkdownableHtmlPandocField(load_from="testData")
    custom_field_values = fields.List(fields.Dict(), load_from="customFieldValues")

    # Custom fields
    example_code = MarkdownableHtmlPandocField()  # name: "Example Code"

    @pre_load(pass_many=False)
    def extract_custom_fields(self, data):
        # Custom fields
        custom_field_values = data.get("customFieldValues", list())
        for custom_field in custom_field_values:
            string_value = custom_field["stringValue"]
            name = custom_field["customField"]["name"]
            name = name.lower().replace(" ", "_")
            data[name] = string_value


class TestCase(Schema):
    key = fields.String(required=True)
    keyid = fields.Integer()
    name = HtmlPandocField(required=True)
    owner = fields.Function(deserialize=lambda obj: owner_for_id(obj), default="Unassigned")
    owner_id = fields.String(load_from="owner")
    jira_url = fields.String()
    component = fields.String()
    created_on = fields.Function(deserialize=lambda o: as_arrow(o['createdOn']))
    precondition = HtmlPandocField()
    objective = HtmlPandocField()
    version = fields.Integer(load_from='majorVersion', required=True)
    status = fields.String(required=True)
    priority = fields.String(required=True)
    labels = fields.List(fields.String(), missing=list())
    test_script = fields.Method(deserialize="process_steps", load_from="testScript", required=True)
    requirement_issue_keys = fields.List(fields.String(), load_from="issueLinks")

    # Just in case it's necessary - these aren't guaranteed to be correct
    custom_fields = fields.Dict(load_from="customFields")

    # custom fields go here and in pre_load
    verification_type = fields.String()
    verification_configuration = HtmlPandocField()
    predecessors = HtmlPandocField()
    critical_event = fields.String()
    associated_risks = HtmlPandocField()
    unit_under_test = HtmlPandocField()
    required_software = HtmlPandocField()
    test_equipment = HtmlPandocField()
    test_personnel = HtmlPandocField()
    safety_hazards = HtmlPandocField()
    required_ppe = HtmlPandocField()
    postcondition = HtmlPandocField()

    # synthesized fields (See @pre_load and @post_load)
    doc_href = fields.String()
    requirements = fields.Nested(Issue, many=True)

    @pre_load(pass_many=False)
    def extract_custom_fields(self, data):
        # Synthesized fields
        data["jira_url"] = Config.TESTCASE_UI_URL.format(testcase=data['key'])
        data["doc_href"] = as_anchor(f"{data['key']} - {data['name']}")
        custom_fields = data["customFields"]

        def _set_if(target_field, custom_field):
            if custom_field in custom_fields:
                data[target_field] = custom_fields[custom_field]

        _set_if("verification_type", "Verification Type")
        _set_if("verification_configuration", "Verification Configuration")
        _set_if("predecessors", "Predecessors")
        _set_if("critical_event", "Critical Event")
        _set_if("associated_risks", "Associated Risks")
        _set_if("unit_under_test", "Unit Under Test")
        _set_if("required_software", "Required Software")
        _set_if("test_equipment", "Test Equipment")
        _set_if("test_personnel", "Test Personnel")
        _set_if("safety_hazards", "Safety Hazards")
        _set_if("required_ppe", "Required PPE")
        _set_if("postcondition", "Postcondition")
        return data

    @post_load
    def postprocess(self, data):
        # Need to do this here because we need requirement_issue_keys _and_ key
        data['requirements'] = self.process_requirements(data)
        # need the numeric key of the test case
        data['keyid'] = int(data["key"].strip("LVV-T"))
        return data

    def process_requirements(self, data):
        issues = []
        if "requirement_issue_keys" in data:
            # Build list of requirements
            for issue_key in data["requirement_issue_keys"]:
                issue = Config.CACHED_VELEMENTS.get(issue_key, None)
                if not issue:
                    resp = requests.get(Config.ISSUE_URL.format(issue=issue_key), auth=Config.AUTH)
                    resp.raise_for_status()
                    issue_resp = resp.json()
                    issue, errors = Issue().load(issue_resp)
                    if errors:
                        raise Exception("Unable to Process Requirement: " + str(errors))
                    Config.CACHED_VELEMENTS[issue_key] = issue
                Config.REQUIREMENTS_TO_TESTCASES.setdefault(issue_key, []).append(data['key'])
                issues.append(issue)
        return issues

    def process_steps(self, test_script):
        teststeps, errors = TestStep().load(test_script['steps'], many=True)
        if errors:
            raise Exception("Unable to process Test Steps: " + str(errors))
        # Prefetch any testcases we might need
        for teststep in teststeps:
            if teststep.get("test_case_key"):
                step_testcase = test_case_for_key(teststep["test_case_key"])
                Config.CACHED_LIBTESTCASES[step_testcase['key']] = step_testcase
        teststeps_sorted = sorted(teststeps, key=lambda step: step["index"])
        return teststeps_sorted


def get_lvv_details(key):
    """ Get LVV information from Jira

    PARAMETERS
    ----------
    key: `str`
        LVV jira Key
    RETURNS
    -------
    lvv: dictionary
        The LVV information that is not available in the test case.
        In a first stage, the only information required are
        the High Level Requirements
    """
    lvv = dict()
    lvv['high_level_req'] = []
    if key != "":
        resp = requests.get(
            Config.ISSUE_URL.format(issue=key),
            auth=Config.AUTH
        )
        if resp.status_code != 200:
            print(f"Unable to download: {resp.text}")
            sys.exit(1)
        lvv_resp = resp.json()
        if lvv_resp['fields'][Config.HIGH_LEVEL_REQS_FIELD]:
            lvv['high_level_req'] = re.findall(r'\[([^[]+?)\|', lvv_resp['fields']['customfield_13515'])
    return lvv


def build_spec_model(folder):
    # query = f'folder = "{folder}"'
    # FIXME: use the previous query if they fix the ATM testcases/search API
    folders = get_folders(folder)
    folders_quoted = [f'"{folder}"' for folder in folders]
    folders_inside = ", ".join(folders_quoted)
    query = f"folder IN ({folders_inside})"

    # create folders for images and attachments if not already there
    create_folders_and_files()

    max_tests = 100
    startAt = 0
    testcases = []
    testcases_dict = dict()
    deprecated = []
    requirements = {}
    while True:
        resp = requests.get(
            Config.TESTCASE_SEARCH_URL,
            params=dict(query=query, maxResults=max_tests, startAt=startAt),
            auth=Config.AUTH
        )
        if resp.status_code != 200:
            print("Unable to download")
            print(resp.text)
            sys.exit(1)
        testcases_resp = resp.json()
        tc_count = 0
        testcases_resp.sort(key=lambda tc: alphanum_key(tc["key"]))
        for testcase_resp in testcases_resp:
            tc_count = tc_count + 1
            testcase, errors = TestCase().load(testcase_resp)
            if errors:
                raise Exception("Unable to process errors: " + str(errors))
            testcase["name"] = testcase["name"].rstrip()
            if testcase["key"] not in Config.CACHED_TESTCASES:
                Config.CACHED_TESTCASES["key"] = testcase
                if testcase['status'] == 'Deprecated':
                    deprecated.append(testcase)
                else:
                    if testcase['status'] not in testcases_dict.keys():
                        testcases_dict[testcase['status']] = []
                    testcases_dict[testcase['status']].append(testcase)
                    testcases.append(testcase)
                for req in testcase['requirements']:
                    if req['key'] not in requirements.keys():
                        # get the req information
                        lvv = get_lvv_details(req['key'])
                        req['high_level_req'] = lvv['high_level_req']
                        requirements[req['key']] = req
        if tc_count < max_tests:
            break
        else:
            startAt = startAt + max_tests

    # if max_tests == len(testcases):
    #    print("[WARNING]: Test case count same as max_tests", file=sys.stderr)

    alltestcases = {}
    alltestcases["active"] = testcases
    alltestcases['deprecated'] = deprecated

    for tc_s in testcases_dict.keys():
        print(tc_s, len(testcases_dict[tc_s]))

    return alltestcases, requirements, testcases_dict
