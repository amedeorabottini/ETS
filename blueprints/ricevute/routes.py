# -*- coding: utf-8 -*-
# Route del modulo "Ricevute"

from . import ricevute_bp
import sqlite3
import io

from flask import render_template, redirect, url_for, session, request, flash, jsonify, send_file
from db import get_db_connection

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from datetime import date
from datetime import date

# =================================================
# NUOVA RICEVUTA – UI (SCADENZIARIO / MANUALE)
# =================================================
@ricevute_bp.route("/ricevute/nuova")
def nuova_ricevuta():
    if "associazione_id" not in session:
        return redirect(url_for("start"))

    import sqlite3
    from datetime import date

    associazione_id = session["associazione_id"]

    socio_id = request.args.get("socio_id", type=int)
    quota_id = request.args.get("quota_id", type=int)   # <-- ora è quota_id (tipologia)
    anno = request.args.get("anno", type=int)
    mese = request.args.get("mese", type=int)

    ricevuta_id = request.args.get("ricevuta_id", type=int)

    # fallback anno
    if anno is None:
        anno = session.get("anno")
    if anno is None:
        anno = date.today().year

    quota_socio_id = request.args.get("quota_socio_id", type=int)

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row

    # -------------------------
    # MODIFICA RICEVUTA (se arriva ricevuta_id)
    # -------------------------
    ricevuta_edit = None
    righe_edit = []

    ricevuta = None
    righe_esistenti = []
    is_edit = False

    if ricevuta_id:
        ricevuta_edit = conn.execute(
            """
            SELECT *
            FROM ricevute
            WHERE id = ?
              AND associazione_id = ?
            """,
            (ricevuta_id, associazione_id)
        ).fetchone()

        if not ricevuta_edit:
            conn.close()
            flash("Ricevuta non trovata.", "error")
            return redirect(url_for("ricevute_bp.elenco_ricevute"))

        righe_edit = conn.execute(
            """
            SELECT *
            FROM ricevute_righe
            WHERE ricevuta_id = ?
            ORDER BY id
            """,
            (ricevuta_id,)
        ).fetchall()

        # 🔧 filtra righe sporche/vuote (create durante prove)
        righe_edit = [
            r for r in righe_edit
            if (r["quota_id"] is not None)
            or (r["descrizione"] and str(r["descrizione"]).strip())
        ]

        is_edit = True
        ricevuta = dict(ricevuta_edit) if ricevuta_edit else None
        righe_esistenti = [dict(r) for r in righe_edit]

        print("RIGHE ESISTENTI:", righe_esistenti)

        # precompilo almeno il socio
        socio_id = ricevuta_edit["socio_id"]

        # se vuoi, forzo anche l'anno dal documento (utile per dropdown quote)
        if ricevuta_edit["data_emissione"]:
            anno = int(str(ricevuta_edit["data_emissione"])[:4])


    # -------------------------
    # sync quote_soci per anno/esercizio
    # (solo in creazione, NON in modifica ricevuta)
    # -------------------------
    from services.quote_sync_service import sync_quote_soci

    if not ricevuta_id:
        row_es = conn.execute(
            """
            SELECT id
            FROM esercizi
            WHERE associazione_id = ?
            AND anno = ?
            """,
            (associazione_id, anno)
        ).fetchone()

        if row_es:
            sync_quote_soci(conn, associazione_id, row_es["id"], anno)

    # -------------------------
    # PRECOMPILAZIONE DA SCADENZIARIO (quota_socio_id)
    # -------------------------
    if quota_socio_id:
        r = conn.execute(
            """
            SELECT socio_id, quota_id, anno, mese
            FROM quote_soci
            WHERE id = ?
              AND associazione_id = ?
            """,
            (quota_socio_id, associazione_id)
        ).fetchone()

        if r:
            socio_id = r["socio_id"]
            quota_id = r["quota_id"]     # <-- tipologia quota
            anno = r["anno"]
            mese = r["mese"]

    # -------------------------
    # PERIODO (UI) - coerente con (anno,mese)
    # -------------------------
    periodo = None
    if anno:
        if mese is not None and mese > 0:
            periodo = f"{anno}-{mese:02d}"
        else:
            periodo = f"{anno} (annuale)"

    # -------------------------
    # LISTA SOCI
    # -------------------------
    soci = conn.execute(
        """
        SELECT id, nome, cognome
        FROM soci
        WHERE associazione_id = ?
          AND data_uscita IS NULL
        ORDER BY cognome, nome
        """,
        (associazione_id,)
    ).fetchall()

    # -------------------------
    # SOCIO SELEZIONATO (serve al template)
    # -------------------------
    socio = None
    if socio_id:
        socio = conn.execute(
            """
            SELECT id, nome, cognome
            FROM soci
            WHERE id = ?
              AND associazione_id = ?
            """,
            (socio_id, associazione_id)
        ).fetchone()

    # -------------------------
    # DROPDOWN QUOTE: SOLO TIPOLOGIE (DISTINCT quota_id)
    # + importo per quota_id
    # -------------------------
    quote = []
    quote_importi = {}
    quota = None

    # --- MODIFICA RICEVUTA: precompilo testa + righe ---
    righe_esistenti = []
    metodo_pagamento_sel = None
    sezionale_sel = None
    conto_sel = None

    if socio_id and anno:
        # ✅ in modifica: includo anche le quote già presenti nelle righe ricevuta
        quota_ids_in_ricevuta = []
        if is_edit and righe_esistenti:
            quota_ids_in_ricevuta = [
                int(r["quota_id"])
                for r in righe_esistenti
                if r.get("tipo") == "QUOTA" and r.get("quota_id")
            ]

        extra_filter = ""
        params = [associazione_id, socio_id, anno]

        if quota_ids_in_ricevuta:
            placeholders = ",".join(["?"] * len(quota_ids_in_ricevuta))
            extra_filter = f" OR qs.quota_id IN ({placeholders}) "
            params.extend(quota_ids_in_ricevuta)

        quote = conn.execute(
            f"""
            SELECT
                q.id            AS quota_id,
                q.nome,
                q.periodicita,
                MAX(qs.importo) AS importo
            FROM quote_soci qs
            JOIN quote q ON q.id = qs.quota_id
            WHERE qs.associazione_id = ?
            AND qs.socio_id = ?
            AND qs.anno = ?
            AND (qs.stato = 'DA_PAGARE' {extra_filter})
            GROUP BY q.id, q.nome, q.periodicita
            ORDER BY q.nome
            """,
            params
        ).fetchall()

    quote_importi = {int(q["quota_id"]): float(q["importo"] or 0) for q in quote}

    if quota_id:
        quota = next((q for q in quote if int(q["quota_id"]) == int(quota_id)), None)

        # mappa importo per quota_id (non per quota_socio_id!)
        quote_importi = {int(q["quota_id"]): float(q["importo"]) for q in quote}

        if quota_id:
            quota = next((q for q in quote if int(q["quota_id"]) == int(quota_id)), None)

    # -------------------------
    # SEZIONALI RICEVUTE
    # -------------------------
    sezionali = conn.execute(
        """
        SELECT id, nome, codice, is_default
        FROM ricevute_sezionali
        WHERE associazione_id = ?
        ORDER BY is_default DESC, nome
        """,
        (associazione_id,)
    ).fetchall()

    sezionale_default = next((s for s in sezionali if s["is_default"] == 1), None)

    # -------------------------
    # CONTI PAGAMENTO
    # -------------------------
    conti_pagamento = conn.execute(
        """
        SELECT id, nome
        FROM conti_correnti
        WHERE associazione_id = ?
        ORDER BY codice
        """,
        (associazione_id,)
    ).fetchall()

    # -------------------------
    # SELEZIONI IN MODIFICA (testa + righe)
    # -------------------------
    sezionale_sel = None
    metodo_pagamento_sel = None
    conto_sel = None
    righe_esistenti = []

    if ricevuta_id and ricevuta_edit:
        sezionale_sel = ricevuta_edit["sezionale_id"]
        metodo_pagamento_sel = ricevuta_edit["metodo_pagamento"]
        # se la colonna NON esiste in DB, lascia None:
        conto_sel = ricevuta_edit["conto_pagamento_id"] if "conto_pagamento_id" in ricevuta_edit.keys() else None

        righe_esistenti = righe_edit  # quelle che hai già letto sopra

        righe_esistenti = [dict(r) for r in righe_esistenti]

    # -------------------------
    # NUMERO PROPOSTO AUTOMATICO
    # -------------------------
    oggi = date.today().isoformat()
    anno_ricevuta = int(oggi[:4])
    numero_proposto = None

    if ricevuta_id and ricevuta_edit:
        numero_proposto = ricevuta_edit["numero_progressivo"]
        oggi = ricevuta_edit["data_emissione"] or oggi
    else:
        if sezionale_default:
            last = conn.execute(
                """
                SELECT MAX(numero_progressivo) AS max_num
                FROM ricevute
                WHERE associazione_id = ?
                  AND anno = ?
                  AND sezionale_id = ?
                """,
                (associazione_id, anno_ricevuta, sezionale_default["id"])
            ).fetchone()
            numero_proposto = (last["max_num"] or 0) + 1

    conn.close()

    print("DEBUG type(ricevuta):", type(ricevuta))

    return render_template(
        "ricevuta_nuova.html",
        soci=soci,
        socio=socio,
        quote=quote,
        quota=quota,
        periodo=periodo,
        anno=anno,
        mese=mese,
        quote_importi=quote_importi,
        sezionali=sezionali,
        sezionale_default=sezionale_default,
        conti_pagamento=conti_pagamento,
        oggi=oggi,
        numero_proposto=numero_proposto,
        ricevuta_id=ricevuta_id,
        is_edit=is_edit,
        ricevuta=ricevuta,
        righe_esistenti=righe_esistenti,
        metodo_pagamento_sel=metodo_pagamento_sel,
        sezionale_sel=sezionale_sel,
        conto_sel=conto_sel,
    )

