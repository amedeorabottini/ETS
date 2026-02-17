# -*- coding: utf-8 -*-
# Tutte le route del blueprint "soci" vanno qui.

import sqlite3
from datetime import date
from utils.abilitazioni import inizializza_abilitazioni_anno
from utils.esercizi import assicurati_esercizi
from flask import render_template, redirect, url_for, session, request, flash
from db import get_db_connection
from . import soci_bp  # importa il Blueprint creato in __init__.py
from services.tesseramenti_service import get_abilitazioni_tesseramento
from services.generatore_quote_soci import genera_quote_soci

# =================================================
# LIBRO SOCI – ELENCO
# =================================================
@soci_bp.route("/soci", endpoint="libro_soci")
def libro_soci():
    if "associazione_id" not in session:
        return redirect(url_for("start"))

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    soci = cur.execute(
        """
        SELECT *,
            CASE
                WHEN data_uscita IS NULL THEN 'ATTIVO'
                ELSE 'USCITO'
            END AS stato
        FROM soci
        WHERE associazione_id = ?
        ORDER BY matricola ASC
        """,
        (session["associazione_id"],)
    ).fetchall()

    conn.close()

    return render_template(
        "libro_soci.html",
        soci=soci
    )

# =================================================
# NUOVO SOCIO – FORM INSERIMENTO
# =================================================
@soci_bp.route("/soci/nuovo", methods=["GET", "POST"])
def nuovo_socio():
    if "associazione_id" not in session:
        return redirect(url_for("start"))

    if request.method == "POST":        
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        associazione_id = session["associazione_id"]

        print("🧪 NUOVO SOCIO – DATI FORM:")
        for k, v in request.form.items():
            print(f"   {k} = {v}")

        print("🧪 associazione_id =", associazione_id)

        # ==========================
        # A2 – CALCOLO MATRICOLA
        # ==========================
        row = cur.execute(
            """
            SELECT COALESCE(MAX(matricola), 0) + 1 AS nuova_matricola
            FROM soci
            WHERE associazione_id = ?
            """,
            (associazione_id,)
        ).fetchone()

        matricola = row["nuova_matricola"]

        print("🧪 matricola assegnata =", matricola)

        # ==========================
        # INSERT SOCIO
        # ==========================
        cur.execute(
            """
            INSERT INTO soci (
                associazione_id,
                matricola,
                nome,
                cognome,
                codice_fiscale,
                data_nascita,
                luogo_nascita,
                indirizzo,
                cap,
                comune,
                provincia,
                email,
                telefono,
                data_ingresso,
                note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                associazione_id,
                matricola,
                request.form["nome"],
                request.form["cognome"],
                request.form.get("codice_fiscale"),
                request.form.get("data_nascita"),
                request.form.get("luogo_nascita"),
                request.form.get("indirizzo"),
                request.form.get("cap"),
                request.form.get("comune"),
                request.form.get("provincia"),
                request.form.get("email"),
                request.form.get("telefono"),
                request.form["data_ingresso"],
                request.form.get("note")
            )

        )

        socio_id = cur.lastrowid

        # ==========================
        # CREAZIONE AUTOMATICA ESERCIZI
        # ==========================

        data_ingresso = request.form["data_ingresso"]
        anno_ingresso = int(data_ingresso[:4])

        print("🧪 ESERCIZI → anno ingresso socio:", anno_ingresso)

        # recupero esercizi esistenti
        anni_esistenti = cur.execute(
            """
            SELECT anno
            FROM esercizi
            WHERE associazione_id = ?
            ORDER BY anno
            """,
            (associazione_id,)
        ).fetchall()

        anni_esistenti = [r["anno"] for r in anni_esistenti]

        print("🧪 ESERCIZI → anni esistenti PRIMA:", anni_esistenti)

        if anni_esistenti:
            anno_max = max(anni_esistenti)
        else:
            anno_max = anno_ingresso

        for anno in range(anno_ingresso, anno_max + 1):
            if anno not in anni_esistenti:
                print("🧪 ESERCIZI → creo esercizio", anno)
                cur.execute(
                    """
                    INSERT INTO esercizi (associazione_id, anno)
                    VALUES (?, ?)
                    """,
                    (associazione_id, anno)
                )
                inizializza_abilitazioni_anno(conn, associazione_id, anno)

        # ==========================
        # ASSEGNAZIONE AUTOMATICA QUOTA ASSOCIATIVA DI SISTEMA
        # ==========================
        quota_assoc = cur.execute(
            """
            SELECT id
            FROM quote
            WHERE associazione_id = ?
            AND is_quota_associativa = 1
            AND attiva = 1
            LIMIT 1
            """,
            (associazione_id,)
        ).fetchone()

        if quota_assoc:
            # evita doppioni (se per qualche motivo lo richiami 2 volte)
            gia = cur.execute(
                """
                SELECT 1
                FROM soci_quote
                WHERE associazione_id = ?
                AND socio_id = ?
                AND quota_id = ?
                LIMIT 1
                """,
                (associazione_id, socio_id, quota_assoc["id"])
            ).fetchone()

            if not gia:
                cur.execute(
                    """
                    INSERT INTO soci_quote (
                        associazione_id,
                        socio_id,
                        quota_id,
                        data_inizio,
                        data_fine
                    )
                    VALUES (?, ?, ?, ?, NULL)
                    """,
                    (associazione_id, socio_id, quota_assoc["id"], data_ingresso)
                )
        conn.commit()
        conn.close()

        flash(f"Socio inserito correttamente (matricola {matricola}).", "success")
        return redirect(url_for("libro_soci"))

    return render_template("soci_nuovo.html")

# =================================================
# DETTAGLIO / MODIFICA SOCIO
# =================================================
@soci_bp.route("/soci/<int:socio_id>", methods=["GET", "POST"])
def dettaglio_socio(socio_id):
    if "associazione_id" not in session:
        return redirect(url_for("start"))

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row

    try:
        cur = conn.cursor()

        print("🧪 DB (GET dettaglio socio) PATH =", conn.execute("PRAGMA database_list").fetchone()[2])

        socio = cur.execute(
            """
            SELECT *
            FROM soci
            WHERE id = ?
              AND associazione_id = ?
            """,
            (socio_id, session["associazione_id"])
        ).fetchone()

        if not socio:
            flash("Socio non trovato.", "error")
            return redirect(url_for("libro_soci"))
        
        # -------------------------
        # ANNO CORRENTE (default UI)
        # -------------------------
        anno_corrente = date.today().year
        anno_ingresso = int(socio["data_ingresso"][:4])

        anni_abilitazioni = list(range(anno_ingresso, anno_corrente + 1))

        # -------------------------
        # ANNO SELEZIONATO DA UI (?anno=YYYY)
        # -------------------------
        anno_selezionato = request.args.get("anno", type=int)
        if not anno_selezionato:
            anno_selezionato = anno_corrente

        # -------------------------
        # ABILITAZIONI SOCIO (STORICO PER ANNO)
        # -------------------------
        abilitazioni_anno = cur.execute(
            """
            SELECT *
            FROM soci_abilitazioni_storico
            WHERE socio_id = ?
            AND associazione_id = ?
            AND anno = ?
            """,
            (socio_id, session["associazione_id"], anno_selezionato)
        ).fetchone()


        # -------------------------
        # ENTI DI AFFILIAZIONE ATTIVI
        # -------------------------
        enti_affiliazione = cur.execute(
            """
            SELECT id, codice, nome
            FROM enti_affiliazione
            WHERE associazione_id = ?
            AND attivo = 1
            ORDER BY nome
            """,
            (session["associazione_id"],)
        ).fetchall()

        # mappa codice ente -> id ente (SERVE per abilitazioni)
        codice_to_id = {e["codice"]: e["id"] for e in enti_affiliazione}
       
        
        # -------------------------
        # POST → SALVATAGGIO
        # -------------------------
        if request.method == "POST":
            cur.execute(
                """
                UPDATE soci
                SET
                    nome = ?,
                    cognome = ?,
                    codice_fiscale = ?,
                    data_nascita = ?,
                    luogo_nascita = ?,
                    indirizzo = ?,
                    cap = ?,
                    comune = ?,
                    provincia = ?,
                    email = ?,
                    telefono = ?,
                    data_ingresso = ?,
                    data_uscita = ?,
                    note = ?,

                    gestione_tesseramento = ?,
                    gestione_certificati_medici = ?,
                    is_volontario = ?,
                    abilita_rimborso_spese = ?

                WHERE id = ?
                AND associazione_id = ?
                """,
                (
                    request.form["nome"],
                    request.form["cognome"],
                    request.form.get("codice_fiscale"),
                    request.form.get("data_nascita"),
                    request.form.get("luogo_nascita"),
                    request.form.get("indirizzo"),
                    request.form.get("cap"),
                    request.form.get("comune"),
                    request.form.get("provincia"),
                    request.form.get("email"),
                    request.form.get("telefono"),
                    request.form["data_ingresso"],
                    request.form.get("data_uscita") or None,
                    request.form.get("note"),
                     # 🔽 NUOVI FLAG (checkbox-safe)
                    1 if request.form.get("gestione_tesseramento") else 0,
                    1 if request.form.get("gestione_certificati_medici") else 0,
                    1 if request.form.get("is_volontario") else 0,
                    1 if request.form.get("abilita_rimborso_spese") else 0,
                    socio_id,
                    session["associazione_id"]
                )
            )

            data_ingresso = request.form["data_ingresso"]
            anno_ingresso = int(data_ingresso[:4])

            assicurati_esercizi(
                conn=conn,
                associazione_id=session["associazione_id"],
                anno_minimo=anno_ingresso
            )


            conn.commit()
            flash("Dati socio aggiornati.", "success")
            return redirect(url_for("dettaglio_socio", socio_id=socio_id))

        # -------------------------
        # GET → DATI PER TEMPLATE
        # -------------------------
        quote = cur.execute(
            """
            SELECT id, nome, importo, periodicita
            FROM quote
            WHERE associazione_id = ?
              AND attiva = 1
            ORDER BY nome
            """,
            (session["associazione_id"],)
        ).fetchall()

        quote_socio = cur.execute(
            """
            SELECT
                sq.id,
                q.nome,
                q.importo,
                q.periodicita,
                sq.data_inizio,
                sq.data_fine,
                sq.attiva          -- 👈 FONDAMENTALE
            FROM soci_quote sq
            JOIN quote q
            ON q.id = sq.quota_id
            AND q.associazione_id = sq.associazione_id
            WHERE sq.socio_id = ?
            AND sq.associazione_id = ?
            AND sq.attiva = 1
            ORDER BY sq.data_inizio DESC
            """,
            (socio_id, session["associazione_id"])
        ).fetchall()

        # DEBUG: mostra a terminale la riga della quota assegnata id=14 (se presente)
        for r in quote_socio:
            if r["id"] == 14:
                print("🧪 GET quote_socio id=14 =", dict(r))
                break

        soci_elenco = cur.execute(
            """
            SELECT id, cognome, nome
            FROM soci
            WHERE associazione_id = ?
            ORDER BY cognome, nome
            """,
            (session["associazione_id"],)
        ).fetchall()

        return render_template(
            "socio_dettaglio.html",
            socio=socio,
            soci_elenco=soci_elenco, 
            quote=quote,
            quote_socio=quote_socio,
            enti_affiliazione=enti_affiliazione,
            abilitazioni_anno=abilitazioni_anno,
            anni_abilitazioni=anni_abilitazioni,
            anno_selezionato=anno_selezionato,
            anno_corrente=anno_corrente
        )

    finally:
        conn.close()

# =================================================
# USCITA SOCI
# =================================================


@soci_bp.route("/soci/uscita/<int:socio_id>", methods=["POST"])
def uscita_socio(socio_id):
    if "associazione_id" not in session:
        return redirect(url_for("start"))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE soci
        SET data_uscita = ?
        WHERE id = ?
          AND associazione_id = ?
        """,
        (
            date.today().isoformat(),
            socio_id,
            session["associazione_id"]
        )
    )

    conn.commit()
    conn.close()

    flash("Socio segnato come USCITO.", "success")
    return redirect(url_for("libro_soci"))

