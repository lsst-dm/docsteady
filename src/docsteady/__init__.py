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

import contextlib
import json
import logging
import os
import sys
import warnings
from collections import OrderedDict
from importlib.metadata import PackageNotFoundError, version
from typing import ContextManager, Optional, TextIO, cast

import arrow
import click
from jinja2 import (
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    PackageLoader,
    Template,
    TemplateNotFound,
)

from .config import Config
from .formatters import alphanum_key
from .spec import build_spec_model
from .tplan import build_tpr_model, render_report
from .vcd import build_vcd_dict, summary
from .ve_baseline import do_ve_model

# Silence BeautifulSoup warning about providing Unicode markup together
# with from_encoding
warnings.filterwarnings(
    "ignore",
    message=(
        r"You provided Unicode markup but also provided a value for "
        r"from_encoding\. Your from_encoding will be ignored\."
    ),
)

try:
    __version__ = version(__name__)
except PackageNotFoundError:
    __version__ = "0.0.0"

OUTPUT_FORMAT = "latex"

if "ZEPHYR_TOKEN" in os.environ:
    Config.ZEPHYR_TOKEN = os.environ["ZEPHYR_TOKEN"]
if "JIRA_PASSWORD" in os.environ:
    Config.AUTH = (os.environ["JIRA_USER"], os.environ["JIRA_PASSWORD"])

logging.getLogger("root").setLevel(logging.ERROR)
logging.getLogger().setLevel(logging.ERROR)
logging.getLogger("bs4.dammit").setLevel(logging.ERROR)


def _as_output_format(text: str) -> str:
    """Return converted text when template language differs from
    output format.
    """
    if Config.TEMPLATE_LANGUAGE != OUTPUT_FORMAT:
        setattr(Config.DOC, Config.TEMPLATE_LANGUAGE, text.encode("utf-8"))
        return getattr(Config.DOC, OUTPUT_FORMAT).decode("utf-8")
    return text


def _env() -> Environment:
    return Environment(
        loader=ChoiceLoader(
            [
                FileSystemLoader(Config.TEMPLATE_DIRECTORY),
                PackageLoader("docsteady", "templates"),
            ]
        ),
        lstrip_blocks=True,
        trim_blocks=True,
        autoescape=False,
    )


def _load_template(env: Environment, target: str) -> Optional[Template]:
    path = f"{target}.{Config.TEMPLATE_LANGUAGE}.jinja2"
    try:
        return env.get_template(path)
    except TemplateNotFound:
        click.echo(f"No Template Found: {path}", err=True)
        return None


def _write_output(text: str, path: Optional[str]) -> None:
    if Config.TEMPLATE_LANGUAGE != OUTPUT_FORMAT:
        setattr(Config.DOC, Config.TEMPLATE_LANGUAGE, text.encode("utf-8"))
        text = getattr(Config.DOC, OUTPUT_FORMAT).decode("utf-8")
    if path:
        with open(path, "w", encoding="utf-8") as fp:
            fp.write(text)
    else:
        sys.stdout.write(text)


def _try_appendix_template(
    env: Environment, target: str
) -> Optional[Template]:
    try:
        return env.get_template(
            f"{target}-appendix.{Config.TEMPLATE_LANGUAGE}.jinja2"
        )
    except TemplateNotFound:
        return None


def _get_appendix_path(path: Optional[str]) -> ContextManager[TextIO]:
    """Return a context manager that yields a writable TextIO.

    If `path` is None or doesn't look like a filename with an
    extension, yield sys.stdout via contextlib.nullcontext. Otherwise
    open the appendix file for writing and yield that file object.
    """
    if not path:
        return cast(ContextManager[TextIO], contextlib.nullcontext(sys.stdout))
    parts = path.split(".")
    if len(parts) < 2:
        return cast(ContextManager[TextIO], contextlib.nullcontext(sys.stdout))
    appendix = ".".join(parts[:-1] + ["appendix", parts[-1]])
    return open(appendix, "w", encoding="utf-8")


def _metadata() -> dict:
    return {
        "created_on": arrow.now(),
        "docsteady_version": __version__,
        "project": "LVV",
    }


@click.group()
@click.option(
    "--namespace",
    default="dm",
    help=("Project namespace (dm, ts, example, etc..). " "Defaults to dm."),
)
@click.option(
    "--template-format",
    "template_format",
    default="latex",
    help=("Template language (latex, html). Defaults to latex."),
)
@click.option(
    "--load-from",
    "load_from",
    default=os.path.curdir,
    help=(
        "Path to search for templates in. Defaults to the working " "directory"
    ),
)
@click.option(
    "--token",
    prompt="Jira Zephyr Token",
    hide_input=True,
    envvar="ZEPHYR_TOKEN",
    help="Jira token from jira cloud, Zyphry API Token",
)
@click.option(
    "--username",
    prompt="Jira User Name for Jira API",
    hide_input=True,
    envvar="JIRA_USER",
    help="Jira cloud user - an email address",
)
@click.option(
    "--password",
    prompt="Jira password (or Token)  for Jira API",
    hide_input=True,
    envvar="JIRA_PASSWORD",
    help="Jira cloud password - usually an API token",
)
@click.version_option(__version__)
def cli(
    namespace: str,
    template_format: str,
    load_from: str,
    token: str,
    username: str,
    password: str,
) -> None:
    Config.MODE_PREFIX = f"{namespace.lower()}-" if namespace else ""
    Config.NAMESPACE = namespace
    Config.TEMPLATE_LANGUAGE = template_format
    Config.TEMPLATE_DIRECTORY = load_from
    Config.ZEPHYR_TOKEN = token
    Config.AUTH = (username, password)


