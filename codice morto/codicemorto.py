# =================================================
# SCADENZIARIO QUOTE SOCI (DEFINITIVO) ELENCO NON CALENDARIO
# =================================================
@app.route("/scadenziario", methods=["GET", "POST"])
def scadenziario():
    if "associazione_id" not in session:
        return redirect(url_for("start"))

    associazione_id = session["associazione_id"]
    esercizio_id = session.get("esercizio_id")

    if not esercizio_id:
        flash("Seleziona prima un esercizio.", "error")
        return redirect(url_for("gestione_esercizio"))

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # -------------------------
    # ANNO ESERCIZIO
    # -------------------------
    row = cur.execute(
        "SELECT anno FROM esercizi WHERE id = ? AND associazione_id = ?",
        (esercizio_id, associazione_id)
    ).fetchone()
    anno = row["anno"]

    # -------------------------
    # FILTRI (DEFAULT)
    # -------------------------
    filtri = {
        "q": "",
        "quota_id": "",
        "stato": "",
        "da": f"{anno}-01",
        "a": f"{anno}-12"
    }

    if request.method == "POST":
        filtri["q"] = request.form.get("q", "").strip()
        filtri["quota_id"] = request.form.get("quota_id") or ""
        filtri["stato"] = request.form.get("stato") or ""
        filtri["da"] = request.form.get("da") or filtri["da"]
        filtri["a"] = request.form.get("a") or filtri["a"]

    # -------------------------
    # QUERY BASE (MENSILI DI DEFAULT)
    # -------------------------
    sql = """
        SELECT
            qs.id,
            qs.socio_id,
            qs.quota_id,
            qs.anno,
            qs.mese,
            qs.importo,
            qs.stato,
            qs.ricevuta_id,

            s.nome,
            s.cognome,

            q.nome AS quota_nome,
            q.periodicita
        FROM quote_soci qs
        JOIN soci s
            ON s.id = qs.socio_id
           AND s.associazione_id = qs.associazione_id
        JOIN quote q
            ON q.id = qs.quota_id
           AND q.associazione_id = qs.associazione_id
        WHERE
            qs.associazione_id = ?
            AND qs.esercizio_id = ?
            AND q.periodicita = 'MENSILE'
    """

    params = [associazione_id, esercizio_id]

    # -------------------------
    # FILTRO: socio
    # -------------------------
    if filtri["q"]:
        sql += " AND (s.nome LIKE ? OR s.cognome LIKE ?) "
        like = f"%{filtri['q']}%"
        params.extend([like, like])

    # -------------------------
    # FILTRO: quota
    # -------------------------
    if filtri["quota_id"]:
        sql += " AND qs.quota_id = ? "
        params.append(filtri["quota_id"])

    # -------------------------
    # FILTRO: stato
    # -------------------------
    if filtri["stato"]:
        sql += " AND qs.stato = ? "
        params.append(filtri["stato"])

    # -------------------------
    # FILTRO: periodo (YYYY-MM)
    # -------------------------
    if filtri["da"]:
        a_da, m_da = filtri["da"].split("-")
        sql += """
            AND (
                qs.anno > ?
                OR (qs.anno = ? AND qs.mese >= ?)
            )
        """
        params.extend([a_da, a_da, m_da])

    if filtri["a"]:
        a_a, m_a = filtri["a"].split("-")
        sql += """
            AND (
                qs.anno < ?
                OR (qs.anno = ? AND qs.mese <= ?)
            )
        """
        params.extend([a_a, a_a, m_a])

    # -------------------------
    # ORDINAMENTO
    # -------------------------
    sql += """
        ORDER BY
            s.cognome,
            s.nome,
            qs.anno,
            qs.mese
    """

    righe = cur.execute(sql, params).fetchall()

    # -------------------------
    # QUOTE PER FILTRO
    # -------------------------
    quote = cur.execute(
        """
        SELECT id, nome
        FROM quote
        WHERE associazione_id = ?
          AND attiva = 1
          AND periodicita = 'MENSILE'
        ORDER BY nome
        """,
        (associazione_id,)
    ).fetchall()

    conn.close()

    return render_template(
        "scadenziario.html",
        righe=righe,
        quote=quote,
        filtri=filtri,
        esercizio_id=esercizio_id,
        anno=anno
    )


