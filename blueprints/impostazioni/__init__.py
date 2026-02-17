from flask import Blueprint

impostazioni_bp = Blueprint(
    "impostazioni",
    __name__,
    url_prefix="/impostazioni"
)

# ⬇️ IMPORT DELLE ROUTE (OBBLIGATORIO)
from . import routes