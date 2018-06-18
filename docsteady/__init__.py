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
from collections import OrderedDict
from tempfile import TemporaryFile

import click
import pandoc
import requests
from bs4 import BeautifulSoup
from jinja2 import Environment, PackageLoader

from .config import Config
from .formatters import *
from .utils import *

# Hack because pandoc doesn't have gfm yet
pandoc.Document.OUTPUT_FORMATS = tuple(list(pandoc.Document.OUTPUT_FORMATS) + ['gfm'])
doc = pandoc.Document()

CACHED_TESTCASES = {}
CACHED_USERS = {}
CACHED_REQUIREMENTS = {}

requirements_to_issues = {}
requirements_map = {}


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
    global requirements_to_issues
    Config.PANDOC_TYPE = "latex"
    Config.AUTH = (username, password)

    Config.output = TemporaryFile(mode="r+")

    jinja_formatters = dict(format_tests_preamble=format_tests_preamble,
                            format_dm_requirements=format_dm_requirements,
                            format_dm_testscript=format_dm_testscript,
                            as_jira_test_anchor=as_jira_test_anchor)

    # Build model
    try:
        testcases = build_dm_model(folder)
    except Exception as e:
        print("Error in building model")
        print(e)
        raise e

    # Sort the dictionary
    requirements_to_testcases = OrderedDict(sorted(requirements_to_issues.items(),
                                                   key=lambda item: alphanum_key(item[0])))

    testcases_href = {testcase["key"]: testcase["doc_href"] for testcase in testcases}

    env = Environment(loader=PackageLoader('docsteady', 'templates'),
                      autoescape=None)
    env.globals.update(**jinja_formatters)

    template = env.get_template("dm-testcases-tex.j2")

    text = template.render(testcases=testcases,
                           requirements_to_testcases=requirements_to_testcases,
                           testcases_doc_url_map=testcases_href,
                           requirements_map=requirements_map)

    out_text = text#.encode("utf-8")
    #doc.html = text.encode("utf-8")
    #out_text = getattr(doc, output).decode("utf-8")
    print(out_text, file=file or sys.stdout)

    # latex files output

    summary = "\\section{Test Cases Summary}\\label{test-cases-summary}\n\n" \
              "Follows the list of test cases documented in this specification.\n\n"
    summary += make_summary_table(testcases)

    reqs_text = "\\section{Requirements Traceabiity}\\label{requirements-traceability}\n\n" \
                "In following table the traceability Requirements (Verification Elements) " \
                "to Test Cases is reported.\n\n"
    reqs_text += make_reqs_table(requirements_to_testcases, requirements_map, testcases)

    summary_file = open("summary.tex", 'w')
    summary_file.write(summary)
    summary_file.close()

    trace_file = open("reqtrace.tex", 'w')
    trace_file.write(reqs_text)
    trace_file.close()


