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
from base64 import b64encode

from .config import Config
from .vcd import VerificationE


def get_ve_details(rs, key):
    """

    :param rs:
    :param key:
    :return:
    """

    print(Config.ISSUE_URL.format(issue=key))
    ve_res = rs.get(Config.ISSUE_URL.format(issue=key))
    jve_res = ve_res.json()

    ve_details, errors = VerificationE().load(jve_res)
    print(" - ", ve_details["raw_test_cases"])

    return ve_details


def get_ves(rs, cmp, subcmp):
    """

    :param rs:
    :param cmp:
    :param subcmp:
    :return:
    """
    ve_list = []
    ve_details = dict()

    max = 1000

    result = rs.get(Config.VE_SUBCMP_URL.format(cmpnt=cmp,subcmp=subcmp,maxR=max))
    jresult=result.json()
    for i in jresult["issues"]:
        ve_list.append(i["key"])
        ve_details[i["key"]] = get_ve_details(rs, i["key"])
    # need to hiterate if there are more issues than max

    return ve_list


def do_ve_model(component, subcomponent):
    """
    Extract VE model informatino from Jira
    :param component:
    :param subcomponent:
    :return:
    """

    ves = dict()

    print(f"Looking for all Verificatino element in component {component}, sub-component {subcomponent}.")
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

    # need to get the corresponding test cases

    return ves
