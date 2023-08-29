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
Code for VCD
"""

from collections import Counter
from typing import List

from marshmallow import Schema, fields, pre_load

from .config import Config
from .utils import HtmlPandocField

# Globals
veduplicated: dict = {}
jpr: dict = {}
jst: dict = {}


class VerificationE(Schema):
    key = fields.String(required=True)
    summary = fields.String()
    jira_url = fields.String()
    assignee = fields.String()
    description = HtmlPandocField()
    ve_status = fields.String()
    ve_priority = fields.String()
    req_id = fields.String()
    req_spec = HtmlPandocField()
    req_discussion = HtmlPandocField()
    req_priority = fields.String()
    req_doc_id = fields.String()
    req_params = HtmlPandocField()
    raw_upper_req = HtmlPandocField(allow_none=True)
    upper_reqs = fields.List(fields.String(), missing=list())
    raw_test_cases = HtmlPandocField()
    test_cases = fields.List(fields.String(), missing=list())
    verified_by = fields.Dict(
        keys=fields.String(),
        values=(fields.Dict(keys=fields.String(), values=fields.String())),
    )

    @pre_load(pass_many=False)
    def extract_fields(self, data: dict, **kwargs: List[str]) -> dict:
        data_fields = data["fields"]
        data["summary"] = data_fields["summary"]
        data["jira_url"] = Config.ISSUE_UI_URL.format(issue=data["key"])
        if data_fields["assignee"]:
            data["assignee"] = data_fields["assignee"]["displayName"]
        else:
            data["assignee"] = "UNASSIGNED"
        data["description"] = data["renderedFields"]["description"]
        data["ve_status"] = data_fields["status"]["name"]
        if data_fields["priority"]:
            data["ve_priority"] = data_fields["priority"]["name"]
        try:
            data["req_id"] = data_fields["customfield_15502"]
        except KeyError:
            print(f'Failed to get req_id customfield_15502 for {data["key"]}')
        data["req_spec"] = data["renderedFields"]["customfield_13513"]
        data["req_discussion"] = data["renderedFields"]["customfield_13510"]
        if data_fields["customfield_15204"]:
            data["req_priority"] = data_fields["customfield_15204"]["value"]
        data["req_params"] = data["renderedFields"]["customfield_13512"]
        data["raw_upper_req"] = data_fields["customfield_13515"]
        data["raw_test_cases"] = data_fields["customfield_15106"]
        data["verified_by"] = self.extract_verified_by(data_fields)
        ref = data_fields["customfield_14701"]["value"]
        if ":" in ref:
            ref = ref.split(":")[0]
        data["req_doc_id"] = ref
        return data

    def extract_verified_by(self, data_fields: dict) -> dict:
        if "issuelinks" not in data_fields.keys():
            return {}
        issuelinks = data_fields["issuelinks"]
        verified_by = {}
        for issue in issuelinks:
            if "inwardIssue" in issue.keys():
                if (
                    issue["inwardIssue"]["fields"]["issuetype"]["name"]
                    == "Verification"
                    and issue["type"]["inward"] == "verified by"
                ):
                    tmp_issue = dict()
                    tmp_issue["key"] = issue["inwardIssue"]["key"]
                    tmp_issue["summary"] = issue["inwardIssue"]["fields"][
                        "summary"
                    ]
                    verified_by[issue["inwardIssue"]["key"]] = tmp_issue

        return verified_by


class Coverage_Count:
    """Coverage for Requirements and Verification Elements"""

    notcs = 0
    noexectcs = 0
    failedtcs = 0
    passedtcs = 0
    passedtcs_name = "Passed TCs"
    passedtcs_label = "sec:passedtcs"

    def total_count(self) -> int:
        return self.notcs + self.noexectcs + self.failedtcs + self.passedtcs


def runstatus(trs: str) -> str:
    if trs == "Pass":
        status = "passed"
    elif trs == "Pass w/ Deviation":
        status = "cndpass"
    elif trs == "Fail":
        status = "failed"
    elif trs == "In Progress":
        status = "inprog"
    elif trs == "Blocked":
        status = "blocked"
    else:
        status = "notexec"
    return status


def do_ve_coverage(tcs: dict, results: dict) -> str:
    """

    :param tcs: test cases results
    :return: coverage
    """
    ntc = len(tcs)
    if ntc == 0:
        coverage = "NotCovered"
    else:
        tccount: Counter = Counter()
        for tc in tcs.keys():
            # if tc in results.keys() and results[tc]['lastR']:
            if (
                tc in results.keys()
                and "lastR" in results[tc].keys()
                and results[tc]["lastR"]
            ):
                tccount.update([results[tc]["lastR"]["status"]])
            else:
                tccount.update(["notexec"])
        if tccount["failed"] and tccount["failed"] > 0:
            coverage = "WithFailures"
        else:
            if tccount["passed"] + tccount["cndpass"] == ntc:
                coverage = "FullyVerified"
            else:
                if tccount["notexec"] == ntc:
                    coverage = "NotVerified"
                else:
                    coverage = "PartiallyVerified"

    return coverage


def do_req_coverage(ves: list, ve_coverage: dict) -> str:
    """
    Calculate the coverage level of a requirement
    based on the downstram verification elements.
    :param myvreq: version requirement name
    :param ves:
    :param ve_coverage:
    :return:
    """
    nves = len(ves)
    vecount: Counter = Counter()
    for ve in ves:
        element = ve_coverage[ve]
        # This implies there is only one VE per requirement (true for now)
        cover = element["coverage"]
        vecount.update([cover])
    # @Leanne I dont think we need these failures anymore
    if vecount["WithFailures"] and vecount["WithFailures"] > 0:
        rcoverage = "WithFailures"
    else:
        if "Verified" in vecount.keys():
            if vecount["Verified"] == nves:
                rcoverage = "Verified"
            else:
                rcoverage = "InVerification"
        elif "In Verification" in vecount.keys():
            rcoverage = "InVerification"
        else:
            if vecount["NotCovered"] == nves:
                rcoverage = "NotCovered"
            else:
                rcoverage = "NotVerified"
    return rcoverage


def find_vekey(reqname: str, ve_keys: list[str]) -> str | None:
    """Look through the keys until we find the one my requirment starts with"""
    for k in ve_keys:
        if k.startswith(reqname):
            return k
    return None


def summary(dictionary: list[dict]) -> list:
    """generate and print summary information"""
    global veduplicated
    mtrs = dict()

    verification_elements = dictionary[0]
    reqs: dict = dictionary[1]

    tcases: dict = dictionary[3]

    mtrs["nr"] = len(reqs)
    mtrs["nv"] = len(verification_elements)
    mtrs["nt"] = len(tcases)

    for reqname, req in reqs.items():
        Config.REQ_STATUS_PER_DOC_COUNT.update([req["reqDoc"]])
        Config.REQ_STATUS_PER_DOC_COUNT.update(
            [req["reqDoc"] + "." + req["priority"]]
        )
        # Each VE now has a status so we may be ablet to simplify this
        #  Leanne to help
        for ve in req["VEs"]:
            vcoverage = verification_elements[ve]["status"]
            Config.VE_STATUS_COUNT.update([vcoverage])
            verification_elements[ve]["coverage"] = vcoverage
        # Calculating the requirement coverage based on the VE coverage
        rcoverage = do_req_coverage(req["VEs"], verification_elements)
        Config.REQ_STATUS_COUNT.update([rcoverage])
        Config.REQ_STATUS_PER_DOC_COUNT.update(
            [req["reqDoc"] + ".zAll." + rcoverage]
        )
        Config.REQ_STATUS_PER_DOC_COUNT.update(
            [req["reqDoc"] + "." + req["priority"] + "." + rcoverage]
        )
    for tc in tcases.values():
        if "lastR" in tc.keys() and tc["lastR"]:
            Config.TEST_STATUS_COUNT.update([tc["lastR"]["status"]])
        else:
            Config.TEST_STATUS_COUNT.update([tc["status"]])

    req_coverage = dict()
    for entry in Config.REQ_STATUS_COUNT.items():
        print(entry)
        req_coverage[entry[0]] = entry[1]
    ve_coverage = dict()
    total_ve = 0
    for entry in Config.VE_STATUS_COUNT.items():
        ve_coverage[entry[0]] = entry[1]
        total_ve = total_ve + entry[1]
    tc_status = dict()
    tc_status["NotExecuted"] = 0
    for entry in Config.TEST_STATUS_COUNT.items():
        if entry[0] in (
            "Draft",
            "Approved",
            "Defined",
            "notexec",
            "Deprecated",
        ):
            tc_status["NotExecuted"] = tc_status["NotExecuted"] + entry[1]
        tc_status[entry[0]] = entry[1]
    rec_count_per_doc: dict = dict()
    for entry in Config.REQ_STATUS_PER_DOC_COUNT.items():
        split0 = entry[0].split(".")
        doc = split0[0]
        if doc not in rec_count_per_doc.keys():
            rec_count_per_doc[doc] = dict()
        if len(split0) == 1:
            rec_count_per_doc[doc]["count"] = entry[1]
        else:
            priority = split0[1]
            if priority not in rec_count_per_doc[doc].keys():
                rec_count_per_doc[doc][priority] = dict()
            if len(split0) == 2:
                rec_count_per_doc[doc][priority]["count"] = entry[1]
            else:
                rec_count_per_doc[doc][priority][split0[2]] = entry[1]
    # sorting the priority dictionary
    for doc in rec_count_per_doc.keys():
        tmp_doc = dict()
        for key in sorted(rec_count_per_doc[doc].keys()):
            tmp_doc[key] = rec_count_per_doc[doc][key]
        rec_count_per_doc[doc] = tmp_doc

    size = [len(reqs), total_ve, len(tcases)]

    print(rec_count_per_doc)

    return [
        tc_status,
        ve_coverage,
        req_coverage,
        rec_count_per_doc,
        [],
        [],
        size,
    ]
