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
# from typing import Any, Optional, List, Dict
# from collections import OrderedDict
import arrow
# from arrow.arrow import Arrow
import requests
from marshmallow import Schema, fields, post_load

from docsteady.utils import owner_for_id, test_case_for_key
from .config import Config


def as_arrow(datestring):
    return arrow.get(datestring).to(Config.TIMEZONE)


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

    @post_load
    def process_custom_fields(self, data):
        custom_fields = data["custom_fields"]
        data["software_version"] = custom_fields.get("Software Version / Baseline")


class ScriptResult(Schema):
    index = fields.Integer(load_from='index')
    expected_result = fields.String(load_from='expectedResult')
    execution_date = fields.String(load_from='executionDate')
    description = fields.String(load_from='description')
    comment = fields.String(load_from='comment')
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

    # for testresult_resp in testresults_resp:
    #     testresult = {}
    #     testresult['key']: str = testresult_resp["key"]
    #     testresult['name']: str = testresult_resp['name']
    #     testresult['description']: str = testresult_resp["description"]
    #     testresult['status']: str = testresult_resp['status']
    #     testresult['execution_time']: int = testresult_resp["execution_time"]
    #     testresult['execution_date']: Arrow = arrow.get(
    #         testresult_resp["executionDate"]).to("US/Pacific")
    #     testresult['created_on']: Arrow = arrow.get(
    #         testresult_resp["createdOn"]).to("US/Pacific")
    #     testresult['updated_on']: Arrow = arrow.get(
    #         testresult_resp["updated_on"]).to("US/Pacific")
    #     testresult['planned_start_date']: Arrow = arrow.get(
    #         testresult_resp["plannedStartDate"]).to("US/Pacific")
    #     testresult["owner_id"]: str = testresult_resp["owner"]
    #     testresult["owner"]: str = owner_for_id(testresult_resp["owner"])
    #     testresult["created_by"]: str = owner_for_id(testresult_resp["createdBy"])
    #
    #     script_results = []
    #     for i, sr_item in enumerate(testresult_resp["scriptResults"]):
    #         script_result = {} # dict(script_result_resp.items())
    #         script_result["execution_date"]: Arrow = arrow.get(sr_item["executionDate"]).to("US/Pacific")
    #         # script_date = script_date.format('YYYY-MM-DD HH:mm:ss')
    #         script_result['expected_result']: Optional[str] = sr_item.get("expectedResult")
    #         script_result['test_data']: Optional[str] = sr_item.get("testData")
    #         script_result['comment']: str = sr_item.get("comment")
    #         script_results.append(script_result)
    #     testresult_resp["script_results"]: List[Dict[str, Any]] = script_results
    #     testresults.append(testresult_resp)
    # return testresults
