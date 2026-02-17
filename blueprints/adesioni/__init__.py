from flask import Blueprint

adesioni_bp = Blueprint(
    "adesioni",
    __name__,
    url_prefix="/soci/adesioni"
)

from . import routes