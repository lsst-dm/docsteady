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
from jinja2 import Environment, PackageLoader, TemplateNotFound, ChoiceLoader, FileSystemLoader
from pkg_resources import get_distribution, DistributionNotFound

from .config import Config
from .formatters import alphanum_key, alphanum_map_sort
from .spec import build_spec_model
from .tplan import build_tpr_model
from .vcd import vcdsql, summary
from .ve_baseline import do_ve_model

try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    # package is not installed
    pass


@click.group()
@click.option('--namespace', default='dm', help='Project namespace (dm, ts, example, etc..). '
                                                'Defaults to "dm".')
@click.option('--template-format', default='latex', help='Template language (latex, html). '
                                                         'Defaults to "latex".')
@click.option('--load-from', default=os.path.curdir, help='Path to search for templates in. '
                                                          'Defaults to the working directory')
@click.version_option(__version__)
def cli(namespace, template_format, load_from):
    """Docsteady generates documents from Jira with the
    Test Management for Jira (TM4J) plugin.
    """
    Config.MODE_PREFIX = f"{namespace.lower()}-" if namespace else ""
    Config.NAMESPACE = namespace
    Config.TEMPLATE_LANGUAGE = template_format
    Config.TEMPLATE_DIRECTORY = load_from


@cli.command("generate-spec")
@click.option('--format', default='latex', help='Pandoc output format (see pandoc for options)')
@click.option('--username', prompt="Jira Username", envvar="JIRA_USER", help="Jira username")
@click.option('--password', prompt="Jira Password", hide_input=True,
              envvar="JIRA_PASSWORD", help="Jira Password")
