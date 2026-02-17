# -*- coding: utf-8 -*-
from flask import Blueprint

quote_bp = Blueprint("quote_bp", __name__)

from . import routes  # noqa: F401