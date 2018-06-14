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
from tempfile import TemporaryFile

import click
import pandoc
import requests
from bs4 import BeautifulSoup
from jinja2 import Environment, PackageLoader

from .config import Config
from .formatters import *

# Hack because pandoc doesn't have gfm yet
pandoc.Document.OUTPUT_FORMATS = tuple(list(pandoc.Document.OUTPUT_FORMATS) + ['gfm'])

CACHED_TESTCASES = {}
CACHED_USERS = {}


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

    jinja_formatters = dict(format_tests_preamble=format_tests_preamble,
                            format_dm_requirements=format_dm_requirements,
                            format_dm_testscript=format_dm_testscript,
                            as_jira_test_anchor=as_jira_test_anchor)

    # Build model
    testcases = build_dm_model(folder)
    env = Environment(loader=PackageLoader('docsteady', 'templates'),
                      autoescape=None)
    env.globals.update(**jinja_formatters)

    template = env.get_template("dm-testcases.j2")
    text = template.render(testcases=testcases)
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
        # build simple summary
        testcase['summary'] = build_summary(testcase)

        testcase.setdefault("requirements", [])
        # Build list of requirements
        if "issueLinks" in testcase:
            for issue in testcase["issueLinks"]:
                resp = requests.get(Config.ISSUE_URL.format(issue=issue), auth=Config.AUTH).json()
                summary = resp["fields"]["summary"]
                jira_url = Config.ISSUE_UI_URL.format(issue=issue)
                anchor = f'<a href="{jira_url}">{issue}</a>'
                testcase["requirements"].append(dict(key=issue, summary=summary, anchor=anchor))

        # Extract bolded items from objective
        if "objective" in testcase:
            more_info = extract_strong(testcase["objective"])
            testcase.update(more_info)

        # order and dereference steps (non-recursive)
        if 'steps' in testcase.get("testScript"):
            steps = testcase['testScript']['steps']
            dereferenced_steps = []
            sorted_steps = sorted(steps, key=lambda i: i['index'])
            for step in sorted_steps:
                if 'testCaseKey' in step:
                    step_key = step['testCaseKey']
                    step_testcase = CACHED_TESTCASES.get(step_key)
                    if not step_testcase:
                        step_testcase = requests.get(Config.TESTCASE_URL.format(testcase=step_key),
                                                     auth=Config.AUTH).json()
                        more_sorted_steps = sorted(step_testcase['testScript']['steps'],
                                                   key=lambda i: i['index'])
                        step_testcase['steps'] = more_sorted_steps
                        CACHED_TESTCASES[step_key] = step_testcase
                    dereferenced_steps.extend(step_testcase['testScript']['steps'])
                else:
                    dereferenced_steps.append(step)
            testcase['testScript']['steps'] = dereferenced_steps
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
            # translate requirements to "deprecated requirements"
            if "requirements" in element_name:
                element_name = "deprecated_requirements"
            element_neighbor_text = ""
            continue
        element_neighbor_text += str(elem) + "\n"
    headers[element_name] = element_neighbor_text
    return headers


def build_summary(testcase):
    if testcase['owner'] not in CACHED_USERS:
        resp = requests.get(Config.USER_URL.format(username=testcase["owner"]), auth=Config.AUTH)
        user = resp.json()
        CACHED_USERS[testcase["owner"]] = user
    user = CACHED_USERS[testcase["owner"]]
    testcase_summary = OrderedDict(
        version=testcase['majorVersion'],
        status=testcase['status'],
        priority=testcase['priority'],
        verification_type=testcase["customFields"]["Verification Type"],
        critical_event=testcase["customFields"]["Critical Event?"],
        owner=user["displayName"])
    return testcase_summary


if __name__ == '__main__':
    cli()
