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


def make_summary_table(testcases):

   jlnk="https://jira.lsstcorp.org/secure/Tests.jspa\#/testCase/"

   sumtable = "\\begin{longtable}[]{p{3cm}p{13cm}}\n"
   sumtable = sumtable + "\\toprule\nTest Id & Test Name\\tabularnewline\n"
   sumtable = sumtable + "\\midrule\n\\endhead"
   for TCase in testcases:
      label = TCase['key'].lower()
      sumtable = sumtable + "\\protect\\hyperlink{" + label + "}{" + TCase['key'] + "} & \n"
      sumtable = sumtable + "  \\href{" + jlnk + TCase['key'] + "}{" + TCase['name'] + "} \\tabularnewline\n"

   sumtable = sumtable + "\\bottomrule\n\\end{longtable}\n"

   return(sumtable)
