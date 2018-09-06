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
from jinja2 import Environment, PackageLoader
from .spec import build_dm_spec_model
from .run import build_results_model
from .config import Config
from .formatters import *

# Hack because pandoc doesn't have gfm yet
pandoc.Document.OUTPUT_FORMATS = tuple(list(pandoc.Document.OUTPUT_FORMATS) + ['gfm'])


@click.group()
@click.option('--mode', default='dm', help='Project mode (dm, ts, etc..)')
@click.option('--template', default='latex', help='Template language (latex, html)')
def cli(mode, template):
    Config.MODE_PREFIX = f"{mode.lower()}-"
    Config.TEMPLATE_LANGUAGE = template
    Config.DOC = pandoc.Document()


@cli.command("generate-spec")
@click.option('--format', default='latex', help='Pandoc output format (see pandoc for options)')
@click.option('--username', prompt="Jira Username", envvar="JIRA_USER")
@click.option('--password', prompt="Jira Password", hide_input=True,
              envvar="JIRA_PASSWORD", help="Output file")
@click.argument('folder')
@click.argument('file', required=False, type=click.File('w'))
def generate_spec(format, username, password, folder, file):
    """Read in tests from Adaptavist Test management where FOLDER
    is the ATM Test Case Folder. If specified, FILE is the resulting
    output.
    """
    global OUTPUT_FORMAT
    OUTPUT_FORMAT = format
    Config.AUTH = (username, password)

    Config.output = TemporaryFile(mode="r+")

    jinja_formatters = dict(format_tests_preamble=format_tests_preamble,
                            format_dm_requirements=format_dm_requirements,
                            format_dm_testscript=format_dm_testscript,
                            as_jira_test_anchor=as_jira_test_anchor)

    # Build model
    try:
        testcases = build_dm_spec_model(folder)
    except Exception as e:
        print("Error in building model")
        print(e)
        raise e

    # Sort the dictionary
    requirements_to_testcases = OrderedDict(sorted(Config.REQUIREMENTS_TO_TESTCASES.items(),
                                                   key=lambda item: alphanum_key(item[0])))

    testcases_href = {testcase["key"]: testcase["doc_href"] for testcase in testcases}

    env = Environment(loader=PackageLoader('docsteady', 'templates'),
                      lstrip_blocks=True, trim_blocks=True,
                      autoescape=None)
    env.globals.update(**jinja_formatters)

    template = env.get_template(f"{Config.MODE_PREFIX}testcases.{Config.TEMPLATE_LANGUAGE}.jinja2")

    text = template.render(testcases=testcases,
                           requirements_to_testcases=requirements_to_testcases,
                           testcases_doc_url_map=testcases_href,
                           requirements_map=Config.CACHED_REQUIREMENTS,
                           testcases_map=Config.CACHED_TESTCASES)

    if Config.TEMPLATE_LANGUAGE != OUTPUT_FORMAT:
        setattr(Config.DOC, Config.TEMPLATE_LANGUAGE, text.encode("utf-8"))
        text = getattr(Config.DOC, OUTPUT_FORMAT).decode("utf-8")
    print(text, file=file or sys.stdout)


@cli.command("generate-cycle")
@click.option('--format', default='latex', help='Pandoc output format (see pandoc for options)')
@click.option('--username', prompt="Jira Username", envvar="JIRA_USER")
@click.option('--password', prompt="Jira Password", hide_input=True,
              envvar="JIRA_PASSWORD", help="Output file")
@click.argument('cycle')
@click.argument('file', required=False, type=click.File('w'))
def generate_report(format, username, password, cycle, file):
    global OUTPUT_FORMAT
    OUTPUT_FORMAT = format
    Config.AUTH = (username, password)

    Config.output = TemporaryFile(mode="r+")
    test_cycle, test_results = build_results_model(cycle)
    sorted(test_results, key=lambda item: alphanum_key(item['test_case_key']))

    env = Environment(loader=PackageLoader('docsteady', 'templates'),
                      autoescape=None)

    template = env.get_template(f"{Config.MODE_PREFIX}testcycle.{Config.TEMPLATE_LANGUAGE}.jinja2")
    text = template.render(testcycle=test_cycle,
                           testresults=test_results,
                           testcase_index=Config.CACHED_TESTCASES)

    if Config.TEMPLATE_LANGUAGE != OUTPUT_FORMAT:
        setattr(Config.DOC, Config.TEMPLATE_LANGUAGE, text.encode("utf-8"))
        text = getattr(Config.DOC, OUTPUT_FORMAT).decode("utf-8")
    print(text, file=file or sys.stdout)


if __name__ == '__main__':
    cli()
