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
from collections import Counter

class Config:
    JIRA_INSTANCE = "https://jira.lsstcorp.org"
    JIRA_API = f"{JIRA_INSTANCE}/rest/api/latest"
    ATM_API = f"{JIRA_INSTANCE}/rest/atm/1.0"
    ATMT_API = f"{JIRA_INSTANCE}/rest/tests/1.0"
    ISSUE_URL = f"{JIRA_API}/issue/{{issue}}?&expand=renderedFields"
    ISSUE_UI_URL = f"{JIRA_INSTANCE}/browse/{{issue}}"
    USER_URL = f"{JIRA_API}/user?username={{username}}"
    TESTCASE_URL = f"{ATM_API}/testcase/{{testcase}}"
    TESTCASE_UI_URL = f"{JIRA_INSTANCE}/secure/Tests.jspa#/testCase/{{testcase}}"
    TESTCASE_SEARCH_URL = f"{ATM_API}/testcase/search"
    TESTCYCLE_URL = f"{ATM_API}/testrun/{{testrun}}"
    TESTPLAN_URL = f"{ATM_API}/testplan/{{testplan}}"
    TESTRESULTS_URL = f"{ATM_API}/testrun/{{testrun}}/testresults"
    ISSUETCASES_URL = f"{ATM_API}/issuelink/{{issuekey}}/testcases"
    TESTCASERESULT_URL = f"{ATM_API}/testcase/{{tcid}}/testresult/latest"
    TESTPLANCYCLE_URL = f"{ATMT_API}/testresult/{{trk}}?fields=testRun(key,testPlan(key))"
    TPLANCF_URL = f"{ATM_API}//testplan/{{tpk}}?fields=customFields"
    # FIXME: Using undocumented API
    FOLDERTREE_API = f"{JIRA_INSTANCE}/rest/tests/1.0/project/12800/foldertree/testcase"
    VE_SEARCH_URL = f"{JIRA_API}/search?jql=project%20%3D%20LVV%20AND%20component%20%20%3D%20%27{{cmpnt}}%27%20and%20issuetype%20%3D%20Verification&fields=key,summary,customfield_13511,customfield_13513,customfield_12002,customfield_12206,customfield_13703&maxResults={{maxR}}"
    VE_SUBCMP_URL = f"{JIRA_API}/search?jql=project%20%3D%20LVV%20and%20component%20%3D%20%22{{cmpnt}}%22%20%20and%20Sub-Component%20%20%3D%20%27{{subcmp}}%27%20and%20issuetype%20%3D%20Verification%20ORDER%20BY%20key%20ASC&fields=key&maxResults={{maxR}}"
    PANDOC_TYPE = None
    AUTH = None
    REQID_FIELD = "customfield_12001"
    HIGH_LEVEL_REQS_FIELD = "customfield_13515"
    OUTPUT_FORMAT = None
    CACHED_TESTCASES = {}
    CACHED_LIBTESTCASES = {}
    CACHED_USERS = {}
    CACHED_REQUIREMENTS = {}  # type : Dict[str, Issue]
                              # TODO: DM-23715 this should be renamed in CACHED_VERIFICATIONELEMENTS
    CACHED_REQS_FOR_VES = {}
    CACHED_ISSUES = {}  # type : Dict[str, Issue]
    MODE_PREFIX = None
    TIMEZONE = "US/Pacific"
    REQUIREMENTS_TO_TESTCASES = {}
    ISSUES_TO_TESTRESULTS = {}
    TEMPLATE_LANGUAGE = "latex"
    TEMPLATE_DIRECTORY = os.curdir

    # Regexes for LSST things
    DOC_NAMES = ['LDM', 'LSE', 'DMTN', 'DMTR', 'TSS', 'LPM', 'LTS']
    doc_pattern_text = r"\b(" + "|".join(DOC_NAMES) + r")(-\d+)\b(?!-)"
    DOCUSHARE_DOC_PATTERN = re.compile(doc_pattern_text)
    milestone_pattern_text = r"\b(" + "|".join(DOC_NAMES) + r")(-\d+-\d+)([\s\.])"
    MILESTONE_PATTERN = re.compile(milestone_pattern_text)
    DOWNLOAD_IMAGES = True
    MAX_IMG_PIXELS = 450
    MIN_IMG_PIXELS = 32

    REQ_STATUS_COUNT = Counter()
    REQ_STATUS_PER_DOC_COUNT = Counter()
    VE_STATUS_COUNT = Counter()
    TEST_STATUS_COUNT = Counter()

    new_coverage = [   # Coverage for requirements and verification elements
        {"id": 0, "key": "FullyVerified", "name": "Fully Verified", "label": "sec:fullyverified"},
        {"id": 1, "key": "PartiallyVerified", "name": "Partially Verified", "label": "sec:partiallyverified"},
        {"id": 2, "key": "WithFailures", "name": "With Failed TCs", "label": "sec:withfaulres"},
        {"id": 3, "key": "NotVerified", "name": "Not Verified", "label": "sec:notverified"},
        {"id": 4, "key": "NotCovered", "name": "Not Cov. by TCs", "label": "sec:notcovered"},
    ]

    tcresults = [  # Results for Test cases
        {"id": 0, "key": "passed", "name": "Passed", "label": "sec:pass"},
        {"id": 1, "key": "cndpass", "name": "P. w/Dev.", "label": "sec:condpass"},
        {"id": 2, "key": "failed", "name": "Failed", "label": "sec:fail"},
        {"id": 3, "key": "NotExecuted", "name": "Not Ex.", "label": "sec:notexec"},
    ]