# =================================================
# NUMERAZIONE AUTOMATICA RICEVUTE (PER SEZIONALE)
# =================================================
@ricevute_bp.route("/ricevute/next-numero/<int:sezionale_id>")
def next_numero_ricevuta(sezionale_id):
    if "associazione_id" not in session:
        return jsonify({"numero": None})

    associazione_id = session["associazione_id"]

    oggi = date.today().isoformat()
    anno = oggi[:4]

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row

    # =========================
    # MODIFICA RICEVUTA (prefill)
    # =========================
    ricevuta = None
    righe_ricevuta = []

    if ricevuta_id:
        ricevuta = conn.execute(
            """
            SELECT *
            FROM ricevute
            WHERE id = ?
              AND associazione_id = ?
            """,
            (ricevuta_id, associazione_id)
        ).fetchone()

        if not ricevuta:
            conn.close()
            flash("Ricevuta non trovata.", "error")
            return redirect(url_for("ricevute_bp.elenco_ricevute"))

        righe_ricevuta = conn.execute(
            """
            SELECT *
            FROM ricevute_righe
            WHERE ricevuta_id = ?
            ORDER BY id
            """,
            (ricevuta_id,)
        ).fetchall()

        # Prefill campi principali
        socio_id = ricevuta["socio_id"]
        anno = int(ricevuta["anno"]) if ricevuta["anno"] else anno

    cur = conn.cursor()

    row = cur.execute(
        """
        SELECT MAX(numero_progressivo) AS max_num
        FROM ricevute
        WHERE associazione_id = ?
          AND anno = ?
          AND sezionale_id = ?
        """,
        (associazione_id, anno, sezionale_id)
    ).fetchone()

    conn.close()

    max_num = row["max_num"] if row and row["max_num"] is not None else 0
    numero = int(max_num) + 1

    return jsonify({"numero": numero})

