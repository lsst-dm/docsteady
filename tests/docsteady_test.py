import json
import os
from unittest import TestCase

from bs4 import BeautifulSoup
from marshmallow import EXCLUDE

from docsteady.config import Config
from docsteady.tplan import TestPlan
from docsteady.utils import download_and_rewrite_images


class TestHtmlPandocField(TestCase):
    def test_download(self) -> None:
        Config.DOWNLOAD_IMAGES = False
        has_json_text = r"""The default catalog
        (SDSS Stripe 82, 2013 LSST Processing)
        is fine for this.<br><br>Choose columns to return by:<br>1)
        unchecking the top
        box in the column selection box<br>2) checking columns for
        id, coord_ra, coord_dec, and parent.
        <br><br>
        The result should look like the following:
        <br>&nbsp;<img src="../rest/tests/1.0/attachment/image/244"
        style="width: 300px;" class="fr-fic fr-fil fr-dii"><br>"""
        value = download_and_rewrite_images(has_json_text)
        soup = BeautifulSoup(value.encode("utf-8"), "html.parser")
        self.assertEqual(soup.find("img")["src"], "jira_imgs/244")


class TestTplan(TestCase):
    def test_tplan(self) -> None:
        cwd = os.getcwd()
        print(cwd)
        fn = "./data/tplandata.json"
        with open(fn) as f:
            data = json.load(f)
        Config.CACHED_USERS["womullan"] = {"displayName": "wil"}
        Config.CACHED_USERS["gpdf"] = {
            "displayName": "Gregory Dubois-Felsmann"
        }
        Config.CACHED_USERS["mareuter"] = {"displayName": "Michael Reuter"}
        testplan: dict = TestPlan(unknown=EXCLUDE).load(data)
        self.assertEqual(
            testplan["name"], "LDM-503-EFDb: Replication of Summit EFD to USDF"
        )
