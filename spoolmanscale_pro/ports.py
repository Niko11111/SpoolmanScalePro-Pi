"""The ports this service listens on. One place, because the page (CSP and
links), the proxy and the entry point all need them."""

# The page and its API.
PAGE_PORT = 80
# The paired scale's web interface, passed through (scale_proxy.py).
PROXY_PORT = 8081
