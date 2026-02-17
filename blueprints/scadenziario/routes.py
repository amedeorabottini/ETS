# -*- coding: utf-8 -*-

from flask import redirect, url_for, session
import sqlite3
from flask import render_template, redirect, url_for, session, request, flash
from db import get_db_connection
from services.quote_sync_service import sync_quote_soci
from . import scadenziario_bp
from services.generatore_quote_soci import genera_quote_soci

# =================================================
# SCADENZIARIO MATRICE
# =================================================
@scadenziario_bp.route("/scadenziario/matrice", methods=["GET"], endpoint="scadenziario_matrice")
def scadenziario_matrice():
    if "associazione_id" not in session:
        return redirect(url_for("start"))

    associazione_id = session["associazione_id"]

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    from services.quote_sync_service import sync_quote_soci

    # -------------------------
    # ESERCIZI DISPONIBILI (per select)
    # -------------------------
    esercizi = cur.execute(
        """
        SELECT id, anno
        FROM esercizi
        WHERE associazione_id = ?
        ORDER BY anno
        """,
        (associazione_id,)
    ).fetchall()

    # -------------------------
    # ESERCIZIO SELEZIONATO
    # -------------------------
    esercizio_id = request.args.get("esercizio_id", type=int)

    if not esercizio_id:
        row = cur.execute(
            """
            SELECT id
            FROM esercizi
            WHERE associazione_id = ?
            ORDER BY anno DESC
            LIMIT 1
            """,
            (associazione_id,)
        ).fetchone()

        if not row:
            flash("Nessun esercizio disponibile.", "error")
            conn.close()
            return redirect(url_for("gestione_esercizio"))

        esercizio_id = row["id"]

    # sincronizzo sessione
    session["esercizio_id"] = esercizio_id

    row = cur.execute(
        """
        SELECT anno
        FROM esercizi
        WHERE id = ?
          AND associazione_id = ?
        """,
        (esercizio_id, associazione_id)
    ).fetchone()

    if not row:
        flash("Esercizio non valido.", "error")
        conn.close()
        return redirect(url_for("gestione_esercizio"))

    anno = int(row["anno"])

    # -------------------------
    # SYNC IMPEGNI ECONOMICI (quote_soci)
    # -------------------------
    sync_quote_soci(conn, associazione_id, esercizio_id, anno)

    # -------------------------
    # FILTRI (GET)
    # -------------------------
    filtri = {
        "anno": anno,
        "q": (request.args.get("q") or "").strip(),
        "quota_id": request.args.get("quota_id") or "",
        "tipo": request.args.get("tipo") or "MENSILE",
    }

    mesi = [f"{anno}-{m:02d}" for m in range(1, 13)]

    # -------------------------
    # QUOTE (per select filtri)
    # -------------------------
    quote = cur.execute(
        """
        SELECT id, nome, periodicita
        FROM quote
        WHERE associazione_id = ?
          AND attiva = 1
        ORDER BY nome
        """,
        (associazione_id,)
    ).fetchall()

    # -------------------------
    # SOCI (per anagrafica matrice)
    # con filtro q (se presente)
    # -------------------------
    soci_sql = """
        SELECT id, cognome, nome
        FROM soci
        WHERE associazione_id = ?
    """
    soci_params = [associazione_id]

    if filtri["q"]:
        soci_sql += " AND (nome LIKE ? OR cognome LIKE ? OR codice_fiscale LIKE ?) "
        like = f"%{filtri['q']}%"
        soci_params.extend([like, like, like])

    soci_sql += " ORDER BY cognome, nome "
    soci_rows = cur.execute(soci_sql, soci_params).fetchall()

    # -------------------------
    # QUERY MATRICE: SOLO quote_soci (impegni reali)
    # -------------------------
    quote_soci_sql = """
        SELECT
            qs.id        AS quota_socio_id,
            qs.socio_id,
            qs.quota_id,
            qs.anno,
            qs.mese,
            qs.stato,
            qs.ricevuta_id,
            q.nome       AS quota_nome,
            q.periodicita
        FROM quote_soci qs
        JOIN quote q ON q.id = qs.quota_id
        WHERE qs.associazione_id = ?
        AND qs.anno = ?
        AND qs.stato IN ('DA_PAGARE', 'PAGATA')
    """
    params_matrice = [associazione_id, anno]

    # filtro quota_id
    if filtri["quota_id"]:
        quote_soci_sql += " AND qs.quota_id = ? "
        params_matrice.append(int(filtri["quota_id"]))

    # filtro tipo (periodicita)
    if filtri["tipo"]:
        quote_soci_sql += " AND q.periodicita = ? "
        params_matrice.append(filtri["tipo"])

    quote_soci_sql += " ORDER BY qs.socio_id, q.nome, qs.mese "

    quote_rows = cur.execute(quote_soci_sql, params_matrice).fetchall()
    print("DEBUG stati:", sorted(set([r["stato"] for r in quote_rows])))

    # -------------------------
    # COSTRUZIONE MATRICE
    # righe = socio + quota
    # -------------------------
    matrix = {}

    # 1) inizializzo tutti i soci “in chiaro” (riga vuota)
    for s in soci_rows:
        matrix[(s["id"], 0)] = {
            "socio_id": s["id"],
            "cognome": s["cognome"],
            "nome": s["nome"],
            "quota_id": 0,
            "quota_nome": "",
            "periodicita": "",
            "mesi": {
                m: {"stato": "NON_PRESENTE", "quota_socio_id": None, "ricevuta_id": None}
                for m in mesi
            }
        }

    # 2) riempio righe reali da quote_soci
    for r in quote_rows:
        key = (r["socio_id"], r["quota_id"])

        if key not in matrix:
            # se il socio non è in soci_rows (per via filtro q) evito KeyError
            base = matrix.get((r["socio_id"], 0))
            if not base:
                # socio filtrato fuori: ignoro
                continue

            matrix[key] = {
                "socio_id": r["socio_id"],
                "cognome": base["cognome"],
                "nome": base["nome"],
                "quota_id": r["quota_id"],
                "quota_nome": r["quota_nome"],
                "periodicita": r["periodicita"],
                "mesi": {
                    m: {"stato": "NON_PRESENTE", "quota_socio_id": None, "ricevuta_id": None}
                    for m in mesi
                }
            }

        # mese=0 (annuale) → metto a gennaio nella matrice (YYYY-01)
        if int(r["mese"]) == 0:
            mese_key = f"{anno}-01"
        else:
            mese_key = f"{anno}-{int(r['mese']):02d}"

        if mese_key in matrix[key]["mesi"]:
            matrix[key]["mesi"][mese_key] = {
                "stato": r["stato"],                 # ✅ stato reale: DA_PAGARE / PAGATA
                "quota_socio_id": r["quota_socio_id"],
                "ricevuta_id": r["ricevuta_id"]      # ✅ utile per linkare la ricevuta
            }
    

    # 3) tolgo la riga vuota dei soci che hanno almeno una quota visibile
    soci_con_quote = {r["socio_id"] for r in quote_rows}
    for socio_id in soci_con_quote:
        matrix.pop((socio_id, 0), None)

    # 4) tengo solo righe che hanno almeno una cella != NON_PRESENTE
    righe_matrice = [
        r for r in matrix.values()
        if any(c["stato"] != "NON_PRESENTE" for c in r["mesi"].values())
    ]

    conn.close()

    return render_template(
        "scadenziario_matrice.html",
        anno=filtri["anno"],
        esercizio_id=esercizio_id,
        esercizi=esercizi,
        mesi=mesi,
        righe=righe_matrice,
        quote=quote,
        filtri=filtri
    )

# =================================================
# GENERA SCADENZA
# =================================================
@scadenziario_bp.route("/scadenziario/genera", methods=["POST"], endpoint="genera_scadenze_quote")
def genera_scadenze_quote():
    if "associazione_id" not in session or "esercizio_id" not in session:
        return redirect(url_for("start"))

    conn = get_db_connection()

    try:
        genera_quote_soci(
            conn,
            session["associazione_id"],
            session["esercizio_id"]
        )
        conn.commit()  # ✅ FONDAMENTALE (la funzione non fa commit)
        flash("Scadenze quote generate per l’esercizio.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Errore generazione scadenze: {e}", "error")
    finally:
        conn.close()

    return redirect(url_for("scadenziario_matrice"))