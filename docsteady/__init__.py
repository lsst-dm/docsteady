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
from jinja2 import Environment, PackageLoader, TemplateNotFound
from .spec import build_spec_model
from .cycle import build_results_model
from .config import Config
from .formatters import alphanum_key

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
@click.argument('path', required=False, type=click.Path())
def generate_spec(format, username, password, folder, path):
    """Read in tests from Adaptavist Test management where FOLDER
    is the ATM Test Case Folder. If specified, PATH is the resulting
    output.

    If PATH is specified, docsteady will examine the output filename
    and attempt to write an appendix to a similar file.
    For example, if the output is jira_docugen.tex, the output
    will also print out a jira_docugen.appendix.tex file if a
    template for the appendix is found. Otherwise, it will print
    to standard out.
    """
    global OUTPUT_FORMAT
    OUTPUT_FORMAT = format
    Config.AUTH = (username, password)

    Config.output = TemporaryFile(mode="r+")

    # Build model
    try:
        testcases = build_spec_model(folder)
    except Exception as e:
        print("Error in building model")
        print(e)
        raise e

    file = open(path, "w") if path else sys.stdout

    # Sort the dictionary
    requirements_to_testcases = OrderedDict(sorted(Config.REQUIREMENTS_TO_TESTCASES.items(),
                                                   key=lambda item: alphanum_key(item[0])))

    env = Environment(loader=PackageLoader('docsteady', 'templates'),
                      lstrip_blocks=True, trim_blocks=True,
                      autoescape=None)

    try:
        template_path = f"{Config.MODE_PREFIX}testcases.{Config.TEMPLATE_LANGUAGE}.jinja2"
        template = env.get_template(template_path)
    except TemplateNotFound as e:
        click.echo(f"No Template Found: {template_path}", err=True)
        sys.exit(1)

    text = template.render(testcases=testcases,
                           requirements_to_testcases=requirements_to_testcases,
                           requirements_map=Config.CACHED_REQUIREMENTS,
                           testcases_map=Config.CACHED_TESTCASES)

    if Config.TEMPLATE_LANGUAGE != OUTPUT_FORMAT:
        setattr(Config.DOC, Config.TEMPLATE_LANGUAGE, text.encode("utf-8"))
        text = getattr(Config.DOC, OUTPUT_FORMAT).decode("utf-8")
    print(text, file=file)

    # Now appendix
    appendix_path = None
    if path:
        parts = path.split(".")
        extension = parts[-1]
        path_parts = parts[:-1] + ["appendix", extension]
        appendix_path = ".".join(path_parts)

    appendix_file = open(appendix_path, "w") if appendix_path else sys.stdout

    appendix_template_path = \
        f"{Config.MODE_PREFIX}testcases-appendix.{Config.TEMPLATE_LANGUAGE}.jinja2"

    try:
        appendix_template = env.get_template(appendix_template_path)
    except TemplateNotFound as e:
        click.echo(f"No Appendix Template Found: {appendix_template_path}", err=True)
        sys.exit(0)

    appendix_text = appendix_template.render(
        testcases=testcases,
        requirements_to_testcases=requirements_to_testcases,
        requirements_map=Config.CACHED_REQUIREMENTS,
        testcases_map=Config.CACHED_TESTCASES)

    print(appendix_text, file=appendix_file)


@cli.command("generate-cycle")
@click.option('--format', default='latex', help='Pandoc output format (see pandoc for options)')
@click.option('--username', prompt="Jira Username", envvar="JIRA_USER")
@click.option('--password', prompt="Jira Password", hide_input=True,
              envvar="JIRA_PASSWORD", help="Output file")
@click.argument('cycle')
@click.argument('file', required=False, type=click.File('w'))
def generate_cycle(format, username, password, cycle, file):
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
                           testcases_map=Config.CACHED_TESTCASES)

    if Config.TEMPLATE_LANGUAGE != OUTPUT_FORMAT:
        setattr(Config.DOC, Config.TEMPLATE_LANGUAGE, text.encode("utf-8"))
        text = getattr(Config.DOC, OUTPUT_FORMAT).decode("utf-8")
    print(text, file=file or sys.stdout)


if __name__ == '__main__':
    cli()
