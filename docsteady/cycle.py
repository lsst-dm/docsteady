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
    software_version = HtmlPandocField()

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


class TestResult(Schema):
    id = fields.Integer(required=True)
    key = fields.String(required=True)
    automated = fields.Boolean(required=True)
    environment = fields.String()
    execution_time = fields.Integer(load_from='executionTime', required=True)
    test_case_key = fields.Function(deserialize=lambda key: test_case_for_key(key)["key"],
                                    load_from='testCaseKey', required=True)
    execution_date = fields.Function(deserialize=lambda o: as_arrow(o), required=True,
                                     load_from='executionDate')
    script_results = fields.Nested(ScriptResult, many=True, load_from="scriptResults",
                                   required=True)
    user_id = fields.String(load_from="userKey")
    user = fields.Function(deserialize=lambda obj: owner_for_id(obj), load_from="userKey")
    status = fields.String(load_from='status', required=True)


def build_results_model(testrun_id):
    resp = requests.get(Config.TESTRUN_URL.format(testrun=testrun_id),
                        auth=Config.AUTH)
    resp.raise_for_status()
    testcycle, errors = TestCycle().load(resp.json())
    resp = requests.get(Config.TESTRESULTS_URL.format(testrun=testrun_id),
                        auth=Config.AUTH)
    resp.raise_for_status()
    testresults, errors = TestResult().load(resp.json(), many=True)
    return testcycle, testresults
