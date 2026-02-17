# =================================================
# INIZIALIZZA NUOVO ANNO
# =================================================

def inizializza_abilitazioni_anno(conn, associazione_id, anno):
    cur = conn.cursor()

    soci = cur.execute(
        """
        SELECT id
        FROM soci
        WHERE associazione_id = ?
        """,
        (associazione_id,)
    ).fetchall()

    for s in soci:
        socio_id = s["id"]

        ultima = cur.execute(
            """
            SELECT *
            FROM soci_abilitazioni_storico
            WHERE associazione_id = ?
              AND socio_id = ?
              AND anno < ?
            ORDER BY anno DESC
            LIMIT 1
            """,
            (associazione_id, socio_id, anno)
        ).fetchone()

        if not ultima:
            continue

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
            """,
            (
                associazione_id,
                socio_id,
                anno,
                ultima["gestione_tesseramento"],
                ultima["enti_tesseramento"],
                ultima["certificato_agonistico"],
                ultima["certificato_non_agonistico"],
                ultima["is_volontario"],
                ultima["abilita_rimborso_spese"],
            )
        )

