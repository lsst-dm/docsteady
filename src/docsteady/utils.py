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
import os
import re
import warnings
from base64 import b64encode
from collections import OrderedDict
from os.path import dirname, exists
from typing import Any, List, MutableMapping
from urllib.parse import urljoin, urlparse

import arrow
import pypandoc
import requests
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from marshmallow import EXCLUDE, fields
from requests import Session
from zephyr import ZephyrScale
from zephyr.scale.cloud.cloud_api import CloudApiWrapper
from zephyr.scale.cloud.endpoints import paths

from .config import Config

global THE_SESSION


class HtmlPandocField(fields.String):
    """
    A field that originates as HTML but is normalized to a template
    language.
    """

    def _deserialize(
        self, value: Any, attr: Any, data: Any, **kwargs: Any
    ) -> Any:
        if isinstance(value, str) and Config.TEMPLATE_LANGUAGE:
            value = download_and_rewrite_images(value)
            value = pypandoc.convert_text(
                value, Config.TEMPLATE_LANGUAGE, format="html"
            ).replace("height=\\textheight", "")
            if Config.TEMPLATE_LANGUAGE == "latex":
                value = cite_docushare_handles(value)
        return value.strip()


class SubsectionableHtmlPandocField(fields.String):
    """
    A field that originates as HTML but is normalized to a template
    language.
    """

    def __init__(
        self,
        *args: list[str],
        extractable: list[Any] | None = None,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self.extractable = extractable or []

    def _deserialize(
        self, value: Any, attr: Any, data: Any, **kwargs: Any
    ) -> Any:
        if isinstance(value, str) and Config.TEMPLATE_LANGUAGE:
            value = download_and_rewrite_images(value)
            value = rewrite_strong_to_subsection(value, self.extractable)
            value = pypandoc.convert_text(
                value, Config.TEMPLATE_LANGUAGE, format="html"
            )
            if Config.TEMPLATE_LANGUAGE == "latex":
                value = cite_docushare_handles(value)
        return value


def cite_docushare_handles(text: str) -> str:
    """This will find matching docushare handles and replace
    the text with the ``\\citeds{text}``."""
    output_tex = ""
    for entry in text.split(" "):
        if not ("href" in entry or "url" in entry):
            output_tex = (
                output_tex
                + " "
                + Config.DOCUSHARE_DOC_PATTERN.sub(r"\\citeds{\1\2}", entry)
            )
        else:
            output_tex = output_tex + " " + entry
    return output_tex


class MarkdownableHtmlPandocField(fields.String):
    """
    An field that originates as HTML, but is intepreted as plain
    text (bold, italics, and font styles are ignored) if the field
    has a markdown comment in the beginning, of the form `[markdown]: #`
    """

    def _deserialize(
        self, value: Any, attr: Any, data: Any, **kwargs: Any
    ) -> Any:
        if value and isinstance(value, str) and Config.TEMPLATE_LANGUAGE:
            # If it exists, look for markdown text
            # Remove spurious character occasionally generated by Jira API
            value = download_and_rewrite_images(value).replace("Â", "")
            # normalizes HTML, replace breaks with newline, non-breaking spaces
            description_txt = value.replace("<br/>", "\n").replace("\xa0", " ")
            # matches `[markdown]: #` at the top of description
            if re.match(
                "\\[markdown\\].*:.*#(.*)", description_txt.splitlines()[0]
            ):
                # Assume github-flavored markdown
                value = pypandoc.convert_text(
                    description_txt, Config.TEMPLATE_LANGUAGE, format="gfm"
                )
            else:
                value = pypandoc.convert_text(
                    value, Config.TEMPLATE_LANGUAGE, format="html"
                ).replace("height=\\textheight", " ")
        return value


def as_arrow(datestring: str) -> arrow.Arrow:
    return arrow.get(datestring).to(Config.TIMEZONE)


def owner_for_id(owner_id: str | dict) -> str:
    if not owner_id or owner_id == "None":
        return "Undefined"
    if type(owner_id) is str:
        oid: str = owner_id
    if type(owner_id) is dict:
        oid = owner_id["accountId"]
    user_resp: dict = {"displayName": oid}
    if oid not in Config.CACHED_USERS:
        sess = get_rest_session()
        # https://rubinobs.atlassian.net/rest/api/2/user?accountId=
        url = f"{Config.JIRA_API}user?accountId={oid}"
        resp = sess.get(url, auth=Config.AUTH)
        resp.raise_for_status()
        user_resp = resp.json()
        Config.CACHED_USERS[oid] = user_resp
    return Config.CACHED_USERS[oid]["displayName"]


def t_case_for_key(test_case_key: str) -> dict[str, Any]:
    """
    This will return a cached testcases (a test case already processed)
    or fetch it if and add to cache.
    Named t_case to not clash with test in pytest.
    Not sure why tox causes a problem with this (not pytest).:
    :param test_case_key: Key of test case to fetch
    :return: Cached or fetched test case.
    """
    # Prevent circular import
    from .spec import TestCase

    cached_testcase_resp = Config.CACHED_TESTCASES.get(test_case_key)
    if not cached_testcase_resp:
        zapi = get_zephyr_api()
        resp = zapi.test_cases.get_test_case(test_case_key)
        if resp:
            testcase = TestCase(unknown=EXCLUDE).load(resp)
            Config.CACHED_TESTCASES[test_case_key] = testcase
        else:
            testcase = {
                "objective": "This Test Case has been archived. "
                "Information here may not completed.",
                "key": test_case_key,
                "status": "ARCHIVED",
            }
        cached_testcase_resp = testcase
    return cached_testcase_resp


def download_and_rewrite_images(value: str) -> str:
    warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)
    soup = BeautifulSoup(value.encode("utf-8"), "html.parser")
    rest_location = urljoin(Config.JIRA_INSTANCE, "rest")
    for img in soup.find_all("img"):
        # print(" - ", img)
        try:
            img_width = re.sub("[^0-9]", "", img["style"])
        except Exception:
            img_width = "150"
        img_url = urljoin(rest_location, img["src"])
        url_path = urlparse(img_url).path[1:]
        img_name = os.path.basename(url_path).replace(".", "_")
        fs_path = Config.IMAGE_FOLDER + img_name
        if Config.DOWNLOAD_IMAGES:
            os.makedirs(dirname(fs_path), exist_ok=True)
            existing_files = os.listdir(dirname(fs_path))
            # Look for a file in this path, we don't know what the extension is
            for existing_file in existing_files:
                if fs_path in existing_file:
                    fs_path = existing_file
            if not exists(fs_path):
                errstr = None
                if img_url.startswith(Config.JIRA_INSTANCE):
                    try:
                        resp = requests.get(img_url, auth=Config.AUTH)
                    except ConnectionError as ce:
                        Config.exeuction_errored = True
                        errstr = f"Failed to get {img_url}: {ce}"
                else:
                    # the rest api does not work for images in smartbear
                    try:
                        if "cloudfront" in img_url or "smartbear" in img_url:
                            resp = get_zephy_image(img_url)
                        else:
                            resp = requests.get(img_url)
                        resp.raise_for_status()
                    except requests.exceptions.HTTPError as err:
                        Config.exeuction_errored = True
                        errstr = str(err)
                if errstr is not None:
                    print(errstr)
                    # in order the final user can see where the problem is
                    img.insert_before(
                        soup.new_tag("<b>Image Download Error</b>")
                    )
                    img.decompose()
                    return str(soup)
                extension = None
                if "png" in resp.headers["content-type"]:
                    extension = "png"
                elif "jpeg" in resp.headers["content-type"]:
                    extension = "jpg"
                elif "gif" in resp.headers["content-type"]:
                    extension = "gif"
                elif "svg" in resp.headers["content-type"]:
                    extension = "svg"
                fs_pathe = f"{fs_path}.{extension}"
                with open(fs_pathe, "w+b") as img_f:
                    img_f.write(resp.content)
        if (
            img.previous_element is not None
            and img.previous_element.name != "br"
        ):
            img.insert_before(soup.new_tag("br"))
        img["style"] = ""
        # fixing the aspect ratio of images is working only with pandoc 1.19.1
        img["width"] = f"{img_width}px"
        img["display"] = "block"
        img["src"] = fs_path
        # Latex includegrpahics does not need extention -
        # svg will have to be converted anyway
    return str(soup)


