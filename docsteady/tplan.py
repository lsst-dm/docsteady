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
from marshmallow import Schema, fields, pre_load

from docsteady.cycle import TestCycle, TestResult
from docsteady.spec import Issue, TestCase
from docsteady.utils import owner_for_id, as_arrow, HtmlPandocField, SubsectionableHtmlPandocField
from .config import Config


class TestPlan(Schema):
    key = fields.String(required=True)
    name = fields.String(required=True)
    objective = SubsectionableHtmlPandocField(extractable=["scope"])
    status = fields.String(required=True)
    folder = fields.String(required=True)
    created_on = fields.Function(deserialize=lambda o: as_arrow(o['createdOn']))
    updated_on = fields.Function(deserialize=lambda o: as_arrow(o['updatedOn']))
    owner_id = fields.String(load_from="owner", required=True)
    owner = fields.Function(deserialize=lambda obj: owner_for_id(obj))
    created_by = fields.Function(deserialize=lambda obj: owner_for_id(obj), load_from="createdBy")
    custom_fields = fields.Dict(load_from="customFields")

    # See preprocess_plan function for this. It's really nested, but we
    # pull out the keys and ignore ``testRuns``
    cycles = fields.List(fields.String())

    # Derived fields
    milestone_id = fields.String()
    milestone_name = fields.String()
    product = fields.String()

    # custom fields
    #system_overview = HtmlPandocField()
    system_overview = SubsectionableHtmlPandocField(extractable=["applicable_documents"])
    verification_environment = HtmlPandocField()
    entry_criteria = HtmlPandocField()
    exit_criteria = HtmlPandocField()
    pmcs_activity = HtmlPandocField()
    verification_artifacts = HtmlPandocField()
    observing_required = fields.Boolean()
    overall_assessment = HtmlPandocField()
    recommended_improvements = HtmlPandocField()
    # Note: Add More custom fields above here (and don't forget preprocess_plan)

    @pre_load(pass_many=False)
    def preprocess_plan(self, data):
        """
        During pre_load, we modify the input dictionary to make it look like
        extra data was in the request information. This means that we "pull up"
        custom fields in from the ``customFields`` dict, and we also, for the
        test plan, extract milestone information from the folrder information.

        Marshmallow will see the modified input dictionary and use the
        schema definition appropriately.
        """

        # Handle custom fields first
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
        # Note: Add More custom fields above here

        # Derived fields
        # Extract milestone information
        sname = data['name'].split(" ")
        namekey = sname[0][:3]
        namekey1 = sname[0][:7]
        if namekey == '503' or namekey1 == 'LDM-503':
            data['milestone_id'] = sname[0]
            data['milestone_name'] = data['name'].replace(sname[0], '').strip().capitalize()
        else:
            data['milestone_id'] = data['key']
            data['milestone_name'] = data['name'].capitalize()

        # Product
        data['product'] = data['folder'].split('/')[-1]

        # Flatten out testRuns
        data["cycles"] = [cycle["key"] for cycle in data["testRuns"]]
        return data


def build_tpr_model(tplan_id):
    resp = requests.get(Config.TESTPLAN_URL.format(testplan=tplan_id),
                        auth=Config.AUTH)
    resp.raise_for_status()
    testplan, errors = TestPlan().load(resp.json())

    # get a list of extra fields
    # not possible now.

    test_cycles_map = {}
    test_results_map = {}
    test_cases_map = {}

    for cycle_key in testplan['cycles']:
        resp = requests.get(Config.TESTCYCLE_URL.format(testrun=cycle_key), auth=Config.AUTH)
        test_cycle, error = TestCycle().load(resp.json())
        test_cycles_map[cycle_key] = test_cycle

        resp = requests.get(Config.TESTRESULTS_URL.format(testrun=cycle_key), auth=Config.AUTH)
        resp.raise_for_status()
        testresult, errors = TestResult().load(resp.json(), many=True)
        test_results_map[cycle_key] = testresult

        # Get all the test cases from the test items
        for test_item in test_cycle['test_items']:
            resp = requests.get(Config.TESTCASE_URL.format(testcase=test_item['test_case_key']),
                                auth=Config.AUTH)
            testcase, errors = TestCase().load(resp.json())
            test_cases_map[test_item['test_case_key']] = testcase

    tpr = {}
    tpr['tplan'] = testplan
    tpr['test_cycles_map'] = test_cycles_map
    tpr['test_results_map'] = test_results_map
    tpr['test_cases_map'] = test_cases_map

    return tpr
