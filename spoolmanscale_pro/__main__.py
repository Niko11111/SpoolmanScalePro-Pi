"""Entry point: python -m spoolmanscale_pro [--host H] [--port P]

Serves the application with waitress, a production WSGI server in pure
Python. The systemd unit (system/spoolmanscale-pro.service) runs exactly
this, and so does a developer on a laptop with SSPRO_DATA_DIR set.
"""

import argparse
import logging
import threading

from waitress import serve

from .ports import PAGE_PORT, PROXY_PORT
from .scale_proxy import create_proxy_app
from .web import create_app

# Enough for a few browsers polling and one long upload at once. Each
# thread costs little; the jobs run in a thread of their own.
SERVER_THREADS = 6
# The scale's pages load a handful of files at once.
PROXY_THREADS = 4


def main() -> None:
    parser = argparse.ArgumentParser(prog="spoolmanscale_pro")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=PAGE_PORT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    app = create_app()
    # The scale's web interface on a port of its own (scale_proxy.py).
    proxy = threading.Thread(target=serve, args=(create_proxy_app(args.port),), daemon=True, name="scale-proxy",
                             kwargs={"host": args.host, "port": PROXY_PORT, "threads": PROXY_THREADS,
                                     "ident": "spoolmanscale-pro"})
    proxy.start()
    serve(app, host=args.host, port=args.port, threads=SERVER_THREADS, ident="spoolmanscale-pro")


if __name__ == "__main__":
    main()
