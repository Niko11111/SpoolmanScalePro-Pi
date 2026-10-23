"""Logging in to the FilaMan this Pi runs, as its admin, to make what the
scale needs: an API key and a device with a registration code.

FilaMan's own API (v1.4.3, read in its source):
  POST /auth/login                {email, password}  -> cookie session_id
  GET  /auth/me                   any logged-in request sets cookie csrf_token
  POST /api/v1/me/api-keys        {name}             -> {token: "uak...."}
  POST /api/v1/admin/devices      {name, device_type} -> {device_code}
  POST /auth/logout
Writing with a session needs header X-CSRF-Token equal to the csrf_token
cookie (core/middleware.py, CsrfMiddleware).
"""

import http.cookiejar
import json
import logging
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

REQUEST_TIMEOUT_S = 15
KEY_NAME = "SpoolmanScale"
DEVICE_NAME = "SpoolmanScale"


class FilamanError(Exception):
    """code: filaman_login_failed, filaman_unreachable, filaman_refused."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


class FilamanAdmin:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def _csrf(self) -> str:
        return next((c.value for c in self.jar if c.name == "csrf_token"), "")

    def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self._csrf():
            req.add_header("X-CSRF-Token", self._csrf())
        try:
            with self.opener.open(req, timeout=REQUEST_TIMEOUT_S) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            if path == "/auth/login" and e.code == 401:
                raise FilamanError("filaman_login_failed") from e
            raise FilamanError("filaman_refused", f"{method} {path}: HTTP {e.code}") from e
        except (urllib.error.URLError, OSError) as e:
            raise FilamanError("filaman_unreachable", str(e)) from e
        try:
            return json.loads(raw) if raw else {}
        except json.JSONDecodeError as e:
            raise FilamanError("filaman_refused", f"{path} gave no JSON") from e

    def login(self, email: str, password: str) -> None:
        self._call("POST", "/auth/login", {"email": email, "password": password})
        # The CSRF cookie comes with the first request after the login.
        self._call("GET", "/auth/me")

    def create_api_key(self) -> str:
        token = self._call("POST", "/api/v1/me/api-keys", {"name": KEY_NAME}).get("token", "")
        if not token:
            raise FilamanError("filaman_refused", "no API key in the answer")
        return token

    def create_device(self) -> str:
        code = self._call("POST", "/api/v1/admin/devices",
                          {"name": DEVICE_NAME, "device_type": "scale"}).get("device_code", "")
        if not code:
            raise FilamanError("filaman_refused", "no device code in the answer")
        return code

    def logout(self) -> None:
        try:
            self._call("POST", "/auth/logout")
        except FilamanError as e:
            log.info("FilaMan logout: %s", e)  # the session ends by itself
