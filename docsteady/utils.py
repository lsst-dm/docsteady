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
import os
from os.path import dirname, exists

import arrow
from bs4 import BeautifulSoup
from marshmallow import fields
import pypandoc

from .config import Config
import requests

from urllib.parse import urlparse
from urllib.parse import urljoin

jhost = "140.252.32.64"
jdb = "jira"


class HtmlPandocField(fields.String):
    """
    A field that originates as HTML but is normalized to a template
    language.
    """
    def _deserialize(self, value, attr, data):
        if isinstance(value, str) and Config.TEMPLATE_LANGUAGE:
            value = download_and_rewrite_images(value)
            value = pypandoc.convert_text(value, Config.TEMPLATE_LANGUAGE, format="html")
            if Config.TEMPLATE_LANGUAGE == 'latex':
                value = cite_docushare_handles(value)
        return value.strip()


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
            value = download_and_rewrite_images(value)
            value = rewrite_strong_to_subsection(value, self.extractable)
            value = pypandoc.convert_text(value, Config.TEMPLATE_LANGUAGE, format="html")
            if Config.TEMPLATE_LANGUAGE == 'latex':
                value = cite_docushare_handles(value)
        return value


def cite_docushare_handles(text):
    """This will find matching docushare handles and replace
    the text with the ``\\citeds{text}``."""
    output_tex = ""
    for entry in text.split(" "):
        if not ("href" in entry or "url" in entry):
            output_tex = output_tex + " " + Config.DOCUSHARE_DOC_PATTERN.sub(r"\\citeds{\1\2}", entry)
        else:
            output_tex = output_tex + " " + entry
    return output_tex


class MarkdownableHtmlPandocField(fields.String):
    """
    An field that originates as HTML, but is intepreted as plain
    text (bold, italics, and font styles are ignored) if the field
    has a markdown comment in the beginning, of the form `[markdown]: #`
    """
    def _deserialize(self, value, attr, data):
        if value and isinstance(value, str) and Config.TEMPLATE_LANGUAGE:
            # If it exists, look for markdown text
            value = download_and_rewrite_images(value)
            soup = BeautifulSoup(value, "html.parser")
            # normalizes HTML, replace breaks with newline, non-breaking spaces
            description_txt = str(soup).replace("<br/>", "\n").replace("\xa0", " ")
            # matches `[markdown]: #` at the top of description
            if re.match("\\[markdown\\].*:.*#(.*)", description_txt.splitlines()[0]):
                # Assume github-flavored markdown
                value = pypandoc.convert_text(description_txt, Config.TEMPLATE_LANGUAGE, format="gfm")
            else:
                value = pypandoc.convert_text(value, Config.TEMPLATE_LANGUAGE, format="html")
        return value


def as_arrow(datestring):
    return arrow.get(datestring).to(Config.TIMEZONE)


def owner_for_id(owner_id):
    if not owner_id:
        return "Undefined"
    if owner_id not in Config.CACHED_USERS:
        resp = requests.get(Config.USER_URL.format(username=owner_id),
                            auth=Config.AUTH)
        if resp.status_code == 404:
            Config.CACHED_USERS[owner_id] = {'displayName': owner_id}
            user_resp = {'displayName': owner_id}
        else:
            resp.raise_for_status()
            user_resp = resp.json()
            Config.CACHED_USERS[owner_id] = user_resp
    else:
        user_resp = Config.CACHED_USERS[owner_id]
    displayName = user_resp['displayName']
    return displayName


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
        if resp.status_code == 200:
            testcase_resp = resp.json()
            testcase, errors = TestCase().load(testcase_resp)
            if errors:
                raise Exception("Unable to process test cases: " + str(errors))
            Config.CACHED_TESTCASES[test_case_key] = testcase
        else:
            testcase = {'objective': 'This Test Case has been archived. '
                                     'Information not available anymore',
                        'key': test_case_key, 'status': 'ARCHIVED'}
        cached_testcase_resp = testcase
    return cached_testcase_resp


