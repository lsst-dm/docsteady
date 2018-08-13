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
from .config import Config


def make_summary_table(testcases):

    summary_table = "\\begin{longtable}[]{p{3cm}p{13cm}}\n" \
                    "\\toprule\n" \
                    "Test Id & Test Name\\tabularnewline\n" \
                    "\\midrule\n" \
                    "\\endhead\n"
    for testcase in testcases:
        label = testcase['key'].lower()
        href = Config.TESTCASE_UI_URL.format(testcase=testcase['key'])
        summary_table += "\\hyperref[" + label + "]{" + testcase['key'] + "} & \n"
        summary_table += "\\href{" + href + "}{" + testcase['name'] + "} \\tabularnewline\n"

    summary_table += "\\bottomrule\n\\end{longtable}\n"
    return summary_table


def make_reqs_table(reqissues, reqmap, testcases):

    trace_to_ve = {}

    for tc in testcases:
        if "issueLinks" in tc:
            for issue in tc['issueLinks']:
                trace_to_ve.setdefault(issue, []).append(tc['key'])

    reqstable = "\\scriptsize{\\begin{longtable}[]{p{13cm}p{3cm}}\n" \
                "\\toprule \n" \
                "Verification Requirement & Test Cases\\tabularnewline\n" \
                "\\midrule\n" \
                "\\endhead"

    for issue in reqissues:
        href = Config.ISSUE_UI_URL.format(issue=reqmap[issue]['key'])
        title = issue + " - " + reqmap[issue]['summary']
        reqstable += " \\href{" + href + "}{ " + title + " } & \n{"
        for tc in trace_to_ve[issue]:
            label = tc.lower()
            reqstable += " \\hyperref[" + label + "]{" + tc + "}"

        reqstable = reqstable.rstrip(',')
        reqstable += "} \\\\ \n"

    reqstable += "\\tabularnewline\n" \
                 "\\bottomrule\n" \
                 "\\end{longtable}}\n"
    return reqstable
