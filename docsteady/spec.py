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

from bs4 import BeautifulSoup
import requests
import sys

from marshmallow import Schema, fields, post_load, pre_load

from .config import Config
from .formatters import as_anchor, alphanum_key
from .utils import owner_for_id, test_case_for_key, as_arrow
import re


class HtmlPandocField(fields.Field):
    def _deserialize(self, value, attr, data):
        if isinstance(value, str) and Config.TEMPLATE_LANGUAGE:
            Config.DOC.html = value.encode("utf-8")
            value = getattr(Config.DOC, Config.TEMPLATE_LANGUAGE).decode("utf-8")
        return value


class TestCase(Schema):
    key = fields.String(required=True)
    name = fields.String(required=True)
    owner = fields.Function(deserialize=lambda obj: owner_for_id(obj))
    owner_id = fields.String(load_from="owner", required=True)
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

    # custom fields go here and in pre_load
    verification_type = fields.String()
    verification_configuration = HtmlPandocField()
    predecessors = fields.String()
    critical_event = fields.String()
    associated_risks = HtmlPandocField()
    unit_under_test = HtmlPandocField()
    required_software = HtmlPandocField()
    test_equipment = HtmlPandocField()
    test_personnel = HtmlPandocField()
    safety_hazards = HtmlPandocField()
    required_ppe = HtmlPandocField()
    postcondition = HtmlPandocField()

    @pre_load(pass_many=False)
    def extract_custom_fields(self, data):
        custom_fields = data["customFields"]
        del data["customFields"]

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
        data["full_name"] = f"{data['key']} - {data['name']}"
        data["doc_href"] = as_anchor(data["full_name"])
        data['requirements'] = self.process_requirements(data)
        return data

    def process_requirements(self, data):
        requirements = []
        if "issue_links" in data:
            # Build list of requirements
            for issue in data["issue_links"]:
                requirement = Config.CACHED_REQUIREMENTS.get(issue, None)
                if not requirement:
                    resp = requests.get(Config.ISSUE_URL.format(issue=issue), auth=Config.AUTH)
                    resp.raise_for_status()
                    requirement_resp = resp.json()
                    jira_url = Config.ISSUE_UI_URL.format(issue=issue)

                    requirement = {}
                    requirement["key"]: str = issue
                    requirement["summary"]: str = requirement_resp["fields"]["summary"]
                    requirement["jira_url"]: str = jira_url

                    Config.CACHED_REQUIREMENTS[issue] = requirement

                Config.REQUIREMENTS_TO_ISSUES.setdefault(issue, []).append(data['key'])
                requirements.append(requirement)
        return requirements

    def process_steps(self, test_script):
        return preprocess_steps(test_script['steps'], dereference=True)


def build_dm_spec_model(folder):
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
        testcases.append(testcase)
    return testcases


def process_steps(testcase_resp):
    if 'steps' in testcase_resp.get("testScript"):
        raw_steps = testcase_resp['testScript']['steps']
        return preprocess_steps(raw_steps, dereference=True)
    raise KeyError("No Steps found for testcase")


def preprocess_steps(steps_resp, dereference=True):
    sorted_steps = sorted(steps_resp, key=lambda i: i['index'])
    processed_steps = []
    for step_resp in sorted_steps:
        if 'description' in step_resp:
            step = _make_step(step_resp)
            processed_steps.append(step)
        elif 'testCaseKey' in step_resp and dereference:
            step_key = step_resp['testCaseKey']
            cached_testcase_resp = test_case_for_key(step_key)
            more_raw_steps = cached_testcase_resp['testScript']['steps']
            made_steps = [_make_step(step) for step in preprocess_steps(more_raw_steps)]
            processed_steps.extend(made_steps)
        else:
            from pprint import pprint
            pprint(step_resp)
            raise KeyError("Malformed Step")
    return processed_steps


def _make_step(step_raw):
    def extract_description(description):
        if not description:
            return description
        # If it exists, look for markdown text
        soup = BeautifulSoup(description, "html.parser")
        # normalizes HTML, replace breaks with newline, non-breaking spaces
        description_txt = str(soup).replace("<br/>", "\n").replace("\xa0", " ")
        # matches `[markdown]: #` at the top of description
        if re.match("\[markdown\].*:.*#(.*)", description_txt.splitlines()[0]):
            Config.DOC.gfm = description_txt.encode("utf-8")
            description = getattr(Config.DOC, Config.TEMPLATE_LANGUAGE).decode("utf-8")
        return description

    step = {}
    step['index'] = step_raw['index']
    step['description'] = extract_description(step_raw.get('description'))
    step['expected_result'] = extract_description(step_raw.get('expectedResult'))
    step['test_data'] = extract_description(step_raw.get('testData'))
    # Note: Don't dereference any further
    # If testCaseKey is in step, then go ahead and add it....
    step['test_case_key'] = step_raw.get('testCaseKey')
    return step
