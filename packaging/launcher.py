"""Entry point for the PyInstaller executable."""

import sys

from taxnetlab.cli import main

if __name__ == "__main__":
    sys.exit(main())