@cli.command("generate-spec")
@click.option(
    "--format",
    "format_",
    default="latex",
    help="Pandoc output format (see pandoc for options)",
)
@click.argument("folder")
@click.argument("path", required=False, type=click.Path())
def generate_spec(format_: str, folder: str, path: Optional[str]) -> None:
    global OUTPUT_FORMAT
    OUTPUT_FORMAT = format_
    target = "spec"

    try:
        testcases, requirements, tcs_dict = build_spec_model(folder)
    except Exception as exc:
        click.echo("Error in building model", err=True)
        raise exc

    requirements_to_testcases = OrderedDict(
        sorted(
            Config.REQUIREMENTS_TO_TESTCASES.items(),
            key=lambda item: alphanum_key(item[0]),
        )
    )

    env = _env()
    template = _load_template(env, target)
    if not template:
        sys.exit(1)

    libtestcases = sorted(
        Config.CACHED_LIBTESTCASES.values(), key=lambda t: t["keyid"]
    )
    metadata = _metadata()
    metadata.update(folder=folder, template=template.filename)

    text = template.render(
        metadata=metadata,
        deprecated=testcases["deprecated"],
        tcs_dict=tcs_dict,
        libtestcases=libtestcases,
        requirements_to_testcases=requirements_to_testcases,
        requirements_map=requirements,
        tc_status_list=Config.TESTCASE_STATUS_LIST,
        testcases_map=Config.CACHED_TESTCASES,
    )
    _write_output(text, path)

    appendix = _try_appendix_template(env, target)
    if not appendix:
        click.echo("No Appendix Template Found, skipping...", err=True)
        return

    metadata["template"] = appendix.filename
    with _get_appendix_path(path) as ap:
        appendix_text = appendix.render(
            metadata=metadata,
            testcases=testcases,
            requirements_to_testcases=requirements_to_testcases,
            requirements_map=requirements,
            testcases_map=Config.CACHED_TESTCASES,
        )
        ap.write(_as_output_format(appendix_text) if False else appendix_text)


@cli.command("generate-tpr")
@click.option(
    "--excludenoexec",
    "excludenoexec",
    is_flag=True,
    default=False,
    help=("Ignore the test execution steps not executed/with no " "comment"),
)
@click.option(
    "--includeall",
    "includeall",
    is_flag=True,
    default=False,
    help=(
        "Ignore the include in report field for executions and " "include all"
    ),
)
@click.option(
    "--format",
    "format_",
    default="latex",
    help="Pandoc output format (see pandoc for options)",
)
@click.option(
    "--trace",
    "trace",
    is_flag=True,
    default=False,
    help=("If true, traceability table will be added in appendix"),
)
@click.option(
    "--dump",
    "dump",
    default=False,
    help=(
        "If true, dump json before rendering tex, if the file "
        "exists use it next time instead of hitting server"
    ),
)
@click.argument("plan")
@click.argument("path", required=False, type=click.Path())
def generate_report(
    format_: str,
    trace: bool,
    plan: str,
    path: Optional[str],
    includeall: bool,
    excludenoexec: bool,
    dump: bool,
) -> None:
    global OUTPUT_FORMAT
    OUTPUT_FORMAT = format_
    Config.INCLUDE_ALL_EXECS = includeall
    target = "tpr"

    if Config.NAMESPACE.upper() not in Config.COMPONENTS:
        click.echo(f"Wrong input component {Config.NAMESPACE}", err=True)
        sys.exit(1)

    fname = "tpr_model.json"
    if dump and os.path.isfile(fname):
        with open(fname, "r", encoding="utf-8") as fp:
            plan_dict = json.load(fp)
    else:
        plan_dict = build_tpr_model(plan)
        with open(fname, "w", encoding="utf-8") as fp:
            fp.write(json.dumps(plan_dict))

    metadata = _metadata()
    metadata["namespace"] = Config.NAMESPACE
    metadata["component_long_name"] = Config.COMPONENTS[
        Config.NAMESPACE.upper()
    ]

    render_report(
        excludenoexec, metadata, target, plan_dict, OUTPUT_FORMAT, path
    )

    # output the plan - TR without results
    target = "tpnoresult"
    path_plan = (path or "output.tex").replace(".tex", "-plan.tex")
    render_report(
        excludenoexec, metadata, target, plan_dict, OUTPUT_FORMAT, path_plan
    )

    if trace:
        env = _env()
        appendix = _try_appendix_template(env, target)
        if appendix:
            metadata["template"] = appendix.filename
            with _get_appendix_path(path_plan) as ap:
                appendix_text = appendix.render(
                    metadata=metadata,
                    testcases_map=plan_dict["testcases_map"],
                )
                ap.write(appendix_text)

    if Config.exeuction_errored:
        raise SystemError("Content Problem, please check.")