# =================================================
# VISUALIZZA RICEVUTA
# =================================================
@ricevute_bp.route("/ricevute/<int:ricevuta_id>")
def visualizza_ricevuta(ricevuta_id):
    if "associazione_id" not in session:
        return redirect(url_for("start"))

    conn = get_db_connection()

    ricevuta = conn.execute(
        """
        SELECT r.*, s.nome, s.cognome
        FROM ricevute r
        LEFT JOIN soci s ON s.id = r.socio_id
        WHERE r.id = ?
          AND r.associazione_id = ?
        """,
        (ricevuta_id, session["associazione_id"])
    ).fetchone()

    if not ricevuta:
        conn.close()
        flash("Ricevuta non trovata.", "error")
        return redirect(url_for("libro_soci"))

    righe = conn.execute(
        """
        SELECT rr.*, q.nome AS quota_nome
        FROM ricevute_righe rr
        LEFT JOIN quote q ON q.id = rr.quota_id
        WHERE rr.ricevuta_id = ?
        """,
        (ricevuta_id,)
    ).fetchall()

    conn.close()

    return render_template(
        "ricevuta_visualizza.html",
        ricevuta=ricevuta,
        righe=righe
    )


# =================================================
# RICERCA INSOLUTI
# =================================================
@ricevute_bp.route("/api/insoluti/<int:socio_id>/<int:quota_id>", endpoint="api_insoluti")
def api_insoluti(socio_id, quota_id):
    if "associazione_id" not in session:
        return jsonify({"mesi": []})

    from datetime import date
    import sqlite3

    associazione_id = session["associazione_id"]

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 🔹 mesi teorici (pagati + da pagare)
    rows = cur.execute("""
        SELECT anno, mese
        FROM quote_soci
        WHERE associazione_id = ?
          AND socio_id = ?
          AND quota_id = ?
          AND stato IN ('DA_PAGARE', 'PAGATA')
    """, (associazione_id, socio_id, quota_id)).fetchall()

    oggi = date.today()
    anno_corrente = oggi.year
    mese_corrente = oggi.month

    tutti = []

    for r in rows:
        anno = r["anno"]
        mese = r["mese"]

        # ❌ anni futuri
        if anno > anno_corrente:
            continue

        # ==========================
        # QUOTA ANNUALE
        # ==========================
        if mese == 0:
            tutti.append(f"{anno}-01")
            continue

        # ❌ mesi futuri anno corrente
        if anno == anno_corrente and mese > mese_corrente:
            continue

        tutti.append(f"{anno}-{mese:02d}")

    # 🔹 mesi già pagati
    pagati_rows = cur.execute("""
        SELECT anno, mese
        FROM quote_soci
        WHERE associazione_id = ?
          AND socio_id = ?
          AND quota_id = ?
          AND stato = 'PAGATA'
    """, (associazione_id, socio_id, quota_id)).fetchall()

    pagati = set()
    for r in pagati_rows:
        if r["mese"] == 0:
            pagati.add(f"{r['anno']}-01")
        else:
            pagati.add(f"{r['anno']}-{r['mese']:02d}")

    insoluti = sorted(set(tutti) - pagati)

    conn.close()

    return jsonify({"mesi": insoluti})