def build_dm_model(folder):
    tmp = pandoc.Document()
    query = f'folder = "{folder}"'
    resp = requests.get(Config.TESTCASE_SEARCH_URL, params=dict(query=query), auth=Config.AUTH)

    if resp.status_code != 200:
        print("Unable to download")
        print(resp.text)
        sys.exit(1)

    testcases = resp.json()
    testcases.sort(key=lambda tc: alphanum_key(tc["key"]))
    for testcase in testcases:
        # Make a doc_href attribute for the test case
        full_name = f"{testcase['key']} - {testcase['name']}"
        testcase["doc_href"] = "\label{"
        testcase["doc_href"] += as_anchor(testcase["key"])
        testcase["doc_href"] += "}"
        testcase["jira_href"] = "\href{https://jira.lsstcorp.org/secure/Tests.jspa\#/testCase/"+testcase["key"]+"}"

        # build simple summary
        testcase['summary'] = build_summary(testcase)

        # Build list of requirements
        if "issueLinks" in testcase:
            testcase.setdefault("requirements", [])
            for issue in testcase["issueLinks"]:
                resp = requests.get(Config.ISSUE_URL.format(issue=issue), auth=Config.AUTH)
                resp.raise_for_status()
                requirement = resp.json()

                CACHED_REQUIREMENTS[issue] = requirement
                requirements_to_issues.setdefault(issue, []).append(testcase['key'])
                summary = requirement["fields"]["summary"]
                jira_url = Config.ISSUE_UI_URL.format(issue=issue)
                anchor = f'<a href="{jira_url}">{issue}</a>'
                requirement["jira_url"] = jira_url
                requirement["summary"] = summary
                requirements_map[issue] = requirement
                testcase["requirements"].append(dict(key=issue, summary=summary, anchor=anchor))

        # Extract bolded items from objective and convert html to tex
        if "objective" in testcase:
            more_info = extract_strong(testcase["objective"], "test_items")
            if "test_items" in more_info:
                split_text = more_info["test_items"].splitlines()
                # omit first "test items" line
                if split_text and re.match("test item", split_text[0].lower()):
                    split_text = split_text[1:]
                testcase["test_items"] = "\n".join(split_text)
                del more_info["test_items"]
            testcase["more objectives"] = more_info
            tmp.html = testcase["objective"].encode("utf-8")
            testcase["objective"] = getattr(tmp, 'latex').decode("utf-8") 

        # Extract bolded items from precondition and convert html to tex
        if "precondition" in testcase:
            more_info = extract_strong(testcase["precondition"], "")
            testcase["more precondition"] = more_info
            tmp.html = testcase["precondition"].encode("utf-8")
            testcase["precondition"] = getattr(tmp, 'latex').decode("utf-8")

        # Extract bolded items from Required Software and convert html to tex
        if "Required Software" in testcase["customFields"]:
            more_info = extract_strong(testcase["customFields"]["Required Software"], "")
            testcase["customFields"]["more Required Software"] = more_info
            tmp.html = testcase["customFields"]["Required Software"].encode("utf-8")
            testcase["customFields"]["Required Software"] = getattr(tmp, 'latex').decode("utf-8")

        # Extract bolded items from Test Equipment and convert html to tex
        if "Test Equipment" in testcase["customFields"]:
            more_info = extract_strong(testcase["customFields"]["Test Equipment"], "")
            testcase["customFields"]["more Test Equipment"] = more_info
            tmp.html = testcase["customFields"]["Test Equipment"].encode("utf-8")
            testcase["customFields"]["Test Equipment"] = getattr(tmp, 'latex').decode("utf-8")

        # Extract bolded items from Postcondition and convert html to tex
        if "Postcondition" in testcase["customFields"]:
            more_info = extract_strong(testcase["customFields"]["Postcondition"], "")
            testcase["customFields"]["more Postcondition"] = more_info
            tmp.html = testcase["customFields"]["Postcondition"].encode("utf-8")
            testcase["customFields"]["Postcondition"] = getattr(tmp, 'latex').decode("utf-8")

        # Extract bolded items from Predecessors and convert html to tex
        if "Predecessors" in testcase["customFields"]:
            more_info = extract_strong(testcase["customFields"]["Predecessors"], "")
            testcase["customFields"]["more Predecessors"] = more_info
            tmp.html = testcase["customFields"]["Predecessors"].encode("utf-8")
            testcase["customFields"]["Predecessors"] = getattr(tmp, 'latex').decode("utf-8")

        # order and dereference steps (non-recursive)
        if 'steps' in testcase.get("testScript"):
            steps = testcase['testScript']['steps']
            dereferenced_steps = []
            sorted_steps = process_steps(steps)
            for step in sorted_steps:
                if 'testCaseKey' in step:
                    step_key = step['testCaseKey']
                    step_testcase = CACHED_TESTCASES.get(step_key)
                    if not step_testcase:
                        resp = requests.get(Config.TESTCASE_URL.format(testcase=step_key),
                                            auth=Config.AUTH)
                        step_testcase = resp.json()
                        more_sorted_steps = process_steps(step_testcase['testScript']['steps'])
                        deref_substeps = []
                        for refstep in more_sorted_steps:
                            tmp.html = refstep['description'].encode("utf-8")
                            refstep['description'] = getattr(tmp, 'latex').decode("utf-8")
                            deref_substeps.append(refstep)    
                        step_testcase['steps'] = deref_substeps
                        CACHED_TESTCASES[step_key] = step_testcase
                        refanchor = "\hyperref["+as_anchor(step["testCaseKey"])+"]{"+step["testCaseKey"]+"}"
                        #dereferenced_steps.extend(step_testcase['testScript']['steps'])
                        subStep = {"testCaseKey": step['testCaseKey'], "subSteps": deref_substeps, "refanchor":refanchor}
                    else:
                        refanchor = "\hyperref["+as_anchor(step["testCaseKey"])+"]{"+step["testCaseKey"]+"}"
                        subStep = {"testCaseKey": step['testCaseKey'], "subSteps": deref_substeps, "refanchor":refanchor}
                    dereferenced_steps.append(subStep)
                else:
                    tmp.html = step['description'].encode("utf-8")
                    step['description'] = getattr(tmp, 'latex').decode("utf-8")
                    if 'testData' in step:
                        tmp.html = step['testData'].encode("utf-8")
                        step['testData'] = getattr(tmp, 'latex').decode("utf-8")
                    else:
                        step['testData'] = "No data."
                    if 'expectedResult' in step:
                        tmp.html = step['expectedResult'].encode("utf-8")
                        step['expectedResult'] = getattr(tmp, 'latex').decode("utf-8")
                    else:
                        step['expectedResult'] = "-"
                    dereferenced_steps.append(step)
            testcase['testScript']['steps'] = dereferenced_steps
            #print(len(testcase['testScript']['steps']))
            #for step in testcase['testScript']['steps']:
            #    if 'testCaseKey' in step:
            #        for subStep in step['subSteps']:
            #            print(step['testCaseKey'], subStep['id'], subStep['index'])
            #    else:
            #        print(step['id'], step['index'])
    return testcases


