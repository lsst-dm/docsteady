# debug entry point
from docsteady import cli
import sys

# there are reams of warnings from inside BeautifulSoup about fles handles and urls.
# I have been unable to find how to fix the warings which have no impact, so supressing.
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module='bs4')

if __name__ == '__main__':
    sys.exit(cli.main())
