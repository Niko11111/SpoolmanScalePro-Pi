"""Points the service at a throwaway data directory before any test imports
it: paths.py reads SSPRO_DATA_DIR once, at import. Then creates the folders
in it, as the service does at start."""

import os
import tempfile

os.environ["SSPRO_DATA_DIR"] = tempfile.mkdtemp(prefix="sspro-test-")

from spoolmanscale_pro import paths  # noqa: E402  (after the variable above)

paths.ensure_data_dirs()