def download_and_rewrite_images(value):
    soup = BeautifulSoup(value.encode("utf-8"), "html.parser")
    rest_location = urljoin(Config.JIRA_INSTANCE, "rest")
    for img in soup.find_all("img"):
        img_width = re.sub('[^0-9]', '', img["style"])
        img_url = urljoin(rest_location, img["src"])
        url_path = urlparse(img_url).path[1:]
        img_name = os.path.basename(url_path)
        fs_path = Config.IMAGE_FOLDER + img_name
        if Config.DOWNLOAD_IMAGES:
            os.makedirs(dirname(fs_path), exist_ok=True)
            existing_files = os.listdir(dirname(fs_path))
            # Look for a file in this path, we don't know what the extension is
            for existing_file in existing_files:
                if fs_path in existing_file:
                    fs_path = existing_file
            if not exists(fs_path):
                resp = requests.get(img_url, auth=Config.AUTH)
                resp.raise_for_status()
                extension = None
                if "png" in resp.headers["content-type"]:
                    extension = "png"
                elif "jpeg" in resp.headers["content-type"]:
                    extension = "jpg"
                elif "gif" in resp.headers["content-type"]:
                    extension = "gif"
                fs_path = f"{fs_path}.{extension}"
                with open(fs_path, "w+b") as img_f:
                    img_f.write(resp.content)
        if img.previous_element.name != "br":
            img.insert_before(soup.new_tag("br"))
        img["style"] = ""
        # fixing the aspect ratio of images is working only with pandoc 1.19.1
        img["width"] = f"{img_width}px"
        img["display"] = "block"
        img["height"] = "auto"
        img["src"] = fs_path
    return str(soup)


def download_attachments(rs, link):
    """
    download the
    :param link: attachment resource location in the Jira server
    :return: none
    """
    attachments = []
    resp = rs.get(link)
    for doc in resp.json():
        # prepare information
        attachment_name = doc['filename'].replace(" ", "")
        fs_path = Config.ATTACHMENT_FOLDER + attachment_name

        # download the attachment
        resp = requests.get(doc['url'], auth=Config.AUTH)
        resp.raise_for_status()
        with open(fs_path, "w+b") as att_f:
            att_f.write(resp.content)

        # add attachment information to the list
        attachments.append({'id': doc['id'], 'filename': attachment_name, 'filesize': doc['filesize'],
                            'filepath': fs_path})
    return attachments


def create_folders_and_files():
    """
    Create attachment and image folders if missing
    :return:
    """
    os.makedirs(dirname(Config.IMAGE_FOLDER), exist_ok=True)
    os.makedirs(dirname(Config.ATTACHMENT_FOLDER), exist_ok=True)
    # creating empty files so the folder can be added to Git
    imgs_empty_file = Config.IMAGE_FOLDER + '.empty'
    atts_empty_file = Config.ATTACHMENT_FOLDER + '.empty'
    local_bib_file = 'local.bib'
    # create empty files in them so they can be added to Git
    if not os.path.isfile(imgs_empty_file):
        with open(imgs_empty_file, 'w'):
            pass
    if not os.path.isfile(atts_empty_file):
        with open(atts_empty_file, 'w'):
            pass
    # create local.bib so the build don't fails
    if not os.path.isfile(local_bib_file):
        with open(local_bib_file, 'w'):
            pass


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


# FIXME: This can be removed ATM API testcases/search API is fixed
def get_folders(target_folder):
    """
    Get all folders that that have the target folder in their string
    """
    def collect_children(children, path, folders):
        """Recursively collection children"""
        for child in children:
            child_path = path + f"/{child['name']}"
            folders.append(child_path)
            if len(child["children"]):
                collect_children(child["children"], child_path, folders)
    resp = requests.get(Config.FOLDERTREE_API, auth=Config.AUTH)
    resp.raise_for_status()
    foldertree_json = resp.json()

    folders = []
    collect_children(foldertree_json["children"], "", folders)
    target_folders = []
    for folder in folders:
        if folder.startswith(target_folder):
            target_folders.append(folder)
    return target_folders


def get_tspec(folder):
    sf = folder.split('/')
    for d in sf:
        sd = d.split('|')
        if len(sd) == 2:
            return sd[1]
    return ""
