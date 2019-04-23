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

import os
import re


class Config:
    JIRA_INSTANCE = "https://jira.lsstcorp.org"
    JIRA_API = f"{JIRA_INSTANCE}/rest/api/latest"
    ATM_API = f"{JIRA_INSTANCE}/rest/atm/1.0"
    ISSUE_URL = f"{JIRA_API}/issue/{{issue}}"
    ISSUE_UI_URL = f"{JIRA_INSTANCE}/browse/{{issue}}"
    USER_URL = f"{JIRA_API}/user?username={{username}}"
    TESTCASE_URL = f"{ATM_API}/testcase/{{testcase}}"
    TESTCASE_UI_URL = f"{JIRA_INSTANCE}/secure/Tests.jspa#/testCase/{{testcase}}"
    TESTCASE_SEARCH_URL = f"{ATM_API}/testcase/search"
    TESTCYCLE_URL = f"{ATM_API}/testrun/{{testrun}}"
    TESTPLAN_URL = f"{ATM_API}/testplan/{{testplan}}"
    TESTRESULTS_URL = f"{ATM_API}/testrun/{{testrun}}/testresults"
    # FIXME: Using undocumented API
    FOLDERTREE_API = f"{JIRA_INSTANCE}/rest/tests/1.0/project/12800/foldertree/testcase"
    PANDOC_TYPE = None
    AUTH = None
    REQID_FIELD = "customfield_12001"
    DOC = None
    OUTPUT_FORMAT = None
    CACHED_TESTCASES = {}
    CACHED_USERS = {}
    CACHED_REQUIREMENTS = {}  # type : Dict[str, Issue]
    CACHED_ISSUES = {}  # type : Dict[str, Issue]
    CACHED_VES = {} 
    MODE_PREFIX = None
    TIMEZONE = "US/Pacific"
    REQUIREMENTS_TO_TESTCASES = {}
    ISSUES_TO_TESTRESULTS = {}
    TEMPLATE_LANGUAGE = "latex"
    TEMPLATE_DIRECTORY = os.curdir

    # Regexes for LSST things
    DOC_NAMES = ['LDM', 'LSE', 'DMTN', 'DMTR', 'TSS', 'LPM']
    doc_pattern_text = r"\b(" + "|".join(DOC_NAMES) + r")(-\d+)\b(?!-)"
    DOCUSHARE_DOC_PATTERN = re.compile(doc_pattern_text)
    milestone_pattern_text = r"\b(" + "|".join(DOC_NAMES) + r")(-\d+-\d+)([\s\.])"
    MILESTONE_PATTERN = re.compile(milestone_pattern_text)
