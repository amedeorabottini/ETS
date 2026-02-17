# -*- coding: utf-8 -*-
# Qui metteremo tutte le route del modulo "Quote"

from . import quote_bp
import sqlite3
from flask import render_template, redirect, url_for, session, request, flash
from db import get_db_connection

# =================================================
# GESTIONE QUOTE (ANAGRAFICA)
# =================================================
@quote_bp.route("/quote", methods=["GET", "POST"])
def gestione_quote():
    if "associazione_id" not in session:
        return redirect(url_for("start"))

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # -------------------------
    # ✅ GARANTISCI QUOTA ASSOCIATIVA DI SISTEMA (ANNUALE)
    # -------------------------
    qa = cur.execute(
        """
        SELECT id
        FROM quote
        WHERE associazione_id = ?
          AND is_quota_associativa = 1
        LIMIT 1
        """,
        (session["associazione_id"],)
    ).fetchone()

    if not qa:
        # crea quota associativa di default (editabile, non eliminabile)
        cur.execute(
            """
            INSERT INTO quote (
                associazione_id, nome, descrizione, importo, periodicita, attiva, is_quota_associativa
            )
            VALUES (?, ?, ?, ?, 'ANNUALE', 1, 1)
            """,
            (
                session["associazione_id"],
                "Quota associativa",
                "Quota associativa annuale (di sistema)",
                0.0
            )
        )
        conn.commit()

    # -------------------------
    # INSERIMENTO NUOVA QUOTA
    # -------------------------
    if request.method == "POST":
        print("POST /quote:", dict(request.form))
        try:
            cur.execute(
                """
                INSERT INTO quote (
                    associazione_id,
                    nome,
                    descrizione,
                    importo,
                    periodicita,
                    is_quota_associativa
                )
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                (
                    session["associazione_id"],
                    request.form["nome"].strip(),
                    (request.form.get("descrizione") or "").strip(),
                    float(request.form["importo"]),
                    request.form["periodicita"]
                )
            )
            conn.commit()
            flash("Quota creata correttamente.", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Errore creazione quota: {e}", "error")
        finally:
            conn.close()

        # 🔥 FONDAMENTALE: evita duplicati su refresh
        return redirect(url_for("gestione_quote"))

    # -------------------------
    # ELENCO QUOTE (SOLO GET)
    # -------------------------
    quote = cur.execute(
        """
        SELECT *
        FROM quote
        WHERE associazione_id = ?
        ORDER BY id DESC
        """,
        (session["associazione_id"],)
    ).fetchall()

    conn.close()
    return render_template("quote.html", quote=quote)

   

# =================================================
# MODIFICA QUOTE (ANAGRAFICA)
# =================================================

@quote_bp.route("/quote/modifica/<int:quota_id>", methods=["GET", "POST"])
def modifica_quota(quota_id):
    if "associazione_id" not in session:
        return redirect(url_for("start"))

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    quota = cur.execute(
        """
        SELECT *
        FROM quote
        WHERE id = ? AND associazione_id = ?
        """,
        (quota_id, session["associazione_id"])
    ).fetchone()

    is_assoc = quota["is_quota_associativa"] == 1

    if not quota:
        conn.close()
        flash("Quota non trovata.", "error")
        return redirect(url_for("gestione_quote"))

    if request.method == "POST":
        try:
            # 🔒 se quota associativa → blocco campi critici
            if quota["is_quota_associativa"] == 1:
                periodicita = quota["periodicita"]   # FORZATA
                nome = quota["nome"]                  # FORZATO
            else:
                periodicita = request.form["periodicita"]
                nome = request.form["nome"].strip()

            cur.execute(
                """
                UPDATE quote
                SET nome = ?, descrizione = ?, importo = ?, periodicita = ?
                WHERE id = ? AND associazione_id = ?
                """,
                (
                    nome,
                    (request.form.get("descrizione") or "").strip(),
                    float(request.form["importo"]),
                    periodicita,
                    quota_id,
                    session["associazione_id"]
                )
            )
            conn.commit()
            flash("Quota aggiornata.", "success")

        except Exception as e:
            conn.rollback()
            flash(f"Errore aggiornamento quota: {e}", "error")

        finally:
            conn.close()

        return redirect(url_for("gestione_quote"))

    conn.close()
    return render_template("quota_modifica.html", quota=quota)

# =================================================
# ELIMINA QUOTE (ANAGRAFICA)
# =================================================
@quote_bp.route("/quote/elimina/<int:quota_id>", methods=["POST"])
def elimina_quota(quota_id):
    if "associazione_id" not in session:
        return redirect(url_for("start"))

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        # 1️⃣ recupero quota
        quota = cur.execute(
            """
            SELECT is_quota_associativa
            FROM quote
            WHERE id = ? AND associazione_id = ?
            """,
            (quota_id, session["associazione_id"])
        ).fetchone()

        if not quota:
            flash("Quota non trovata.", "error")
            return redirect(url_for("gestione_quote"))

        # 2️⃣ 🔒 BLOCCO QUOTA ASSOCIATIVA
        if quota["is_quota_associativa"] == 1:
            flash(
                "La quota associativa di sistema non può essere eliminata.",
                "error"
            )
            return redirect(url_for("gestione_quote"))

        # 3️⃣ eliminazione normale
        cur.execute(
            """
            DELETE FROM quote
            WHERE id = ? AND associazione_id = ?
            """,
            (quota_id, session["associazione_id"])
        )

        conn.commit()
        flash("Quota eliminata.", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Errore eliminazione quota: {e}", "error")

    finally:
        conn.close()

    return redirect(url_for("gestione_quote"))


# =================================================
# API – ANNULLA QUOTA SOCIO (C1) - COMMENTATA PERCHE' NEL REFACTOR NON ABBIAMO CAPITO A COSA SERVE
# =================================================
#@quote_bp.route("/api/quote-soci/<int:quota_socio_id>/annulla", methods=["POST"])
#def api_annulla_quota_socio(quota_socio_id):
#    if "associazione_id" not in session:
#        return {"ok": False, "error": "Sessione non valida"}, 403
#
#    associazione_id = session["associazione_id"]
#
#    conn = get_db_connection()
#    cur = conn.cursor()
#
#    try:
#        # aggiorna solo se NON già pagata
#        cur.execute(
#            """
#            UPDATE quote_soci
#            SET stato = 'ANNULLATA'
#            WHERE id = ?
#              AND associazione_id = ?
#              AND stato != 'PAGATA'
#            """,
#            (quota_socio_id, associazione_id)
#        )
#
#        if cur.rowcount == 0:
#            raise ValueError("Quota non trovata o già pagata")
#
#        conn.commit()
#        return {"ok": True}
#
#    except Exception as e:
#        conn.rollback()
#        return {"ok": False, "error": str(e)}, 400
#
#    finally:
#        conn.close()