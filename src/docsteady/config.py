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

from __future__ import annotations

import os
import re
from collections import Counter
from typing import TYPE_CHECKING, Any

from requests import Session
from zephyr import ZephyrScale

if TYPE_CHECKING:
    from .spec import Issue


class Config:
    """Configuration for docsteady."""

    # Not convinced I need DOC but its is used in the code
    # so I will add it here to pass type checks
    DOC: Any = None
    PROJECT: str = "LVV"
    INCLUDE_ALL_EXECS: bool = False
    THE_SESSION: Session | None = None
    THE_ZEPHYR: ZephyrScale = None
    ZEPHYR_TOKEN = "set in env or with --token"
    JIRA_INSTANCE = "https://rubinobs.atlassian.net"
    JIRA_API = f"{JIRA_INSTANCE}/rest/api/3/"
    ATM_API = f"https://api.zephyrscale.smartbear.com/v2/"
    ISSUE_URL = f"{JIRA_API}/issue/{{issue}}?&expand=renderedFields"
    ISSUE_UI_URL = f"{JIRA_INSTANCE}/browse/{{issue}}"
    USER_URL = f"{JIRA_API}/people/{{accountId}}"
    TESTCASE_UI_URL = f"{JIRA_INSTANCE}/projects/LVV?selectedItem=com.atlassian.plugins.atlassian-connect-plugin:com.kanoah.test-manager__main-project-page#!/v2/testCase/{{testcase}}"
    TESTCASE_SEARCH_URL = f"{ATM_API}/testcase/search"
    # providing an ordered list of statuses we can control for user args
    # the order they are rendered in the Test Spec
    TESTCASE_STATUS_LIST = ["Defined", "Approved", "Draft"]

    # chech thees later
    GET_ISSUE_COMPONENT = (
        f"{JIRA_API}/issue/{{issue}}?fields=components,customfield_15001"
    )

    VE_SEARCH_URL = (
        f"{JIRA_API}/search?jql=project%20%3D%20LVV%20AND%20component"
        f"%20%20%3D%20%27{{cmpnt}}"
        f"%27%20and%20issuetype%20%3D%20Verification&fields=key,summary,"
        f"customfield_13511,"
        f"customfield_13513,customfield_12002,"
        f"customfield_12206,customfield_13703&"
        f"maxResults={{maxR}}"
    )
    VE_COMPONENT_URL = (
        f"{JIRA_API}/search?jql=project%20%3D%20LVV%20and%20component%20%3D%"
        f"20%22{{cmpnt}}"
        f"%22%20%20and%20issuetype%20%3D%20Verification%20ORDER%20BY"
        f"%20key%20ASC&fields=key"
        f"&maxResults={{maxR}}&startAt={{startAt}}"
    )
    VE_SUBCMP_URL = (
        f"{JIRA_API}/search?jql=project%20%3D%20LVV%20and%20component"
        f"%20%3D%20%22{{cmpnt}}"
        f"%22%20%20and%20Sub-Component%20%20%3D%20%27{{subcmp}}%27%20and"
        f"%20issuetype%20%3D%2"
        f"0Verification%20ORDER%20BY%20key%20ASC&fields=key&maxResults="
        f"{{maxR}}"
        f"&startAt={{startAt}}"
    )
    VE_NULLSUBCMP_URL = (
        f"{JIRA_API}/search?jql=project%20%3D%20LVV%20and%20component%"
        f"20%3D%20%22{{cmpnt}}"
        f"%22%20%20AND%20Sub-Component%20is%20null%20and%20issuetype%20%3D%2"
        f"0Verification%20ORDER%20BY%20key%20ASC&fields=key&maxResults="
        f"{{maxR}}"
        f"&startAt={{startAt}}"
    )
    PANDOC_TYPE: None = None
    AUTH: Any = None  # for Jira - cna not access all via zephyr
    REQID_FIELD = "customfield_12001"
    HIGH_LEVEL_REQS_FIELD = "customfield_13515"
    OUTPUT_FORMAT: Any = None
    CACHED_TESTCASES: dict = {}
    CACHED_LIBTESTCASES: dict = {}
    CACHED_USERS: dict[str, dict] = {}
    CACHED_TESTRES_SUM: dict = {}
    CACHED_VELEMENTS: dict[str, Issue] = {}  # type : Dict[str, Issue]
    CACHED_REQS_FOR_VES: dict = {}
    CACHED_ISSUES: dict[str, Issue] = {}  # type : Dict[str, Issue]
    CACHED_POINTERS: dict = {}  # URL and value
    CACHED_TEST_EXECUTIONS: dict = (
        {}
    )  # all the execution probalby since i cna not get one from a cycle ..
    MODE_PREFIX: Any = None
    NAMESPACE: Any = None
    TIMEZONE = "US/Pacific"
    REQUIREMENTS_TO_TESTCASES: dict = {}
    ISSUES_TO_TESTRESULTS: dict = {}
    TEMPLATE_LANGUAGE: str = "latex"
    TEMPLATE_DIRECTORY: str = os.curdir

    # Regexes for LSST things
    DOC_NAMES = ["LDM", "LSE", "DMTN", "DMTR", "TSS", "LPM", "LTS"]
    doc_pattern_text = r"\b(" + "|".join(DOC_NAMES) + r")(-\d+)\b(?!-)"
    DOCUSHARE_DOC_PATTERN = re.compile(doc_pattern_text)
    milestone_pattern_text = (
        r"\b(" + "|".join(DOC_NAMES) + r")(-\d+-\d+)([\s\.])"
    )
    MILESTONE_PATTERN = re.compile(milestone_pattern_text)
    DOWNLOAD_IMAGES = True
    MAX_IMG_PIXELS = 450
    MIN_IMG_PIXELS = 32
    IMAGE_FOLDER = "jira_imgs/"
    ATTACHMENT_FOLDER = "attachments/"

    REQ_STATUS_COUNT: Counter = Counter()
    REQ_STATUS_PER_DOC_COUNT: Counter = Counter()
    VE_STATUS_COUNT: Counter = Counter()
    TEST_STATUS_COUNT: Counter = Counter()
    REQ_PER_DOC: dict = dict()

    exeuction_errored = False

    coverage = [  # Coverage for requirements and verification elements
        {
            "id": 0,
            "key": "FullyVerified",
            "name": "Fully Verified",
            "label": "sec:fullyverified",
        },
        {
            "id": 1,
            "key": "PartiallyVerified",
            "name": "Partially Verified",
            "label": "sec:partiallyverified",
        },
        {
            "id": 2,
            "key": "WithFailures",
            "name": "With Failures",
            "label": "sec:withfaulres",
        },
        {
            "id": 3,
            "key": "NotVerified",
            "name": "Not Verified",
            "label": "sec:notverified",
        },
        {
            "id": 4,
            "key": "NotCovered",
            "name": "Not Covered",
            "label": "sec:notcovered",
        },
    ]

    tcresults = [  # Results for Test cases
        {"id": 0, "key": "passed", "name": "Passed", "label": "sec:pass"},
        {
            "id": 1,
            "key": "cndpass",
            "name": "P. w/Dev.",
            "label": "sec:condpass",
        },
        {"id": 2, "key": "failed", "name": "Failed", "label": "sec:fail"},
        {
            "id": 3,
            "key": "NotExecuted",
            "name": "Not Ex.",
            "label": "sec:notexec",
        },
    ]

    COMPONENTS = {  # Rubin Observatory SubSystems
        "DM": "Data Management Subsystem",
        "CAM": "Camera Subsystem",
        "OCS": "Observatory Control System Subsystem",
        "EPO": "Education and Public Outreach Subsystem",
        "T&S": "Telescope and Site Subsystem",
        "PSE": "Project System Engineering and Commissioning",
    }

    # Jira Status and Priority, this was extracted from the DB, but when using
    # rest API, it must be hardcoded.
    # This needs to be kept up-to-date when changes
    # are made in Jira (hopefully none for the test)
    jst = {
        "1": "Unplanned",
        "10000": "Deferred",
        "10001": "To Do",
        "10002": "Done",
        "10004": "In Review",
        "10006": "Acknowledged",
        "10101": "Reviewed",
        "10301": "Code Review",
        "10401": "Planning",
        "10403": "Blocked",
        "10404": "Awaiting Signoff",
        "10405": "Won't Fix",
        "10505": "Can't Reproduce",
        "10605": "Withdrawn",
        "10606": "Flagged",
        "10705": "Retired",
        "10805": "Proposed",
        "10806": "Adopted",
        "10906": "Duplicate",
        "11005": "Invalid",
        "11105": "Implemented",
        "11205": "Backlog",
        "11206": "Selected for Development",
        "11207": "With PubBoard",
        "11208": "With Reviewer",
        "11209": "With Project",
        "11210": "Closeout Review",
        "11211": "Denied",
        "11212": "Journal Submitted",
        "11213": "Journal In Review",
        "11214": "Journal In Press",
        "11215": "With Author",
        "11305": "Active",
        "11306": "In Analysis",
        "11307": "Passed",
        "11405": "Board Recommended",
        "11505": "Manager Approved",
        "11506": "Discuss",
        "11507": "PM Approval",
        "11508": "Returned",
        "11605": "Review",
        "11606": "Cancelled",
        "11705": "Covered",
        "11706": "In Verification",
        "11707": "Verified",
        "11708": "Monitoring",
        "11709": "Failed",
        "11710": "Verified w/ Deviation",
        "11711": "Accepted",
        "11712": "Not Covered",
        "11713": "Descoped",
        "11714": "Out of Compliance",
        "11805": "CCB Review",
        "11806": "Impact Analysis",
        "11905": "Waiting",
        "11906": "Subordinated",
        "11907": "Active Risk/Opportunity",
        "11908": "Realized",
        "11909": "Deprecated",
        "12005": "Requested",
        "12105": "FRB Review",
        "12106": "CA Approved",
        "12107": "SE Review",
        "12205": "Planned",
        "12305": "Admin Review",
        "12405": "Open",
        "12406": "Under Review",
        "12407": "Maintenance Approved",
        "12408": "Rejected",
        "12505": "Admin Request",
        "12506": "Traveler Input Required",
        "12507": "Fulfilled",
        "12508": "Reqless Request",
        "12509": "Proposed Task",
        "12605": "Safety Review",
        "12606": "Unverified",
        "12705": "Investigation",
        "12706": "Waiting Customer",
        "12707": "Waiting External",
        "12708": "Pending Approval",
        "12709": "Pending Review",
        "12710": "Pending Documentation",
        "12711": "Escalated L2",
        "12712": "Escalated L3",
        "12805": "Parametric Configuration",
        "3": "In Progress",
        "4": "Reopened",
        "5": "Resolved",
        "6": "Closed",
    }
    jpr = {
        "1": "Blocker",
        "10000": "Undefined",
        "10100": "1",
        "10101": "1a",
        "10102": "1b",
        "10103": "2",
        "10104": "3",
        "10200": "Standard",
        "10201": "Urgent",
        "10300": "SUMMIT-1",
        "10301": "SUMMIT-2",
        "10302": "SUMMIT-3",
        "10303": "SUMMIT-4",
        "10304": "SUMMIT-5",
        "10400": "TEST-TEMP",
        "10401": "Low",
        "10402": "Medium",
        "10403": "High",
        "2": "Critical",
        "3": "Major",
        "4": "Minor",
        "5": "Trivial",
    }
