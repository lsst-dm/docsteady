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
    MarkdownableHtmlPandocField, test_case_for_key, get_folders


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
        # Need to do this here because we need requirement_issue_keys _and_ key
        data['requirements'] = self.process_requirements(data)
        return data

    def process_requirements(self, data):
        issues = []
        if "requirement_issue_keys" in data:
            # Build list of requirements
            for issue_key in data["requirement_issue_keys"]:
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


class VerificationElementIssue(Schema):
    key = fields.String(required=True)
    summary = MarkdownableHtmlPandocField()
    status = fields.String()
    description = MarkdownableHtmlPandocField()
    components = fields.List(fields.String())
    jira_url = fields.String()
    assignee = fields.Function(deserialize=lambda obj: owner_for_id(obj))
    assignee_id = fields.String(load_from="assignee", required=True)
    requirement_id = fields.String()

    # FIXME: Some of the following seem to be in Jira Markdown and not HTML
    #requirement_verification_siblings = MarkdownableHtmlPandocField()
    #requirement_text = MarkdownableHtmlPandocField()
    #requirement_discussion = MarkdownableHtmlPandocField()
    #higher_level_requirement = fields.String()  # See Below in extract_fields
    verification_method = fields.String()
    verification_level = fields.String()
    percentage_passing = fields.Float()
    success_criteria = MarkdownableHtmlPandocField()

    @pre_load(pass_many=False)
    def extract_fields(self, data):
        data_fields = data["fields"]
        data["summary"] = data_fields["summary"]
        data["components"] = [component["name"] for component in data_fields["components"]]
        data["jira_url"] = Config.ISSUE_UI_URL.format(issue=data["key"])
        data["requirement_id"] = data_fields["customfield_12001"]
        #data["requirement_verification_siblings"] = data_fields["customfield_14810"]
        #data["requirement_text"] = data_fields["customfield_13513"]
        #data["requirement_discussion"] = data_fields["customfield_13510"]
        #data["percentage_passing"] = data_fields["customfield_13002"]
        data["success_criteria"] = data_fields["customfield_12204"]

        # Simplify this so we elverage existing owner_for_id code
        data["assignee"] = data_fields["assignee"]["key"]

        # This one may need a regex, it seems to be in jira markdown
        #data["higher_level_requirement"] = data_fields["customfield_13515"]

        # The following are not simple objects, but we just want the value
        data["verification_method"] = data_fields["customfield_12002"]["value"]
        if data_fields["customfield_12206"]  == None:
            data["verification_level"] = "NO Verification Level Provided!"
        else:
            data["verification_level"] = data_fields["customfield_12206"]["value"]
        data["status"] = data_fields["status"]["name"]
        return data


def build_spec_model(folder):
    # query = f'folder = "{folder}"'
    # FIXME: use the previous query if they fix the ATM testcases/search API
    folders = get_folders(folder)
    folders_quoted = [f'"{folder}"' for folder in folders]
    folders_inside = ", ".join(folders_quoted)
    query = f"folder IN ({folders_inside})"

    max_tests = 2000
    resp = requests.get(
        Config.TESTCASE_SEARCH_URL,
        params=dict(query=query, maxResults=max_tests),
        auth=Config.AUTH
    )

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
            Config.CACHED_TESTCASES[ testcase["key"] ] = testcase
        testcases.append(testcase)

    if max_tests == len(testcases):
        print("[WARNING]: Test case count same as max_tests", file=sys.stderr)

    return testcases


#
# Get the VE details
#
def build_ve_model(vetrace):
    v = 0
    verificationelements = {}
    rs = requests.Session()
    rs.auth = Config.AUTH
    for ve in vetrace:
        v = v + 1
        #print(v, ve, Config.ISSUE_URL.format(issue=ve))
        veresp = rs.get(Config.ISSUE_URL.format(issue=ve))
        verespj = veresp.json()
        verificationelement, errors = VerificationElementIssue().load(verespj)
        #print(verificationelement['components'])
        #print(verificationelement)
        #verificationelements.append(verificationelement)
        verificationelements[ verificationelement['key'] ] = verificationelement
    return(verificationelements)
 
