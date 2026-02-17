# -*- coding: utf-8 -*-
import os
import sqlite3
from datetime import date
from werkzeug.utils import secure_filename

from flask import render_template, redirect, url_for, session, request, flash
from db import get_db_connection
from . import certificati_bp

# =================================================
# STORICO CERTIFICATI MEDICI SOCI (UNIFICATA)
# =================================================

@certificati_bp.route("/soci/certificati", methods=["GET", "POST"])
@certificati_bp.route("/soci/<int:socio_id>/certificati", methods=["GET", "POST"])
def storico_certificati_medici_socio(socio_id=None):

    # 🔧 FIX: recupera socio_id anche da GET
    if socio_id is None:
        socio_id = request.args.get("socio_id", type=int)

    # 🔧 FIX: recupera socio_id anche da POST (hidden input)
    if request.method == "POST" and socio_id is None:
        socio_id = request.form.get("socio_id", type=int)

    if "associazione_id" not in session:
        return redirect(url_for("start"))

    associazione_id = session["associazione_id"]
    anno = session.get("esercizio_anno") or date.today().year

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # -------------------------
    # SOCI (sempre)
    # -------------------------
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
    certificati = []
    abilitazioni_certificati = None
    edit_id = None
    edit_certificato = None

    # -------------------------
    # SE SOCIO SELEZIONATO
    # -------------------------
    if socio_id:
        socio = cur.execute(
            """
            SELECT *
            FROM soci
            WHERE id = ?
              AND associazione_id = ?
            """,
            (socio_id, associazione_id)
        ).fetchone()

        if not socio:
            conn.close()
            flash("Socio non trovato.", "error")
            return redirect(url_for("certificati_bp.storico_certificati_medici_socio"))       

        # -------------------------
        # ABILITAZIONI CERTIFICATI (per anno)
        # -------------------------
        row = cur.execute(
            """
            SELECT
                certificato_agonistico,
                certificato_non_agonistico
            FROM soci_abilitazioni_storico
            WHERE socio_id = ?
            AND associazione_id = ?
            AND anno = ?
            """,
            (socio_id, associazione_id, anno)
        ).fetchone()

        # default: NON abilitato
        abilitazioni_certificati = None

        if row:
            abil_ago = bool(row["certificato_agonistico"])
            abil_non = bool(row["certificato_non_agonistico"])

            if abil_ago or abil_non:
                abilitazioni_certificati = {
                    "agonistico": abil_ago,
                    "non_agonistico": abil_non
                }

        # -------------------------
        # EDIT MODE (GET ?edit_id=...)
        # -------------------------
        edit_id = request.args.get("edit_id", type=int)

        if edit_id:
            edit_certificato = cur.execute(
                """
                SELECT *
                FROM soci_certificati_medici
                WHERE id = ?
                AND socio_id = ?
                AND associazione_id = ?
                AND annullato = 0
                """,
                (edit_id, socio_id, associazione_id)
            ).fetchone()

            if not edit_certificato:
                flash("Certificato da modificare non trovato.", "error")
                return redirect(
                    url_for("certificati_bp.storico_certificati_medici_socio", socio_id=socio_id)
                )
            
        
        # -------------------------
        # POST → SALVA CERTIFICATO
        # -------------------------
        if request.method == "POST":

            tipo = request.form.get("tipo")
            data_rilascio = request.form.get("data_rilascio")
            data_scadenza = request.form.get("data_scadenza")

            if tipo not in ("AGONISTICO", "NON_AGONISTICO"):
                flash("Seleziona un tipo di certificato valido.", "error")
                return redirect(request.url)

            if not data_rilascio or len(data_rilascio) < 10:
                flash("Inserisci una data di rilascio valida.", "error")
                return redirect(request.url)

            if not data_scadenza or len(data_scadenza) < 10:
                flash("Inserisci una data di scadenza valida.", "error")
                return redirect(request.url)

            if data_scadenza < data_rilascio:
                flash("La scadenza non può essere precedente al rilascio.", "error")
                return redirect(request.url)           

            if not data_rilascio or len(data_rilascio) < 4:
                flash("Inserisci una data di rilascio valida.", "error")
                return redirect(request.url)
            # =========================
            # VALIDAZIONE ABILITAZIONI
            # in base all'anno di rilascio
            # =========================    
            anno_rilascio = int(data_rilascio[:4])
            row_abil = cur.execute(
                """
                SELECT
                    certificato_agonistico,
                    certificato_non_agonistico
                FROM soci_abilitazioni_storico
                WHERE socio_id = ?
                AND associazione_id = ?
                AND anno = ?
                """,
                (socio_id, associazione_id, anno_rilascio)
            ).fetchone()

            if not row_abil:
                flash(
                    f"Nessuna abilitazione certificati per l'anno {anno_rilascio}.",
                    "error"
                )
                return redirect(request.url)

            if tipo == "AGONISTICO" and not bool(row_abil["certificato_agonistico"]):
                flash(
                    f"Socio NON abilitato al certificato agonistico per l'anno {anno_rilascio}.",
                    "error"
                )
                return redirect(request.url)

            if tipo == "NON_AGONISTICO" and not bool(row_abil["certificato_non_agonistico"]):
                flash(
                    f"Socio NON abilitato al certificato non agonistico per l'anno {anno_rilascio}.",
                    "error"
                )
                return redirect(request.url)
            
            medico = request.form.get("medico")
            struttura = request.form.get("struttura")
            note = request.form.get("note")

            edit_id_post = request.form.get("edit_id")
            edit_id_post = int(edit_id_post) if edit_id_post else None
            
            if edit_id_post:
                # UPDATE
                cur.execute(
                    """
                    UPDATE soci_certificati_medici
                    SET tipo = ?,
                        data_rilascio = ?,
                        data_scadenza = ?,
                        medico = ?,
                        struttura = ?,
                        note = ?
                    WHERE id = ?
                      AND socio_id = ?
                      AND associazione_id = ?
                      AND annullato = 0
                    """,
                    (
                        tipo,
                        data_rilascio,
                        data_scadenza,
                        medico,
                        struttura,
                        note,
                        edit_id_post,
                        socio_id,
                        associazione_id
                    )
                )
                certificato_id = edit_id_post
                flash("Certificato aggiornato.", "success")
            else:
                # INSERT
                cur.execute(
                    """
                    INSERT INTO soci_certificati_medici
                    (
                        socio_id,
                        associazione_id,
                        tipo,
                        data_rilascio,
                        data_scadenza,
                        medico,
                        struttura,
                        note
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        socio_id,
                        associazione_id,
                        tipo,
                        data_rilascio,
                        data_scadenza,
                        medico,
                        struttura,
                        note
                    )
                )
                certificato_id = cur.lastrowid
                

            

            file = request.files.get("file_certificato")

            if file and file.filename:
                filename = secure_filename(file.filename)

                folder = f"uploads/documenti/{associazione_id}/certificati"
                os.makedirs(folder, exist_ok=True)

                file_path = os.path.join(folder, filename)
                file.save(file_path)

                cur.execute(
                    """
                    INSERT INTO documenti_file
                    (
                        associazione_id,
                        entita,
                        entita_id,
                        nome_originale,
                        file_path,
                        mime_type,
                        dimensione
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        associazione_id,
                        "CERTIFICATO_MEDICO",
                        certificato_id,
                        filename,
                        file_path,
                        file.mimetype,
                        os.path.getsize(file_path)
                    )
                )

            conn.commit()
            flash("Certificato caricato.", "success")

            return redirect(url_for(
                "certificati_bp.storico_certificati_medici_socio",
                socio_id=socio_id
            ))

        # -------------------------
        # STORICO CERTIFICATI
        # -------------------------
        certificati = cur.execute(
            """
            SELECT *,
                CASE
                    WHEN date(data_scadenza) >= date('now')
                    THEN 'VALIDO'
                    ELSE 'SCADUTO'
                END AS stato
            FROM soci_certificati_medici
            WHERE socio_id = ?
              AND associazione_id = ?
              AND annullato = 0
            ORDER BY data_scadenza DESC
            """,
            (socio_id, associazione_id)
        ).fetchall()

        certificati_con_file = []

        for c in certificati:
            files = cur.execute(
                """
                SELECT *
                FROM documenti_file
                WHERE associazione_id = ?
                AND entita = 'CERTIFICATO_MEDICO'
                AND entita_id = ?
                ORDER BY caricato_il DESC
                """,
                (associazione_id, c["id"])
            ).fetchall()

            certificati_con_file.append({
                **dict(c),
                "files": files
            })

        certificati = certificati_con_file

    conn.close()

    return render_template(
        "soci/certificati_storico.html",
        soci=soci,
        socio=socio,
        certificati=certificati,
        abilitazioni_certificati=abilitazioni_certificati,
        edit_certificato=edit_certificato
    )


