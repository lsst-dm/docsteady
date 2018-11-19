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
import requests
import sys
from marshmallow import Schema, fields, pre_load, post_load

from docsteady.spec import Issue, TestCase
from docsteady.utils import owner_for_id, test_case_for_key, as_arrow, HtmlPandocField, \
    MarkdownableHtmlPandocField
from .config import Config


class TestCycleItem(Schema):
    id = fields.Integer(required=True)
    test_case_key = fields.Function(deserialize=lambda key: test_case_for_key(key)["key"],
                                    load_from='testCaseKey', required=True)
    user_id = fields.String(load_from="userKey")
    user = fields.Function(deserialize=lambda obj: owner_for_id(obj["userKey"]))
    execution_date = fields.Function(deserialize=lambda o: as_arrow(o['executionDate']))
    status = fields.String(required=True)


class TestCycle(Schema):
    key = fields.String(required=True)
    name = fields.String(required=True)
    description = fields.String(required=True)
    status = fields.String(required=True)
    execution_time = fields.Integer(required=True, load_from="executionTime")
    created_on = fields.Function(deserialize=lambda o: as_arrow(o['createdOn']))
    updated_on = fields.Function(deserialize=lambda o: as_arrow(o['updatedOn']))
    planned_start_date = fields.Function(deserialize=lambda o: as_arrow(o['plannedStartDate']))
    owner_id = fields.String(load_from="owner", required=True)
    owner = fields.Function(deserialize=lambda obj: owner_for_id(obj))
    created_by = fields.Function(deserialize=lambda obj: owner_for_id(obj), load_from="createdBy")
    custom_fields = fields.Dict(load_from="customFields")
    items = fields.Nested(TestCycleItem, many=True)

    # custom fields
    name = HtmlPandocField()
    description = HtmlPandocField()
    software_version = HtmlPandocField()
    configuration = HtmlPandocField()

    @pre_load(pass_many=False)
    def extract_custom_fields(self, data):
        custom_fields = data["customFields"]

        def _set_if(target_field, custom_field):
            if custom_field in custom_fields:
                data[target_field] = custom_fields[custom_field]

        _set_if("software_version", "Software Version / Baseline")
        return data


class ScriptResult(Schema):
    index = fields.Integer(load_from='index')
    expected_result = MarkdownableHtmlPandocField(load_from='expectedResult')
    execution_date = fields.String(load_from='executionDate')
    description = MarkdownableHtmlPandocField(load_from='description')
    comment = MarkdownableHtmlPandocField(load_from='comment')
    status = fields.String(load_from='status')


class TestIssue(Schema):
    key = fields.String()
    jira_url = fields.String()


class TestResult(Schema):
    id = fields.Integer(required=True)
    key = fields.String(required=True)
    automated = fields.Boolean(required=True)
    environment = fields.String()
    comment = fields.String()
    execution_time = fields.Integer(load_from='executionTime', required=True)
    test_case_key = fields.Function(deserialize=lambda key: test_case_for_key(key)["key"],
                                    load_from='testCaseKey', required=True)
    execution_date = fields.Function(deserialize=lambda o: as_arrow(o), required=True,
                                     load_from='executionDate')
    script_results = fields.Nested(ScriptResult, many=True, load_from="scriptResults",
                                   required=True)
    issues = fields.Nested(Issue, many=True)
    issue_links = fields.List(fields.String(), load_from="issueLinks")
    user_id = fields.String(load_from="userKey")
    user = fields.Function(deserialize=lambda obj: owner_for_id(obj), load_from="userKey")
    status = fields.String(load_from='status', required=True)

    @post_load
    def postprocess(self, data):
        # Need to do this here because we need issue_links _and_ key
        data['issues'] = self.process_issues(data)
        return data

    def process_issues(self, data):
        issues = []
        if "issue_links" in data:
            # Build list of requirements
            for issue_key in data["issue_links"]:
                issue = Config.CACHED_ISSUES.get(issue_key, None)
                if not issue:
                    resp = requests.get(Config.ISSUE_URL.format(issue=issue_key), auth=Config.AUTH)
                    resp.raise_for_status()
                    issue_resp = resp.json()
                    issue, errors = Issue().load(issue_resp)
                    if errors:
                        raise Exception("Unable to Process Requirement: " + str(errors))
                    Config.CACHED_ISSUES[issue_key] = issue
                Config.ISSUES_TO_TESTRESULTS.setdefault(issue_key, []).append(data['key'])
                issues.append(issue)
        return issues

class TestCycleId(Schema):
    #
    # Apparantly the TestCycle class do not return the related test cases
    # when called from the TestPlan class
    # So I populate the TestPlan with just the TestCycle IDs and
    # extract the full TestCycle details in a second moment
    #
    key = fields.String(required=True)