def get_zephy_image(img_url: str) -> requests.Response:
    headers: MutableMapping[str, str | bytes] = {
        "accept": "application/json",
        "Authorization": "Bearer %s" % Config.ZEPHYR_TOKEN,
        "JWT": "%s" % Config.ZEPHYR_TOKEN,
    }
    rs: Session = requests.Session()
    rs.headers = headers
    rs.cookies.set("JWT", Config.ZEPHYR_TOKEN)

    # params = {"return_raw": False} does not work so not sure if i need raw
    resp = rs.get(img_url)
    return resp


def download_attachments(adict: dict) -> list[dict[str, str]]:
    """
    download the
    :param adict: the thing containing links
    :return: none
    """
    attachments = []
    rs = get_rest_session()
    weblinks = []
    if "links" in adict:
        weblinks = adict["links"]["webLinks"]
    for link in weblinks:
        doc = rs.get(link).json()
        # prepare information
        attachment_name = doc["filename"].replace(" ", "")
        fs_path = Config.ATTACHMENT_FOLDER + attachment_name

        # download the attachment
        try:
            zs = get_zephyr_api().session
            b4 = zs.base_url
            zs.base_url = ""
            resp = zs.get(doc["url"])
            zs.base_url = b4
            with open(fs_path, "w+b") as att_f:
                att_f.write(resp.content)
            # add attachment information to the list
        except requests.exceptions.HTTPError:
            print(f"Error getting attachment {attachment_name} from {link}")
            # indicating in the file name that the attachment is not available
            attachment_name = "NA-" + attachment_name
        attachments.append(
            {
                "id": doc["id"],
                "filename": attachment_name,
                "filesize": doc["filesize"],
                "filepath": fs_path,
            }
        )

    return attachments


