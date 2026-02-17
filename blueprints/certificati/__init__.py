from flask import Blueprint

certificati_bp = Blueprint("certificati_bp", __name__)

from . import routes  # noqa: F401