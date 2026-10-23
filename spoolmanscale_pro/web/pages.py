"""The page shell. Everything after it is drawn by static/js from /api."""

from flask import Blueprint, render_template

from ..version import APP_VERSION

bp = Blueprint("pages", __name__)


@bp.get("/")
def index():
    return render_template("index.html", version=APP_VERSION)
