import unittest

from docsteady.config import Config
from docsteady.utils import get_zephy_image


class TestGetImage(unittest.TestCase):
    def test_image(self) -> None:
        # images look like
        imgo = (
            "tenant/eda8235d-f9b3-3651-"
            "8805-cde8801fc677/project/10277/"
            "35b0a167-34ab-4a4d-8589-9db890355489-1686940252586.png"
        )

        img = (
            "https://cloudfront.tm4j.smartbear.com/tenant/eda8235d-f9b3-3651-"
            "8805-cde8801fc677/project/10277/35b0a167-34ab-4a4d-8589-"
            "9db890355489-1686940252586.png"
        )
        img = f"{img}{imgo}"
        # and the standard auth seems to fail

        if not Config.ZEPHYR_TOKEN.startswith("set"):
            resp = get_zephy_image(img)
            self.assertFalse(resp is None)

            # will fail until I get a fix from zephyr - which they say never
            # self.assertTrue(resp.ok)


python_classes = "TestCase"
