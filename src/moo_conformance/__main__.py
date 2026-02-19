"""Allow running as: python -m moo_conformance --moo-port=9898"""

import sys

from .cli import main

sys.exit(main())