def create_folders_and_files() -> None:
    """
    Create attachment and image folders if missing
    :return:
    """
    os.makedirs(dirname(Config.IMAGE_FOLDER), exist_ok=True)
    os.makedirs(dirname(Config.ATTACHMENT_FOLDER), exist_ok=True)
    # creating empty files so the folder can be added to Git
    imgs_empty_file = Config.IMAGE_FOLDER + ".empty"
    atts_empty_file = Config.ATTACHMENT_FOLDER + ".empty"
    local_bib_file = "local.bib"
    # create empty files in them so they can be added to Git
    if not os.path.isfile(imgs_empty_file):
        with open(imgs_empty_file, "w"):
            pass
    if not os.path.isfile(atts_empty_file):
        with open(atts_empty_file, "w"):
            pass
    # create local.bib so the build don't fails
    if not os.path.isfile(local_bib_file):
        with open(local_bib_file, "w"):
            pass


def rewrite_strong_to_subsection(content: str, extractable: list) -> str:
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
    seen_name: str | None = None
    shelved: list[str] = []
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
def get_folders(target_folder: str) -> list[str]:
    """
    Get all folders that have the target folder in their string
    """

    def collect_children(children: list, path: str, folders: list) -> None:
        """Recursively collection children"""
        for child in children:
            child_path = path + f"/{child['name']}"
            folders.append(child_path)
            if len(child["children"]):
                collect_children(child["children"], child_path, folders)

    foldertree_json = get_zephyr_api().folders.get_folders()
    folders: list = []
    collect_children(foldertree_json["children"], "", folders)
    target_folders: list = []
    for folder in folders:
        if folder.startswith(target_folder):
            target_folders.append(folder)
    return target_folders


def get_tspec(folder: str) -> str:
    sf = folder.split("/")
    for d in sf:
        sd = d.split("|")
        if len(sd) == 2:
            return sd[1]
    return ""


def _as_output_format(text: str, format: str) -> str:
    if Config.TEMPLATE_LANGUAGE != format:
        setattr(Config.DOC, Config.TEMPLATE_LANGUAGE, text.encode("utf-8"))
        text = getattr(Config.DOC, format).decode("utf-8")
    return text


def get_zephyr() -> ZephyrScale:
    """Requires token to be in the config"""
    if not Config.THE_ZEPHYR:
        if Config.ZEPHYR_TOKEN.startswith("set"):
            raise (
                Exception(
                    "The ZEPHYR_TOKEN has not be set - "
                    "Zephyr will fail to connect"
                )
            )
        Config.THE_ZEPHYR = ZephyrScale(
            base_url=Config.ATM_API, token=Config.ZEPHYR_TOKEN
        )
    return Config.THE_ZEPHYR


def get_zephyr_api() -> CloudApiWrapper:
    return get_zephyr().api