@click.argument('folder')
@click.argument('path', required=False, type=click.Path())
def generate_spec(format, username, password, folder, path):
    """Read in tests from TM4J plugin where FOLDER
    is the TM4J Test Case Folder. If specified, PATH is the resulting
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
        testcases, requirements, tcs_dict = build_spec_model(folder)
    except Exception as e:
        print("Error in building model")
        print(e)
        raise e

    file = open(path, "w") if path else sys.stdout

    # Sort the dictionary
    requirements_to_testcases = OrderedDict(sorted(Config.REQUIREMENTS_TO_TESTCASES.items(),
                                                   key=lambda item: alphanum_key(item[0])))

    env = Environment(loader=ChoiceLoader([
        FileSystemLoader(Config.TEMPLATE_DIRECTORY),
        PackageLoader('docsteady', 'templates')
    ]),
        lstrip_blocks=True, trim_blocks=True,
        autoescape=None
    )

    try:
        template_path = f"{target}.{Config.TEMPLATE_LANGUAGE}.jinja2"
        template = env.get_template(template_path)
    except TemplateNotFound:
        click.echo(f"No Template Found: {template_path}", err=True)
        sys.exit(1)

    libtestcases = sorted(Config.CACHED_LIBTESTCASES.values(), key=lambda testc: testc["keyid"])

    metadata = _metadata()
    metadata["folder"] = folder
    metadata["template"] = template.filename
    text = template.render(metadata=metadata,
                           deprecated=testcases['deprecated'],
                           tcs_dict=tcs_dict,
                           libtestcases=libtestcases,
                           requirements_to_testcases=requirements_to_testcases,
                           requirements_map=requirements,
                           tc_status_list=Config.TESTCASE_STATUS_LIST,
                           testcases_map=Config.CACHED_TESTCASES)

    print(_as_output_format(text), file=file)

    # Will exit if it can't find a template
    appendix_template = _try_appendix_template(target, env)
    if not appendix_template:
        click.echo("No Appendix Template Found, skipping...", err=True)
        sys.exit(0)
    metadata["template"] = appendix_template.filename
    appendix_file = _get_appendix_output(path)
    appendix_text = appendix_template.render(
        metadata=metadata,
        testcases=testcases,
        requirements_to_testcases=requirements_to_testcases,
        requirements_map=requirements,
        testcases_map=Config.CACHED_TESTCASES)
    print(_as_output_format(appendix_text), file=appendix_file)


@cli.command("generate-tpr")
@click.option('--format', default='latex', help='Pandoc output format (see pandoc for options)')
@click.option('--username', prompt="Jira Username", envvar="JIRA_USER", help="Jira username")
@click.option('--password', prompt="Jira Password", hide_input=True,
              envvar="JIRA_PASSWORD", help="Jira Password")
@click.option('--trace', default=False, help='If true, traceability table will be added in appendix')
@click.argument('plan')
@click.argument('path', required=False, type=click.Path())
def generate_report(format, username, password, trace, plan, path):
    """Read in a Test Plan and related cycles from TM4J.
    If specified, PATH is the resulting output.
    """
    global OUTPUT_FORMAT
    OUTPUT_FORMAT = format
    Config.AUTH = (username, password)
    target = "tpr"
    
    if Config.NAMESPACE.upper() not in Config.COMPONENTS.keys():
        print(f"Wrong input component {Config.NAMESPACE}")
        exit()

    Config.output = TemporaryFile(mode="r+")

    plan_dict = build_tpr_model(plan)

    # Sort maps by keys
    testcycles_map = alphanum_map_sort(plan_dict['test_cycles_map'])
    testresults_map = alphanum_map_sort(plan_dict['test_results_map'])
    testcases_map = alphanum_map_sort(plan_dict['test_cases_map'])

    env = Environment(loader=ChoiceLoader([
        FileSystemLoader(Config.TEMPLATE_DIRECTORY),
        PackageLoader('docsteady', 'templates')
    ]),
        lstrip_blocks=True, trim_blocks=True,
        autoescape=None
    )

    template = env.get_template(f"{target}.{Config.TEMPLATE_LANGUAGE}.jinja2")

    metadata = _metadata()
    metadata["template"] = template.filename
    metadata["namespace"] = Config.NAMESPACE
    metadata["component_long_name"] = Config.COMPONENTS[Config.NAMESPACE.upper()]

    text = template.render(metadata=metadata,
                           testplan=plan_dict['tplan'],
                           testcycles=list(testcycles_map.values()),  # For convenience (sorted)
                           testcycles_map=testcycles_map,
                           testresults=list(testresults_map.values()),  # For convenience (sorted)
                           testresults_map=testresults_map,
                           attachments=plan_dict['attachments'],
                           testcases_map=testcases_map)

    file = open(path, "w") if path else sys.stdout
    print(_as_output_format(text), file=file or sys.stdout)

    if trace:
        # Will exit if it can't find a template
        appendix_template = _try_appendix_template(target, env)
        if not appendix_template:
            click.echo("No Appendix Template Found, skipping...", err=True)
            sys.exit(0)
        metadata["template"] = appendix_template.filename
        appendix_file = _get_appendix_output(path)
        appendix_text = appendix_template.render(
            metadata=metadata,
            testcases_map=testcases_map)
        print(_as_output_format(appendix_text), file=appendix_file)

    if Config.exeuction_errored:
        raise SystemError("Content Problem, please check.")


def _try_appendix_template(target, env):
    # Now appendix
    appendix_template_path = \
        f"{target}-appendix.{Config.TEMPLATE_LANGUAGE}.jinja2"

    try:
        return env.get_template(appendix_template_path)
    except TemplateNotFound:
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


@cli.command("generate-vcd")
@click.option('--format', default='latex', help='Pandoc output format (see pandoc for options)')
@click.option('--jiradb', prompt="Jira DB Server", envvar="JIRA_DB", help="Jira database server")
@click.option('--vcduser', prompt="Jira Username", envvar="JIRA_VCD_USER", help="Jira username")
@click.option('--vcdpwd', prompt="Jira Password", hide_input=True,
              envvar="JIRA_VCD_PASSWORD", help="Jira Password")
@click.option('--sql', required=False, default=False,
              help="True if direct access to the database shall be used")
@click.option('--spec', required=False, default=False,
              help="Req|Test specifications to print out test case prioritization")
@click.argument('path', required=False, type=click.Path())
def generate_vcd(format, jiradb, vcduser, vcdpwd, sql, spec, path):
    """Given a specific namespace, corresponding to a Jira Component
    or Rubin Subsystem, build the VCD. By default build the DM VCD.
    If specified, PATH is the resulting output.
    """
    global OUTPUT_FORMAT
    OUTPUT_FORMAT = format
    target = "vcd"

    component = Config.NAMESPACE.upper()

    Config.DB_PARAMETERS = {"host": jiradb, "user": vcduser, "pwd": vcdpwd, "schema": "jira"}

    if spec:
        RSP = spec
    else:
        RSP = ""

    if sql:
        print('Building model using direct SQL access')
        vcd_dict = vcdsql(component, RSP)
    else:
        print("VCD via rest API disabled. Use '--sql True' option")
        exit()

    sum_dict = summary(vcd_dict)

    file = open(path, "w") if path else sys.stdout

    env = Environment(loader=ChoiceLoader([
        FileSystemLoader(Config.TEMPLATE_DIRECTORY),
        PackageLoader('docsteady', 'templates')
    ]),
        lstrip_blocks=True, trim_blocks=True,
        autoescape=None
    )

    try:
        template_path = f"{target}.{Config.TEMPLATE_LANGUAGE}.jinja2"
        template = env.get_template(template_path)
    except TemplateNotFound:
        click.echo(f"No Template Found: {template_path}", err=True)
        sys.exit(1)

    metadata = _metadata()
    metadata["component"] = component
    metadata["template"] = template.filename
    text = template.render(metadata=metadata,
                           coverage=Config.coverage,
                           tcresults=Config.tcresults,
                           sum_dict=sum_dict,
                           spec_to_reqs=Config.REQ_PER_DOC,
                           vcd_dict=vcd_dict)

    print(_as_output_format(text), file=file)


if __name__ == '__main__':
    cli()


@cli.command("baseline-ve")
@click.option('--format', default='latex', help='Pandoc output format (see pandoc for options)')
@click.option('--username', prompt="Jira Username", envvar="JIRA_USER", help="Jira username")
@click.option('--password', prompt="Jira Password", hide_input=True,
              envvar="JIRA_PASSWORD", help="Jira Password")
@click.option('--details', default=False, help='If true, an extra detailed report will be produced')
@click.option('--subcomponent', required=False, help='Extract Verification Elements only '
                                                     'for the specified subcomponent')
@click.argument('path', required=False, type=click.Path())
def baseline_ve(format, username, password, details, subcomponent, path):
    """Given a specific subsystem (component), and subcomponent,
    a document is generated including all corresponding Verification Elements
    and related Test Cases. This is not a Verification Control Document:
    no Test Result information is provided
    """
    global OUTPUT_FORMAT
    OUTPUT_FORMAT = format
    Config.AUTH = (username, password)
    target = "ve"

    component = Config.NAMESPACE.upper()

    if not subcomponent:
        subcomponent=""

    ve_model = do_ve_model(component, subcomponent)

    file = open(path, "w") if path else sys.stdout

    env = Environment(loader=ChoiceLoader([
        FileSystemLoader(Config.TEMPLATE_DIRECTORY),
        PackageLoader('docsteady', 'templates')
    ]),
        lstrip_blocks=True, trim_blocks=True,
        autoescape=None
    )

    try:
        template_path = f"{target}.{Config.TEMPLATE_LANGUAGE}.jinja2"
        template = env.get_template(template_path)
    except TemplateNotFound:
        click.echo(f"No Template Found: {template_path}", err=True)
        sys.exit(1)

    metadata = _metadata()
    metadata["component"] = component
    metadata["subcomponent"] = subcomponent
    metadata["template"] = template.filename
    text = template.render(metadata=metadata,
                           velements=ve_model,
                           reqs=Config.CACHED_REQS_FOR_VES,
                           test_cases=Config.CACHED_TESTCASES)

    print(_as_output_format(text), file=file)
    file.close()

    # Writing detailed VE document
    if details:
        details_file_name = "ve_details.tex"
        details_file = open(details_file_name, "w")
        try:
            template_path = f"{target}-details.{Config.TEMPLATE_LANGUAGE}.jinja2"
            template_details = env.get_template(template_path)
        except TemplateNotFound:
            click.echo(f"No Detailed template found: {template_path}", err=True)

        text_details = template_details.render(metadata=metadata,
                                               velements=ve_model,
                                               reqs=Config.CACHED_REQS_FOR_VES,
                                               test_cases=Config.CACHED_TESTCASES)

        print(_as_output_format(text_details), file=details_file)
        details_file.close()
