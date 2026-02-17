# -*- coding: utf-8 -*-
from flask import Blueprint

soci_bp = Blueprint("soci_bp", __name__)

import sqlite3
from flask import render_template, redirect, url_for, session, request, flash
from db import get_db_connection




from . import routes  # noqa: F401