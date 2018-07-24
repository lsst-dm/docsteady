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
from collections import OrderedDict
import requests
import sys
from .config import Config
from .formatters import as_anchor, alphanum_key
# import re


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
            testcase["key"] = testcase_resp["key"]
            testcase["name"] = testcase_resp["name"]
            testcase["full_name"] = f"{testcase_resp['key']} - {testcase_resp['name']}"
            testcase["owner_id"] = testcase_resp["owner"]
            testcase["owner"] = owner_for_id(testcase["owner_id"])
            testcase["component"] = testcase_resp.get("component", None)
            # FIXME: Use Arrow
            testcase["created_on"] = testcase_resp.get("createdOn", None)
            testcase["precondition"] = testcase_resp.get("precondition", None)
            testcase["version"] = testcase_resp['majorVersion']
            testcase["status"] = testcase_resp['status']
            testcase["priority"] = testcase_resp['priority']

            # For easy referencing later
            testcase["doc_href"] = as_anchor(testcase["full_name"])

            # customFields
            custom_fields = testcase_resp["customFields"]
            testcase["verification_type"] = custom_fields.get("Verification Type", None)
            testcase["verification_configuration"] = \
                custom_fields.get("Verification Configuration", None)
            testcase["predecessors"] = custom_fields.get("Predecessors", None)
            testcase["critical_event"] = custom_fields.get("Critical Event?", None)
            testcase["associated_risks"] = custom_fields.get("Associated Risks", None)
            testcase["unit_under_test"] = custom_fields.get("Unit Under Test", None)
            testcase["required_software"] = custom_fields.get("Required Software", None)
            testcase["test_equipment"] = custom_fields.get("Test Equipment", None)
            testcase["test_personnel"] = custom_fields.get("Test Personnel", None)
            testcase["safety_hazards"] = custom_fields.get("Safety Hazards", None)
            testcase["required_ppe"] = custom_fields.get("Required PPE", None)
            testcase["postcondition"] = custom_fields.get("Postcondition", None)

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

        # Extract bolded items from objective
        # if "objective" in testcase_resp:
        #     more_info = extract_strong(testcase_resp["objective"], "test_items")
        #     if "test_items" in more_info:
        #         split_text = more_info["test_items"].splitlines()
        #         # omit first "test items" line
        #         if split_text and re.match("test item", split_text[0].lower()):
        #             split_text = split_text[1:]
        #         testcase["test_items"] = "\n".join(split_text)
        #         del more_info["test_items"]
        #     testcase["more_objectives"] = more_info

        testcases_model.append(testcase)
    return testcases_model


# def extract_strong(content, first_text_name=None):
#     """
#     Extract "strong" elements and attach their siblings up to the
#     next "strong" element.
#     :param first_text_name:
#     :param content: HTML to parse
#     :return: A dict of those elements with the sibling HTML as the values
#     """
#     soup = BeautifulSoup(content, "html.parser")
#     headers = OrderedDict()
#     element_name = first_text_name
#     element_neighbor_text = ""
#     for elem in soup.children:
#         if "strong" == elem.name:
#             if element_name:
#                 headers[element_name] = element_neighbor_text
#             element_name = elem.text.lower().replace(" ", "_")
#             # translate requirements to "deprecated requirements" style
#             if "requirements" in element_name:
#                 element_name = "requirements"
#             element_neighbor_text = ""
#             continue
#         element_neighbor_text += str(elem) + "\n"
#     headers[element_name] = element_neighbor_text
#     return headers


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
            requirement = {"key": issue,
                           "summary": summary,
                           "anchor": anchor,
                           "jira_url": jira_url
                           }
            requirements_map[issue] = requirement
            requirements.append(requirement)
    return requirements


def _make_step(step_raw):
    def extract_description(description):
        if not description:
            return description
        # If it exists, look for markdown text
        soup = BeautifulSoup(description, "html.parser")
        # normalizes HTML, replace breaks with newline, non-breaking spaces
        description = str(soup).replace("<br/>", "\n").replace("\xa0", " ")
        # matches `[markdown]: #`
        # if re.match("\[(.*)\].*:.*#(.*)", description.splitlines()[0]):
        Config.DOC.gfm = description.encode("utf-8")
        description = Config.DOC.html.decode("utf-8")
        return description

    step = {}
    step['index'] = step_raw['index']
    step['description'] = extract_description(step_raw.get('description', None))
    step['expected_result'] = step_raw.get('expectedResult', None)
    # Note: Don't dereference any further
    # If testCaseKey is in step, then go ahead and add it....
    step['test_case_key'] = step_raw.get('testCaseKey', None)
    return step
