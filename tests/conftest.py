"""Points the service at a throwaway data directory before any test imports
it: paths.py reads SSPRO_DATA_DIR once, at import."""

import os
import tempfile

os.environ["SSPRO_DATA_DIR"] = tempfile.mkdtemp(prefix="sspro-test-")