# =================================================
# NUOVO SCADENZIARIO
# =================================================

import calendar
from datetime import date

def calcola_scadenziario_socio(conn, socio_id, associazione_id, esercizio_id=None):
    """
    Nuovo scadenziario socio basato SOLO su quote_soci.
    Ritorna:
      - mesi (YYYY-MM) dell'esercizio
      - quote: per ogni quota una mappa mese->stato
    Stati:
      - DA_PAGARE / PAGATA / ANNULLATA
      - NON_PRESENTE (nessuna riga quote_soci per quel mese)
      - ANNUALE (chiave speciale per mese=0)
    """

    cur = conn.cursor()

    # -------------------------
    # esercizio_id obbligatorio o recupero "ultimo" per associazione
    # -------------------------
    if esercizio_id is None:
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
            return {"anni": [], "mesi": [], "quote": []}
        esercizio_id = row["id"]

    # anno esercizio
    row = cur.execute(
        "SELECT anno FROM esercizi WHERE id = ? AND associazione_id = ?",
        (esercizio_id, associazione_id)
    ).fetchone()
    if not row:
        return {"anni": [], "mesi": [], "quote": []}

    anno = int(row["anno"])

    # mesi dell'esercizio (sempre 12)
    mesi = [f"{anno}-{m:02d}" for m in range(1, 13)]

    # -------------------------
    # leggo tutte le scadenze da quote_soci
    # -------------------------
    rows = cur.execute(
        """
        SELECT
            qs.quota_id,
            qs.anno,
            qs.mese,
            qs.importo,
            qs.stato,
            qs.ricevuta_id,
            q.nome AS quota_nome,
            q.periodicita
        FROM quote_soci qs
        JOIN quote q ON q.id = qs.quota_id AND q.associazione_id = qs.associazione_id
        WHERE qs.associazione_id = ?
          AND qs.esercizio_id = ?
          AND qs.socio_id = ?
        ORDER BY q.nome, qs.mese
        """,
        (associazione_id, esercizio_id, socio_id)
    ).fetchall()

    # raggruppo per quota
    per_quota = {}

    for r in rows:
        quota_id = r["quota_id"]
        if quota_id not in per_quota:
            per_quota[quota_id] = {
                "quota_id": quota_id,
                "nome": r["quota_nome"],
                "importo": r["importo"],          # importo base (per visual)
                "periodicita": r["periodicita"],
                "mesi": {m: "NON_PRESENTE" for m in mesi},
                "annuale": None  # per mese=0
            }

            # 🔧 FIX quota annuale (generica + di sistema)
            if r["periodicita"] == "ANNUALE":
                # mese di riferimento:
                # - se presente mese_inizio → quello
                # - altrimenti gennaio
                mese_attivo = f"{anno}-01"

                if r.get("mese_inizio"):
                    mese_attivo = f"{anno}-{int(r['mese_inizio']):02d}"

                # azzera tutti i mesi
                per_quota[quota_id]["mesi"] = {m: "NON_PRESENTE" for m in mesi}

                # attiva SOLO il mese valido
                per_quota[quota_id]["mesi"][mese_attivo] = "DA_PAGARE"


        if int(r["mese"]) == 0:
            # quota annuale
            per_quota[quota_id]["annuale"] = {
                "stato": r["stato"],
                "importo": r["importo"],
                "ricevuta_id": r["ricevuta_id"]
            }
            per_quota[quota_id]["is_annuale"] = True   # ← AGGIUNGI QUESTA
        else:
            # ❌ se la quota è annuale, IGNORA sempre i mesi 1–12
            if not per_quota[quota_id].get("is_annuale"):
                key = f"{anno}-{int(r['mese']):02d}"
                per_quota[quota_id]["mesi"][key] = r["stato"]

    # output finale
    return {
        "anni": [anno],
        "mesi": mesi,
        "quote": list(per_quota.values()),
        "esercizio_id": esercizio_id,
        "anno": anno
    }



