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

import requests
import sys

from marshmallow import Schema, fields, post_load, pre_load

from .config import Config
from .formatters import as_anchor, alphanum_key
from .utils import owner_for_id, as_arrow, HtmlPandocField, \
    MarkdownableHtmlPandocField, test_case_for_key


class Issue(Schema):
    key = fields.String(required=True)
    summary = fields.String()
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


class TestCase(Schema):
    key = fields.String(required=True)
    name = fields.String(required=True)
    owner = fields.Function(deserialize=lambda obj: owner_for_id(obj))
    owner_id = fields.String(load_from="owner", required=True)
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
    issue_links = fields.List(fields.String(), load_from="issueLinks")

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
        _set_if("critical_event", "Critical Event?")
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
        # Need to do this here because we need issue_links _and_ key
        data['requirements'] = self.process_requirements(data)
        return data

    def process_requirements(self, data):
        issues = []
        if "issue_links" in data:
            # Build list of requirements
            for issue_key in data["issue_links"]:
                issue = Config.CACHED_REQUIREMENTS.get(issue_key, None)
                if not issue:
                    resp = requests.get(Config.ISSUE_URL.format(issue=issue_key), auth=Config.AUTH)
                    resp.raise_for_status()
                    issue_resp = resp.json()
                    issue, errors = Issue().load(issue_resp)
                    if errors:
                        raise Exception("Unable to Process Requirement: " + str(errors))
                    Config.CACHED_REQUIREMENTS[issue_key] = issue
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
                test_case_for_key(teststep["test_case_key"])
        return teststeps


def build_spec_model(folder):
    query = f'folder = "{folder}"'
    resp = requests.get(Config.TESTCASE_SEARCH_URL, params=dict(query=query), auth=Config.AUTH)

    if resp.status_code != 200:
        print("Unable to download")
        print(resp.text)
        sys.exit(1)

    testcases_resp = resp.json()
    testcases_resp.sort(key=lambda tc: alphanum_key(tc["key"]))
    testcases = []
    for testcase_resp in testcases_resp:
        testcase, errors = TestCase().load(testcase_resp)
        if errors:
            raise Exception("Unable to process errors: " + str(errors))
        if testcase["key"] not in Config.CACHED_TESTCASES:
            Config.CACHED_TESTCASES["key"] = testcase
        testcases.append(testcase)
    return testcases