def extract_strong(content, first_text_name=None):
    tmp = pandoc.Document()
    """
    Extract "strong" elements and attach their siblings up to the
    next "strong" element.
    :param content: HTML to parse
    :return: A dict of those elements with the sibling HTML as the values
    """
    soup = BeautifulSoup(content, "html.parser")
    headers = OrderedDict()
    element_name = first_text_name
    element_neighbor_text = ""
    for elem in soup.children:
        if "strong" == elem.name:
            if element_name:
                headers[element_name] = element_neighbor_text
            element_name = elem.text.lower().replace(" ", "_")
            # translate requirements to "deprecated requirements" style
            if "requirements" in element_name:
                element_name = "requirements"
            element_neighbor_text = ""
            continue
        element_neighbor_text += str(elem) + "\n"
    tmp.html = element_neighbor_text.encode("utf-8")
    element_neighbor_text = getattr(tmp, 'latex').decode("utf-8")
    headers[element_name] = element_neighbor_text
    return headers


def build_summary(testcase):
    if testcase['owner'] not in CACHED_USERS:
        resp = requests.get(Config.USER_URL.format(username=testcase["owner"]), auth=Config.AUTH)
        resp.raise_for_status()
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


def process_steps(steps):
    sorted_steps = sorted(steps, key=lambda i: i['index'])
    for step in sorted_steps:
        description = step.get("description")
        if description:
            soup = BeautifulSoup(description, "html.parser")
            # normalizes HTML, replace breaks with newline, non-breaking spaces
            description = str(soup).replace("<br/>", "\n").replace("\xa0", " ")
            # matches `[markdown]: #`
            # if re.match("\[(.*)\].*:.*#(.*)", description.splitlines()[0]):
            doc.gfm = description.encode("utf-8")
            description = doc.html.decode("utf-8")
            step['description'] = description
    return sorted_steps


def alphanum_key(key):
    return [int(c) if c.isdigit() else c for c in re.split('([0-9]+)', key)]


if __name__ == '__main__':
    cli()