# =================================================
# ELIMINA CERTIFICATO MEDICO
# =================================================
@certificati_bp.route(
    "/soci/certificati/<int:certificato_id>/elimina",
    methods=["POST"],
    endpoint="elimina_certificato_medico"
)
def elimina_certificato_medico(certificato_id):

    if "associazione_id" not in session:
        return redirect(url_for("start"))

    associazione_id = session["associazione_id"]

    conn = get_db_connection()
    cur = conn.cursor()

    # recupera socio_id (serve per redirect)
    row = cur.execute(
        """
        SELECT socio_id
        FROM soci_certificati_medici
        WHERE id = ?
          AND associazione_id = ?
        """,
        (certificato_id, associazione_id)
    ).fetchone()

    if not row:
        flash("Certificato non trovato.", "error")
        conn.close()
        return redirect(url_for("certificati_bp.storico_certificati_medici_socio"))

    socio_id = row["socio_id"]

    # soft delete (usa la colonna ESISTENTE: annullato)
    cur.execute(
        """
        UPDATE soci_certificati_medici
        SET annullato = 1
        WHERE id = ?
          AND associazione_id = ?
        """,
        (certificato_id, associazione_id)
    )

    conn.commit()
    conn.close()

    flash("Certificato annullato.", "success")
    return redirect(url_for(
        "certificati_bp.storico_certificati_medici_socio",
        socio_id=socio_id
    ))

