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
import datetime
import logging
import sys
from typing import List

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PackageLoader
from marshmallow import EXCLUDE, INCLUDE, Schema, fields, pre_load
from zephyr.scale.cloud.endpoints import paths

from .config import Config
from .cycle import ScriptResult, TestCycle, TestResult
from .formatters import alphanum_map_sort
from .spec import TestCase
from .utils import (
    HtmlPandocField,
    SubsectionableHtmlPandocField,
    _as_output_format,
    as_arrow,
    create_folders_and_files,
    download_attachments,
    fix_json,
    get_execs,
    get_teststeps,
    get_value,
    get_zephyr_api,
    owner_for_id,
)


class TestPlan(Schema):
    key = fields.String(required=True)
    # the name (TPR title) can contain extra characters that requires pandoc.
    # this may break the bib reference generation
    name = HtmlPandocField(required=True)
    objective = SubsectionableHtmlPandocField(extractable=["scope"])
    folder = fields.Function(deserialize=lambda obj: get_value(obj))
    status = fields.Function(deserialize=lambda obj: get_value(obj))
    created_on = fields.Function(
        deserialize=lambda o: as_arrow(o["createdOn"])
    )
    updated_on = fields.Function(
        deserialize=lambda o: as_arrow(o["updatedOn"])
    )
    owner = fields.Function(deserialize=lambda obj: owner_for_id(obj))
    owner_id = fields.Function(
        deserialize=lambda obj: get_value(obj, "accountId")
    )
    created_by = fields.Function(
        deserialize=lambda obj: owner_for_id(obj), data_key="createdBy"
    )
    custom_fields = fields.Dict(data_key="customFields")

    # See preprocess_plan function for this. It's really nested, but we
    # pull out the keys and ignore ``testRuns``
    cycles = fields.List(fields.String())

    # Derived fields
    milestone_id = fields.String()
    milestone_name = HtmlPandocField()
    product = fields.String()
    doc_name = HtmlPandocField()

    # custom fields
    system_overview = SubsectionableHtmlPandocField(
        extractable=["applicable_documents"]
    )
    verification_environment = HtmlPandocField()
    entry_criteria = HtmlPandocField(allow_none=True)
    exit_criteria = HtmlPandocField(allow_none=True)
    pmcs_activity = HtmlPandocField(allow_none=True)
    verification_artifacts = HtmlPandocField(allow_none=True)
    observing_required = fields.Boolean()
    overall_assessment = HtmlPandocField()
    recommended_improvements = HtmlPandocField()
    document_id = fields.String()
    extract_date = fields.String()

    # Note: Add More custom fields above here
    # (and don't forget preprocess_plan)

    @pre_load(pass_many=False)
    def preprocess_plan(self, data: dict, **kwargs: List[str]) -> dict:
        """
        During pre_load, we modify the input dictionary to make it look like
        extra data was in the request information. This means that we "pull up"
        custom fields in from the ``customFields`` dict, and we also, for the
        test plan, extract milestone information from the folder information.

        Marshmallow will see the modified input dictionary and use the
        schema definition appropriately.
        """

        def _set_if(target_field: str, custom_field: str) -> None:
            if custom_field in custom_fields:
                data[target_field] = custom_fields[custom_field]

        # Handle custom fields first
        if "customFields" in data.keys():
            custom_fields = data["customFields"]

            _set_if("system_overview", "System Overview")
            _set_if("verification_environment", "Verification Environment")
            _set_if("exit_criteria", "Exit Criteria")
            _set_if("entry_criteria", "Entry Criteria")
            _set_if("pmcs_activity", "PMCS Activity")
            _set_if("observing_required", "Observing Required")
            _set_if("verification_artifacts", "Verification Artifacts")
            _set_if("overall_assessment", "Overall Assessment")
            _set_if("recommended_improvements", "Recommended Improvements")
            _set_if("document_id", "Document ID")
            data["extract_date"] = datetime.date.today().isoformat()
            # validator complains abuout Null when these are None
            # Note: Add More custom fields above here

        # Derived fields
        # Extract milestone information
        sname = data["name"].split(":")
        if len(sname) != 1:
            data["milestone_id"] = sname[0]
            data["milestone_name"] = (
                data["name"].replace(sname[0], "").replace(":", "").strip()
            )
            data["doc_name"] = (
                data["milestone_id"] + ": " + data["milestone_name"]
            )
        else:
            data["milestone_id"] = ""
            data["milestone_name"] = data["name"].strip()
            data["doc_name"] = data["key"] + ": " + data["name"].strip()

        # Product  -  the made these all urls now ..
        data["product"] = get_value(data["folder"])

        # Flatten out testRuns - now testCycles
        cycles = data["links"]["testCycles"]
        data["cycles"] = [str(cycle["testCycleId"]) for cycle in cycles]
        return data


