from flask import (
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_file,
    abort
)

import sqlite3 
from . import adesioni_bp
from utils.documenti import attach_documento
from db import get_db_connection
import os

# =================================================
# ADESIONI
# =================================================
@adesioni_bp.route("/", methods=["GET"])
@adesioni_bp.route("/<int:socio_id>", methods=["GET"])
def adesioni_socio(socio_id=None):

    if "associazione_id" not in session:
        return redirect(url_for("start"))

    associazione_id = session["associazione_id"]

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # elenco soci (per select)
    soci = cur.execute(
        """
        SELECT id, cognome, nome
        FROM soci
        WHERE associazione_id = ?
        ORDER BY cognome, nome
        """,
        (associazione_id,)
    ).fetchall()

    socio = None
    anni = []

    if not socio_id:
        socio_id = request.args.get("socio_id", type=int)

    if socio_id:
        socio = cur.execute(
            """
            SELECT id, nome, cognome
            FROM soci
            WHERE id = ? AND associazione_id = ?
            """,
            (socio_id, associazione_id)
        ).fetchone()
    

    ha_enti = cur.execute(
            """
            SELECT COUNT(*) as cnt
            FROM enti_affiliazione
            WHERE associazione_id = ?
            """,
            (associazione_id,)
        ).fetchone()["cnt"] > 0

    moduli = cur.execute(
        """
        SELECT anno_riferimento AS anno
        FROM documenti_file
        WHERE associazione_id = ?
        AND entita = 'ADESIONE_SOCIO'
        AND entita_id = ?
        """,
        (associazione_id, socio_id)
    ).fetchall()

    anni_con_modulo = {int(r["anno"]) for r in moduli}

    # -------------------------
    # ANNO DI INGRESSO SOCIO
    # -------------------------
    anno_ingresso = None

    if socio:
        row_ingresso = cur.execute(
            """
            SELECT data_ingresso
            FROM soci
            WHERE id = ?
            AND associazione_id = ?
            """,
            (socio_id, associazione_id)
        ).fetchone()

        if row_ingresso and row_ingresso["data_ingresso"]:
            anno_ingresso = int(row_ingresso["data_ingresso"][:4])

    from datetime import date
    anno_corrente = date.today().year

    if anno_ingresso:
        anni = list(range(anno_ingresso - 1, anno_corrente + 1))
    else:
        anni = []

    

    conn.close()


    # -------------------------
    # ADESIONI / RINNOVI (BASE)
    # -------------------------
    righe_adesioni = []

    for anno in anni:

        # anni prima dell’ingresso
        if anno < anno_ingresso:
            stato = "GRIGIO"

        else:
            if ha_enti:
                # adesione + rinnovi annuali
                stato = "VERDE" if anno in anni_con_modulo else "ROSSO"
            else:
                # solo adesione iniziale
                stato = "VERDE" if anno_ingresso in anni_con_modulo else "ROSSO"

        righe_adesioni.append({
            "anno": anno,
            "stato": stato
        })

    return render_template(
        "soci/adesioni.html",
        soci=soci,
        socio=socio,
        righe_adesioni=righe_adesioni

    )


# =================================================
# ROUTE DI STAMPA ADESIONI 
# =================================================

@adesioni_bp.route("/<int:socio_id>/<int:anno>/stampa")
def stampa_adesione(socio_id, anno):

    if "associazione_id" not in session:
        return redirect(url_for("start"))

    associazione_id = session["associazione_id"]

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    socio = cur.execute(
        """
        SELECT *
        FROM soci
        WHERE id = ? AND associazione_id = ?
        """,
        (socio_id, associazione_id)
    ).fetchone()

    associazione = cur.execute(
        """
        SELECT denominazione
        FROM associazioni
        WHERE id = ?
        """,
        (associazione_id,)
    ).fetchone()

    conn.close()

    if not socio:
        abort(404)

    return render_template(
        "soci/adesione_stampa.html",
        socio=socio,
        associazione=associazione,
        anno=anno
    )

# =================================================
# ROUTE UPLOAD ADESIONI 
# =================================================