@cli.command("generate-vcd")
@click.option(
    "--format",
    "format_",
    default="latex",
    help="Pandoc output format (see pandoc for options)",
)
@click.option(
    "--spec",
    "spec",
    is_flag=True,
    default=False,
    help=("Req|Test specifications to print out test case " "prioritization"),
)
@click.option(
    "--subcomponent",
    "subcomponent",
    required=False,
    help=(
        "Extract Verification Elements only for the specified " "subcomponent"
    ),
)
@click.option(
    "--dump",
    default=False,
    help=(
        "If true, dump json before rendering tex, if the file "
        "exists use it next time instead of hitting server"
    ),
)
@click.argument("path", required=False, type=click.Path())
def generate_vcd(
    format_: str,
    spec: bool,
    subcomponent: Optional[str],
    path: Optional[str],
    dump: bool,
) -> None:
    global OUTPUT_FORMAT
    OUTPUT_FORMAT = format_
    target = "vcd"
    component = Config.NAMESPACE.upper()
    subcomponent = subcomponent or ""

    if dump:
        with open("VEmodel.json", "r", encoding="utf-8") as fp:
            ve_model = json.load(fp)
    else:
        ve_model = do_ve_model(component, subcomponent)

    vcd_dict = build_vcd_dict(ve_model, usedump=dump)
    sum_dict = summary(vcd_dict)

    env = _env()
    template = _load_template(env, target)
    if not template:
        sys.exit(1)

    metadata = _metadata()
    metadata.update(component=component, template=template.filename)
    text = template.render(
        metadata=metadata,
        coverage=Config.req_coverage,
        tcresults=Config.tcresults,
        sum_dict=sum_dict,
        spec_to_reqs=Config.REQ_PER_DOC,
        vcd_dict=vcd_dict,
    )
    _write_output(text, path)


@cli.command("baseline-ve")
@click.option(
    "--format",
    "format_",
    default="latex",
    help="Pandoc output format (see pandoc for options)",
)
@click.option(
    "--details",
    "details",
    is_flag=True,
    default=False,
    help=("If true, an extra detailed report will be produced"),
)
@click.option(
    "--subcomponent",
    "subcomponent",
    required=False,
    help=(
        "Extract Verification Elements only for the specified " "subcomponent"
    ),
)
@click.option(
    "--dump",
    default=False,
    help=(
        "If true, dump json before rendering tex, if the file "
        "exists use it next time instead of hitting server"
    ),
)
@click.argument("path", required=False, type=click.Path())
def baseline_ve(
    format_: str,
    details: bool,
    dump: bool,
    subcomponent: Optional[str],
    path: Optional[str],
) -> None:
    global OUTPUT_FORMAT
    OUTPUT_FORMAT = format_
    target = "ve"
    jfile = f"baseline_{target}.json"
    component = Config.NAMESPACE.upper()
    subcomponent = subcomponent or ""

    if dump and os.path.exists(jfile):
        with open(jfile, "r", encoding="utf-8") as fp:
            ve_model = json.load(fp)
    else:
        ve_model = do_ve_model(component, subcomponent)
        with open(jfile, "w", encoding="utf-8") as fp:
            fp.write(json.dumps(ve_model))

    env = _env()
    template = _load_template(env, target)
    if not template:
        sys.exit(1)

    metadata = _metadata()
    metadata.update(
        component=component,
        subcomponent=subcomponent,
        template=template.filename,
    )
    text = template.render(
        metadata=metadata,
        velements=ve_model,
        reqs=Config.CACHED_REQS_FOR_VES,
        test_cases=Config.CACHED_TESTCASES,
    )
    _write_output(text, path)

    if details:
        try:
            template_details = env.get_template(
                f"{target}-details.{Config.TEMPLATE_LANGUAGE}.jinja2"
            )
            details_text = template_details.render(
                metadata=metadata,
                velements=ve_model,
                reqs=Config.CACHED_REQS_FOR_VES,
                test_cases=Config.CACHED_TESTCASES,
            )
            with open("ve_details.tex", "w", encoding="utf-8") as df:
                df.write(details_text)
        except TemplateNotFound:
            click.echo(
                f"No Detailed template found: {target}-details."
                f"{Config.TEMPLATE_LANGUAGE}.jinja2",
                err=True,
            )


if __name__ == "__main__":
    cli()
