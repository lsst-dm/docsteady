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

"""
Code for Test Specification Model Generation
"""
import re

import arrow
from bs4 import BeautifulSoup
from marshmallow import fields

from .config import Config
import requests


class HtmlPandocField(fields.String):
    """
    A field that originates as HTML but is normalized to a template
    language.
    """
    def _deserialize(self, value, attr, data):
        if isinstance(value, str) and Config.TEMPLATE_LANGUAGE:
            Config.DOC.html = value.encode("utf-8")
            value = getattr(Config.DOC, Config.TEMPLATE_LANGUAGE).decode("utf-8")
        return value


class MarkdownableHtmlPandocField(fields.String):
    """
    An field that originates as HTML, but is intepreted as plain
    text (bold, italics, and font styles are ignored) if the field
    has a markdown comment in the beginning, of the form `[markdown]: #`
    """
    def _deserialize(self, value, attr, data):
        if value and isinstance(value, str) and Config.TEMPLATE_LANGUAGE:
            # If it exists, look for markdown text
            soup = BeautifulSoup(value, "html.parser")
            # normalizes HTML, replace breaks with newline, non-breaking spaces
            description_txt = str(soup).replace("<br/>", "\n").replace("\xa0", " ")
            # matches `[markdown]: #` at the top of description
            if re.match("\[markdown\].*:.*#(.*)", description_txt.splitlines()[0]):
                # Assume github-flavored markdown
                Config.DOC.gfm = description_txt.encode("utf-8")
            else:
                Config.DOC.html = value.encode("utf-8")
            value = getattr(Config.DOC, Config.TEMPLATE_LANGUAGE).decode("utf-8")
        return value


def as_arrow(datestring):
    return arrow.get(datestring).to(Config.TIMEZONE)


def owner_for_id(owner_id):
    if owner_id not in Config.CACHED_USERS:
        resp = requests.get(Config.USER_URL.format(username=owner_id),
                            auth=Config.AUTH)
        resp.raise_for_status()
        user_resp = resp.json()
        Config.CACHED_USERS[owner_id] = user_resp
    user_resp = Config.CACHED_USERS[owner_id]
    return user_resp["displayName"]


def test_case_for_key(test_case_key):
    cached_testcase_resp = Config.CACHED_TESTCASES.get(test_case_key)
    if not cached_testcase_resp:
        resp = requests.get(Config.TESTCASE_URL.format(testcase=test_case_key),
                            auth=Config.AUTH)
        step_testcase_resp = resp.json()
        Config.CACHED_TESTCASES[test_case_key] = step_testcase_resp
        cached_testcase_resp = step_testcase_resp
    return cached_testcase_resp
