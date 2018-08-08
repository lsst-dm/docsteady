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
Code for Test Specification Model Generation
"""
import arrow
from .config import Config
import requests


def as_arrow(datestring):
    return arrow.get(datestring).to(Config.TIMEZONE)


def owner_for_id(owner_id):
    if owner_id not in Config.CACHED_USERS:
        resp = requests.get(Config.USER_URL.format(username=owner_id),
                            auth=Config.AUTH)
        resp.raise_for_status()
        user_resp = resp.json()
        Config.CACHED_USERS[owner_id] = user_resp
    user_resp = Config.CACHED_USERS[owner_id]
    return user_resp["displayName"]


def test_case_for_key(test_case_key):
    cached_testcase_resp = Config.CACHED_TESTCASES.get(test_case_key)
    if not cached_testcase_resp:
        resp = requests.get(Config.TESTCASE_URL.format(testcase=test_case_key),
                            auth=Config.AUTH)
        step_testcase_resp = resp.json()
        Config.CACHED_TESTCASES[test_case_key] = step_testcase_resp
        cached_testcase_resp = step_testcase_resp
    return cached_testcase_resp
