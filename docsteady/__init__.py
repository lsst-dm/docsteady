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

import sys

import click
from .config import Config
from .formatters import *
import pandoc
from bs4 import BeautifulSoup
from tempfile import TemporaryFile


def write_test(test, formatters):
    for field, fmt in formatters:
        if isinstance(fmt, type) and issubclass(fmt, Formatter):
            fmt = fmt()
        if isinstance(fmt, Formatter):
            oldfmt = fmt
            fmt = lambda field, target, object=None: oldfmt.format(field, target, object)
        if field in test:
            fmt(field, test[field], test)
        elif field in test['customFields']:
            fmt(field, test['customFields'][field], test)
        elif field is None:
            fmt(None, test, test)
        else:
            print(f"Error with field: {field}", file=sys.stderr)


@click.command()
@click.option('--output', default='latex', help='Pandoc output format (see pandoc for options)')
@click.option('--username', prompt="Jira Username", envvar="JIRA_USER")
@click.option('--password', prompt="Jira Password", hide_input=True,
              envvar="JIRA_PASSWORD", help="Output file")
@click.argument('folder')
@click.argument('file', required=False, type=click.File('w'))
def cli(output, username, password, folder, file):
    """Read in tests from Adaptavist Test management where FOLDER
    is the ATM Test Case Folder. If specified, FILE is the resulting
    output.
    """
    Config.PANDOC_TYPE = "html"
    Config.AUTH = (username, password)

    Config.output = TemporaryFile(mode="r+")

    jinja_formatters = {sc.__name__: sc() for sc in Formatter.__subclasses__()}

    # Build model
    testcases = build_dm_model(folder)
    test_formatters = get_dm_formatters()

    write_pd("<h1>Test Case Summary</h1>")
    print_tests_preamble(testcases)
    write_pd("<h1>Test Cases</h1>")
    for testcase in testcases:
        write_test(testcase, test_formatters)
    Config.output.seek(0)
    text = Config.output.read()
    doc = pandoc.Document()
    doc.html = text.encode("utf-8")
    out_text = getattr(doc, output).decode("utf-8")
    print(out_text, file=file or sys.stdout)


def build_dm_model(folder):
    query = f'folder = "{folder}"'
    resp = requests.get(Config.TESTCASE_SEARCH_URL, params=dict(query=query), auth=Config.AUTH)

    if resp.status_code != 200:
        print("Unable to download")
        print(resp.text)
        sys.exit(1)

    testcases = resp.json()
    testcases.sort(key=lambda tc: tc["name"].split(":")[0])
    for testcase in testcases:
        testcase.setdefault("requirements", [])
        if "issueLinks" in testcase:
            for issue in testcase["issueLinks"]:
                resp = requests.get(Config.ISSUE_URL.format(issue=issue), auth=Config.AUTH).json()
                summary = resp["fields"]["summary"]
                jira_url = Config.ISSUE_UI_URL.format(issue=issue)
                anchor = f'<a href="{jira_url}">{item["key"]}</a>'
                testcase["requirements"].append(dict(key=issue, summary=summary, anchor=anchor))
        if "objective" in testcase:
            more_info = extract_strong(testcase["objective"])
            testcase.update(more_info)
    return testcases


def extract_strong(content):
    """
    Extract "strong" elements and attach their siblings up to the
    next "strong" element.
    :param content: HTML to parse
    :return: A dict of those elements with the sibling HTML as the values
    """
    soup = BeautifulSoup(content, "html.parser")
    headers = {}
    element_name = None
    element_neighbor_text = ""
    for elem in soup.children:
        if "strong" == elem.name:
            if element_name:
                headers[element_name] = element_neighbor_text
            element_name = elem.text.lower().replace(" ", "_")
            element_neighbor_text = ""
            continue
        element_neighbor_text += str(elem) + "\n"
    headers[element_name] = element_neighbor_text
    return headers


def get_dm_formatters():
    test_formatters = [
        [None,
         lambda field, content, testcase:
             write_pd(f"## {testcase['key']} - {testcase['name']}", from_="markdown")],
        [None, StatusTableFormatter],
        ["test_items", Format3],
        ["deprecated_requirements", Format3],
        ["requirements", DmRequirementFormatter],
        ["Predecessors", Format3],
        ["Required Software", Format3],
        ["precondition", Format3],
        ["Postcondition", Format3],
        ["testScript", TestScriptFormatter],
    ]
    return test_formatters


if __name__ == '__main__':
    cli()