# =================================================
# SALVA RICEVUTA
# =================================================
@ricevute_bp.route("/ricevute/salva", methods=["POST"], endpoint="salva_ricevuta")
def salva_ricevuta():
    if "associazione_id" not in session:
        return redirect(url_for("start"))

    associazione_id = session["associazione_id"]

    socio_id = request.form.get("socio_id")
    socio_id = int(socio_id) if socio_id else None
    if socio_id is None:
        raise ValueError("socio_id mancante nel form (hidden input non valorizzato)")

    # ✅ usa la data del form
    data_emissione = (request.form.get("data_emissione") or "").strip()
    if not data_emissione:
        flash("Data ricevuta mancante.", "error")
        return redirect(url_for("nuova_ricevuta"))

    anno = data_emissione[:4]  # YYYY (stringa)

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        # -------------------------
        # NUMERO PROGRESSIVO
        # -------------------------
        sezionale_id = request.form.get("sezionale_id")
        if not sezionale_id:
            raise ValueError("Sezionale mancante")

        last = cur.execute(
            """
            SELECT MAX(numero_progressivo) AS max_num
            FROM ricevute
            WHERE associazione_id = ?
              AND anno = ?
              AND sezionale_id = ?
            """,
            (associazione_id, anno, sezionale_id)
        ).fetchone()

        numero = (last["max_num"] or 0) + 1
        metodo_pagamento = request.form.get("metodo_pagamento") or "CASSA"

        # -------------------------
        # INSERIMENTO RICEVUTA (testa)
        # -------------------------
        cur.execute(
            """
            INSERT INTO ricevute (
                associazione_id,
                socio_id,
                data_emissione,
                anno,
                numero_progressivo,
                totale,
                sezionale_id,
                metodo_pagamento
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                associazione_id,
                socio_id,
                data_emissione,
                anno,
                numero,
                0.0,
                sezionale_id,
                metodo_pagamento
            )
        )

        ricevuta_id = cur.lastrowid
        totale = 0.0

        # -------------------------
        # RIGHE AUTOMATICHE (QUOTE)
        # -------------------------
        quota_ids = request.form.getlist("quota_id[]")
        anni = request.form.getlist("anno[]")
        mesi = request.form.getlist("mese[]")
        importi = request.form.getlist("importo[]")

        # Mappa: quote.id -> nome
        quote_map = {
            row["id"]: row["nome"]
            for row in cur.execute(
                "SELECT id, nome FROM quote WHERE associazione_id = ?",
                (associazione_id,)
            ).fetchall()
        }

        # Mappa: quote.id -> nome + periodicita (serve per gestire ANNUALE)
        quote_info = {
            row["id"]: {"nome": row["nome"], "periodicita": row["periodicita"]}
            for row in cur.execute(
                "SELECT id, nome, periodicita FROM quote WHERE associazione_id = ?",
                (associazione_id,)
            ).fetchall()
        }

        for quota_id, a, m, imp in zip(quota_ids, anni, mesi, importi):
            if not quota_id or not a or m is None or m == "" or not imp:
                continue

            quota_id = int(quota_id)   # <-- quote.id
            a = int(a)
            m = int(m)                 # può essere 0 per annuale
            imp = float(imp)

            # --- normalizzazione mese annuale ---
            info = quote_info.get(quota_id) or {}
            periodicita = (info.get("periodicita") or "").upper()

            # mese che SALVIAMO in quote_soci (chiave DB)
            mese_db = m
            # mese che mostriamo/storiamo in ricevute_righe come YYYY-MM
            mese_riga = m

            if periodicita == "ANNUALE":
                # in quote_soci l'annuale è mese=0
                mese_db = 0
                # in ricevute_righe vogliamo mostrare 01 (non 00)
                mese_riga = 1

            totale += imp

            # YYYY-MM (per annuale mese=0 => YYYY-00)
            mese_composto = f"{a}-{mese_riga:02d}"
            descrizione = quote_map.get(quota_id, "Quota")

            # riga ricevuta
            cur.execute(
                """
                INSERT INTO ricevute_righe (
                    ricevuta_id,
                    quota_id,
                    mese,
                    descrizione,
                    importo,
                    tipo
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    ricevuta_id,
                    quota_id,
                    mese_composto,
                    descrizione,
                    imp,
                    "QUOTA"
                )
            )

            # ✅ aggiorna la riga GIUSTA in quote_soci (chiave completa)
            cur.execute(
                """
                UPDATE quote_soci
                SET
                    stato = 'PAGATA',
                    ricevuta_id = ?,
                    data_pagamento = ?
                WHERE associazione_id = ?
                  AND socio_id = ?
                  AND quota_id = ?
                  AND anno = ?
                  AND mese = ?
                """,
                (
                    ricevuta_id,
                    data_emissione,
                    associazione_id,
                    socio_id,
                    quota_id,
                    a,
                    mese_db
                )
            )

            if cur.rowcount == 0:
                print(
                    "⚠️ UPDATE quote_soci NON ha aggiornato nulla (chiave):",
                    {
                        "associazione_id": associazione_id,
                        "socio_id": socio_id,
                        "quota_id": quota_id,
                        "anno": a,
                        "mese": m,
                    }
                )

        # -------------------------
        # RIGHE MANUALI
        # -------------------------
        descrizioni = request.form.getlist("descrizione_manual[]")
        anni_m = request.form.getlist("anno_manual[]")
        mesi_m = request.form.getlist("mese_manual[]")
        importi_m = request.form.getlist("importo_manual[]")

        for desc, a, m, imp in zip(descrizioni, anni_m, mesi_m, importi_m):
            if not imp:
                continue

            imp = float(imp)
            totale += imp

            mese_composto = None
            if a and m:
                mese_composto = f"{a}-{m}"  # YYYY-MM

            cur.execute(
                """
                INSERT INTO ricevute_righe (
                    ricevuta_id,
                    quota_id,
                    mese,
                    descrizione,
                    importo,
                    tipo
                )
                VALUES (?, NULL, ?, ?, ?, ?)
                """,
                (
                    ricevuta_id,
                    mese_composto,
                    (desc or "").strip(),
                    imp,
                    "MANUALE"
                )
            )

        # -------------------------
        # AGGIORNA TOTALE
        # -------------------------
        cur.execute(
            """
            UPDATE ricevute
            SET totale = ?
            WHERE id = ?
            """,
            (totale, ricevuta_id)
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    flash(f"Ricevuta n. {numero}/{anno} emessa correttamente.", "success")
    return redirect(url_for("ricevute_bp.elenco_ricevute")) 

# -------------------------
# GENERA RICEVUTA
# -------------------------

def genera_pdf_ricevuta(ricevuta_id, associazione_id):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row

    # ricevuta + socio + sezionale 🔧 FIX
    r = conn.execute(
        """
        SELECT r.*,
               s.nome, s.cognome, s.codice_fiscale,
               s.indirizzo, s.cap, s.comune, s.provincia,
               sez.codice AS codice_sezionale
        FROM ricevute r
        LEFT JOIN soci s ON s.id = r.socio_id
        LEFT JOIN ricevute_sezionali sez ON sez.id = r.sezionale_id
        WHERE r.id = ?
          AND r.associazione_id = ?
        """,
        (ricevuta_id, associazione_id)
    ).fetchone()

    if not r:
        conn.close()
        return None

    righe = conn.execute(
        """
        SELECT rr.*, q.nome AS quota_nome
        FROM ricevute_righe rr
        LEFT JOIN quote q ON q.id = rr.quota_id
        WHERE rr.ricevuta_id = ?
        ORDER BY rr.id
        """,
        (ricevuta_id,)
    ).fetchall()

    conn.close()

    # === PDF in memoria
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    x0 = 18 * mm
    y = h - 18 * mm

    # Titolo
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x0, y, "RICEVUTA")

    # 🔧 FIX NUMERO + SEZIONALE
    numero = r["numero_progressivo"]
    codice_sezionale = r["codice_sezionale"]

    if codice_sezionale:
        numero_txt = f"{numero}/{codice_sezionale}"
    else:
        numero_txt = str(numero)

    data_iso = r["data_emissione"] or ""
    data_txt = (
        f"{data_iso[8:10]}/{data_iso[5:7]}/{data_iso[0:4]}"
        if len(data_iso) >= 10 else data_iso
    )

    y -= 10 * mm
    c.setFont("Helvetica", 11)

    # Numero a sinistra
    c.drawString(x0, y, f"Numero: {numero_txt}")

    # Data spostata a destra (come nel PDF)
    c.drawString(x0 + 110 * mm, y, f"Data: {data_txt}")

    metodo = r["metodo_pagamento"] or "POS"
    y -= 7 * mm
    c.drawString(x0, y, f"Metodo pagamento: {metodo}")

    # Cliente
    y -= 10 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x0, y, "Cliente")

    c.setFont("Helvetica", 11)
    y -= 7 * mm
    nomec = ""
    if r["cognome"] or r["nome"]:
        nomec = f'{r["nome"] or ""} {r["cognome"] or ""}'.strip()
    c.drawString(x0, y, nomec or "-")

    y -= 6 * mm
    cf = r["codice_fiscale"] or ""
    c.drawString(x0, y, f"CF: {cf}" if cf else "CF:")

    indir = (r["indirizzo"] or "").strip()
    cap = (r["cap"] or "").strip()
    com = (r["comune"] or "").strip()
    prov = (r["provincia"] or "").strip()
    y -= 6 * mm
    if indir:
        c.drawString(x0, y, indir)
    y -= 6 * mm
    if cap or com or prov:
        c.drawString(x0, y, f"{cap} {com} ({prov})".strip())

    # Prodotti e Servizi
    y -= 12 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x0, y, "Prodotti e Servizi")

    # Header tabella
    y -= 7 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x0, y, "Descrizione")
    c.drawString(x0 + 110 * mm, y, "Periodo")
    c.drawRightString(w - 18 * mm, y, "Importo (EUR)")

    # LINEA NERA
    y -= 4 * mm
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(1)
    c.line(x0, y, w - 18 * mm, y)

    # righe
    c.setFont("Helvetica", 10)
    y -= 6 * mm

    totale = 0.0
    for rr in righe:
        descr = rr["descrizione"] or rr["quota_nome"] or ""
        periodo = rr["mese"] or ""

        if len(periodo) == 7 and periodo[4] == "-":
            periodo = f"{periodo[5:7]}/{periodo[0:4]}"

        imp = float(rr["importo"] or 0.0)
        totale += imp

        if y < 30 * mm:
            c.showPage()
            y = h - 18 * mm
            c.setFont("Helvetica", 10)

        c.drawString(x0, y, descr[:80])
        c.drawString(x0 + 110 * mm, y, periodo)
        c.drawRightString(w - 18 * mm, y, f"{_fmt_num(imp)} EUR")
        y -= 6 * mm

    # LINEA TOTALE
    y -= 2 * mm
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(1)
    c.line(x0, y, w - 18 * mm, y)

    y -= 8 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(w - 18 * mm, y, f"TOTALE  {_fmt_num(totale)} EUR")

    y -= 10 * mm
    c.setFont("Helvetica", 10)
    c.drawString(x0, y, "Natura IVA: N2.2 (fuori campo IVA)")

    y -= 8 * mm
    c.drawString(x0, y, "Corrispettivo fuori campo IVA ai sensi dell’art. 4, c.4, DPR 633/1972.")
    y -= 6 * mm
    c.drawString(x0, y, "Il presente documento costituisce ricevuta di pagamento")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

