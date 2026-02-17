from flask import Blueprint

tesseramenti_bp = Blueprint("tesseramenti_bp", __name__)

from . import routes  # noqa: F401