# =================================================
# ELIMINA SOCIO + TUTTI I RECORD COLLEGATI (SOLO TEST)
# =================================================
@soci_bp.route("/soci/<int:socio_id>/elimina-tutto", methods=["POST"])
def elimina_socio_tutto(socio_id):
    if "associazione_id" not in session:
        return redirect(url_for("start"))

    associazione_id = session["associazione_id"]

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        # 0) verifica socio
        row = cur.execute(
            "SELECT id FROM soci WHERE id = ? AND associazione_id = ?",
            (socio_id, associazione_id)
        ).fetchone()
        if not row:
            flash("Socio non trovato.", "error")
            return redirect(url_for("libro_soci"))

        # 1) ricevute + righe ricevute
        ricevute_ids = [
            r["id"] for r in cur.execute(
                "SELECT id FROM ricevute WHERE associazione_id = ? AND socio_id = ?",
                (associazione_id, socio_id)
            ).fetchall()
        ]

        if ricevute_ids:
            ph = ",".join(["?"] * len(ricevute_ids))

            # IMPORTANTISSIMO: sgancio quote_soci -> ricevute (se esiste il link)
            cur.execute(
                f"""
                UPDATE quote_soci
                SET ricevuta_id = NULL
                WHERE associazione_id = ?
                  AND socio_id = ?
                  AND ricevuta_id IN ({ph})
                """,
                (associazione_id, socio_id, *ricevute_ids)
            )

            cur.execute(
                f"DELETE FROM ricevute_righe WHERE associazione_id = ? AND ricevuta_id IN ({ph})",
                (associazione_id, *ricevute_ids)
            )
            cur.execute(
                f"DELETE FROM ricevute WHERE associazione_id = ? AND id IN ({ph})",
                (associazione_id, *ricevute_ids)
            )

        # 2) quote generate + collegamenti quote
        cur.execute(
            "DELETE FROM quote_soci WHERE associazione_id = ? AND socio_id = ?",
            (associazione_id, socio_id)
        )
        cur.execute(
            "DELETE FROM soci_quote WHERE associazione_id = ? AND socio_id = ?",
            (associazione_id, socio_id)
        )

        # 3) storico/extra soci
        cur.execute(
            "DELETE FROM soci_abilitazioni_storico WHERE associazione_id = ? AND socio_id = ?",
            (associazione_id, socio_id)
        )
        cur.execute(
            "DELETE FROM soci_certificati_medici WHERE associazione_id = ? AND socio_id = ?",
            (associazione_id, socio_id)
        )
        cur.execute(
            "DELETE FROM soci_tesseramenti WHERE associazione_id = ? AND socio_id = ?",
            (associazione_id, socio_id)
        )

        # 4) socio
        cur.execute(
            "DELETE FROM soci WHERE associazione_id = ? AND id = ?",
            (associazione_id, socio_id)
        )

        conn.commit()
        flash("Socio eliminato (con tutti i collegamenti).", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Errore eliminazione socio: {e}", "error")

    finally:
        conn.close()

    return redirect(url_for("libro_soci"))

# =================================================
# MODIFICA QUOTA ASSEGNATA A SOCIO (STORICIZZAZIONE)
# =================================================
@soci_bp.route(
    "/soci/<int:socio_id>/quota/<int:soci_quota_id>/modifica",
    methods=["GET", "POST"]
)
def modifica_quota_socio(socio_id, soci_quota_id):
    if "associazione_id" not in session:
        return redirect(url_for("start"))

    associazione_id = session["associazione_id"]
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    print("🧪 DB (POST quota socio) PATH =", conn.execute("PRAGMA database_list").fetchone()[2])

    quota_socio = cur.execute(
        """
        SELECT *
        FROM soci_quote
        WHERE id = ?
        AND socio_id = ?
        AND associazione_id = ?
        """,
        (soci_quota_id, socio_id, associazione_id)
    ).fetchone()

    # Fallback: se l'id non è di soci_quote, potrebbe essere l'id di quote_soci (scadenze generate)
    if not quota_socio:
        qs = cur.execute(
            """
            SELECT quota_id
            FROM quote_soci
            WHERE id = ?
            AND socio_id = ?
            AND associazione_id = ?
            """,
            (soci_quota_id, socio_id, associazione_id)
        ).fetchone()

        if qs:
            # prendo l'assegnazione attiva più recente per quella quota
            quota_socio = cur.execute(
                """
                SELECT *
                FROM soci_quote
                WHERE socio_id = ?
                AND associazione_id = ?
                AND quota_id = ?
                AND attiva = 1
                ORDER BY data_inizio DESC, id DESC
                LIMIT 1
                """,
                (socio_id, associazione_id, qs["quota_id"])
            ).fetchone()

    if not quota_socio:
        conn.close()
        flash("Quota assegnata non trovata.", "error")
        return redirect(url_for("dettaglio_socio", socio_id=socio_id))

    # Se siamo arrivati qui, quota_socio esiste sicuramente:
    soci_quota_id = quota_socio["id"]

    if request.method == "POST":
        data_inizio = request.form.get("data_inizio")
        data_fine   = request.form.get("data_fine") or None
        print("🧪 POST modifica_quota_socio:", "socio_id=", socio_id, "soci_quota_id=", soci_quota_id, "data_inizio=", data_inizio, "data_fine=", data_fine)
        
        # -------------------------
        # VALIDAZIONI
        # -------------------------
        if not data_inizio:
            flash("La data di inizio è obbligatoria.", "error")
            return redirect(request.url)

        

        try:
            # 1️⃣ aggiorno soci_quote (STORICO)
            prima = cur.execute(
                """
                SELECT id, quota_id, data_inizio, data_fine
                FROM soci_quote
                WHERE id = ? AND socio_id = ? AND associazione_id = ?
                """,
                (soci_quota_id, socio_id, associazione_id)
            ).fetchone()
            print("🧪 PRIMA UPDATE soci_quote =", dict(prima) if prima else None)
            cur.execute(
                """
                UPDATE soci_quote
                SET
                    data_inizio = ?,
                    data_fine   = ?
                WHERE id = ?
                AND socio_id = ?
                AND associazione_id = ?
                """,
                (
                    data_inizio,
                    data_fine,
                    soci_quota_id,
                    socio_id,
                    associazione_id
                )
            )

            print("🧪 UPDATE rowcount =", cur.rowcount)

            dopo = cur.execute(
                """
                SELECT id, quota_id, data_inizio, data_fine
                FROM soci_quote
                WHERE id = ? AND socio_id = ? AND associazione_id = ?
                """,
                (soci_quota_id, socio_id, associazione_id)
            ).fetchone()
            print("🧪 DOPO UPDATE soci_quote  =", dict(dopo) if dopo else None)

            # ✅ Verifica che l'update abbia davvero modificato una riga
            if cur.rowcount == 0:
                conn.rollback()
                flash("Nessuna modifica salvata: record quota non trovato (o non appartenente al socio).", "error")
                conn.close()
                return redirect(url_for("dettaglio_socio", socio_id=socio_id))

            # ✅ Commit subito: la modifica a soci_quote deve restare salvata anche se la rigenerazione ha problemi
            conn.commit()

            # 2️⃣ rigenero scadenze
            for r in cur.execute(
                "SELECT id FROM esercizi WHERE associazione_id = ?",
                (associazione_id,)
            ):
                genera_quote_soci(
                    conn=conn,
                    associazione_id=associazione_id,
                    esercizio_id=r["id"]
                )

            conn.commit()
            flash("Quota assegnata aggiornata correttamente.", "success")

        except Exception as e:
            conn.rollback()
            flash(f"Errore modifica quota: {e}", "error")

        finally:
            conn.close()

        return redirect(url_for("dettaglio_socio", socio_id=socio_id))

    conn.close()
    return render_template("soci_quota_modifica.html", socio_id=socio_id, quota_socio=quota_socio)

# =================================================
# SALVA ABILITAZIONI SOCIO (STORICO PER ANNO)
# =================================================
@soci_bp.route("/soci/<int:socio_id>/abilitazioni", methods=["POST"])
def salva_abilitazioni_socio(socio_id):
    if "associazione_id" not in session:
        return redirect(url_for("start"))

    associazione_id = session["associazione_id"]

    # anno obbligatorio
    anno = request.form.get("anno")
    if not anno:
        flash("Seleziona l’anno di validità delle abilitazioni.", "error")
        return redirect(url_for("dettaglio_socio", socio_id=socio_id))

    anno = int(anno)
    
    # 🔽 FLAG PROPAGAZIONE ANNI SUCCESSIVI
    propaga = request.form.get("propaga_anni_successivi") == "1"

    # checkbox-safe
    gestione_tesseramento = 1 if request.form.get("gestione_tesseramento") else 0
    certificato_agonistico = 1 if request.form.get("certificato_agonistico") else 0
    certificato_non_agonistico = 1 if request.form.get("certificato_non_agonistico") else 0
    is_volontario = 1 if request.form.get("is_volontario") else 0
    abilita_rimborso_spese = 1 if request.form.get("abilita_rimborso_spese") else 0

    # enti tesseramento (CSV)
    enti = request.form.getlist("enti_tesseramento")
    enti_csv = ",".join(enti) if enti else None

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO soci_abilitazioni_storico (
                associazione_id,
                socio_id,
                anno,
                gestione_tesseramento,
                enti_tesseramento,
                certificato_agonistico,
                certificato_non_agonistico,
                is_volontario,
                abilita_rimborso_spese
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(associazione_id, socio_id, anno)
            DO UPDATE SET
                gestione_tesseramento = excluded.gestione_tesseramento,
                enti_tesseramento = excluded.enti_tesseramento,
                certificato_agonistico = excluded.certificato_agonistico,
                certificato_non_agonistico = excluded.certificato_non_agonistico,
                is_volontario = excluded.is_volontario,
                abilita_rimborso_spese = excluded.abilita_rimborso_spese
            """,
            (
                associazione_id,
                socio_id,
                anno,
                gestione_tesseramento,
                enti_csv,
                certificato_agonistico,
                certificato_non_agonistico,
                is_volontario,
                abilita_rimborso_spese
            )
        )

        # ✅ QUI (prima del commit)
        if propaga:
            anni_successivi = cur.execute(
                """
                SELECT anno
                FROM esercizi
                WHERE associazione_id = ?
                AND anno > ?
                ORDER BY anno
                """,
                (associazione_id, anno)
            ).fetchall()

            for r in anni_successivi:
                anno_dest = r["anno"]
                cur.execute(
                    """
                    INSERT INTO soci_abilitazioni_storico (
                        associazione_id,
                        socio_id,
                        anno,
                        gestione_tesseramento,
                        enti_tesseramento,
                        certificato_agonistico,
                        certificato_non_agonistico,
                        is_volontario,
                        abilita_rimborso_spese
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(associazione_id, socio_id, anno)
                    DO UPDATE SET
                        gestione_tesseramento = excluded.gestione_tesseramento,
                        enti_tesseramento = excluded.enti_tesseramento,
                        certificato_agonistico = excluded.certificato_agonistico,
                        certificato_non_agonistico = excluded.certificato_non_agonistico,
                        is_volontario = excluded.is_volontario,
                        abilita_rimborso_spese = excluded.abilita_rimborso_spese
                    """,
                    (
                        associazione_id,
                        socio_id,
                        anno_dest,
                        gestione_tesseramento,
                        enti_csv,
                        certificato_agonistico,
                        certificato_non_agonistico,
                        is_volontario,
                        abilita_rimborso_spese
                    )
                )

        conn.commit()

        if propaga:
            flash(f"Abilitazioni salvate per l’anno {anno} e copiate negli anni successivi.", "success")
        else:
            flash(f"Abilitazioni salvate per l’anno {anno}.", "success")

    finally:
        conn.close()

        

    return redirect(url_for("dettaglio_socio", socio_id=socio_id))

# =================================================
# GET ABILITAZIONI SOCIO (AJAX / JSON)
# =================================================
@soci_bp.route("/soci/<int:socio_id>/abilitazioni/json")
def get_abilitazioni_socio_json(socio_id):
    if "associazione_id" not in session:
        return {"error": "unauthorized"}, 401

    associazione_id = session["associazione_id"]
    anno = request.args.get("anno", type=int)

    if not anno:
        return {"error": "anno mancante"}, 400

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    ab = cur.execute(
        """
        SELECT *
        FROM soci_abilitazioni_storico
        WHERE socio_id = ?
          AND associazione_id = ?
          AND anno = ?
        """,
        (socio_id, associazione_id, anno)
    ).fetchone()

    conn.close()

    if not ab:
        return {
            "gestione_tesseramento": 0,
            "enti_tesseramento": [],
            "certificato_agonistico": 0,
            "certificato_non_agonistico": 0,
            "is_volontario": 0,
            "abilita_rimborso_spese": 0
        }

    return {
        "gestione_tesseramento": ab["gestione_tesseramento"],
        "enti_tesseramento": ab["enti_tesseramento"].split(",") if ab["enti_tesseramento"] else [],
        "certificato_agonistico": ab["certificato_agonistico"],
        "certificato_non_agonistico": ab["certificato_non_agonistico"],
        "is_volontario": ab["is_volontario"],
        "abilita_rimborso_spese": ab["abilita_rimborso_spese"]
    }


# =================================================
# COLLEGAMENTO QUOTE SOCI
# =================================================
@soci_bp.route(
    "/soci/<int:socio_id>/assegna-quota",
    methods=["POST"],
    endpoint="assegna_quota_socio"
)
def assegna_quota_socio(socio_id):
    if "associazione_id" not in session:
        return redirect(url_for("start"))

    associazione_id = session["associazione_id"]

    # -------------------------
    # DATI DAL FORM
    # -------------------------
    quota_id = request.form.get("quota_id")
    data_inizio = request.form.get("data_inizio")
    data_fine = request.form.get("data_fine") or None
    
    # -------------------------
    # VALIDAZIONI
    # -------------------------
    if not quota_id or not data_inizio:
        flash("Quota e data inizio sono obbligatorie.", "error")
        return redirect(url_for("dettaglio_socio", socio_id=socio_id))

    
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # -------------------------
        # INSERT SOCI_QUOTE
        # -------------------------
        cur.execute(
            """
            INSERT INTO soci_quote (
                associazione_id,
                socio_id,
                quota_id,
                data_inizio
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                associazione_id,
                socio_id,
                quota_id,
                data_inizio
            )
        )

        conn.commit()
        flash("Quota assegnata al socio.", "success")

    finally:
        conn.close()

    return redirect(url_for("dettaglio_socio", socio_id=socio_id))


# =================================================
# ELIMINA (STORICIZZA) QUOTA ASSEGNATA A SOCIO
# =================================================
from services.generatore_quote_soci import genera_quote_soci

@soci_bp.route(
    "/soci/<int:socio_id>/quota/<int:soci_quota_id>/elimina",
    methods=["POST"],
    endpoint="elimina_quota_socio"
)
def elimina_quota_socio(socio_id, soci_quota_id):
    if "associazione_id" not in session:
        return redirect(url_for("start"))

    associazione_id = session["associazione_id"]
    data_fine = request.form.get("data_fine")

    if not data_fine:
        flash("La data di fine è obbligatoria.", "error")
        return redirect(url_for("soci_bp.dettaglio_socio", socio_id=socio_id))

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        # 1️⃣ STORICIZZO IL COLLEGAMENTO
        cur.execute(
            """
            UPDATE soci_quote
            SET
                attiva = 0,
                data_fine = ?
            WHERE id = ?
              AND socio_id = ?
              AND associazione_id = ?
            """,
            (
                data_fine,
                soci_quota_id,
                socio_id,
                associazione_id
            )
        )

        # 2️⃣ RIGENERO LE QUOTE SU TUTTI GLI ESERCIZI
        esercizi = cur.execute(
            "SELECT id FROM esercizi WHERE associazione_id = ?",
            (associazione_id,)
        ).fetchall()

        for r in esercizi:
            genera_quote_soci(
                conn,
                associazione_id,
                r["id"]
            )

        conn.commit()
        flash("Quota eliminata e storicizzata correttamente.", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Errore eliminazione quota: {e}", "error")

    finally:
        conn.close()

    return redirect(url_for("soci_bp.dettaglio_socio", socio_id=socio_id))