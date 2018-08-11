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


class Config:
    ISSUE_URL = "https://jira.lsstcorp.org/rest/api/latest/issue/{issue}"
    ISSUE_UI_URL = "https://jira.lsstcorp.org/browse/{issue}"
    USER_URL = "https://jira.lsstcorp.org/rest/api/latest/user?username={username}"
    TESTCASE_URL = "https://jira.lsstcorp.org/rest/atm/1.0/testcase/{testcase}"
    TESTCASE_UI_URL = "https://jira.lsstcorp.org/secure/Tests.jspa#/testCase/{testcase}"
    TESTCASE_SEARCH_URL = "https://jira.lsstcorp.org/rest/atm/1.0/testcase/search"
    TESTRUN_URL = "https://jira.lsstcorp.org/rest/atm/1.0/testrun/{testrun}"
    TESTRESULTS_URL = "https://jira.lsstcorp.org/rest/atm/1.0/testrun/{testrun}/testresults"
    PANDOC_TYPE = None
    AUTH = None
    REQID_FIELD = "customfield_12001"
    DOC = None
    OUTPUT_FORMAT = None
    CACHED_TESTCASES = {}
    CACHED_USERS = {}
    CACHED_REQUIREMENTS = {}
    MODE_PREFIX = None
    TIMEZONE = "US/Pacific"
    REQUIREMENTS_TO_ISSUES = {}
    TEMPLATE_LANGUAGE = "latex"