def get_rest_session() -> Session:
    """Requires JIRA_USER and JIRA_PASSWORD to be in the config"""
    if Config.THE_SESSION:
        return Config.THE_SESSION

    # initialize connection to Jira REST API
    usr_pwd = Config.AUTH[0] + ":" + Config.AUTH[1]
    connection_str = b64encode(usr_pwd.encode("ascii")).decode("ascii")
    headers: MutableMapping[str, str | bytes] = {
        "accept": "application/json",
        "authorization": "Basic %s" % connection_str,
        "Connection": "close",
    }
    rs: Session = requests.Session()
    rs.headers = headers
    Config.THE_SESSION = rs
    return rs


def get_key(pointer: dict, key: str = "self") -> str:
    """
    the self in some poinnters has the KEY embeded ..
    """
    parts = str(pointer[key]).split("/")
    for p in parts:
        if p.startswith(Config.PROJECT):
            return p
    return "NO_KEY_FOUND"


def get_id(pointer: dict, key: str = "id") -> str:
    return pointer[key]


def get_via_zephyr(url: str) -> dict:
    """Zephyr has a bunch of relative urls BUT frequntely returns FULL urls
    so temporarily store the base URL get the full url restore the base url.

    The Zephyr response is a json dict of the values
    returned from the url call.
    """

    rs = get_zephyr_api().session
    b4 = rs.base_url
    if url.startswith("http"):
        rs.base_url = ""
    result = rs.get(url)
    rs.base_url = b4
    return result


def get_value(pointer: dict | str, key: str = "self") -> str:
    """
    Given a dict there is a pointer in it which resolves to a name
    follow it and cache it.
    Sometimes zephyr returns a regular Jira api call,
    those are not authorized by the zephy token
    they require a regular JIRA session
    """
    if type(pointer) is str:
        return pointer
    if type(pointer) is dict:
        p = pointer[key]
    if p not in Config.CACHED_POINTERS:
        if p.startswith(Config.JIRA_INSTANCE):
            rs = get_rest_session()
            hresult = rs.get(p)
            hresult.raise_for_status()
            result: dict = hresult.json()
        else:
            result = get_via_zephyr(p)
        keys = ["name", "key", "id"]
        key = "unknown"
        for k in keys:
            if k in result:
                key = k
                break
        if key in result:
            Config.CACHED_POINTERS[p] = result[key]
        else:
            Config.CACHED_POINTERS[p] = result

    return Config.CACHED_POINTERS[p]


def fix_json(json: dict) -> dict:
    """Seems some nulls are in the Jason instead of None ..
    marshmallow is not happy"""
    for k, v in json.items():
        if v is None:
            json[k] = "None"
        elif type(v) is dict:
            json[k] = fix_json(v)
        elif type(v) is str:
            json[k] = v.replace("\u2060", "")  # some junky char in the jira
    return json


def get_teststeps(
    id: str, burl: str = paths.CloudPaths.CASE_STEPS
) -> List[dict]:
    """get all the test steps from the paginated url call"""
    steps = []
    max = 1000
    params = {"maxResults": str(max)}
    zapi = get_zephyr_api().session
    url = str.format(burl, id)
    b4 = zapi.base_url
    done = False
    index = 0
    startAt = 0
    while not done:
        resp = zapi.get(url, params=params)
        done = resp.get("isLast") is True
        if not done:
            url = resp.get("next")
            zapi.base_url = ""
            startAt += max
            params["startAt"] = str(startAt)
        if "values" in resp:
            inlines = resp.get("values", [])
            vals = [fix_json(i["inline"]) for i in inlines]
            # old system had an index ..
            # new one does not seem to so assume they are in order ..
            for v in vals:
                v["index"] = index
                index += 1
            steps += vals

    zapi.base_url = b4
    return steps


def get_execs(cycleId: str) -> List[dict]:
    """
    get execs for a given cycleId and cache them
    return the executions for this cycle
    """
    if cycleId in Config.CACHED_TEST_EXECUTIONS:
        return Config.CACHED_TEST_EXECUTIONS[cycleId]
    params = {}
    params["testCycle"] = cycleId
    tc_execs = get_tc_executions(params)
    Config.CACHED_TEST_EXECUTIONS[cycleId] = tc_execs
    return tc_execs


