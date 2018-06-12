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
import re
from collections import OrderedDict


def pandoc_table_html(rows, with_header=True):
    table = "<table>"
    if with_header:
        header_row = [str(i).replace("_", " ").title() for i in rows[0]]
        rows = rows[1:]
        table += "<tr><th>" + "</th><th>".join(header_row) + "</th></tr>"
    for row in rows:
        formatted_row = [str(i) for i in row]
        table += "<tr><td>" + "</td><td>".join(formatted_row) + "</td></tr>"
    table += "</table>"
    return table


def format_dm_testscript(test_script):
    formatted = "<h3>Test Script</h3>"
    steps = test_script['steps']
    for index, step in enumerate(steps):
        step_idx = index + 1
        formatted += f"<h4>Step {step_idx}</h4>"
        formatted += step["description"]
        if 'testData' in step:
            formatted += step["testData"]
    return formatted


def format_status_table(testcase):
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
    return pandoc_table_html(rows, with_header=True)


def format_dm_requirements(requirements):
    text = "<h3>Requirements</h3>"
    text += "<ul>"
    for item in requirements:
        text += f"<li>{anchor} - {item['summary']}</li>"
    text += "</ul>"
    return text


def format_tests_preamble(testcases):
    rows = [["Jira ID", "Test Name"]]
    for testcase in testcases:
        full_name = f"{testcase['key']} - {testcase['name']}"
        href = as_anchor(full_name)
        anchor = f'<a href="#{href}">{testcase["key"]}</a>'
        rows.append([anchor, testcase["name"]])
    return pandoc_table_html(rows, with_header=True)


def as_anchor(text):
    text = re.sub('[^0-9a-zA-Z -]+', '', text)
    text = text.replace(" ", "-")
    text = text.lower()
    return text
