from flask import Blueprint

scadenziario_bp = Blueprint("scadenziario_bp", __name__)

from . import routes  # noqa: F401,E402