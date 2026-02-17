# services/generatore_quote_soci.py
# -*- coding: utf-8 -*-

import calendar

def genera_quote_soci(conn, associazione_id, esercizio_id):
    """
    Generatore scadenze quote_soci (centrale).
    NOTA: questa funzione NON fa commit.
    Il commit deve essere fatto dalla route che la chiama.
    """
    cur = conn.cursor()

    # TODO: qui incolleremo il corpo della tua funzione attuale (da app.py)
    # e toglieremo il conn.commit() finale.
       

    # anno esercizio
    anno = cur.execute(
        "SELECT anno FROM esercizi WHERE id = ?",
        (esercizio_id,)
    ).fetchone()["anno"]

    # TUTTI i soci (la validità la gestiamo dentro)
    soci = cur.execute("""
        SELECT id, data_uscita
        FROM soci
        WHERE associazione_id = ?
    """, (associazione_id,)).fetchall()

    for socio in soci:
        socio_id = socio["id"]
        data_uscita_socio = socio["data_uscita"]

        quote_assegnate = cur.execute("""
            SELECT
                sq.quota_id,
                sq.data_inizio,
                sq.data_fine,                
                q.importo,
                q.periodicita
            FROM soci_quote sq
            JOIN quote q
              ON q.id = sq.quota_id
             AND q.associazione_id = sq.associazione_id
            WHERE sq.socio_id = ?
              AND sq.associazione_id = ?
              AND sq.attiva = 1
              AND q.attiva = 1
        """, (socio_id, associazione_id)).fetchall()

        for qa in quote_assegnate:
            quota_id   = qa["quota_id"]
            importo    = qa["importo"]
            periodicita = qa["periodicita"]
            data_inizio = qa["data_inizio"]
            data_fine   = qa["data_fine"]
            
            
            # =============================
            # QUOTA ANNUALE (VERSIONE PULITA E COERENTE)
            # =============================
            if periodicita == "ANNUALE":
                y_start, _, _ = map(int, data_inizio.split("-"))

                # limite massimo di validità
                y_end = None
                if data_fine:
                    y_end, _, _ = map(int, data_fine.split("-"))

                y_exit = None
                if data_uscita_socio:
                    y_exit, _, _ = map(int, data_uscita_socio.split("-"))

                limiti = [x for x in (y_end, y_exit) if x is not None]
                y_max = min(limiti) if limiti else None

                # 1️⃣ CANCELLO TUTTE LE ANNUALI FUTURE NON PIÙ VALIDE (TUTTI GLI ESERCIZI)
                if y_max is not None:
                    cur.execute("""
                        DELETE FROM quote_soci
                        WHERE associazione_id = ?
                          AND socio_id = ?
                          AND quota_id = ?
                          AND mese = 0
                          AND anno > ?
                          AND COALESCE(stato,'') != 'PAGATA'
                          AND ricevuta_id IS NULL
                    """, (
                        associazione_id,
                        socio_id,
                        quota_id,
                        y_max
                    ))

                # 2️⃣ SE QUESTO ANNO NON È VALIDO, CANCELLO E STOP
                if anno < y_start or (y_max is not None and anno > y_max):
                    cur.execute("""
                        DELETE FROM quote_soci
                        WHERE associazione_id = ?
                          AND socio_id = ?
                          AND esercizio_id = ?
                          AND quota_id = ?
                          AND anno = ?
                          AND mese = 0
                          AND COALESCE(stato,'') != 'PAGATA'
                          AND ricevuta_id IS NULL
                    """, (
                        associazione_id,
                        socio_id,
                        esercizio_id,
                        quota_id,
                        anno
                    ))
                    continue

                # 3️⃣ INSERISCO L'ANNUALE VALIDA PER QUESTO ESERCIZIO
                cur.execute("""
                    INSERT OR IGNORE INTO quote_soci
                    (associazione_id, socio_id, esercizio_id, quota_id,
                     anno, mese, importo, data_scadenza)
                    VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                """, (
                    associazione_id,
                    socio_id,
                    esercizio_id,
                    quota_id,
                    anno,
                    importo,
                    f"{anno}-12-31"
                ))

            # =============================
            # QUOTA MENSILE (VERSIONE PULITA)
            # =============================
            elif periodicita == "MENSILE":
                # data inizio quota
                y_start, m_start, _ = map(int, data_inizio.split("-"))

                # limite fine quota
                y_end = None
                m_end = None
                if data_fine:
                    y_end, m_end, _ = map(int, data_fine.split("-"))

                # limite uscita socio
                y_exit = None
                m_exit = None
                if data_uscita_socio:
                    y_exit, m_exit, _ = map(int, data_uscita_socio.split("-"))

                # funzione utilitaria: confronto (anno, mese)
                def after(a1, m1, a2, m2):
                    return (a1, m1) > (a2, m2)

                def before(a1, m1, a2, m2):
                    return (a1, m1) < (a2, m2)

                # ==========================
                # 1️⃣ CANCELLO TUTTI I MESI FUTURI NON VALIDI (TUTTI GLI ESERCIZI)
                # ==========================
                if y_end is not None:
                    cur.execute("""
                        DELETE FROM quote_soci
                        WHERE associazione_id = ?
                          AND socio_id = ?
                          AND quota_id = ?
                          AND mese BETWEEN 1 AND 12
                          AND (anno > ? OR (anno = ? AND mese > ?))
                          AND COALESCE(stato,'') != 'PAGATA'
                          AND ricevuta_id IS NULL
                    """, (
                        associazione_id,
                        socio_id,
                        quota_id,
                        y_end, y_end, m_end
                    ))

                if y_exit is not None:
                    # ultimo mese valido = mese uscita - 1
                    last_y, last_m = y_exit, m_exit - 1
                    if last_m == 0:
                        last_y -= 1
                        last_m = 12

                    cur.execute("""
                        DELETE FROM quote_soci
                        WHERE associazione_id = ?
                          AND socio_id = ?
                          AND quota_id = ?
                          AND mese BETWEEN 1 AND 12
                          AND (anno > ? OR (anno = ? AND mese > ?))
                          AND COALESCE(stato,'') != 'PAGATA'
                          AND ricevuta_id IS NULL
                    """, (
                        associazione_id,
                        socio_id,
                        quota_id,
                        last_y, last_y, last_m
                    ))

                # ==========================
                # 2️⃣ SE QUESTO ESERCIZIO È FUORI RANGE → CANCELLO E STOP
                # ==========================
                # prima dell'inizio
                if before(anno, 1, y_start, m_start):
                    cur.execute("""
                        DELETE FROM quote_soci
                        WHERE associazione_id = ?
                          AND socio_id = ?
                          AND esercizio_id = ?
                          AND quota_id = ?
                          AND mese BETWEEN 1 AND 12
                          AND COALESCE(stato,'') != 'PAGATA'
                          AND ricevuta_id IS NULL
                    """, (
                        associazione_id,
                        socio_id,
                        esercizio_id,
                        quota_id
                    ))
                    continue

                # dopo fine quota
                if y_end is not None and after(anno, 1, y_end, m_end):
                    continue

                # dopo uscita socio
                if y_exit is not None and after(anno, 1, y_exit, m_exit):
                    continue

                # ==========================
                # 3️⃣ CALCOLO RANGE MESI VALIDI NELL’ANNO
                # ==========================
                mese_da = 1
                mese_a = 12

                if anno == y_start:
                    mese_da = m_start

                if y_end is not None and anno == y_end:
                    mese_a = m_end

                if y_exit is not None and anno == y_exit:
                    mese_a = min(mese_a, m_exit - 1)

                if mese_da > mese_a:
                    continue

                # ==========================
                # 4️⃣ PULIZIA MESI FUORI RANGE NELL’ANNO
                # ==========================
                cur.execute("""
                    DELETE FROM quote_soci
                    WHERE associazione_id = ?
                      AND socio_id = ?
                      AND esercizio_id = ?
                      AND quota_id = ?
                      AND mese BETWEEN 1 AND 12
                      AND mese NOT BETWEEN ? AND ?
                      AND COALESCE(stato,'') != 'PAGATA'
                      AND ricevuta_id IS NULL
                """, (
                    associazione_id,
                    socio_id,
                    esercizio_id,
                    quota_id,
                    mese_da,
                    mese_a
                ))

                # ==========================
                # 5️⃣ INSERIMENTO MESI VALIDI
                # ==========================
                for mese in range(mese_da, mese_a + 1):
                    ultimo = calendar.monthrange(anno, mese)[1]
                    cur.execute("""
                        INSERT OR IGNORE INTO quote_soci
                        (associazione_id, socio_id, esercizio_id, quota_id,
                         anno, mese, importo, data_scadenza)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        associazione_id,
                        socio_id,
                        esercizio_id,
                        quota_id,
                        anno,
                        mese,
                        importo,
                        f"{anno}-{mese:02d}-{ultimo}"
                    ))
            
            # =============================
            # QUOTA UNA TANTUM
            # =============================
            elif periodicita == "UNA_TANTUM":
                y, m, _ = map(int, data_inizio.split("-"))

                # ---- socio uscito prima
                if data_uscita_socio:
                    yu, mu, _ = map(int, data_uscita_socio.split("-"))
                    if (yu < y) or (yu == y and mu < m):
                        continue

                # -------------------------
                # PULIZIA EVENTO NON PAGATO
                # -------------------------
                cur.execute("""
                    DELETE FROM quote_soci
                    WHERE associazione_id = ?
                    AND socio_id = ?
                    AND quota_id = ?
                    AND anno = ?
                    AND mese = ?
                    AND COALESCE(stato,'') != 'PAGATA'
                    AND ricevuta_id IS NULL
                """, (
                    associazione_id,
                    socio_id,
                    quota_id,
                    y,
                    m
                ))

                # -------------------------
                # INSERIMENTO UNA TANTUM
                # -------------------------
                ultimo = calendar.monthrange(y, m)[1]
                cur.execute("""
                    INSERT OR IGNORE INTO quote_soci
                    (associazione_id, socio_id, esercizio_id, quota_id,
                    anno, mese, importo, data_scadenza)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    associazione_id,
                    socio_id,
                    esercizio_id,
                    quota_id,
                    y,
                    m,
                    importo,
                    f"{y}-{m:02d}-{ultimo}"
                ))

    
