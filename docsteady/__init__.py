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
import sys
from getpass import getpass

from . import config
from .formatters import *

if "JIRA_USER" in os.environ and "JIRA_PASSWORD" in os.environ:
    username = os.environ["JIRA_USER"]
    password = os.environ["JIRA_PASSWORD"]
else:
    username = input("Jira user name: ")
    password = getpass("Password: ")

config.AUTH = (username, password)

folder = sys.argv[1] if len(sys.argv) > 1 else "/Data Management/LSP"


def print_test(test, formatters):
    for field, fmt in formatters:
        if isinstance(fmt, type) and issubclass(fmt, Formatter):
            fmt = fmt()
        if isinstance(fmt, Formatter):
            oldfmt = fmt
            fmt = lambda field, content, object=None: oldfmt.format(field, content, object)
        if field in test:
            fmt(field, test[field])
        elif field in test['customFields']:
            fmt(field, test['customFields'][field])
        else:
            print(f"Error with field: {field}", file=sys.stderr)


test_formatters = [
    ["key", lambda field, content: print_pd_md(f"# {content}")],
    ["name", lambda field, content: print_pd_md(f"# {content}")],
    ["lastTestResultStatus", lambda field, content: print_pd_md(f"## Status: {content}")],
    ["issueLinks", RequirementsFormatter],
    ["precondition", Format2],
    ["testScript", TestScriptFormatter],
    ["objective", DmObjectiveFormatter]
]

query = f'folder = "{folder}"'
resp = requests.get(config.TESTCASE_SEARCH_URL, params=dict(query=query), auth=config.AUTH)

if resp.status_code != 200:
    print("Unable to download")
    print(resp.text)
    sys.exit(1)

testcases = resp.json()
testcases.sort(key=lambda tc: tc["name"].split(":")[0])
for testcase in testcases:
    print_test(testcase, test_formatters)
