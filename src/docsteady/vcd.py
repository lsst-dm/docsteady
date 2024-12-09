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

import json
import os
from collections import Counter
from typing import Any, List

from marshmallow import Schema, fields, pre_load

from .config import Config
from .utils import HtmlPandocField, get_tspec

# Globals
veduplicated: dict = {}
jpr: dict = {}
jst: dict = {}


class VerificationE(Schema):
    key = fields.String(required=True)
    id = fields.String()
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
            data["req_id"] = data_fields["customfield_10395"]  # 15502
        except KeyError:
            print(f'Failed to get req_id customfield_10395 for {data["key"]}')
        data["req_spec"] = data["renderedFields"][
            "customfield_10396"
        ]  # requirement specification (13513)
        data["req_discussion"] = data["renderedFields"]["customfield_10080"]
        if data_fields[
            "customfield_10166"
        ]:  # Priority - though not sure any more
            if type(data_fields["customfield_10166"]) is str:
                data["req_priority"] = data_fields["customfield_10166"]
            else:
                data["req_priority"] = data_fields["customfield_10166"][
                    "value"
                ]
        data["req_params"] = data["renderedFields"][
            "customfield_10101"
        ]  # Refining Parameters ?
        # gone data["raw_upper_req"] = data_fields["customfield_13515"]
        # gone data["raw_test_cases"] = data_fields["customfield_15106"]
        data["verified_by"] = self.extract_verified_by(data_fields)
        ref = data_fields["customfield_10076"]["value"]
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


def summary(dictionary: list) -> list[dict | Any]:
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
        # Each VE now has a status so we may be able to simplify this
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

    print(ve_coverage)
    print(req_coverage)
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


def build_vcd_dict(
    ve_model: dict, usedump: bool = False, path: str = "./"
) -> list:
    """
    Build the VCD model.
    Use json files to store data extracted from jira so they
    can be reused in the next run
    (assuming no need to get fresh infor from jira).
    Possibly dumo is most usefull in testing
    """

    cfile = f"{path}/coverage.json"
    tcrfile = f"{path}/tcresults.json"
    vcdfile = f"{path}/vcd.json"
    docfile = f"{path}/reqperdoc.json"
    reqfile = f"{path}/reqperve.json"
    tcasefile = f"{path}/cachedtestcases.json"
    tcresfile = f"{path}/cachedtestressum.json"

    if usedump and os.path.exists(cfile):
        with open(cfile, "r") as fp:
            Config.coverage = json.load(fp)
        with open(tcrfile, "r") as fp:
            Config.tcresults = json.load(fp)
        with open(vcdfile, "r") as fp:
            vcd_dict = json.load(fp)
        with open(docfile, "r") as fp:
            Config.REQ_PER_DOC = json.load(fp)
        with open(reqfile, "r") as fp:
            Config.CACHED_REQS_FOR_VES = json.load(fp)
        with open(tcasefile, "r") as fp:
            Config.CACHED_TESTCASES = json.load(fp)
        with open(tcresfile, "r") as fp:
            Config.CACHED_TESTRES_SUM = json.load(fp)

    req_dict = dict()
    ve_dict = dict()
    for req in Config.CACHED_REQS_FOR_VES.keys():
        tmp_req = {}
        tmp_req["VEs"] = Config.CACHED_REQS_FOR_VES[req]
        tmp_req["reqDoc"] = ""
        tmp_req["priority"] = ""
        # tmp_req['reqTitle'] = ""  # not needed for the VCD
        # tmp_req['reqText'] = ""  # not needed for the VCD
        req_dict[req] = tmp_req
    for ve in ve_model.keys():
        ve_long_name = ve_model[ve]["summary"].split(":")
        tmp_ve = dict()
        tmp_ve["jkey"] = ve
        tmp_ve["status"] = ve_model[ve]["ve_status"]
        if "ve_priority" in ve_model[ve].keys():
            tmp_ve["priority"] = ve_model[ve]["ve_priority"]
        else:
            tmp_ve["priority"] = "Not Set"
        if tmp_ve["priority"] == "":
            tmp_ve["priority"] = "Not Set"
        tmp_ve["Requirement ID"] = ve_model[ve]["req_id"]
        tmp_ve["verified_by"] = []
        if "verified_by" in ve_model[ve].keys():
            for vby in ve_model[ve]["verified_by"]:
                tmp_ve["verified_by"].append(vby)
        tmp_ve["tcs"] = {}
        if "test_cases" in ve_model[ve].keys():
            for tc in ve_model[ve]["test_cases"]:
                tmp_tc = {
                    "status": Config.CACHED_TESTCASES[tc["key"]]["status"]
                }
                if tc["key"] in Config.CACHED_TESTRES_SUM.keys():
                    tmp_tc["lastR"] = Config.CACHED_TESTRES_SUM[tc["key"]]
                else:
                    tmp_tc["lastR"] = None
                if "folder" in Config.CACHED_TESTCASES[tc["key"]].keys():
                    tmp_tc["tspec"] = get_tspec(
                        Config.CACHED_TESTCASES[tc["key"]]["folder"]
                    )
                else:
                    tmp_tc["tspec"] = ""
                tmp_ve["tcs"][tc["key"]] = tmp_tc
        # adding missing fields in reqs
        if "ve_priority" in ve_model[ve].keys():
            req_dict[ve_model[ve]["req_id"]]["priority"] = ve_model[ve][
                "ve_priority"
            ]
        else:
            req_dict[ve_model[ve]["req_id"]]["priority"] = "Not Set"
        if req_dict[ve_model[ve]["req_id"]]["priority"] == "":
            req_dict[ve_model[ve]["req_id"]]["priority"] = "Not Set"
        if "req_doc_id" in ve_model[ve].keys():
            req_dict[ve_model[ve]["req_id"]]["reqDoc"] = ve_model[ve][
                "req_doc_id"
            ]
        ve_dict[ve_long_name[0]] = tmp_ve
    # Not sure why the ve_dict is keyed on Requirement with a version -
    # everything wants verificaiton element so remaking it (wom)
    # vee_dict will be all VEs keyed on verification element
    # ve_dict remains keyed on versioned requirement.
    vee_dict = {}
    for vreq, elem in ve_dict.items():
        lvv = elem["jkey"]
        vee_dict[lvv] = elem
    # now keyed on verification element it should work in jinga
    vcd_dict = [vee_dict, req_dict, [], Config.CACHED_TESTCASES]
    # creating the lookup Specs to Reqs
    for req, values in req_dict.items():
        if values["reqDoc"] not in Config.REQ_PER_DOC.keys():
            Config.REQ_PER_DOC[values["reqDoc"]] = []
            Config.REQ_PER_DOC[values["reqDoc"]].append(req)

    with open(cfile, "w") as fp:
        json.dump(Config.coverage, fp)
    with open(tcrfile, "w") as fp:
        json.dump(Config.tcresults, fp)
    with open(vcdfile, "w") as fp:
        json.dump(vcd_dict, fp)
    with open(docfile, "w") as fp:
        json.dump(Config.REQ_PER_DOC, fp)
    with open(reqfile, "w") as fp:
        json.dump(Config.CACHED_REQS_FOR_VES, fp)
    with open(tcasefile, "w") as fp:
        json.dump(Config.CACHED_TESTCASES, fp)
    with open(tcresfile, "w") as fp:
        json.dump(Config.CACHED_TESTRES_SUM, fp)
    with open("ve_model.json", "w") as fp:
        json.dump(ve_model, fp)

    return vcd_dict
