# -*- coding: utf-8 -*-
import sqlite3
from datetime import date

from flask import render_template, redirect, url_for, session, request, flash
from db import get_db_connection
from . import tesseramenti_bp

# =================================================
# STORICO TESSERAMENTI SOCI (UNIFICATA)
# =================================================
@tesseramenti_bp.route("/soci/tesseramenti", methods=["GET"])
@tesseramenti_bp.route("/soci/<int:socio_id>/tesseramenti", methods=["GET", "POST"])
def storico_tesseramenti_socio(socio_id=None):
    if "associazione_id" not in session:
        return redirect(url_for("start"))

    from datetime import date

    associazione_id = session["associazione_id"]
    oggi = date.today()

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # -------------------------
    # ELENCO SOCI (PER SELECT)
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

    # -------------------------
    # SE SOCIO NON SELEZIONATO
    # (provo a leggerlo da ?socio_id=...)
    # -------------------------
    if not socio_id:
        socio_id = request.args.get("socio_id", type=int)

    if not socio_id:
        conn.close()
        return render_template(
            "soci/tesseramenti_storico.html",
            socio=None,
            soci=soci,
            enti=[],
            tesseramenti=[],
            oggi=oggi,
            edit_tesseramento=None
        )

    # -------------------------
    # SOCIO SELEZIONATO
    # -------------------------
    socio = cur.execute(
        """
        SELECT id, nome, cognome
        FROM soci
        WHERE id = ? AND associazione_id = ?
        """,
        (socio_id, associazione_id)
    ).fetchone()

    if not socio:
        conn.close()
        flash("Socio non trovato.", "error")
        return redirect(url_for("storico_tesseramenti_socio"))

    # -------------------------
    # EDIT MODE (GET ?edit_id=...)
    # -------------------------
    edit_id = request.args.get("edit_id", type=int)
    edit_tesseramento = None

    if edit_id:
        edit_tesseramento = cur.execute(
            """
            SELECT *
            FROM soci_tesseramenti
            WHERE id = ?
              AND socio_id = ?
              AND associazione_id = ?
            """,
            (edit_id, socio_id, associazione_id)
        ).fetchone()

        if not edit_tesseramento:
            flash("Tesseramento da modificare non trovato.", "error")
            return redirect(
                url_for("storico_tesseramenti_socio", socio_id=socio_id)
            )

    # -------------------------
    # ENTI AFFILIAZIONE
    # -------------------------
    enti = cur.execute(
        """
        SELECT id, nome
        FROM enti_affiliazione
        WHERE associazione_id = ?
        ORDER BY nome
        """,
        (associazione_id,)
    ).fetchall()

    enti_map = {str(e["id"]): e["nome"] for e in enti}

    # -------------------------
    # INSERIMENTO / MODIFICA TESSERAMENTO
    # -------------------------
    if request.method == "POST":

        ente_id = request.form.get("ente_affiliazione_id")
        data_emissione = request.form.get("data_emissione")
        data_scadenza = request.form.get("data_scadenza")
        numero_tessera = request.form.get("numero_tessera")

        # ---- validazioni base ----
        if not ente_id or not data_emissione or not data_scadenza:
            flash("Compila tutti i campi obbligatori.", "error")
            return redirect(request.url)

        # ---- anno di riferimento (da data emissione) ----
        if len(data_emissione) < 4:
            flash("Data di emissione non valida.", "error")
            return redirect(request.url)

        anno_emissione = int(data_emissione[:4])

        row_abil = get_abilitazioni_tesseramento(
            cur,
            socio_id,
            associazione_id,
            anno_emissione
        )

        if not row_abil:
            flash(
                f"Il socio non è abilitato al tesseramento per l’anno {anno_emissione}.",
                "error"
            )
            return redirect(request.url)

        # 🔴 LEGGI edit_id DAL FORM
        edit_id_post = request.form.get("edit_id")
        edit_id_post = int(edit_id_post) if edit_id_post else None

        # -------------------------
        # VERIFICA ABILITAZIONE ENTE PER ANNO
        # -------------------------

        if not row_abil:
            flash(
                f"Il socio non è abilitato al tesseramento per l’anno {anno_emissione}.",
                "error"
            )
            return redirect(request.url)

        # nome dell'ente selezionato (da ID)
        ente_nome_scelto = (enti_map.get(str(ente_id)) or "").strip().lower()

        # enti abilitati dal DB (nomi)
        enti_abilitati_raw = row_abil["enti_tesseramento"] or ""
        enti_abilitati = [
            e.strip().lower()
            for e in enti_abilitati_raw.replace(";", ",").split(",")
            if e.strip()
        ]

        if ente_nome_scelto not in enti_abilitati:
            flash(
                f"Il socio NON è abilitato all’ente selezionato per l’anno {anno_emissione}.",
                "error"
            )
            return redirect(request.url)

        # -------------------------
        # UPDATE vs INSERT
        # -------------------------
        if edit_id_post:
            # UPDATE
            cur.execute(
                """
                UPDATE soci_tesseramenti
                SET ente_id = ?,
                    data_inizio = ?,
                    data_scadenza = ?,
                    numero_tessera = ?
                WHERE id = ?
                AND socio_id = ?
                AND associazione_id = ?
                """,
                (
                    ente_id,
                    data_emissione,
                    data_scadenza,
                    numero_tessera,
                    edit_id_post,
                    socio_id,
                    associazione_id
                )
            )
            flash("Tesseramento aggiornato correttamente.", "success")

        else:
            # INSERT
            cur.execute(
                """
                INSERT INTO soci_tesseramenti (
                    associazione_id,
                    socio_id,
                    ente_id,
                    data_inizio,
                    data_scadenza,
                    numero_tessera
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    associazione_id,
                    socio_id,
                    ente_id,
                    data_emissione,
                    data_scadenza,
                    numero_tessera
                )
            )
            flash("Tesseramento inserito correttamente.", "success")

        conn.commit()
        return redirect(url_for("storico_tesseramenti_socio", socio_id=socio_id))




    # -------------------------
    # TESSERAMENTI STORICI
    # -------------------------
    righe = cur.execute(
        """
        SELECT
            st.id,
            e.nome AS ente_nome,
            st.data_inizio,
            st.data_scadenza,
            st.numero_tessera,
            st.validato_manualmente,
            st.file_path
        FROM soci_tesseramenti st
        JOIN enti_affiliazione e
            ON e.id = st.ente_id
        WHERE st.associazione_id = ?
        AND st.socio_id = ?
        ORDER BY st.data_inizio DESC
        """,
        (associazione_id, socio_id)
    ).fetchall()

    tesseramenti = []
    for r in righe:
        if r["data_scadenza"] < oggi.isoformat():
            stato = "SCADUTO"
        else:
            stato = "VALIDO"

        tesseramenti.append({**dict(r), "stato": stato})

    conn.close()

    return render_template(
        "soci/tesseramenti_storico.html",
        socio=socio,
        soci=soci,
        enti=enti,
        tesseramenti=tesseramenti,
        oggi=oggi,
        edit_tesseramento=edit_tesseramento
    )

# =================================================
# ELIMINA TESSERAMENTO SOCIO (ERRORE INSERIMENTO)
# =================================================
@tesseramenti_bp.route("/soci/tesseramenti/<int:tesseramento_id>/elimina", methods=["POST"])
def elimina_tesseramento(tesseramento_id):
    if "associazione_id" not in session:
        return redirect(url_for("start"))

    associazione_id = session["associazione_id"]

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM soci_tesseramenti
        WHERE id = ?
          AND associazione_id = ?
        """,
        (tesseramento_id, associazione_id)
    )

    conn.commit()
    conn.close()

    flash("Tesseramento eliminato definitivamente.", "success")
    return redirect(request.referrer or url_for("dashboard_soci"))
