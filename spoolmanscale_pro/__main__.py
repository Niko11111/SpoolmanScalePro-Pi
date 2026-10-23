"""Entry point: python -m spoolmanscale_pro [--host H] [--port P]

Serves the application with waitress, a production WSGI server in pure
Python. The systemd unit (system/spoolmanscale-pro.service) runs exactly
this, and so does a developer on a laptop with SSPRO_DATA_DIR set.
"""

import argparse
import logging

from waitress import serve

from .web import create_app

DEFAULT_PORT = 80
# Enough for a few browsers polling and one long upload at once. Each
# thread costs little; the jobs run in a thread of their own.
SERVER_THREADS = 6


def main() -> None:
    parser = argparse.ArgumentParser(prog="spoolmanscale_pro")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    serve(create_app(), host=args.host, port=args.port, threads=SERVER_THREADS,
          ident="spoolmanscale-pro")


if __name__ == "__main__":
    main()