# =================================================
# SCADENZIARIO SOCIO – UI (DEPRECATO)
# =================================================
# ⚠️ DEPRECATO
# Questo endpoint è basato sulla vecchia logica
# calcola_scadenziario_socio (mesi/anni/griglia).
#
# TODO:
# - RISCRIVERE lo scadenziario usando ESCLUSIVAMENTE la tabella quote_soci
# - Modello CENTRALIZZATO e FILTRABILE (non per singolo socio)
# - Click su quota → popup:
#     • Emetti ricevuta
#     • Annulla quota
#
# @app.route("/soci/<int:socio_id>/scadenziario-ui")
# def scadenziario_socio_ui(socio_id):
#     if "associazione_id" not in session:
#         return redirect(url_for("start"))
#
#     conn = get_db_connection()
#
#     # -------------------------
#     # DATI SCADENZIARIO (VECCHIO MODELLO)
#     # -------------------------
#     dati = calcola_scadenziario_socio(
#         conn=conn,
#         socio_id=socio_id,
#         associazione_id=session["associazione_id"],
#     )
#
#     mesi = dati.get("mesi", [])
#     quote = dati.get("quote", [])
#
#     # -------------------------
#     # CALCOLO ANNI (ES. ['2024', '2025'])
#     # -------------------------
#     anni = sorted({m[:4] for m in mesi})
#
#     # -------------------------
#     # DATI SOCIO (INTESTAZIONE)
#     # -------------------------
#     socio = conn.execute(
#     """
#         SELECT id, nome, cognome
#         FROM soci
#         WHERE id = ? AND associazione_id = ?
#         """,
#         (socio_id, session["associazione_id"])
#     ).fetchone()
#
#     conn.close()
#
#     return render_template(
#         "scadenziario_socio.html",
#         socio=socio,
#         mesi=mesi,
#         quote=quote,
#         anni=anni
#     )


# =================================================
# DETTAGLIO RICEVUTA 
# =================================================
# ⚠️ NOTA: al momento non risulta richiamata da nessun template/route (ricerca globale vuota).
# Tenuta temporaneamente. Candidata a rimozione quando facciamo pulizia "Ricevute".

@app.route("/ricevute/dettaglio")
def dettaglio_ricevuta():
    socio_id = int(request.args.get("socio_id"))
    quota_id = int(request.args.get("quota_id"))
    mese = request.args.get("mese")

    conn = get_db_connection()

    r = conn.execute(
        """
        SELECT r.*
        FROM ricevute r
        JOIN ricevute_righe rr ON rr.ricevuta_id = r.id
        WHERE r.socio_id = ?
          AND rr.quota_id = ?
          AND rr.mese = ?
        """,
        (socio_id, quota_id, mese)
    ).fetchone()

    if not r:
        conn.close()
        flash("Ricevuta non trovata.", "error")
        return redirect(url_for("libro_soci"))

    righe = conn.execute(
        """
        SELECT *
        FROM ricevute_righe
        WHERE ricevuta_id = ?
        """,
        (r["id"],)
    ).fetchall()

    conn.close()

    return render_template(
        "ricevuta_dettaglio.html",
        ricevuta=r,
        righe=righe
    )





# =================================================
# VECCHIO CALCOLO BILANCIO (DISATTIVATO)
# Usato prima del Modello D ETS
# NON PIÙ UTILIZZATO
# =================================================
# def calcola_bilancio(associazione_id, esercizio_id):
#     conn = sqlite3.connect(DB_NAME)
#     conn.row_factory = sqlite3.Row
#     cur = conn.cursor()
#
#     conti = cur.execute("""
#         SELECT id, codice, voce
#         FROM piano_conti
#         ORDER BY codice
#     """).fetchall()
#
#     bilancio = {
#         "ENTRATE": [],
#         "USCITE": [],
#         "tot_entrate": 0.0,
#         "tot_uscite": 0.0,
#         "risultato": 0.0
#     }
#
#     for c in conti:
#         totale = cur.execute("""
#             SELECT COALESCE(SUM(importo), 0)
#             FROM operazioni
#             WHERE associazione_id = ?
#               AND esercizio_id = ?
#               AND classificazione_id = ?
#         """, (associazione_id, esercizio_id, c["id"])).fetchone()[0]
#
#         if c["codice"].startswith("D"):
#             bilancio["ENTRATE"].append({
#                 "codice": c["codice"],
#                 "voce": c["voce"],
#                 "totale": totale
#             })
#             bilancio["tot_entrate"] += totale
#
#         elif c["codice"].startswith("U"):
#             bilancio["USCITE"].append({
#                 "codice": c["codice"],
#                 "voce": c["voce"],
#                 "totale": totale
#             })
#             bilancio["tot_uscite"] += totale
#
#     bilancio["risultato"] = (
#         bilancio["tot_entrate"] - bilancio["tot_uscite"]
#     )
#
#     conn.close()
#     return bilancio