@adesioni_bp.route("/<int:socio_id>/<int:anno>/upload", methods=["POST"])
def upload_adesione(socio_id, anno):

    if "associazione_id" not in session:
        return redirect(url_for("start"))

    associazione_id = session["associazione_id"]

    file = request.files.get("file_adesione")
    if not file or not file.filename:
        flash("Nessun file selezionato.", "error")
        return redirect(request.referrer)

    from werkzeug.utils import secure_filename
    import os

    filename = secure_filename(f"adesione_{anno}_{file.filename}")

    folder = f"uploads/documenti/{associazione_id}/adesioni"
    os.makedirs(folder, exist_ok=True)

    file_path = os.path.join(folder, filename)
    file.save(file_path)

    conn = get_db_connection()
    cur = conn.cursor()

    # ✅ rimuove eventuale modulo per stesso socio + stesso anno
    cur.execute(
        """
        DELETE FROM documenti_file
        WHERE associazione_id = ?
          AND entita = 'ADESIONE_SOCIO'
          AND entita_id = ?
          AND anno_riferimento = ?
        """,
        (associazione_id, socio_id, anno)
    )

    # ✅ INSERT CON anno_riferimento
    cur.execute(
        """
        INSERT INTO documenti_file (
            associazione_id,
            entita,
            entita_id,
            anno_riferimento,
            nome_originale,
            file_path,
            mime_type,
            dimensione
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            associazione_id,
            "ADESIONE_SOCIO",
            socio_id,
            anno,
            file.filename,      # nome reale del file
            file_path,
            file.mimetype,
            os.path.getsize(file_path)
        )
    )

    conn.commit()
    conn.close()

    flash("Modulo caricato correttamente.", "success")
    return redirect(request.referrer)

# =================================================
# ROUTE VISUALIZZA ADESIONE
# =================================================

from flask import send_file, abort
import os

@adesioni_bp.route("/<int:socio_id>/<int:anno>/view")
def view_adesione(socio_id, anno):

    if "associazione_id" not in session:
        return redirect(url_for("start"))

    associazione_id = session["associazione_id"]

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    row = cur.execute(
        """
        SELECT file_path
        FROM documenti_file
        WHERE associazione_id = ?
        AND entita = 'ADESIONE_SOCIO'
        AND entita_id = ?
        AND anno_riferimento = ?
        ORDER BY caricato_il DESC
        LIMIT 1
        """,
        (associazione_id, socio_id, anno)
    ).fetchone()

    conn.close()

    if not row:
        abort(404)

    file_path = row["file_path"]

    # 🔴 FIX CHIAVE: path assoluto
    file_path = os.path.abspath(file_path)

    if not os.path.exists(file_path):
        abort(404)

    return send_file(
        file_path,
        as_attachment=False
    )


# =================================================
# ROUTE ELIMINA ADESIONE
# =================================================
@adesioni_bp.route("/<int:socio_id>/<int:anno>/delete", methods=["POST"])
def delete_adesione(socio_id, anno):

    if "associazione_id" not in session:
        return redirect(url_for("start"))

    associazione_id = session["associazione_id"]

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # recupero file
    row = cur.execute(
        """
        SELECT id, file_path
        FROM documenti_file
        WHERE associazione_id = ?
          AND entita = 'ADESIONE_SOCIO'
          AND entita_id = ?
          AND anno_riferimento = ?
        """,
        (associazione_id, socio_id, anno)
    ).fetchone()

    if not row:
        conn.close()
        flash("Modulo non trovato.", "error")
        return redirect(request.referrer)

    file_path = row["file_path"]
    doc_id = row["id"]

    # elimina DB
    cur.execute(
        "DELETE FROM documenti_file WHERE id = ?",
        (doc_id,)
    )

    conn.commit()
    conn.close()

    # elimina file fisico (se esiste)
    import os
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except Exception:
        # non blocchiamo il flusso per errori filesystem
        pass

    flash("Modulo eliminato correttamente.", "info-soft")
    return redirect(request.referrer)
