from flask import (
    render_template,
    request,
    redirect,
    url_for,
    session
)

from datetime import date
from collections import defaultdict
import sqlite3

from db import get_db_connection
from utils.tesseramenti import stato_tesseramento
from . import gestione_soci_bp
from services.quote_service import stato_quota_socio

# =================================================
# GESTIONE SOCI PAGINA PRINCIPALE ELENCO DI STATO
# =================================================

from datetime import date
from utils.tesseramenti import stato_tesseramento

@gestione_soci_bp.route("/", methods=["GET", "POST"])
def gestione_soci():
    if "associazione_id" not in session:
        return redirect(url_for("start"))

    associazione_id = session["associazione_id"]

    anno_corrente = date.today().year

    filtri = {
        "q": request.args.get("q", "").strip(),
        "stato": request.args.get("stato", ""),
        "anno": request.args.get("anno") or str(anno_corrente)
    }

    anno = int(filtri["anno"]) if filtri["anno"] else None

    if request.method == "POST":
        filtri["q"] = request.form.get("q", "").strip()
        filtri["stato"] = request.form.get("stato", "")

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    sql = """
        SELECT
            s.*,
            CASE
                WHEN s.data_uscita IS NULL THEN 'ATTIVO'
                ELSE 'USCITO'
            END AS stato
        FROM soci s
        WHERE s.associazione_id = ?
    """
    params = [associazione_id]

    if filtri["q"]:
        sql += """
            AND (
                s.nome LIKE ?
                OR s.cognome LIKE ?
                OR s.codice_fiscale LIKE ?
            )
        """
        like = f"%{filtri['q']}%"
        params.extend([like, like, like])

    if filtri["stato"] == "ATTIVO":
        sql += " AND s.data_uscita IS NULL "
    elif filtri["stato"] == "USCITO":
        sql += " AND s.data_uscita IS NOT NULL "

    sql += " ORDER BY s.cognome, s.nome "

    soci = cur.execute(sql, params).fetchall()

    # -------------------------
    # QUOTE SOCIO (attive) → mappa per anno
    # -------------------------
    quote_rows = cur.execute(
        """
        SELECT
            socio_id,
            data_inizio,
            data_fine
        FROM soci_quote
        WHERE associazione_id = ?
        AND attiva = 1
        """,
        (associazione_id,)
    ).fetchall()

    quote_map = defaultdict(set)  # (socio_id, anno) -> True

    for r in quote_rows:
        anno_inizio = int(r["data_inizio"][:4])
        anno_fine = int(r["data_fine"][:4]) if r["data_fine"] else 9999

        for a in range(anno_inizio, anno_fine + 1):
            quote_map[(r["socio_id"], a)].add(True)

    abilitazioni_rows = cur.execute(
        """
        SELECT
            socio_id,
            gestione_tesseramento,
            enti_tesseramento
        FROM soci_abilitazioni_storico
        WHERE associazione_id = ?
        AND anno = ?
        """,
        (associazione_id, anno)
    ).fetchall() if anno else []

    enti_affiliazione = cur.execute(
        """
        SELECT id, codice, nome
        FROM enti_affiliazione
        WHERE associazione_id = ?
          AND attivo = 1
        ORDER BY nome
        """,
        (associazione_id,)
    ).fetchall()

    righe_tess = cur.execute(
        """
        SELECT
            socio_id,
            ente_id,
            MAX(data_scadenza) AS data_scadenza
        FROM soci_tesseramenti
        WHERE associazione_id = ?
        GROUP BY socio_id, ente_id
        """,
        (associazione_id,)
    ).fetchall()

    tess_map = {
        (r["socio_id"], r["ente_id"]): r["data_scadenza"]
        for r in righe_tess
    }

    abilitazioni_map = {
        r["socio_id"]: {
            "gestione": bool(r["gestione_tesseramento"]),
            "enti": set(r["enti_tesseramento"].split(",")) if r["enti_tesseramento"] else set()
        }
        for r in abilitazioni_rows
    }

    soci = [dict(s) for s in soci]

    oggi = date.today()

    for s in soci:
        socio_attivo = s.get("data_uscita") is None
        s["tesseramenti"] = {}

        # ✅ STATO QUOTA CENTRALIZZATO (per anno selezionato)
        stato = stato_quota_socio(
            conn,
            associazione_id,
            s["id"],
            anno
        )
        s["quota_colore"] = stato.colore
        s["quota_tooltip"] = stato.tooltip

        # -------------------------
        # TESSERAMENTI (per ente)
        # -------------------------
        for e in enti_affiliazione:
            abil = abilitazioni_map.get(s["id"])

            abilitato = (
                bool(abil)
                and abil["gestione"]
                and e["codice"] in abil["enti"]
            )

            data_scadenza = tess_map.get((s["id"], e["id"]))

            stato_t, colore, label = stato_tesseramento(
                socio_attivo=socio_attivo,
                abilitato=abilitato,
                data_scadenza=data_scadenza,
                oggi=oggi
            )

            s["tesseramenti"][e["id"]] = {
                "stato": stato_t,
                "colore": colore,
                "label": label
            }

    anni_rows = cur.execute(
        """
        SELECT DISTINCT anno
        FROM esercizi
        WHERE associazione_id = ?
        ORDER BY anno DESC
        """,
        (associazione_id,)
    ).fetchall()

    anni = [r["anno"] for r in anni_rows]

    conn.close()

    return render_template(
        "soci/gestione.html",
        soci=soci,
        filtri=filtri,
        anni=anni,
        enti_affiliazione=enti_affiliazione,
    )
