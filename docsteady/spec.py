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
from typing import List, Optional

from bs4 import BeautifulSoup
import requests
import sys
from .config import Config
from .formatters import as_anchor, alphanum_key
import re


def build_dm_spec_model(folder, requirements_to_issues, requirements_map):
    query = f'folder = "{folder}"'
    resp = requests.get(Config.TESTCASE_SEARCH_URL, params=dict(query=query), auth=Config.AUTH)

    if resp.status_code != 200:
        print("Unable to download")
        print(resp.text)
        sys.exit(1)

    testcases_resp = resp.json()
    testcases_resp.sort(key=lambda tc: alphanum_key(tc["key"]))
    testcases_model = []
    for testcase_resp in testcases_resp:
        testcase = {}
        try:
            testcase["key"] : str = testcase_resp["key"]
            testcase["name"] : str = testcase_resp["name"]
            testcase["full_name"] : str = f"{testcase_resp['key']} - {testcase_resp['name']}"
            testcase["owner_id"] : str = testcase_resp["owner"]
            testcase["owner"] : str = owner_for_id(testcase["owner_id"])
            testcase["component"] : Optional[str] = testcase_resp.get("component")

            # FIXME: Use Arrow
            testcase["created_on"] : Optional[str] = testcase_resp.get("createdOn")
            testcase["precondition"] : Optional[str] = testcase_resp.get("precondition")
            testcase["version"] : str = testcase_resp['majorVersion']
            testcase["status"] : str = testcase_resp['status']
            testcase["priority"] : str = testcase_resp['priority']
            testcase["labels"] : List[str] = testcase_resp.get("labels", list())

            # For easy referencing later
            testcase["doc_href"] : str = as_anchor(testcase["full_name"])

            # customFields
            custom_fields = testcase_resp["customFields"]
            testcase["verification_type"] : Optional[str] = custom_fields.get("Verification Type")
            testcase["verification_configuration"] : Optional[str] = \
                custom_fields.get("Verification Configuration")
            testcase["predecessors"] : Optional[str] = custom_fields.get("Predecessors")
            testcase["critical_event"] : Optional[str] = custom_fields.get("Critical Event?")
            testcase["associated_risks"] : Optional[str] = custom_fields.get("Associated Risks")
            testcase["unit_under_test"] : Optional[str] = custom_fields.get("Unit Under Test")
            testcase["required_software"] : Optional[str] = custom_fields.get("Required Software")
            testcase["test_equipment"] : Optional[str] = custom_fields.get("Test Equipment")
            testcase["test_personnel"] : Optional[str] = custom_fields.get("Test Personnel")
            testcase["safety_hazards"] : Optional[str] = custom_fields.get("Safety Hazards")
            testcase["required_ppe"] : Optional[str] = custom_fields.get("Required PPE")
            testcase["postcondition"] : Optional[str] = custom_fields.get("Postcondition")

        except KeyError as e:
            from pprint import pprint
            print("No Key in JSON")
            print(e)
            pprint(testcase_resp)
            raise e

        testcase["requirements"] = process_requirements(testcase_resp,
                                                        requirements_to_issues,
                                                        requirements_map)
        testcase["test_script"] = {}
        testcase['test_script']['steps'] = process_steps(testcase_resp)

        testcases_model.append(testcase)
    return testcases_model


def owner_for_id(owner_id):
    if owner_id not in Config.CACHED_USERS:
        resp = requests.get(Config.USER_URL.format(username=owner_id),
                            auth=Config.AUTH)
        resp.raise_for_status()
        user_resp = resp.json()
        Config.CACHED_USERS[owner_id] = user_resp
    user_resp = Config.CACHED_USERS[owner_id]
    return user_resp["displayName"]


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
            cached_testcase_resp = Config.CACHED_TESTCASES.get(step_key)
            if not cached_testcase_resp:
                resp = requests.get(Config.TESTCASE_URL.format(testcase=step_key),
                                    auth=Config.AUTH)
                step_testcase_resp = resp.json()
                Config.CACHED_TESTCASES[step_key] = step_testcase_resp
                cached_testcase_resp = step_testcase_resp
            more_raw_steps = cached_testcase_resp['testScript']['steps']
            made_steps = [_make_step(step) for step in preprocess_steps(more_raw_steps)]
            processed_steps.extend(made_steps)
        else:
            from pprint import pprint
            pprint(step_resp)
            raise KeyError("Malformed Step")
    return processed_steps


def process_requirements(testcase_resp, requirements_to_issues, requirements_map):
    requirements = []
    # Build list of requirements
    if "issueLinks" in testcase_resp:
        for issue in testcase_resp["issueLinks"]:
            requirement_resp = Config.CACHED_REQUIREMENTS.get(issue, None)
            if not requirement_resp:
                resp = requests.get(Config.ISSUE_URL.format(issue=issue), auth=Config.AUTH)
                resp.raise_for_status()
                requirement_resp = resp.json()
                Config.CACHED_REQUIREMENTS[issue] = requirement_resp

            requirements_to_issues.setdefault(issue, []).append(testcase_resp['key'])
            jira_url = Config.ISSUE_UI_URL.format(issue=issue)
            summary = requirement_resp["fields"]["summary"]
            anchor = f'<a href="{jira_url}">{issue}</a>'
            # FIXME: Get rid of anchor?
            requirement = {}
            requirement["key"]: str = issue
            requirement["summary"]: str = summary
            requirement["anchor"]: str = anchor
            requirement["jira_url"]: str = jira_url
            requirements_map[issue]: str = requirement
            requirements.append(requirement)
    return requirements


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
            description = Config.DOC.html.decode("utf-8")
        return description

    step = {}
    step['index'] = step_raw['index']
    step['description'] = extract_description(step_raw.get('description', None))
    step['expected_result'] = step_raw.get('expectedResult', None)
    step['test_data'] = step_raw.get('testData', None)
    # Note: Don't dereference any further
    # If testCaseKey is in step, then go ahead and add it....
    step['test_case_key'] = step_raw.get('testCaseKey', None)
    return step