def _fmt_num(x):
    try:
        return f"{float(x):.2f}"
    except Exception:
        return "0.00"

# =================================================
# STAMPA RICEVUTA PDF (ROUTE)
# =================================================
@ricevute_bp.route("/ricevute/<int:ricevuta_id>/pdf", endpoint="stampa_ricevuta_pdf")
def stampa_ricevuta_pdf(ricevuta_id):
    if "associazione_id" not in session:
        return redirect(url_for("start"))

    buf = genera_pdf_ricevuta(ricevuta_id, session["associazione_id"])
    if not buf:
        flash("Ricevuta non trovata.", "error")
        return redirect(url_for("ricevute_bp.elenco_ricevute"))

    return send_file(
        buf,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=f"ricevuta_{ricevuta_id}.pdf"
    )

## =================================================
# ELENCO RICEVUTE
# =================================================
@ricevute_bp.route("/ricevute", endpoint="elenco_ricevute")
def elenco_ricevute():
    if "associazione_id" not in session:
        return redirect(url_for("start"))

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row

    ricevute = conn.execute(
        """
        SELECT
            r.id,
            r.numero_progressivo,
            r.anno,
            r.data_emissione,
            r.totale,
            s.nome,
            s.cognome,
            -- ✅ QUI È IL FIX
            COALESCE(NULLIF(rs.codice, ''), rs.nome) AS sezionale
        FROM ricevute r
        LEFT JOIN soci s ON s.id = r.socio_id
        LEFT JOIN ricevute_sezionali rs ON rs.id = r.sezionale_id
        WHERE r.associazione_id = ?
        ORDER BY r.anno DESC, r.numero_progressivo DESC
        """,
        (session["associazione_id"],)
    ).fetchall()

    conn.close()

    return render_template(
        "ricevute_elenco.html",
        ricevute=ricevute
    )