def labelResults(result: dict) -> None:
    # The results index is not unique - if there are multiple parameters the
    # script repeats each step  for each set of parameters
    # (think multiple pointings)
    # Previously this was sorted on index which works for one run
    # but not for multiples.
    # Jira does not number them 1.1 1.2 etc .
    # but based on the order we label them like that
    do_level = False
    step0 = 0
    # first see if we have multiple step 0s
    for r in result["script_results"]:
        if "index" in r and r["index"] == 0:
            step0 = step0 + 1
        if step0 > 1:
            do_level = True
            break

    level = 0
    for i, r in enumerate(result["script_results"]):
        if "index" in r and r["index"] == 0:
            level = level + 1
        if do_level:
            r["label"] = level + (r["index"] + 1) / 10.0
        else:
            if "index" in r:
                r["label"] = r["index"] + 1
            else:
                r["label"] = i + 1
        r["label"] = f"{result['key']}-{r['label']}"
    pass


def build_tpr_model(tplan_key: str) -> dict:
    # create folders for images and attachments if not already there
    logging.log(logging.INFO, "Building Test Plan Report Model")
    create_folders_and_files()

    test_cycles_map: dict = {}
    test_results_map: dict = {}
    test_cases_map: dict = {}
    attachments: dict = {}

    # get test plan information
    zapi = get_zephyr_api()
    resp = fix_json(zapi.test_plans.get_test_plan(tplan_key))
    testplan: dict = TestPlan(unknown=EXCLUDE).load(resp)
    if "document_id" not in testplan or testplan["document_id"] == "":
        print(
            f"ERROR: Document ID missing in {tplan_key}. "
            f"Please complete the metadata before proceeding with "
            f"the extraction."
        )
        exit()

    attachments[tplan_key] = download_attachments(resp)
    n_attachments = len(attachments[tplan_key])

    # get test cycles and results information
    attachments["cycles"] = dict()
    attachments["results"] = dict()
    # This also has pointers now not ids ..
    for cycle_id in testplan["cycles"]:
        logging.log(logging.INFO, f"Adding cycle {cycle_id}")
        resp = zapi.test_cycles.get_test_cycle(cycle_id)
        test_cycle = TestCycle(unknown=EXCLUDE).load(resp, partial=True)
        cycle_key = test_cycle["key"]
        test_cycles_map[cycle_key] = test_cycle
        # there appears no way to get attachements
        attachments["cycles"][cycle_key] = download_attachments(test_cycle)
        n_attachments = n_attachments + len(attachments["cycles"][cycle_key])

        # executions are now per test case not cycle ...
        all_execs = get_execs(cycle_id)
        execs = []
        if Config.INCLUDE_ALL_EXECS:
            execs = all_execs
        else:  # Filter the ones which say Include Execution in report
            for exec in all_execs:
                if exec["customFields"]["Include Execution in Test Report"]:
                    execs.append(exec)

        if len(execs) == 0:
            print(
                "There are no executions marked include execution "
                "in test report - giving up  "
            )
            if len(all_execs) > 0:
                print(
                    f"There are {len(all_execs)} marked False for inclusion "
                    "mark at least one True"
                )

        logging.log(
            logging.INFO, f"Adding {len(execs)} executions to cycle {cycle_id}"
        )
        testresults = TestResult(unknown=EXCLUDE).load(
            execs, many=True, partial=True
        )
        test_results_map[cycle_key] = {}
        for result in testresults:
            # Jira does not number them 1.1 1.2 etc
            if (
                result["testExecutionStatus"] == "Not Executed"
                and result["test_case_key"] in test_results_map[cycle_key]
            ):
                continue
            results = get_teststeps(
                result["id"], paths.CloudPaths.EXECUTIONS_STEPS
            )
            result["script_results"] = ScriptResult(unknown=INCLUDE).load(
                results, many=True, partial=True
            )

            test_results_map[cycle_key][result["key"]] = result
            labelResults(result)
            attachments["results"][result["id"]] = download_attachments(result)
            n_attachments = n_attachments + len(
                attachments["results"][result["id"]]
            )
            # Get the test cases from the execution
            if result["test_case_key"] not in test_cases_map.keys():
                resp = fix_json(
                    zapi.test_cases.get_test_case(result["test_case_key"])
                )
                if len(resp) > 0:
                    testcase = TestCase(unknown=EXCLUDE).load(
                        resp, partial=True
                    )
                    if result["key"] in test_results_map[cycle_key]:
                        items = []
                        if "test_items" in test_cycle:
                            items = test_cycle["test_items"]
                        else:
                            test_cycle["test_items"] = items
                        items.append(result)
                else:
                    testcase = {
                        "objective": "This Test Case has been archived. "
                        "Information here may not completed.",
                        "key": result["test_case_key"],
                        "status": "ARCHIVED",
                    }
                test_cases_map[result["test_case_key"]] = testcase
    attachments["n_attachments"] = n_attachments

    # print(attachments)
    tpr = {
        "tplan": testplan,
        "test_cycles_map": test_cycles_map,
        "test_results_map": test_results_map,
        "test_cases_map": test_cases_map,
        "attachments": attachments,
    }

    return tpr


