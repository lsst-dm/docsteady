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

from marshmallow import EXCLUDE
from requests import Session
from urllib3 import Retry

from .config import Config
from .cycle import TestCycle
from .spec import TestCase
from .utils import (
    create_folders_and_files,
    fix_json,
    get_rest_session,
    get_testcase_executions,
    get_value,
    get_via_zephyr,
    get_zephyr_api,
)
from .vcd import VerificationE

# for dubuging we do not need the hundreads of verificaiton elements
FEWCOUNT = 3


def get_testcase(tckey: str) -> dict | None:
    """
    Get test case details from Jira
    :param rs:
    :param tckey:
    :return:
    """

    zapi = get_zephyr_api()
    jtc_det = fix_json(zapi.test_cases.get_test_case(tckey))
    tc_details = TestCase(unknown=EXCLUDE).load(jtc_det)

    # apparently need to get he last execution also ..
    # Zpehyr no longer returns it
    execs = get_testcase_executions(tckey)
    if len(execs) >= 1:
        jtc_res = execs[0]
        tc_results: dict = dict()
        tc_results["key"] = jtc_res["key"]
        tc_results["status"] = "notexec"
        status = get_value(jtc_res["testExecutionStatus"])
        if status == "Pass":
            tc_results["status"] = "passed"
        elif status == "Fail":
            tc_results["status"] = "failed"
        elif status == "Blocked":
            tc_results["status"] = "blocked"
        elif status == "Pass w/ Deviation":
            tc_results["status"] = "cndpass"
        if "executionDate" in jtc_res.keys():
            tc_results["exdate"] = jtc_res["executionDate"][0:10]
        elif "actualEndDate" in jtc_res.keys():
            tc_results["exdate"] = jtc_res["actualEndDate"][0:10]
        test_cycle = None
        if "testCycle" in jtc_res and type(jtc_res["testCycle"]) is dict:
            test_cyclej = get_via_zephyr(jtc_res["testCycle"]["self"])
            test_cycle = TestCycle(unknown=EXCLUDE).load(fix_json(test_cyclej))
            # now to get the plan should be in the test case but the cycle
            tc_results["tcycle"] = test_cycle["key"]
        if test_cycle and len(test_cycle["test_plans"]) > 0:
            zapi = get_zephyr_api()
            jtp_dets = zapi.test_plans.get_test_plan(
                test_cycle["test_plans"][0]
            )
            if (
                "customFields" in jtp_dets
                and "Document ID" in jtp_dets["customFields"].keys()
            ):
                tc_results["TPR"] = jtp_dets["customFields"]["Document ID"]
            else:
                tc_results["TPR"] = ""
        else:
            tc_results["TPR"] = ""
        Config.CACHED_TESTRES_SUM[tckey] = tc_results
        tc_details["lastR"] = tc_results

    return tc_details


def get_testcases_ve(key: str) -> list[str]:
    "VE key form LVV-NNN"
    zapi = get_zephyr_api()
    resp = zapi.issue_links.get_test_cases(key)
    tcs = []
    for v in resp:
        tcs.append(v["key"])

    return tcs


def process_test_cases(tcs: list[str], ve_details: dict) -> dict:
    # populate test_cases from raw_test_cases
    if tcs and len(tcs) > 0:
        ve_details["test_cases"] = []
        for tc in tcs:
            if tc not in Config.CACHED_TESTCASES:
                Config.CACHED_TESTCASES[tc] = get_testcase(tc)

            ve_details["test_cases"].append(Config.CACHED_TESTCASES[tc])
    return ve_details


def get_ve_details(rs: Session, key: str) -> dict:
    """
    Get Verification Element details from Jira
    :param rs:
    :param key:
    :return:
    """
    # print(f"get_ve_details {key}", end=".", flush=True)
    ve_res = rs.get(Config.ISSUE_URL.format(issue=key))
    jve_res = fix_json(ve_res.json())
    return get_ve_json(jve_res)


def get_ve_json(jve_res: dict) -> dict:
    ve_details = VerificationE(unknown=EXCLUDE).load(jve_res, partial=True)
    ve_details["summary"] = ve_details["summary"].strip()
    # @post_load is not working
    # populate test_cases from raw_test_cases
    rs = get_rest_session()
    tcs = get_testcases_ve(ve_details["key"])
    process_test_cases(tcs, ve_details)
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


def extract_ves(cmp: str, subcmp: str, DOFEW: bool = False) -> dict:
    """
    :param cmp:
    :param subcmp:
    :return:
    """
    # ve_list = []
    ve_details = dict()

    max = 500
    startAt = 0
    # if T&S component is given, the JQL query needs to be adjusted
    cmp = cmp.replace("&", "%26")
    # if subcomponents have & character, need to be encoded as above
    subcmp = subcmp.replace("&", "%26")
    count = 0
    rs: Session | Session = get_rest_session()

    # Setting retries, sometime the connections fails
    # https://stackoverflow.com/questions/15431044/can-i-set-max-retries-for-requests-request
    retries = Retry(
        total=10, backoff_factor=1, status_forcelist=[500, 502, 503, 504]
    )

    rs.adapters["max_retries"] = retries  # type: ignore

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


def do_ve_model(
    component: str, subcomponent: str, DOFEW: bool = False
) -> dict:
    """
    Extract VE model information from Jira, Zephyr
    :param component:
    :param subcomponent:
    :param DOFEW:  mainly for testing - jsut get some VEs not all
    :return:
    """
    # create folders for images and attachments if not already there
    create_folders_and_files()

    print(
        f"Looking for all Verification Elements in component '{component}', "
        f"sub-component '{subcomponent}'."
    )

    # get all VEs details
    ves = extract_ves(component, subcomponent, DOFEW)

    if DOFEW:
        print(f" Only doing (DOFEW={DOFEW}) {len(ves)} Verification Elements.")
    else:
        print(f" Found {len(ves)} Verification Elements.")
    # need to get the corresponding test cases

    return ves
