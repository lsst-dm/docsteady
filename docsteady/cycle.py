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
from typing import Tuple

import requests
from marshmallow import EXCLUDE, INCLUDE, Schema, fields, post_load, pre_load

from docsteady.spec import Issue
from docsteady.utils import (
    HtmlPandocField,
    MarkdownableHtmlPandocField,
    as_arrow,
    owner_for_id,
    test_case_for_key,
)

from .config import Config


class TestCycleItem(Schema):
    id = fields.Integer(required=True)
    test_case_key = fields.Function(
        deserialize=lambda key: test_case_for_key(key)["key"],
        data_key="testCaseKey",
        required=True,
    )
    user_id = fields.String(data_key="userKey")
    user = fields.Function(
        data_key="userKey", deserialize=lambda obj: owner_for_id(obj)
    )
    assignee = fields.Function(
        data_key="assignedTo", deserialize=lambda obj: owner_for_id(obj)
    )
    execution_date = fields.Function(
        deserialize=lambda o: as_arrow(o["executionDate"])
    )
    status = fields.String(required=True)


class TestCycle(Schema):
    key = fields.String(required=True)
    name = HtmlPandocField(required=True)
    description = HtmlPandocField()
    status = fields.String(required=True)
    execution_time = fields.Integer(required=True, data_key="executionTime")
    created_on = fields.Function(
        deserialize=lambda o: as_arrow(o["createdOn"])
    )
    updated_on = fields.Function(
        deserialize=lambda o: as_arrow(o["updatedOn"])
    )
    planned_start_date = fields.Function(
        deserialize=lambda o: as_arrow(o["plannedStartDate"])
    )
    created_by = fields.Function(
        deserialize=lambda obj: owner_for_id(obj), data_key="createdBy"
    )
    owner = fields.Function(
        deserialize=lambda obj: owner_for_id(obj), data_key="owner"
    )
    custom_fields = fields.Dict(data_key="customFields")
    # Renamed to prevent Jinja collision
    test_items = fields.Nested(
        TestCycleItem, many=True, unknown=INCLUDE, data_key="items"
    )

    # custom fields
    software_version = HtmlPandocField()
    configuration = HtmlPandocField()

    @pre_load(pass_many=False)
    def extract_custom_fields(self, data: dict, **kwargs: []) -> dict:
        if "customFields" in data.keys():
            custom_fields = data["customFields"]

            def _set_if(target_field: str, custom_field: str) -> None:
                if custom_field in custom_fields:
                    data[target_field] = custom_fields[custom_field]

            _set_if("software_version", "Software Version / Baseline")
            _set_if("configuration", "Configuration")
        return data


class ScriptResult(Schema):
    index = fields.Integer(data_key="index")
    expected_result = MarkdownableHtmlPandocField(data_key="expectedResult")
    execution_date = fields.String(data_key="executionDate")
    description = MarkdownableHtmlPandocField(data_key="description")
    comment = MarkdownableHtmlPandocField(data_key="comment")
    status = fields.String(data_key="status")
    testdata = MarkdownableHtmlPandocField(data_key="testData")
    # result_issue_keys are actually jira issue keys (not HTTP links)
    result_issue_keys = fields.List(fields.String(), data_key="issueLinks")
    result_issues = fields.Nested(Issue, many=True)
    custom_field_values = fields.List(
        fields.Dict(), data_key="customFieldValues"
    )

    # Custom fields
    example_code = MarkdownableHtmlPandocField()  # name: "Example Code"

    @pre_load(pass_many=False)
    def extract_custom_fields(self, data: dict, **kwargs: []) -> None:
        # Custom fields
        custom_field_values = data.get("customFieldValues", list())
        for custom_field in custom_field_values:
            if "booleanValue" in custom_field:
                string_value = custom_field["booleanValue"]
            else:
                string_value = custom_field["stringValue"]
            name = custom_field["customField"]["name"]
            name = name.lower().replace(" ", "_")
            data[name] = string_value
        return data

    @post_load
    def postprocess(self, data: dict, **kwargs: []) -> dict:
        # Need to do this here because we need result_issue_keys _and_ key
        data["result_issues"] = self.process_result_issues(data)
        return data

    def process_result_issues(self, data: dict) -> list[Issue]:
        issues: list[Issue] = []
        if "result_issue_keys" in data:
            # Build list of issues
            for issue_key in data["result_issue_keys"]:
                if issue_key not in Config.CACHED_ISSUES:
                    resp = requests.get(
                        Config.ISSUE_URL.format(issue=issue_key),
                        auth=Config.AUTH,
                    )
                    resp.raise_for_status()
                    issue_resp = resp.json()
                    issue = Issue(unknown=EXCLUDE).load(
                        issue_resp, partial=True
                    )
                    Config.CACHED_ISSUES[issue_key] = issue
                issues.append(Config.CACHED_ISSUES[issue_key])
        return issues


class TestResult(Schema):
    id = fields.Integer(required=True)
    key = fields.String(required=True)
    comment = HtmlPandocField()
    test_case_key = fields.Function(
        deserialize=lambda key: test_case_for_key(key)["key"],
        data_key="testCaseKey",
        required=True,
    )
    script_results = fields.Nested(
        ScriptResult,
        unknown=EXCLUDE,
        many=True,
        data_key="scriptResults",
        required=True,
    )
    issue_links = fields.List(fields.String(), data_key="issueLinks")
    issues = fields.Nested(Issue, many=True)
    user_id = fields.String(data_key="userKey")
    user = fields.Function(
        deserialize=lambda obj: owner_for_id(obj), data_key="userKey"
    )
    status = fields.String(data_key="status", required=True)
    # These fields are not used at the moment,
    # but maybe we need them in the future
    # automated = fields.Boolean(required=True)
    # environment = fields.String()
    # execution_time = fields.Integer(data_key='executionTime', required=True)
    # execution_date = fields.Function(deserialize=lambda o: as_arrow(o),
    #                          required=True, data_key='executionDate')

    @post_load
    def postprocess(self, data: dict, **kwargs: []) -> dict:
        data["issues"] = self.process_issues(data)
        return data

    def process_issues(self, data: dict) -> list[Issue]:
        issues: list[Issue] = []
        if "issue_links" in data:
            issue: Issue
            for issue_key in data["issue_links"]:
                if issue_key not in Config.CACHED_ISSUES:
                    resp = requests.get(
                        Config.ISSUE_URL.format(issue=issue_key),
                        auth=Config.AUTH,
                    )
                    resp.raise_for_status()
                    issue_resp = resp.json()
                    issue = Issue(unknown=EXCLUDE).load(
                        issue_resp, partial=True
                    )
                    Config.CACHED_ISSUES[issue_key] = issue
                else:
                    issue = Config.CACHED_ISSUES[issue_key]
                Config.ISSUES_TO_TESTRESULTS.setdefault(issue_key, []).append(
                    data["key"]
                )
                issues.append(issue)
        return issues


def build_results_model(testcycle_id: str) -> Tuple[TestCycle, TestResult]:
    resp = requests.get(
        Config.TESTCYCLE_URL.format(testrun=testcycle_id), auth=Config.AUTH
    )
    resp.raise_for_status()
    testcycle = TestCycle(unknown=EXCLUDE).load(resp.json(), partial=True)
    resp = requests.get(
        Config.TESTRESULTS_URL.format(testrun=testcycle_id), auth=Config.AUTH
    )
    resp.raise_for_status()
    testresults = TestResult(unknown=EXCLUDE).load(
        resp.json(), many=True, partial=True
    )
    return testcycle, testresults