def filter_notexecuted_nocomment(testresults_map: dict) -> None:
    for cycle_key, test_results in testresults_map.items():
        for test_exec_key, result in test_results.items():
            newsteps = []
            key = "sorted"  # was sorted
            if key in result:
                for step in result[key]:
                    if step["status"] == "Not Executed" and (
                        "comment" not in step or step["comment"] == ""
                    ):
                        continue
                    else:
                        newsteps.append(step)
                result[key] = newsteps
        pass


def render_report(
    metadata: dict,
    target: str,
    plan_dict: dict,
    format: str,
    path: str | None = None,
) -> Environment:
    # Sort maps by keys
    testcycles_map = alphanum_map_sort(plan_dict["test_cycles_map"])
    testresults_map = alphanum_map_sort(plan_dict["test_results_map"])
    testcases_map = alphanum_map_sort(plan_dict["test_cases_map"])

    filter_notexecuted_nocomment(testresults_map)

    for cycle in plan_dict["test_cycles_map"].values():
        if "test_items" not in cycle:
            logging.log(logging.INFO, f"{cycle['key']} has no test_items")
        else:
            logging.log(
                logging.INFO,
                f"{cycle['key']} has  {len(cycle['test_items'])} test_items",
            )

    env = Environment(
        loader=ChoiceLoader(
            [
                FileSystemLoader(Config.TEMPLATE_DIRECTORY),
                PackageLoader("docsteady", "templates"),
            ]
        ),
        lstrip_blocks=True,
        trim_blocks=True,
        autoescape=False,  # Was None.
    )

    template = env.get_template(f"{target}.{Config.TEMPLATE_LANGUAGE}.jinja2")
    metadata["template"] = template.filename

    text = template.render(
        metadata=metadata,
        testplan=plan_dict["tplan"],
        testcycles=list(testcycles_map.values()),  # For convenience (sorted)
        testcycles_map=testcycles_map,
        testresults=list(testresults_map.values()),  # For convenience (sorted)
        testresults_map=testresults_map,
        attachments=plan_dict["attachments"],
        testcases_map=testcases_map,
    )

    file = open(path, "w") if path else sys.stdout
    print(_as_output_format(text, format), file=file or sys.stdout)

    if file != sys.stdout:
        file.close()

    return env
