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

import requests
import re
from base64 import b64encode

from .config import Config
from .vcd import VerificationE
from .spec import TestCase
from .utils import create_folders_and_files


def get_testcase(rs, tckey):
    """

    :param rs:
    :param key:
    :return:
    """
    r_tc_details = rs.get(Config.TESTCASE_URL.format(testcase=tckey))
    try:
        jtc_det = r_tc_details.json()
    except Exception as error:
        print(error)
        return None
    tc_details, error = TestCase().load(jtc_det)

    # get test case results, so we can build the VCD using the same data
    if "lastTestResultStatus" in jtc_det:
        tc_results = dict()
        print(Config.TESTCASERESULT_URL.format(tcid=tckey))
        exit()
        r_tc_results = rs.get(Config.TESTCASERESULT_URL.format(tcid=tckey))
        try:
            jtc_res = r_tc_results.json()
            tc_results['key'] = jtc_res['key']
            tc_results['exdate'] = jtc_res['executionDate']
            r_tp_key = rs.get(Config.TESTRESULT_PLAN_CYCLE.format(result_ID=jtc_res['key']))
            try:
                jtp_key = r_tp_key.json()
                if 'testPlan' in jtp_key["testRun"].keys():
                    tc_results['tplan'] = jtp_key["testRun"]["testPlan"]["key"]
                else:
                    tc_results['tplan'] = ""
            except Exception as error:
                tc_results['tplan'] = ""
            tc_results['tcycle'] = jtp_key["testRun"]["key"]
            if tc_results['tplan'] and tc_results['tplan'] != "":
                r_tp_dets = rs.get(Config.TESTPLAN_URL.format(testplan=tc_results['tplan']))
                try:
                    jtp_dets = r_tp_dets.json()
                    if "Document ID" in jtp_dets["customFields"].keys():
                        tc_results['TPR'] = jtp_dets["customFields"]["Document ID"]
                    else:
                        tc_results['TPR'] = ""
                except Exception as error:
                    tc_results['TPR'] = ""
            else:
                tc_results['TPR'] = ""
        except Exception as error:
            tc_results['TPR'] = ""
        Config.CACHED_TESTRES_SUM[tckey] = tc_results

    return tc_details


def get_ve_details(rs, key):
    """

    :param rs:
    :param key:
    :return:
    """

    print(key.replace("LVV-", ""), end=".", flush=True)
    ve_res = rs.get(Config.ISSUE_URL.format(issue=key))
    jve_res = ve_res.json()

    ve_details, errors = VerificationE().load(jve_res)
    ve_details["summary"] = ve_details["summary"].strip()
    # @post_load is not working
    # populate test_cases from raw_test_cases
    if "raw_test_cases" in ve_details.keys():
        if ve_details["raw_test_cases"] != "":
            # regex to get content between {}
            regex = r"\{([^}]+)\}"
            matches = re.findall(regex, ve_details["raw_test_cases"])
            for matchNum, match in enumerate(matches):
                if matchNum % 2 == 1:
                    tc_split = match.split(":")
                    tc_split[1] = tc_split[1].strip().replace("\n", " ")
                    ve_details["test_cases"].append(tc_split)
                    if tc_split[0] not in Config.CACHED_TESTCASES:
                        Config.CACHED_TESTCASES[tc_split[0]] = get_testcase(rs, tc_split[0])
    # populate upper level reqs from raw_upper_reqs
    if "raw_upper_req" in ve_details.keys():
        if ve_details["raw_upper_req"] != "":
            ureqs = ve_details["raw_upper_req"].split(',\n')
            for ur in ureqs:
                urs = ur.split('textbar')
                u_id = urs[0].lstrip(r'\{\[\}.- ').rstrip('\\')
                urs = ur.split(':\n')
                u_sum = urs[1].strip().strip('{]}').lstrip('0123456789.- ')
                upper = (u_id, u_sum)
                ve_details["upper_reqs"].append(upper)

    # cache reqs
    if 'req_id' in ve_details.keys():
        ve_long_name = ve_details['summary'].split(":")
        if ve_details["req_id"] not in Config.CACHED_REQS_FOR_VES:
            Config.CACHED_REQS_FOR_VES[ve_details["req_id"]] = []
        Config.CACHED_REQS_FOR_VES[ve_details["req_id"]].append(ve_long_name[0])

    # get component/subcomponent of verified_by
    if "verified_by" in ve_details.keys():
        for vby in ve_details['verified_by'].keys():
            vby_cmp_raw = rs.get(Config.GET_ISSUE_COMPONENT.format(issue=vby))
            jvby_cmp_raw = vby_cmp_raw.json()
            ve_details['verified_by'][vby]['component'] = jvby_cmp_raw['fields']['components'][0]['name']
            if 'customfield_15001' in jvby_cmp_raw['fields'].keys():
                if jvby_cmp_raw['fields']['customfield_15001']:
                    ve_details['verified_by'][vby]['subcomponent'] = jvby_cmp_raw['fields']['customfield_15001']['value']

    return ve_details


def extract_ves(rs, cmp, subcmp):
    """

    :param rs:
    :param cmp:
    :param subcmp:
    :return:
    """
    # ve_list = []
    ve_details = dict()

    max = 1000
    startAt = 0
    # if T&S component is given, the JQL query needs to be adjusted
    cmp = cmp.replace("&", "%26")
    # if subcomponents have & character, need to be encoded as above
    subcmp = subcmp.replace("&", "%26")

    while True:
        if subcmp == "":
            # get all VEs for a given Component
            result = rs.get(Config.VE_COMPONENT_URL.format(cmpnt=cmp, maxR=max, startAt=startAt))
        elif subcmp == "None":
            # get all VEs without SubComponet assigned, for a given Component
            result = rs.get(Config.VE_NULLSUBCMP_URL.format(cmpnt=cmp, maxR=max, startAt=startAt))
        else:
            # get all VES for given Component/SubComponent
            result = rs.get(Config.VE_SUBCMP_URL.format(cmpnt=cmp, subcmp=subcmp, maxR=max, startAt=startAt))
        jresult = result.json()
        if "errors" in jresult.keys():
            print(jresult["errors"])
            print(jresult["errorMessages"])
            exit()
        totals = jresult["total"]
        for i in jresult["issues"]:
            ve_details[i["key"]] = get_ve_details(rs, i["key"])
        print("")
        startAt = startAt + max
        if startAt > totals:
            break
        else:
            print(f"[Found {startAt} VEs. Continuing...]")

    return ve_details


def do_ve_model(component, subcomponent):
    """
    Extract VE model informatino from Jira
    :param component:
    :param subcomponent:
    :return:
    """
    # create folders for images and attachments if not already there
    create_folders_and_files()

    print(f"Looking for all Verification Elements in component '{component}', sub-component '{subcomponent}'.")
    usr_pwd = Config.AUTH[0] + ":" + Config.AUTH[1]
    connection_str = b64encode(usr_pwd.encode("ascii")).decode("ascii")

    headers = {
        'accept': 'application/json',
        'authorization': 'Basic %s' % connection_str,
        'Connection': 'close'
    }

    rs = requests.Session()
    rs.headers = headers
    # Setting retries, sometime the connections fails
    # https://stackoverflow.com/questions/15431044/can-i-set-max-retries-for-requests-request
    rs.adapters.DEFAULT_RETRIES = 5

    # get all VEs details
    ves = extract_ves(rs, component, subcomponent)

    print(" Found ", len(ves), " Verification Elements.")

    # need to get the corresponding test cases

    return ves
