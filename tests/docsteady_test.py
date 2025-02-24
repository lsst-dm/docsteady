from unittest import TestCase

from bs4 import BeautifulSoup
from DocsteadyTestUtils import read_test_data

# from DocsteadyTestUtils import getTplanData,
from marshmallow import EXCLUDE

from docsteady.config import Config
from docsteady.tplan import TestPlan
from docsteady.utils import download_and_rewrite_images, fix_json


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
        # steo through genertion of LVV-P90 DMTR-331 -
        # uncomment this call to remake the test json file
        # data = getTplanData()
        data = read_test_data("tplandata")
        Config.CACHED_USERS["womullan"] = {"displayName": "wil"}
        Config.CACHED_USERS["gpdf"] = {
            "displayName": "Gregory Dubois-Felsmann"
        }
        Config.CACHED_USERS["mareuter"] = {"displayName": "Michael Reuter"}
        Config.CACHED_POINTERS[
            "https://api.zephyrscale.smartbear.com/v2/folders/18157119"
        ] = "Data Management"
        Config.CACHED_POINTERS[
            "https://api.zephyrscale.smartbear.com/v2/statuses/7920149"
        ] = "Approved"
        data = fix_json(data)
        testplan: dict = TestPlan(unknown=EXCLUDE).load(data)
        self.assertEqual(
            testplan["name"], "LDM-503-EFDb: Replication of Summit EFD to USDF"
        )
