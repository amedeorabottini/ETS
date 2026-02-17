# =================================================
# SCADENZIARIO MATRICE
# =================================================

@app.route("/scadenziario/matrice", methods=["GET"])
def scadenziario_matrice():
    if "associazione_id" not in session:
        return redirect(url_for("start"))
    print("DEBUG SESSIONE:", dict(session))

    associazione_id = session["associazione_id"]
    

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

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
    # ESERCIZIO SELEZIONATO (CHIAVE)
    # -------------------------
    esercizio_id = request.args.get("esercizio_id")

    if esercizio_id:
        esercizio_id = int(esercizio_id)
    else:
        # default = esercizio più recente (anno corrente)
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
            return redirect(url_for("gestione_esercizio"))
            anno = int(row["anno"])

        esercizio_id = row["id"]

    # 👉 sincronizzo SEMPRE la sessione
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
        return redirect(url_for("gestione_esercizio"))

    anno = int(row["anno"])   # ← QUESTA ERA LA RIGA MANCANTE


    # -------------------------
    # FILTRI (GET)
    # -------------------------
    filtri = {
        "anno": anno,   # 👈 NON arriva più dal form
        "q": (request.args.get("q") or "").strip(),
        "quota_id": request.args.get("quota_id") or "",
        "tipo": request.args.get("tipo") or "MENSILE",
    }

    mesi = [f"{filtri['anno']}-{m:02d}" for m in range(1, 13)]

    # -------------------------
    # QUOTE per filtri (select)
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
    # SOCI (SEMPRE TUTTI)
    # -------------------------
    soci_rows = cur.execute("""
        SELECT id, cognome, nome
        FROM soci
        WHERE associazione_id = ?
        ORDER BY cognome, nome
    """, (associazione_id,)).fetchall()

    # -------------------------
    # QUOTE SOCI (SOLO SE ESISTONO)
    # -------------------------
    quote_sql = """
        SELECT
            qs.id AS quota_socio_id,
            qs.socio_id,
            qs.quota_id,
            qs.data_inizio,
            qs.data_fine,
            q.nome AS quota_nome,
            q.periodicita
        FROM soci_quote qs
        JOIN quote q
            ON q.id = qs.quota_id
            AND q.associazione_id = qs.associazione_id
        WHERE qs.associazione_id = ?
    """
    params = [associazione_id]

    quote_rows = cur.execute(quote_sql, params).fetchall()
    print("DEBUG quote_rows:", [(r["socio_id"], r["quota_nome"], r["data_inizio"], r["data_fine"]) for r in quote_rows])

    # filtro quota (se selezionato)
    if filtri["quota_id"]:
        quote_sql += " AND qs.quota_id = ? "
        params.append(filtri["quota_id"])

    # filtro tipo quota
    if filtri["tipo"]:
        quote_sql += " AND q.periodicita = ? "
        params.append(filtri["tipo"])

    quote_rows = cur.execute(quote_sql, params).fetchall()

    

    # -------------------------
    # COSTRUZIONE MATRICE
    # righe = socio+quota
    # -------------------------
    matrix = {}

    # 1️⃣ inizializza SEMPRE tutti i soci
    for s in soci_rows:
        matrix[(s["id"], 0)] = {
            "socio_id": s["id"],
            "cognome": s["cognome"],
            "nome": s["nome"],
            "quota_id": 0,
            "quota_nome": "",
            "periodicita": "",
            "mesi": {
                m: {
                    "stato": "NON_PRESENTE",
                    "quota_socio_id": None,
                    "ricevuta_id": None
                } for m in mesi
            }
        }

    # 2️⃣ sovrascrivi SOLO dove esistono quote
    for r in quote_rows:
        key = (r["socio_id"], r["quota_id"])

        # ✅ CREA LA RIGA SOCIO+QUOTA SE NON ESISTE
        if key not in matrix:
            matrix[key] = {
                "socio_id": r["socio_id"],
                "cognome": matrix[(r["socio_id"], 0)]["cognome"],
                "nome": matrix[(r["socio_id"], 0)]["nome"],
                "quota_id": r["quota_id"],
                "quota_nome": r["quota_nome"],
                "periodicita": r["periodicita"],
                "mesi": {
                    m: {
                        "stato": "NON_PRESENTE",
                        "quota_socio_id": None,
                        "ricevuta_id": None
                    } for m in mesi
                }
            }

        data_inizio = r["data_inizio"]
        data_fine = r["data_fine"]

        y_start, m_start, _ = map(int, data_inizio.split("-"))

                # -------------------------
        # ✅ FIX QUOTE ANNUALI:
        # - anno ingresso: solo mese di ingresso (m_start)
        # - anni successivi: solo gennaio
        # -------------------------
        if r["periodicita"] == "ANNUALE":

            # quota futura
            if y_start > anno:
                continue

            # se c'è data_fine e l'anno è oltre la fine → skip
            if data_fine:
                y_end, m_end, _ = map(int, data_fine.split("-"))
                if y_end < anno:
                    continue
            else:
                y_end, m_end = None, None

            # mese "attivo" dell'annuale per questo anno
            mese_attivo = m_start if anno == y_start else 1

            # se nell'anno di fine il mese attivo è oltre m_end → skip
            if data_fine and y_end == anno and mese_attivo > m_end:
                continue

            mese_key = f"{anno}-{mese_attivo:02d}"
            if mese_key in matrix[key]["mesi"]:
                matrix[key]["mesi"][mese_key] = {
                    "stato": "DA_PAGARE",
                    "quota_socio_id": r["quota_socio_id"],
                    "ricevuta_id": None
                }

            # IMPORTANTISSIMO: non far partire la logica "mensile"
            continue

        # quota futura
        if y_start > anno:
            continue

        # mese iniziale
        mese_start = 1
        if y_start == anno:
            mese_start = m_start

        # mese finale
        mese_end = 12
        if data_fine:
            y_end, m_end, _ = map(int, data_fine.split("-"))
            if y_end < anno:
                continue
            if y_end == anno:
                mese_end = m_end

        for m in range(mese_start, mese_end + 1):
            mese_key = f"{anno}-{m:02d}"
            if mese_key in matrix[key]["mesi"]:
                matrix[key]["mesi"][mese_key] = {
                    "stato": "DA_PAGARE",
                    "quota_socio_id": r["quota_socio_id"],
                    "ricevuta_id": None
                }

    # 3️⃣ rimuovi la riga "vuota" per i soci che hanno almeno una quota
    soci_con_quote = {r["socio_id"] for r in quote_rows}

    for socio_id in soci_con_quote:
        matrix.pop((socio_id, 0), None)
    
    # 4️⃣ rimuovi soci ATTIVI che NON hanno quote compatibili col filtro
    soci_con_righe = {k[0] for k in matrix.keys()}

    righe_filtrate = []
    for r in matrix.values():
        # tiene solo righe che hanno almeno una cella != NON_PRESENTE
        if any(c["stato"] != "NON_PRESENTE" for c in r["mesi"].values()):
            righe_filtrate.append(r)

    righe_matrice = righe_filtrate


    conn.close()

    return render_template(
        "scadenziario_matrice.html",
        anno=filtri["anno"],
        esercizio_id=esercizio_id,
        esercizi=esercizi,          # 👈 AGGIUNGI SOLO QUESTA
        mesi=mesi,
        righe=righe_matrice,
        quote=quote,
        filtri=filtri
    )