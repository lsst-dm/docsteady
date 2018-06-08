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
import pandoc
import re
import requests
from collections import OrderedDict
from .config import Config

# Hack because pandoc doesn't have gfm yet
pandoc.Document.OUTPUT_FORMATS = tuple(list(pandoc.Document.OUTPUT_FORMATS) + ['gfm'])

DOC = pandoc.Document()


def format_pd(content, from_="html", to=None):
    to = to or Config.PANDOC_TYPE
    setattr(DOC, from_, content.encode("utf-8"))
    return getattr(DOC, to).decode("utf-8")


def print_pd(html):
    print(format_pd(html))


def print_pd_md(md):
    DOC.markdown = md.encode("utf-8")
    print(getattr(DOC, Config.PANDOC_TYPE).decode("utf-8"))


def pandoc_table_html(rows, with_header=True):
    table = "<table>"
    if with_header:
        header_row = [str(i).replace("_", " ").title() for i in rows[0]]
        rows = rows[1:]
        table += "<tr><th>" + "</th><th>".join(header_row) + "</th></tr>"
    for row in rows:
        table += "<tr><td>" + "</td><td>".join([str(i) for i in row]) + "</td></tr>"
    table += "</table>"
    return table


class Formatter:
    def format(self, field, content, object=None):
        pass


class TestScriptFormatter(Formatter):
    def format(self, field, content, object=None):
        test_script = content
        print_pd_md("## Test Script:")
        steps = test_script['steps']
        for index, step in enumerate(steps):
            step_idx = index + 1
            print_pd_md(f"**Step {step_idx}**")
            print_pd_md(step["description"])
            if 'testData' in step:
                print_pd(step["testData"])


class StatusTableFormatter(Formatter):
    def format(self, field, content, object=None):
        testcase = object
        rows = []
        testcase_summary = OrderedDict(
            version=testcase['majorVersion'],
            status=testcase['status'],
            priority=testcase['priority'],
            verification_type=testcase["customFields"]["Verification Type"],
            critical_event=testcase["customFields"]["Critical Event?"],
            owner=testcase['owner'])
        rows.append(testcase_summary.keys())
        rows.append(testcase_summary.values())
        print_pd(pandoc_table_html(rows, with_header=True))


class Format2(Formatter):
    def __init__(self, override=None):
        self.override = override

    def format(self, field, content, object=None):
        name = self.override or field.title()
        print_pd_md("## {name}: ".format(name=name))
        print_pd(content)


class Format3(Formatter):
    def format(self, field, content, object=None):
        name = field.title()
        print_pd_md("### {name}: ".format(name=name))
        print_pd(content)


class DmObjectiveFormatter(Formatter):
    def format(self, field, content, object=None):
        as_markdown = content.replace("<strong>Test items</strong>", "<h2>Test items</h2>")
        as_markdown = re.sub(r"<strong>.*(Requirements.*)</strong>", "<h2>\g<1></h2>", as_markdown)
        print_pd(as_markdown)


class RequirementsFormatter(Formatter):
    def format(self, field, content, object=None):
        issue_links = content
        requirements = []
        for issue in issue_links:
            issue_json = requests.get(Config.ISSUE_URL.format(issue=issue),
                                      auth=Config.AUTH).json()
            reqid_field = issue_json['fields'][Config.REQID_FIELD]
            if reqid_field:
                requirements.append(reqid_field)
        print_pd_md("## Requirements:")
        print("*{requirements}*".format(requirements=", ".join(requirements)))


def print_tests_preamble(testcases):
    rows = [["Jira ID", "Test Name"]]
    for testcase in testcases:
        rows.append([testcase["key"], testcase["name"]])
    print_pd(pandoc_table_html(rows, with_header=True))


def print_test(test, formatters):
    for field, formatter in formatters:
        if field in test:
            formatter(field, test[field])
        elif field in test['customFields']:
            formatter(field, test['customFields'][field])
