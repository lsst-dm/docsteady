# debug entry point
from docsteady import cli
import sys

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module='bs4')

if __name__ == '__main__':
    sys.exit(cli.main())
