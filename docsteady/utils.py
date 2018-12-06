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
from collections import OrderedDict

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
            if Config.TEMPLATE_LANGUAGE == 'latex':
                value = cite_docushare_handles(value)
        return value


class SubsectionableHtmlPandocField(fields.String):
    """
    A field that originates as HTML but is normalized to a template
    language.
    """

    def __init__(self, *args, extractable=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.extractable = extractable or []

    def _deserialize(self, value, attr, data):
        if isinstance(value, str) and Config.TEMPLATE_LANGUAGE:
            value = rewrite_strong_to_subsection(value, self.extractable)
            Config.DOC.html = value.encode("utf-8")
            value = getattr(Config.DOC, Config.TEMPLATE_LANGUAGE).decode("utf-8")
            if Config.TEMPLATE_LANGUAGE == 'latex':
                value = cite_docushare_handles(value)
        return value


def cite_docushare_handles(text):
    """This will find matching docushare handles and replace
    the text with the ``\citeds{text}``."""
    return Config.DOCUSHARE_DOC_PATTERN.sub(r"\citeds{\1\2}\3", text)


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
    """
    This will return a cached testcases (a test case already processed)
    or fetch it if and add to cache.
    :param test_case_key: Key of test case to fetch
    :return: Cached or fetched test case.
    """
    # Prevent circular import
    from .spec import TestCase
    cached_testcase_resp = Config.CACHED_TESTCASES.get(test_case_key)
    if not cached_testcase_resp:
        resp = requests.get(Config.TESTCASE_URL.format(testcase=test_case_key),
                            auth=Config.AUTH)
        testcase_resp = resp.json()
        testcase, errors = TestCase().load(testcase_resp)
        if errors:
            raise Exception("Unable to process test cases: " + str(errors))
        Config.CACHED_TESTCASES[test_case_key] = testcase
        cached_testcase_resp = testcase
    return cached_testcase_resp


def rewrite_strong_to_subsection(content, extractable):
    """
    Extract specific "strong" elements and rewrite them to headings so
    they appear as subsections in Latex
    :param extractable: List of names that are extractable
    :param content: HTML to parse
    :return: New HTML
    """
    # The default is to preserve order,
    preserve_order = True
    soup = BeautifulSoup(content, "html.parser")
    element_neighbor_text = ""
    seen_name = None
    shelved = []
    new_order = shelved if preserve_order else []
    found_items = OrderedDict()
    for elem in soup.children:
        if "strong" == elem.name:
            if seen_name:
                found_items[seen_name] = element_neighbor_text
                new_order.append(element_neighbor_text)
                seen_name = None
            else:
                shelved.append(element_neighbor_text)

            element_neighbor_text = ""
            element_name = elem.text.lower().replace(" ", "_")
            if element_name in extractable:
                seen_name = element_name
                # h2 appears as subsection in latex via pandoc
                elem.name = "h2"

        element_neighbor_text += str(elem) + "\n"

    if seen_name:
        found_items[seen_name] = element_neighbor_text
        new_order.append(element_neighbor_text)
    else:
        shelved.append(element_neighbor_text)

    # Note: Could sort according to found_items.keys()
    # if not preserve_order:
    #     new_order = list(found_items.values())
    #     new_order.extend(shelved)
    return "".join(new_order)
