"""Asks a backend whether it is ready.

"Ready" means its own health route answers 200. A running container is not
enough: Spoolman and FilaMan run their database migrations after the
container has started, and answer nothing useful until those are done.
"""

import logging
import time
import urllib.error
import urllib.request

from .backends import Backend

log = logging.getLogger(__name__)

PROBE_TIMEOUT_S = 3
PROBE_INTERVAL_S = 2
# Generous on purpose. FilaMan's first start on a Pi 3 migrates its database
# and renders its label assets before it answers.
READY_TIMEOUT_S = 240

# The backends publish their port on the host, so the service reaches them
# the way the scale does.
BACKEND_HOST = "127.0.0.1"


def backend_url(backend: Backend, host: str = BACKEND_HOST) -> str:
    return f"http://{host}:{backend.port}"


def is_ready(backend: Backend) -> bool:
    url = backend_url(backend) + backend.health_path
    try:
        with urllib.request.urlopen(url, timeout=PROBE_TIMEOUT_S) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False  # not up yet, which is the normal answer while starting


def wait_until_ready(backend: Backend, timeout_s: int = READY_TIMEOUT_S,
                     sleep=time.sleep, clock=time.monotonic) -> bool:
    deadline = clock() + timeout_s
    while clock() < deadline:
        if is_ready(backend):
            return True
        sleep(PROBE_INTERVAL_S)
    log.warning("%s did not answer its health route within %d s", backend.key, timeout_s)
    return False
