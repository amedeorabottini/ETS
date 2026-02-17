# -*- coding: utf-8 -*-
from flask import Blueprint

ricevute_bp = Blueprint("ricevute_bp", __name__)

from . import routes  # noqa: F401