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
from typing import List

import requests
from marshmallow import EXCLUDE, Schema, fields, post_load, pre_load

from docsteady.spec import Issue
from docsteady.utils import (
    HtmlPandocField,
    MarkdownableHtmlPandocField,
    as_arrow,
    get_key,
    get_value,
    owner_for_id,
    process_links,
)

from .config import Config


class ScriptResult(Schema):
    index = fields.Integer(data_key="index")
    id = fields.Integer(data_key="key")
    expected_result = MarkdownableHtmlPandocField(data_key="expectedResult")
    actual_result = MarkdownableHtmlPandocField(data_key="actualResult")
    execution_date = fields.String(data_key="executionDate")
    description = MarkdownableHtmlPandocField(data_key="description")
    comment = MarkdownableHtmlPandocField(data_key="comment")
    status = fields.Function(
        deserialize=lambda obj: get_value(obj), data_key="testExecutionStatus"
    )
    testdata = MarkdownableHtmlPandocField(data_key="testData")
    # result_issue_keys are actually jira issue keys (not HTTP links)
    result_issue_links = fields.Method(
        deserialize="process_result_issues", data_key="links", required=False
    )
    result_issues = fields.Nested(Issue, many=True)
    custom_field_values = fields.List(
        fields.Dict(), data_key="customFieldValues"
    )

    # Custom fields
    example_code = MarkdownableHtmlPandocField()  # name: "Example Code"

    @pre_load(pass_many=False)
    def extract_custom_fields(self, data: dict, **kwargs: List[str]) -> dict:
        # Custom fields
        if "customFieldValues" in data:
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
    def postprocess(self, data: dict, **kwargs: List[str]) -> dict:
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
        deserialize=lambda obj: get_key(obj), data_key="testCase"
    )
    script_results = fields.Nested(
        ScriptResult,
        unknown=EXCLUDE,
        many=True,
        data_key="scriptResults",
        required=True,
    )
    issue_links = fields.Method(
        deserialize="process_issue_links", data_key="links", required=False
    )

    issues = fields.Nested(Issue, many=True)
    user_id = fields.String(data_key="executedById")
    user = fields.Function(
        deserialize=lambda obj: owner_for_id(obj), data_key="executedById"
    )
    testExecutionStatus = fields.Function(
        deserialize=lambda obj: get_value(obj)
    )
    assignee = fields.Function(
        data_key="assignedToId", deserialize=lambda obj: owner_for_id(obj)
    )
    executedby = fields.Function(
        data_key="executedById", deserialize=lambda obj: owner_for_id(obj)
    )
    execution_date = fields.Function(
        deserialize=lambda o: as_arrow(o["executionDate"])
    )
    custom_fields = fields.Dict(data_key="customFields")
    # custom field
    include = fields.Boolean()  # include in report

    @pre_load(pass_many=False)
    def extract_custom_fields(self, data: dict, **kwargs: List[str]) -> dict:
        if "customFields" in data.keys():
            custom_fields = data["customFields"]

            def _set_if(target_field: str, custom_field: str) -> None:
                if custom_field in custom_fields:
                    data[target_field] = custom_fields[custom_field]

            _set_if("include", "Include Execution in Test Report")
        return data

    @post_load
    def postprocess(self, data: dict, **kwargs: List[str]) -> dict:
        data["issues"] = self.process_issues(data)
        return data

    def process_issue_links(self, links: dict) -> list | None:
        plinks = process_links(links, "issues")
        keys = []
        for link in plinks:
            keys.append(link["target"])
        return keys

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


class TestCycle(Schema):
    id = fields.Integer(required=True)
    key = fields.String(required=True)
    name = HtmlPandocField(required=True)
    description = HtmlPandocField()
    status = fields.Function(deserialize=lambda obj: get_value(obj))
    execution_time = fields.Integer(required=False, data_key="executionTime")
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

    test_items: List[
        TestResult
    ] = []  # items are not in cyle anymorre test case list near as I can tell

    test_plans = fields.Method(
        deserialize="process_test_plans", data_key="links", required=False
    )

    # custom fields
    software_version = HtmlPandocField()
    configuration = HtmlPandocField()

    @pre_load(pass_many=False)
    def extract_custom_fields(self, data: dict, **kwargs: List[str]) -> dict:
        if "customFields" in data.keys():
            custom_fields = data["customFields"]

            def _set_if(target_field: str, custom_field: str) -> None:
                if custom_field in custom_fields:
                    data[target_field] = custom_fields[custom_field]

            _set_if("software_version", "Software Version / Baseline")
            _set_if("configuration", "Configuration")
        return data

    def process_test_plans(self, data: dict) -> list[str]:
        """Test plan is in links now and it is a pointer
        the target on the pointer gives a 404 -"""
        plans: list[str] = []
        if "testPlans" in data:
            for plan in data["testPlans"]:
                plans.append(plan["testPlanId"])
        return plans