def get_testcase_executions(testCaseId: str) -> list[dict]:
    """
    Get all the test executions and cache them -
    can not get per cycle from the API.
    """
    if testCaseId in Config.CACHED_TEST_EXECUTIONS:
        tc_execs = Config.CACHED_TEST_EXECUTIONS[testCaseId]
        return tc_execs
    params = {}
    params["testCase"] = testCaseId
    tc_execs = get_tc_executions(params)
    Config.CACHED_TEST_EXECUTIONS[testCaseId] = tc_execs
    return tc_execs


def get_tc_executions(params: dict) -> list[dict]:
    """TestExecution call is paged - the parameters allow
    specification of testCase or Cycle which are the two
    ways we access executions.
    This  gets the results and caches them"""
    maxresults = 1000
    params["maxResults"] = str(maxresults)
    tc_execs = []
    burl = paths.CloudPaths.EXECUTIONS
    zapi = get_zephyr_api().session
    b4 = zapi.base_url
    done = False
    startAt = 0
    while not done:
        resp = zapi.get(burl, params=params)
        if "values" in resp:
            values = resp.get("values", [])
            done = resp.get("isLast") is True
            if not done:  # should only be one page really
                burl = resp.get("next")
                zapi.base_url = ""
                startAt += maxresults
                params["startAt"] = str(startAt)
            for exec in values:
                tc_execs.append(fix_json(exec))
    zapi.base_url = b4
    return tc_execs


def get_all_executions() -> None:
    """
    Get all the test executions and cache them -
    can not get per cycle from the API.
    """
    # params = {"query": f"cycleId = {cycleId}"}
    # NOT FOUND base =
    # "https://prod-api.zephyr4jiracloud.com/connect/public/rest/api/2.0/"
    # burl = paths.CloudPaths.ISLINKS_EXECS.format('LVV-R114')
    # CAN NOT USE ISSUELINKS - LVV-R is not an issue
    # burl = "rest/zapi/latest/zql/executeSearch" does nto exist
    max = 1000
    params = {}
    params["maxResults"] = str(max)
    burl = paths.CloudPaths.EXECUTIONS
    zapi = get_zephyr_api().session
    b4 = zapi.base_url
    done = False
    startAt = 0
    count = 0
    while not done:
        resp = zapi.get(burl, params=params)
        if "values" in resp:
            values = resp.get("values", [])
            done = resp.get("isLast") is True
            if not done:
                burl = resp.get("next")
                zapi.base_url = ""
                startAt += max
                params["startAt"] = str(startAt)
            for exec in values:
                count += 1
                project = get_value(exec["project"])
                if (
                    project.startswith(Config.PROJECT)
                    and exec["testCycle"] is not None
                ):
                    cycle = str(exec["testCycle"]["id"])
                    cycle_execs = []
                    if cycle in Config.CACHED_TEST_EXECUTIONS:
                        cycle_execs = Config.CACHED_TEST_EXECUTIONS[cycle]
                    else:
                        Config.CACHED_TEST_EXECUTIONS[cycle] = cycle_execs
                    cycle_execs.append(fix_json(exec))
    zapi.base_url = b4


def get_all(
    burl: str = paths.CloudPaths.EXECUTIONS,
    params: dict | None = None,
    baseurl: str | None = None,
) -> List[dict]:
    """get all the executions or whatever  from the paginated url call"""
    items = []
    zapi = get_zephyr_api().session
    b4 = zapi.base_url
    if baseurl:
        zapi.base_url = baseurl
    # there may be no real formating
    url = str.format(burl, id)
    done = False
    bparams = {"maxResults": "100"}
    if params:
        bparams.update(params)
    while not done:
        resp = zapi.get(url, params=bparams)
        if "values" in resp:
            values = [fix_json(v) for v in resp.get("values", [])]
            items += values
            done = resp.get("isLast") is True
    zapi.base_url = b4
    return values


def process_links(links: dict, item: str) -> List:
    """Zephy returns a Dict of dicts for related links
    If it is a value use it if its a http pointer follow it ..
    links is assumed to be a dict of differnt tytpes of links
    item is the type like 'issues'"""
    if item in links:
        items = []
        array_in = links[item]
        for anitem in array_in:
            # loop through the keys - look at value - follow it if its a link
            # construct a new dict with values no pointers
            newitem = {}
            for k in anitem.keys():
                if k != "self":
                    v = anitem[k]
                    if isinstance(v, str) and v.startswith("http"):
                        v = get_value(anitem, k)
                    newitem[k] = v
            items.append(newitem)

    return items