class TestPlan(Schema):
    key = fields.String(required=True)
    name = fields.String(required=True)
    objective = fields.String(required=True)
    status = fields.String(required=True)
    folder = fields.String(required=True)
    created_on = fields.Function(deserialize=lambda o: as_arrow(o['createdOn']))
    updated_on = fields.Function(deserialize=lambda o: as_arrow(o['updatedOn']))
    owner_id = fields.String(load_from="owner", required=True)
    owner = fields.Function(deserialize=lambda obj: owner_for_id(obj))
    created_by = fields.Function(deserialize=lambda obj: owner_for_id(obj), load_from="createdBy")
    custom_fields = fields.Dict(load_from="customFields")
    tcycles_id = fields.Nested(TestCycle, many=True, load_from="testRuns")

    # custom fields
    name = HtmlPandocField()
    objective = HtmlPandocField()
    system_overview = HtmlPandocField()
    verification_environment = HtmlPandocField()
    entry_criteria = HtmlPandocField()
    exit_criteria = HtmlPandocField()
    pmcs_activity = HtmlPandocField()
    verification_artifacts = HtmlPandocField()
    observing_required = fields.Boolean()
    overall_assessment = HtmlPandocField()
    recommended_improvements = HtmlPandocField()
    product = fields.String()

    @pre_load(pass_many=False)
    def extract_custom_fields(self, data):
        custom_fields = data["customFields"]

        def _set_if(target_field, custom_field):
            if custom_field in custom_fields:
                data[target_field] = custom_fields[custom_field]

        _set_if("system_overview", "System Overview")
        _set_if("verification_environment", "Verification Environment")
        _set_if("exit_criteria", "Exit Criteria")
        _set_if("entry_criteria", "Entry Criteria")
        _set_if("pmcs_activity", "PMCS Activity")
        _set_if("observing_required", "Observing Required")
        _set_if("verification_artifacts", "Verification Artifacts")
        _set_if("overall_assessment", "Overall Assessment")
        _set_if("recommended_improvements", "Recommended Improvements")
        return data

#def render(field):
#    words = field.split(' ')
#    i = 0
#    for word in words:
#        if 'LDM-' in word:
#            print(i, '> ', word)
#            sw = word.split('LDM-')
#            print('    ', sw[1]) 
#            #check that they are not milestones
#            checkm = sw[1].split('-')
#            if len(checkm) == 1:
#                print('........', checkm[0][:3])
#                words[i] = sw[0] + '\citeds(\{LDM-' + checkm[0][:3] + '}' + checkm[0][3:]
#        i += 1
#    rendered = ' '.join(map(str, words))
#    print('R: ', rendered)
#    return rendered


#def cite_docs(element):
#    docs = []
#    l = 0
#    for field in element:
#        print(l)
#        if field not in ('custom_fields', 'tcycles_id'):
#            print('--field: ', field)
#            if isinstance(element[field], str):
#                print('i-> ', element[field])
#                element[l] = render(element[field])
#        l += 1
#    return element

def build_tpr_model(tplan_id):
    resp = requests.get(Config.TESTPLAN_URL.format(testplan=tplan_id),
                        auth=Config.AUTH)
    resp.raise_for_status()
    testplan, errors = TestPlan().load(resp.json())

    # gret the milestone info
    milestone = {}
    sname = testplan['name'].split(" ")
    namekey = sname[0][:3]
    if namekey == '503':
       milestone['id'] = sname[0]
       milestone['name'] = testplan['name'].replace(sname[0],'').strip().capitalize()
    else:
       milestone['id'] = testplan['key']
       milestone['name'] = testplan['key'].capitalize()

    # get last part pf the folder: the product
    sfolder = testplan['folder'].split('/')
    #print(sfolder[len(sfolder)-1])
    product = sfolder[len(sfolder)-1]

    # get a list of extra fields
    # not possible now.

    test_cycles = {}
    test_results = {}
    test_cases = {}
    for tcycle in testplan['tcycles_id']:
        resp = requests.get(Config.TESTCYCLE_URL.format(testrun=tcycle['key']),
                            auth=Config.AUTH)
        testschema, error = TestCycle().load(resp.json())
        test_cycles[tcycle['key']] = testschema
        resp = requests.get(Config.TESTRESULTS_URL.format(testrun=tcycle['key']),
                            auth=Config.AUTH)
        resp.raise_for_status()
        testresult, errors = TestResult().load(resp.json(), many=True)
        test_results[tcycle['key']] = testresult 
        for item in testschema['items']:
            resp = requests.get(Config.TESTCASE_URL.format(testcase=item['test_case_key']),
                               auth=Config.AUTH)
            tcase = TestCase().load(resp.json())
            test_cases[item['test_case_key']] = tcase

    tpr = {}
    tpr['tplan'] = testplan
    tpr['milestone'] = milestone
    tpr['product'] = product
    tpr['test_cycles'] = test_cycles
    tpr['test_results'] = test_results
    tpr['test_cases'] = test_cases

    #return testplan, test_cycles, test_results
    return tpr
