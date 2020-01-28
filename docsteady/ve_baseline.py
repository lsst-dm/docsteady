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


def get_testcase(rs, tckey):
    """

    :param rs:
    :param key:
    :return:
    """
    tc_detail = dict()
    # print(Config.TESTCASE_URL.format(testcase=tckey))
    tc_res = rs.get(Config.TESTCASE_URL.format(testcase=tckey))
    jtc_res = tc_res.json()
    tc_detail, error = TestCase().load(jtc_res)
    # print(tc_detail)

    return tc_detail

def get_ve_details(rs, key):
    """

    :param rs:
    :param key:
    :return:
    """

    # print(key, end=" ", flush=True)
    print(" - ", key)
    ve_res = rs.get(Config.ISSUE_URL.format(issue=key))
    jve_res = ve_res.json()

    ve_details, errors = VerificationE().load(jve_res)
    ve_details["summary"] = ve_details["summary"].strip()
    # @post_load is not working, try to populate test_cases and upper level reqs
    if "raw_test_cases" in ve_details.keys():
        if ve_details["raw_test_cases"] != "":
            # print(" - raw - ", ve_details["raw_test_cases"])
            # regex to get content between {}
            regex = r"\{([^}]+)\}"
            matches = re.findall(regex, ve_details["raw_test_cases"])
            # print(" - matches - ", matches)
            for matchNum, match in enumerate(matches):
                if matchNum % 2 == 1:
                    tc_split = match.split(":")
                    tc_split[1] = tc_split[1].strip().replace("\n", " ")
                    ve_details["test_cases"].append(tc_split)
                    if tc_split[0] not in Config.CACHED_TESTCASES:
                        Config.CACHED_TESTCASES[tc_split[0]] = get_testcase(rs, tc_split[0])
    if "raw_upper_req" in ve_details.keys():
        if ve_details["raw_upper_req"] != "":
            # print(" - ", ve_details["raw_upper_req"])
            ureqs = ve_details["raw_upper_req"].split(',\n')
            for ur in ureqs:
                # print("   - ", ur)
                urs = ur.split('textbar')
                u_id = urs[0].lstrip('\{\[\}.- ').rstrip('\\')
                urs = ur.split(':\n')
                u_sum = urs[1].strip().strip('{]}').lstrip('0123456789.- ')
                upper = (u_id, u_sum)
                print(upper)
                ve_details["upper_reqs"].append(upper)

    return ve_details


def get_ves(rs, cmp, subcmp):
    """

    :param rs:
    :param cmp:
    :param subcmp:
    :return:
    """
    # ve_list = []
    ve_details = dict()

    max = 1000

    result = rs.get(Config.VE_SUBCMP_URL.format(cmpnt=cmp,subcmp=subcmp,maxR=max))
    jresult=result.json()
    for i in jresult["issues"]:
        # ve_list.append(i["key"])
        ve_details[i["key"]] = get_ve_details(rs, i["key"])
    print("")
    # need to hiterate if there are more issues than max

    return ve_details


def do_ve_model(component, subcomponent):
    """
    Extract VE model informatino from Jira
    :param component:
    :param subcomponent:
    :return:
    """

    ves = dict()

    print(f"Looking for all Verification Elements in component {component}, sub-component {subcomponent}.")
    usr_pwd = Config.AUTH[0] + ":" + Config.AUTH[1]
    connection_str = b64encode(usr_pwd.encode("ascii")).decode("ascii")

    headers = {
        'accept': 'application/json',
        'authorization': 'Basic %s' % connection_str,
        'Connection': 'close'
    }

    rs = requests.Session()
    rs.headers = headers

    # get all VEs details
    ves = get_ves(rs, component, subcomponent)

    print(" Found ", len(ves), " Verification Elements.")

    # need to get the corresponding test cases

    return ves
