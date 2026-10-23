"""The two shapes every /api route answers with.

Success: {"ok": true, ...}. Failure: {"ok": false, "error": "<code>"} with a
fitting HTTP status. The code is what the page translates
(static/i18n/*.js, key "err.<code>"); it is never a sentence.
"""

from flask import jsonify


def ok(status: int = 200, **data):
    return jsonify({"ok": True, **data}), status


def fail(code: str, status: int = 400, **data):
    return jsonify({"ok": False, "error": code, **data}), status
