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
Subroutines required to baseline the Verification Elements
"""

import re
from base64 import b64encode
from typing import MutableMapping

import requests
from marshmallow import EXCLUDE
from requests import Session
from urllib3 import Retry

from .config import Config
from .spec import TestCase
from .utils import create_folders_and_files
from .vcd import VerificationE

# for dubuging we do not need the hundreads of verificaiton elements
DOFEW = False
FEWCOUNT = 3


def get_testcase(rs: Session, tckey: str) -> dict | None:
    """
    Get test case details from Jira
    :param rs:
    :param tckey:
    :return:
    """
    r_tc_details = rs.get(Config.TESTCASE_URL.format(testcase=tckey))
    try:
        jtc_det = r_tc_details.json()
    except Exception as exception:
        print(exception)
        return None
    tc_details = TestCase(unknown=EXCLUDE).load(jtc_det)

    # get test case results, so we can build the VCD using the same data
    if "lastTestResultStatus" in jtc_det:
        tc_results: dict = dict()
        r_tc_results = rs.get(Config.TESTCASERESULT_URL.format(tcid=tckey))
        if r_tc_results.status_code == 200:
            jtc_res = r_tc_results.json()
            tc_results["key"] = jtc_res["key"]
            if jtc_res["status"] == "Pass":
                tc_results["status"] = "passed"
            elif jtc_res["status"] == "Fail":
                tc_results["status"] = "failed"
            elif jtc_res["status"] == "Blocked":
                tc_results["status"] = "blocked"
            elif jtc_res["status"] == "Pass w/ Deviation":
                tc_results["status"] = "cndpass"
            else:
                tc_results["status"] = "notexec"
            if "executionDate" in jtc_res.keys():
                tc_results["exdate"] = jtc_res["executionDate"][0:10]
            r_tp_key = rs.get(
                Config.TESTRESULT_PLAN_CYCLE.format(result_ID=jtc_res["key"])
            )
            if r_tp_key.status_code == 200:
                jtp_key = r_tp_key.json()
                if "testPlan" in jtp_key["testRun"].keys():
                    tc_results["tplan"] = jtp_key["testRun"]["testPlan"]["key"]
                else:
                    tc_results["tplan"] = ""
            else:
                tc_results["tplan"] = ""
            tc_results["tcycle"] = jtp_key["testRun"]["key"]
            if tc_results["tplan"] and tc_results["tplan"] != "":
                r_tp_dets = rs.get(
                    Config.TESTPLAN_URL.format(testplan=tc_results["tplan"])
                )
                if r_tp_dets.status_code == 200:
                    jtp_dets = r_tp_dets.json()
                    if (
                        "customFields" in jtp_dets
                        and "Document ID" in jtp_dets["customFields"].keys()
                    ):
                        tc_results["TPR"] = jtp_dets["customFields"][
                            "Document ID"
                        ]
                    else:
                        tc_results["TPR"] = ""
                else:
                    tc_results["TPR"] = ""
            else:
                tc_results["TPR"] = ""
        else:
            Config.CACHED_TESTRES_SUM[tckey] = None
        Config.CACHED_TESTRES_SUM[tckey] = tc_results
        tc_details["lastR"] = tc_results

    return tc_details


def process_raw_test_cases(rs: Session, ve_details: dict) -> dict:
    # populate test_cases from raw_test_cases
    if (
        "raw_test_cases" in ve_details.keys()
        and ve_details["raw_test_cases"] != ""
    ):
        # regex to get content between {}
        regex = r"\{([^}]+)\}"
        matches = re.findall(regex, ve_details["raw_test_cases"])
        ve_details["test_cases"] = []
        for matchNum, match in enumerate(matches):
            if matchNum % 2 == 1:
                tc_split = match.split(":")
                tc_split[1] = tc_split[1].strip().replace("\n", " ")
                ve_details["test_cases"].append(tc_split)
                if tc_split[0] not in Config.CACHED_TESTCASES:
                    Config.CACHED_TESTCASES[tc_split[0]] = get_testcase(
                        rs, tc_split[0]
                    )
    return ve_details


def get_ve_details(rs: Session, key: str) -> dict:
    """
    Get Verification Element details from Jira
    :param rs:
    :param key:
    :return:
    """

    print(f"get_ve_details {key}", end=".", flush=True)
    ve_res = rs.get(Config.ISSUE_URL.format(issue=key))
    jve_res = ve_res.json()

    ve_details = VerificationE(unknown=EXCLUDE).load(jve_res, partial=True)
    ve_details["summary"] = ve_details["summary"].strip()
    # @post_load is not working
    # populate test_cases from raw_test_cases
    process_raw_test_cases(rs, ve_details)
    # populate upper level reqs from raw_upper_reqs
    ve_details["upper_reqs"] = []
    if "raw_upper_req" in ve_details.keys():
        if ve_details["raw_upper_req"] and ve_details["raw_upper_req"] != "":
            ureqs = ve_details["raw_upper_req"].split(",\n")
            for ur in ureqs:
                urs = ur.split("textbar")
                u_id = urs[0].lstrip(r"\{\[\}.- ").rstrip("\\")
                urs = ur.split(":\n")
                u_sum = urs[1].strip().strip("{]}").lstrip("0123456789.- ")
                upper = (u_id, u_sum)
                ve_details["upper_reqs"].append(upper)

    # cache reqs
    if "req_id" in ve_details.keys():
        if ve_details["req_id"] not in Config.CACHED_REQS_FOR_VES:
            Config.CACHED_REQS_FOR_VES[ve_details["req_id"]] = []
        Config.CACHED_REQS_FOR_VES[ve_details["req_id"]].append(
            ve_details["key"]
        )

    # get component/subcomponent of verified_by
    if "verified_by" in ve_details.keys():
        for vby in ve_details["verified_by"].keys():
            vby_cmp_raw = rs.get(Config.GET_ISSUE_COMPONENT.format(issue=vby))
            jvby_cmp_raw = vby_cmp_raw.json()
            ve_details["verified_by"][vby]["component"] = jvby_cmp_raw[
                "fields"
            ]["components"][0]["name"]
            if "customfield_15001" in jvby_cmp_raw["fields"].keys():
                if jvby_cmp_raw["fields"]["customfield_15001"]:
                    tmp = jvby_cmp_raw["fields"]["customfield_15001"]["value"]
                    ve_details["verified_by"][vby]["subcomponent"] = tmp

    return ve_details


def extract_ves(rs: Session, cmp: str, subcmp: str) -> dict:
    """

    :param rs:
    :param cmp:
    :param subcmp:
    :return:
    """
    # ve_list = []
    ve_details = dict()

    max = 200
    startAt = 0
    # if T&S component is given, the JQL query needs to be adjusted
    cmp = cmp.replace("&", "%26")
    # if subcomponents have & character, need to be encoded as above
    subcmp = subcmp.replace("&", "%26")
    count = 0

    while True:
        if subcmp == "":
            # get all VEs for a given Component
            result = rs.get(
                Config.VE_COMPONENT_URL.format(
                    cmpnt=cmp, maxR=max, startAt=startAt
                )
            )
        elif subcmp == "None":
            # get all VEs without SubComponet assigned, for a given Component
            result = rs.get(
                Config.VE_NULLSUBCMP_URL.format(
                    cmpnt=cmp, maxR=max, startAt=startAt
                )
            )
        else:
            # get all VES for given Component/SubComponent
            result = rs.get(
                Config.VE_SUBCMP_URL.format(
                    cmpnt=cmp, subcmp=subcmp, maxR=max, startAt=startAt
                )
            )
        if result.status_code in [401, 403]:  # Forbidden
            print("Wrong password ? Access denied to " + result.url)
            exit(2)
        jresult = result.json()
        if "errors" in jresult.keys():
            print(jresult["errors"])
            print(jresult["errorMessages"])
            exit(3)
        totals = jresult["total"]
        for i in jresult["issues"]:
            ve_details[i["key"]] = get_ve_details(rs, i["key"])
            count = count + 1
            if DOFEW and count >= FEWCOUNT:
                break
        print("")
        startAt = startAt + max
        if startAt > totals:
            break
        else:
            print(f"[Found {startAt} VEs. Continuing...]")
            if DOFEW and count >= FEWCOUNT:
                break

    return ve_details


def do_ve_model(component: str, subcomponent: str) -> dict:
    """
    Extract VE model informatino from Jira
    :param component:
    :param subcomponent:
    :return:
    """
    # create folders for images and attachments if not already there
    create_folders_and_files()

    print(
        f"Looking for all Verification Elements in component '{component}', "
        f"sub-component '{subcomponent}'."
    )
    usr_pwd = Config.AUTH[0] + ":" + Config.AUTH[1]
    connection_str = b64encode(usr_pwd.encode("ascii")).decode("ascii")

    headers: MutableMapping[str, str | bytes] = {
        "accept": "application/json",
        "authorization": "Basic %s" % connection_str,
        "Connection": "close",
    }

    rs = requests.Session()
    rs.headers = headers
    # Setting retries, sometime the connections fails
    # https://stackoverflow.com/questions/15431044/can-i-set-max-retries-for-requests-request
    retries = Retry(
        total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504]
    )

    rs.adapters["max_retries"] = retries

    # get all VEs details
    ves = extract_ves(rs, component, subcomponent)

    print(" Found ", len(ves), " Verification Elements.")

    # need to get the corresponding test cases

    return ves
