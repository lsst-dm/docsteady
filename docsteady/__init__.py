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
from collections import OrderedDict
from tempfile import TemporaryFile

import arrow
import click
import pandoc
from jinja2 import Environment, PackageLoader, TemplateNotFound, ChoiceLoader, FileSystemLoader
from pkg_resources import get_distribution, DistributionNotFound

from .config import Config
from .formatters import alphanum_key, alphanum_map_sort
from .spec import build_spec_model, build_ve_model
from .tplan import build_tpr_model

try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    # package is not installed
    pass

# Hack because pandoc doesn't have gfm yet
pandoc.Document.OUTPUT_FORMATS = tuple(list(pandoc.Document.OUTPUT_FORMATS) + ['gfm'])


@click.group()
@click.option('--namespace', default='dm', help='Project namespace (dm, ts, example, etc..). '
                                                'Defaults to "dm".')
@click.option('--template-format', default='latex', help='Template language (latex, html). '
                                                         'Defaults to "latex".')
@click.option('--load-from', default=os.path.curdir, help='Path to search for templates in. '
                                                          'Defaults to the working directory')
@click.version_option(__version__)
def cli(namespace, template_format, load_from):
    """Docsteady generates documents from Jira with the Adaptavist
    Test Management plugin.
    """
    Config.MODE_PREFIX = f"{namespace.lower()}-" if namespace else ""
    Config.TEMPLATE_LANGUAGE = template_format
    Config.DOC = pandoc.Document()
    Config.TEMPLATE_DIRECTORY = load_from


@cli.command("generate-spec")
@click.option('--format', default='latex', help='Pandoc output format (see pandoc for options)')
@click.option('--username', prompt="Jira Username", envvar="JIRA_USER", help="Jira username")
@click.option('--password', prompt="Jira Password", hide_input=True,
              envvar="JIRA_PASSWORD", help="Jira Password")
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
    target = "spec"
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

    # Get VE information
    ves = build_ve_model(requirements_to_testcases)

    env = Environment(loader=ChoiceLoader([
        FileSystemLoader(Config.TEMPLATE_DIRECTORY),
        PackageLoader('docsteady', 'templates')
        ]),
        lstrip_blocks=True, trim_blocks=True,
        autoescape=None
    )

    try:
        template_path = f"{Config.MODE_PREFIX}{target}.{Config.TEMPLATE_LANGUAGE}.jinja2"
        template = env.get_template(template_path)
    except TemplateNotFound as e:
        click.echo(f"No Template Found: {template_path}", err=True)
        sys.exit(1)

    metadata = _metadata()
    metadata["folder"] = folder
    metadata["template"] = template.filename
    text = template.render(metadata=metadata,
                           testcases=testcases,
                           requirements_to_testcases=requirements_to_testcases,
                           requirements_map=Config.CACHED_REQUIREMENTS,
                           testcases_map=Config.CACHED_TESTCASES)

    print(_as_output_format(text), file=file)

    # Will exit if it can't find a template
    appendix_template = _try_appendix_template(target, env)
    if not appendix_template:
        click.echo(f"No Appendix Template Found, skipping...", err=True)
        sys.exit(0)
    metadata["template"] = appendix_template.filename
    appendix_file = _get_appendix_output(path)
    appendix_text = appendix_template.render(
        metadata=metadata,
        testcases=testcases,
        requirements_to_testcases=requirements_to_testcases,
        requirements_map=Config.CACHED_REQUIREMENTS,
        ves=ves,
        testcases_map=Config.CACHED_TESTCASES)
    print(_as_output_format(appendix_text), file=appendix_file)


@cli.command("generate-tpr")
@click.option('--format', default='latex', help='Pandoc output format (see pandoc for options)')
@click.option('--username', prompt="Jira Username", envvar="JIRA_USER", help="Jira username")
@click.option('--password', prompt="Jira Password", hide_input=True,
              envvar="JIRA_PASSWORD", help="Jira Password")
@click.argument('plan')
@click.argument('path', required=False, type=click.Path())
def generate_report(format, username, password, plan, path):
    """Read in a Test Plan and related cycles from Adaptavist Test management.
    If specified, PATH is the resulting output.
    """
    global OUTPUT_FORMAT
    OUTPUT_FORMAT = format
    Config.AUTH = (username, password)
    target = "tpr"

    Config.output = TemporaryFile(mode="r+")

    plan_dict = build_tpr_model(plan)
    testplan = plan_dict['tplan']

    testcycles_map = plan_dict['test_cycles_map']
    testresults_map = plan_dict['test_results_map']
    testcases_map = plan_dict['test_cases_map']

    # Sort maps by keys
    testcycles_map = alphanum_map_sort(testcycles_map)
    testresults_map = alphanum_map_sort(testresults_map)
    testcases_map = alphanum_map_sort(testcases_map)

    env = Environment(loader=ChoiceLoader([
        FileSystemLoader(Config.TEMPLATE_DIRECTORY),
        PackageLoader('docsteady', 'templates')
        ]),
        lstrip_blocks=True, trim_blocks=True,
        autoescape=None
    )

    template = env.get_template(f"{Config.MODE_PREFIX}{target}.{Config.TEMPLATE_LANGUAGE}.jinja2")

    metadata = _metadata()
    metadata["tplan"] = tplan
    metadata["template"] = template.filename

    text = template.render(metadata=metadata,
                           testplan=testplan,
                           testcycles=list(testcycles_map.values()),  # For convenience (sorted)
                           testcycles_map=testcycles_map,
                           testresults=list(testresults_map.values()),  # For convenience (sorted)
                           testresults_map=testresults_map,
                           testcases_map=testcases_map)

    file = open(path, "w") if path else sys.stdout
    print(_as_output_format(text), file=file or sys.stdout)

    # Will exit if it can't find a template
    appendix_template = _try_appendix_template(target, env)
    if not appendix_template:
        click.echo(f"No Appendix Template Found, skipping...", err=True)
        sys.exit(0)

    metadata["template"] = appendix_template.filename
    appendix_file = _get_appendix_output(path)

    appendix_text = appendix_template.render(
        metadata=metadata,
        testplan=testplan,
        testcycles=list(testcycles_map.values()),  # For convenience (sorted by item key)
        testcycles_map=testcycles_map,
        testresults=list(testresults_map.values()),  # For convenience (sorted by item key)
        testresults_map=testresults_map,
        testcases_map=testcases_map)

    print(_as_output_format(appendix_text), file=appendix_file)


def _try_appendix_template(target, env):
    # Now appendix
    appendix_template_path = \
        f"{Config.MODE_PREFIX}{target}-appendix.{Config.TEMPLATE_LANGUAGE}.jinja2"

    try:
        return env.get_template(appendix_template_path)
    except TemplateNotFound as e:
        return None


def _get_appendix_output(path):
    appendix_path = None
    if path:
        parts = path.split(".")
        extension = parts[-1]
        path_parts = parts[:-1] + ["appendix", extension]
        appendix_path = ".".join(path_parts)
    return open(appendix_path, "w") if appendix_path else sys.stdout


def _as_output_format(text):
    if Config.TEMPLATE_LANGUAGE != OUTPUT_FORMAT:
        setattr(Config.DOC, Config.TEMPLATE_LANGUAGE, text.encode("utf-8"))
        text = getattr(Config.DOC, OUTPUT_FORMAT).decode("utf-8")
    return text


def _metadata():
    return dict(
        created_on=arrow.now(),
        docsteady_version=__version__,
        project="LVV"
    )


if __name__ == '__main__':
    cli()
