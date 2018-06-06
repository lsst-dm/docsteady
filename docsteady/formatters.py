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
import requests
from .config import PANDOC_TYPE, ISSUE_URL, AUTH, REQID_FIELD

DOC = pandoc.Document()


def print_pd(html):
    DOC.html = html.encode("utf-8")
    print(getattr(DOC, PANDOC_TYPE).decode("utf-8"))


def print_pd_md(md):
    DOC.markdown = md.encode("utf-8")
    print(getattr(DOC, PANDOC_TYPE).decode("utf-8"))


def pandoc_table_html(rows, with_header=True):
    table = "<table>"
    if with_header:
        header_row = rows[0]
        rows = rows[1:]
        table += "<tr><th>" + "</th><th>".join(header_row) + "</th></tr>"
    for row in rows:
        table += "<tr><th>" + "</td><td>".join(row) + "</td></tr>"
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
            print_pd_md(f"### Step {index}")
            print_pd_md(step["description"])
            print_pd(step["testData"])


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
        print_pd(content)


class RequirementsFormatter(Formatter):
    def format(self, field, content, object=None):
        issue_links = content
        requirements = []
        for issue in issue_links:
            issue_json = requests.get(ISSUE_URL.format(issue=issue), auth=AUTH).json()
            reqid_field = issue_json['fields'][REQID_FIELD]
            if reqid_field:
                requirements.append(reqid_field)
        print_pd_md("## Requirements:")
        print("*{requirements}*".format(requirements=", ".join(requirements)))


def print_test(test, formatters):
    for field, formatter in formatters:
        if field in test:
            formatter(field, test[field])
        elif field in test['customFields']:
            formatter(field, test['customFields'][field])