# =================================================
# ELIMINA RICEVUTA
# =================================================
@ricevute_bp.route("/ricevute/elimina/<int:ricevuta_id>", methods=["POST"], endpoint="elimina_ricevuta")
def elimina_ricevuta(ricevuta_id):
    if "associazione_id" not in session:
        return redirect(url_for("start"))

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # 1️⃣ riapre le quote (scadenzario)
        cur.execute("""
            UPDATE quote_soci
            SET stato = 'DA_PAGARE',
                data_pagamento = NULL,
                ricevuta_id = NULL
            WHERE ricevuta_id = ?
        """, (ricevuta_id,))

        # 2️⃣ elimina mesi collegati
        cur.execute("""
            DELETE FROM ricevute_mesi
            WHERE ricevuta_riga_id IN (
                SELECT id FROM ricevute_righe WHERE ricevuta_id = ?
            )
        """, (ricevuta_id,))

        # 3️⃣ elimina righe ricevuta
        cur.execute(
            "DELETE FROM ricevute_righe WHERE ricevuta_id = ?",
            (ricevuta_id,)
        )

        # 4️⃣ elimina ricevuta
        cur.execute("""
            DELETE FROM ricevute
            WHERE id = ?
              AND associazione_id = ?
        """, (ricevuta_id, session["associazione_id"]))

        conn.commit()
        flash("Ricevuta eliminata correttamente.", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Errore eliminazione ricevuta: {e}", "error")

    finally:
        conn.close()

    return redirect(url_for("ricevute_bp.elenco_ricevute"))


