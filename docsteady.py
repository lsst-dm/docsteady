# debug entry point
import sys

# there are reams of warnings from inside BeautifulSoup about handles and urls.
# can not  find how to fix the warings which have no impact, so ignoring.
import warnings

from docsteady import cli

warnings.filterwarnings("ignore", category=UserWarning, module="bs4")

if __name__ == "__main__":
    sys.exit(cli.main())