from flask import (
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from . import impostazioni_bp
from db import get_db_connection
import sqlite3

@impostazioni_bp.route("/associazione", methods=["GET", "POST"])
def associazione():

    if "associazione_id" not in session:
        return redirect(url_for("start"))

    associazione_id = session["associazione_id"]

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ==========================
    # POST → SALVATAGGIO
    # ==========================
    if request.method == "POST":

        denominazione = request.form.get("denominazione", "").strip()
        codice_fiscale = request.form.get("codice_fiscale", "").strip()
        indirizzo = request.form.get("indirizzo", "").strip()
        civico = request.form.get("civico", "").strip()
        cap = request.form.get("cap", "").strip()
        citta = request.form.get("citta", "").strip()
        provincia = request.form.get("provincia", "").strip()
        pec = request.form.get("pec", "").strip()
        partita_iva = request.form.get("partita_iva", "").strip()

        # VALIDAZIONE OBBLIGATORI
        if not all([denominazione, codice_fiscale, indirizzo, civico, cap, citta, provincia]):
            flash("Compila tutti i campi obbligatori.", "danger")
        else:
            cur.execute(
                """
                UPDATE associazioni
                SET denominazione = ?,
                    codice_fiscale = ?,
                    indirizzo = ?,
                    civico = ?,
                    cap = ?,
                    citta = ?,
                    provincia = ?,
                    pec = ?,
                    partita_iva = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    denominazione,
                    codice_fiscale,
                    indirizzo,
                    civico,
                    cap,
                    citta,
                    provincia,
                    pec or None,
                    partita_iva or None,
                    associazione_id
                )
            )

            conn.commit()

            # aggiorna sessione (per header)
            session["associazione_nome"] = denominazione
            session["associazione_codice_fiscale"] = codice_fiscale

            flash("Anagrafica associazione aggiornata.", "info-soft")

    # ==========================
    # GET (o dopo POST)
    # ==========================
    associazione = cur.execute(
        "SELECT * FROM associazioni WHERE id = ?",
        (associazione_id,)
    ).fetchone()

    conn.close()

    return render_template(
        "impostazioni/associazione.html",
        associazione=associazione
    )