# =================================================
# DISATTIVA QUOTA ASSEGNATA AL SOCIO (STORICO)
# =================================================
#@app.route("/soci/<int:socio_id>/quota/<int:soci_quota_id>/disattiva", methods=["POST"])
#def disattiva_quota_socio(socio_id, soci_quota_id):
#    if "associazione_id" not in session:
#        return redirect(url_for("start"))
#
#    conn = get_db_connection()
#    cur = conn.cursor()
#
#    try:
#        cur.execute(
#            """
#            UPDATE soci_quote
#            SET
#                attiva = 0,
#                data_fine = DATE('now')
#            WHERE id = ?
#              AND socio_id = ?
#              AND associazione_id = ?
#              AND attiva = 1
#            """,
#            (
#                soci_quota_id,
#                socio_id,
#                session["associazione_id"]
#            )
#        )
#
#        conn.commit()
#        flash("Quota disattivata correttamente.", "success")
#
#    except Exception as e:
#        conn.rollback()
#        flash(f"Errore disattivazione quota: {e}", "error")
#
#    finally:
#        conn.close()
#
#    return redirect(url_for("dettaglio_socio", socio_id=socio_id))

# =================================================
# TESSERAMENTI SOCI
# =================================================
#@app.route("/soci/tesseramenti")
#def tesseramenti():
#    if "associazione_id" not in session:
#        return redirect(url_for("start"))
#
#    return render_template("soci/tesseramenti.html")

# =================================================
# CONTI CORRENTI (ROUTE VECCHIA – TENUTA COME RIFERIMENTO)
# ⚠️ NON USATA – LOGICA SPOSTATA IN:
#     /impostazioni/conti-correnti
# =================================================

# @app.route("/conti-correnti", methods=["GET", "POST"])
# def conti_correnti_page():
#     if "associazione_id" not in session:
#         return redirect(url_for("start"))
#
#     conn = get_db_connection()
#     conn.row_factory = sqlite3.Row
#     cur = conn.cursor()
#
#     if request.method == "POST":
#         try:
#             codice = int(request.form["codice"])
#
#             cur.execute(
#                 """
#                 INSERT INTO conti_correnti (
#                     associazione_id,
#                     codice,
#                     nome,
#                     iban
#                 )
#                 VALUES (?, ?, ?, ?)
#                 """,
#                 (
#                     session["associazione_id"],
#                     codice,
#                     request.form["nome"].strip(),
#                     request.form["iban"].strip()
#                 )
#             )
#
#             conn.commit()
#             flash("Conto corrente inserito correttamente.", "success")
#
#         except sqlite3.IntegrityError as e:
#             conn.rollback()
#
#             if "UNIQUE" in str(e):
#                 flash(
#                     "Esiste già un conto con questo numero per l'associazione.",
#                     "error"
#                 )
#             else:
#                 flash(f"Errore di integrità DB: {e}", "error")
#
#         except sqlite3.OperationalError as e:
#             conn.rollback()
#             flash(f"Errore DB: {e}", "error")
#
#         except ValueError:
#             conn.rollback()
#             flash("Il codice del conto deve essere un numero intero.", "error")
#
#     conti = cur.execute(
#         """
#         SELECT *
#         FROM conti_correnti
#         WHERE associazione_id = ?
#         ORDER BY codice
#         """,
#         (session["associazione_id"],)
#     ).fetchall()
#
#     conn.close()
#
#     return render_template(
#         "conti_correnti.html",
#         conti=conti
#     )

# =================================================
# CERTIFICATI MEDICI
# =================================================
@app.route("/soci/certificati-medici")
def certificati_medici():
    if "associazione_id" not in session:
        return redirect(url_for("start"))

    return render_template("soci/certificati_storico.html")
