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
from .config import Config


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


def format_dm_requirements(requirements):
    text = "<h3>Requirements</h3>"
    text += "<ul>"
    for item in requirements:
        text += f'''<li><a href="{item['jira_url']}">{item['key']}</a> - {item['summary']}</li>'''
    text += "</ul>"
    return text


def format_tests_preamble(testcases):
    rows = [["Jira ID", "Test Name"]]
    for testcase in testcases:
        full_name = f"{testcase['key']} - {testcase['name']}"
        doc_href = as_anchor(full_name)
        jira_href = as_jira_test_anchor(testcase['key'])
        jira_id_link = f'<a href="#{doc_href}">{testcase["key"]}</a>'
        testname_link = f'<a href="{jira_href}">{testcase["name"]}</a>'
        rows.append([jira_id_link, testname_link])
    return pandoc_table_html(rows, with_header=True)


def as_anchor(text):
    text = re.sub('[^0-9a-zA-Z -]+', '', text)
    text = text.replace(" ", "-")
    text = text.lower()
    return text


def as_jira_test_anchor(testcase):
    return Config.TESTCASE_UI_URL.format(testcase=testcase)


def alphanum_key(key):
    return [int(c) if c.isdigit() else c for c in re.split('([0-9]+)', key)]
