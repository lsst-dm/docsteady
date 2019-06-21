from bs4 import BeautifulSoup
from unittest import TestCase
from docsteady.utils import download_and_rewrite_images
from docsteady.config import Config


class TestHtmlPandocField(TestCase):

    def test_download(self):
        Config.DOWNLOAD_IMAGES = False
        has_json_text = 'The default catalog (SDSS Stripe 82, 2013 LSST Processing) is fine for this.<br><br>Choose columns to return by:<br>1) unchecking the top box in the column selection box<br>2) checking columns for id, coord_ra, coord_dec, and parent.<br><br>The result should look like the following:<br>&nbsp;<img src=\"../rest/tests/1.0/attachment/image/244\" style=\"width: 300px;\" class=\"fr-fic fr-fil fr-dii\"><br>'
        value = download_and_rewrite_images(has_json_text)
        soup = BeautifulSoup(value.encode("utf-8"), "html.parser")
        self.assertEqual(soup.find("img")["src"], "rest/tests/1.0/attachment/image/244")
