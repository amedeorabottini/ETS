from flask import Blueprint

gestione_soci_bp = Blueprint(
    "gestione_soci",
    __name__,
    url_prefix="/soci/gestione"
)

from . import routes